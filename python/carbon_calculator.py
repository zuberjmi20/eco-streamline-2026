"""
=============================================================================
Eco-Streamline 2026 | Apex Distribution UK
FILE: carbon_calculator.py
PURPOSE: Scope 3 Category 4 Carbon Calculator — UK SRS Compliance Engine
AUTHOR: Lead Business Transformation Analyst
=============================================================================

BUSINESS CONTEXT
----------------
As of Q4 2026, Apex Distribution's Tier-1 retail partners (Tesco, John Lewis)
require granular Scope 3 carbon data per shipment under the UK Sustainability
Reporting Standards (UK SRS). Failure to provide this data risks termination
of contracts worth 40% of annual revenue (GBP 4.8M).

This module automates the entire Scope 3 reporting workflow:
  1. Calculates carbon emissions per shipment (DEFRA 2025 factors)
  2. Aggregates to supplier, product, and monthly level
  3. Generates a UK SRS-aligned report exportable to retail partners
  4. Compares transport modes (what would Sea vs Air have emitted?)
  5. Tracks progress toward carbon reduction targets

UK SRS SCOPE 3 CATEGORY 4
--------------------------
Category 4: Upstream Transportation and Distribution
Formula: weight_tonnes * distance_km * kg_CO2e_per_tonne_km

DEFRA 2025 Emission Factors Used:
  Road (HGV):       0.100 kg CO2e per tonne-km
  Rail (Freight):   0.028 kg CO2e per tonne-km
  Sea (Container):  0.016 kg CO2e per tonne-km
  Air Freight:      0.602 kg CO2e per tonne-km

Source: UK Government DEFRA Greenhouse Gas Conversion Factors 2025
=============================================================================
"""

import numpy as np
import pandas as pd
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Paths
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
                if '__file__' in dir() else os.path.join(os.getcwd(), 'eco-streamline-2026')
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
REFERENCE_DIR = os.path.join(BASE_DIR, 'data', 'reference')
OUTPUT_DIR    = os.path.join(PROCESSED_DIR)

# DEFRA 2025 emission factors (kg CO2e per tonne-km)
DEFRA_FACTORS = {
    'ROAD': 0.100,
    'RAIL': 0.028,
    'SEA':  0.016,
    'AIR':  0.602,
}

# Reporting metadata
SCOPE_CATEGORY      = 4
REPORT_STANDARD     = 'UK SRS 2026'
DEFRA_SOURCE        = 'DEFRA GHG Conversion Factors 2025'


# =============================================================================
# CORE CALCULATION
# =============================================================================

def calc_shipment_carbon(
    weight_kg:              float,
    distance_km:            float,
    transport_mode:         str,
    quantity_units:         int
) -> dict:
    """
    Calculate Scope 3 Category 4 carbon emissions for a single shipment.

    Parameters
    ----------
    weight_kg       : total shipment weight in kg
    distance_km     : shipping route distance in km
    transport_mode  : ROAD | RAIL | SEA | AIR
    quantity_units  : number of units in shipment

    Returns
    -------
    dict with full carbon breakdown
    """
    emission_factor = DEFRA_FACTORS.get(transport_mode.upper(), 0.0)
    weight_tonnes   = weight_kg / 1000.0
    carbon_kg_co2e  = weight_tonnes * distance_km * emission_factor

    return {
        'weight_kg':                round(weight_kg, 2),
        'weight_tonnes':            round(weight_tonnes, 4),
        'distance_km':              round(distance_km, 1),
        'transport_mode':           transport_mode.upper(),
        'emission_factor':          emission_factor,
        'defra_source':             DEFRA_SOURCE,
        'carbon_kg_co2e':           round(carbon_kg_co2e, 4),
        'carbon_tonnes_co2e':       round(carbon_kg_co2e / 1000.0, 6),
        'carbon_kg_co2e_per_unit':  round(carbon_kg_co2e / max(quantity_units, 1), 6),
        'quantity_units':           quantity_units,
        'scope_category':           SCOPE_CATEGORY,
        'report_standard':          REPORT_STANDARD,
    }


def calc_mode_comparison(
    weight_kg:      float,
    distance_km:    float,
    quantity_units: int,
    origin_country: str
) -> pd.DataFrame:
    """
    Compare carbon emissions across all transport modes for a shipment.
    Used in the Green-ROP trade-off report and Streamlit dashboard.

    Returns
    -------
    DataFrame showing carbon, cost index, and savings vs Air for each mode
    """
    rows = []
    air_carbon = None

    for mode, factor in DEFRA_FACTORS.items():
        carbon = calc_shipment_carbon(weight_kg, distance_km, mode, quantity_units)
        if mode == 'AIR':
            air_carbon = carbon['carbon_kg_co2e']
        rows.append({
            'transport_mode':           mode,
            'emission_factor':          factor,
            'carbon_kg_co2e':           carbon['carbon_kg_co2e'],
            'carbon_tonnes_co2e':       carbon['carbon_tonnes_co2e'],
            'carbon_per_unit_kg':       carbon['carbon_kg_co2e_per_unit'],
        })

    df = pd.DataFrame(rows)

    if air_carbon and air_carbon > 0:
        df['carbon_saving_vs_air_kg']  = air_carbon - df['carbon_kg_co2e']
        df['carbon_saving_vs_air_pct'] = round(
            df['carbon_saving_vs_air_kg'] / air_carbon * 100, 1
        )
    else:
        df['carbon_saving_vs_air_kg']  = 0
        df['carbon_saving_vs_air_pct'] = 0

    df['is_lowest_carbon'] = df['carbon_kg_co2e'] == df['carbon_kg_co2e'].min()
    return df.sort_values('carbon_kg_co2e')


# =============================================================================
# BATCH CARBON CALCULATOR
# =============================================================================

def calculate_all_shipments(
    orders_df:      pd.DataFrame,
    suppliers_df:   pd.DataFrame,
    products_df:    pd.DataFrame,
    distance_df:    pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate Scope 3 carbon for every purchase order in the dataset.

    Merges orders with supplier country → distance matrix → DEFRA factors.
    This is the complete 2-year carbon ledger for Apex Distribution.

    Parameters
    ----------
    orders_df    : fact_purchase_orders data
    suppliers_df : dim_supplier data
    products_df  : dim_product data
    distance_df  : shipping distance matrix

    Returns
    -------
    DataFrame with carbon calculation per shipment
    """
    print("\n[1/4] Calculating carbon emissions per shipment...")

    # Merge supplier country onto orders
    merged = orders_df.merge(
        suppliers_df[['supplier_id', 'supplier_name',
                      'country_of_origin', 'region']],
        on='supplier_id', how='left'
    ).merge(
        products_df[['product_id', 'product_name',
                     'category_code', 'abc_class',
                     'unit_price_gbp', 'gross_margin_pct']],
        on='product_id', how='left'
    )

    # Merge distance for each order's origin country + transport mode
    merged = merged.merge(
        distance_df[['origin_country', 'transport_mode', 'distance_km']],
        left_on  = ['country_of_origin', 'transport_mode'],
        right_on = ['origin_country', 'transport_mode'],
        how='left'
    )

    # Fill missing distances with domestic default
    merged['distance_km'] = merged['distance_km'].fillna(250.0)

    # Apply DEFRA calculation
    merged['emission_factor']       = merged['transport_mode'].map(DEFRA_FACTORS).fillna(0.1)
    merged['weight_tonnes']         = merged['weight_kg_total'] / 1000.0
    merged['carbon_kg_co2e']        = (
        merged['weight_tonnes'] *
        merged['distance_km'] *
        merged['emission_factor']
    ).round(4)
    merged['carbon_tonnes_co2e']    = (merged['carbon_kg_co2e'] / 1000.0).round(6)
    merged['carbon_per_unit_kg']    = (
        merged['carbon_kg_co2e'] / merged['quantity_ordered'].clip(lower=1)
    ).round(6)
    merged['reporting_period']      = pd.to_datetime(
        merged['actual_delivery_date']
    ).dt.to_period('M').astype(str)
    merged['scope_category']        = SCOPE_CATEGORY
    merged['report_standard']       = REPORT_STANDARD
    merged['defra_source']          = DEFRA_SOURCE

    # Counterfactual: what would each shipment emit if sent by Air?
    merged['air_emission_factor']       = DEFRA_FACTORS['AIR']
    merged['carbon_if_air_kg_co2e']     = (
        merged['weight_tonnes'] *
        merged['distance_km'] *
        merged['air_emission_factor']
    ).round(4)
    merged['carbon_saved_vs_air_kg']    = (
        merged['carbon_if_air_kg_co2e'] - merged['carbon_kg_co2e']
    ).clip(lower=0).round(4)

    delivered = merged[merged['order_status'] == 'DELIVERED'].copy()

    print("    OK {:,} shipments calculated".format(len(delivered)))
    print("    OK Total carbon: {:.2f} tonnes CO2e".format(
        delivered['carbon_tonnes_co2e'].sum()
    ))
    print("    OK Carbon saved vs all-Air: {:.2f} tonnes CO2e".format(
        delivered['carbon_saved_vs_air_kg'].sum() / 1000
    ))

    return delivered


# =============================================================================
# AGGREGATED SCOPE 3 REPORTS
# =============================================================================

def build_scope3_by_supplier(carbon_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate Scope 3 emissions by supplier and month.
    This is the report Apex sends to Tesco and John Lewis.
    """
    print("\n[2/4] Building Scope 3 report by supplier...")

    report = carbon_df.groupby(
        ['reporting_period', 'supplier_id', 'supplier_name',
         'country_of_origin', 'region', 'transport_mode']
    ).agg(
        shipment_count          = ('order_id',            'count'),
        total_weight_kg         = ('weight_kg_total',     'sum'),
        total_distance_km       = ('distance_km',         'sum'),
        total_units_shipped     = ('quantity_ordered',    'sum'),
        total_carbon_kg_co2e    = ('carbon_kg_co2e',      'sum'),
        total_carbon_tonnes     = ('carbon_tonnes_co2e',  'sum'),
        avg_carbon_per_unit_kg  = ('carbon_per_unit_kg',  'mean'),
        carbon_saved_vs_air_kg  = ('carbon_saved_vs_air_kg', 'sum'),
        total_order_value_gbp   = ('total_cost_gbp',      'sum'),
    ).reset_index()

    report['total_carbon_kg_co2e']   = report['total_carbon_kg_co2e'].round(2)
    report['total_carbon_tonnes']    = report['total_carbon_tonnes'].round(4)
    report['avg_carbon_per_unit_kg'] = report['avg_carbon_per_unit_kg'].round(6)
    report['carbon_saved_vs_air_kg'] = report['carbon_saved_vs_air_kg'].round(2)
    report['scope_category']         = SCOPE_CATEGORY
    report['report_standard']        = REPORT_STANDARD
    report['defra_source']           = DEFRA_SOURCE

    report = report.sort_values(
        ['reporting_period', 'total_carbon_kg_co2e'],
        ascending=[True, False]
    )

    print("    OK {:,} supplier-month-mode combinations".format(len(report)))
    return report


def build_scope3_by_product(carbon_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Scope 3 by product category and ABC class."""
    print("\n[3/4] Building Scope 3 report by product...")

    report = carbon_df.groupby(
        ['reporting_period', 'product_id', 'product_name',
         'category_code', 'abc_class', 'transport_mode']
    ).agg(
        shipment_count          = ('order_id',            'count'),
        total_units_shipped     = ('quantity_ordered',    'sum'),
        total_carbon_kg_co2e    = ('carbon_kg_co2e',      'sum'),
        total_carbon_tonnes     = ('carbon_tonnes_co2e',  'sum'),
        avg_carbon_per_unit_kg  = ('carbon_per_unit_kg',  'mean'),
    ).reset_index()

    report['total_carbon_kg_co2e']   = report['total_carbon_kg_co2e'].round(2)
    report['avg_carbon_per_unit_kg'] = report['avg_carbon_per_unit_kg'].round(6)
    report = report.sort_values(
        ['reporting_period', 'total_carbon_kg_co2e'],
        ascending=[True, False]
    )

    print("    OK {:,} product-month combinations".format(len(report)))
    return report


def build_executive_carbon_summary(carbon_df: pd.DataFrame) -> pd.DataFrame:
    """
    Monthly executive summary — the top-line numbers for the CFO dashboard.
    Tracks progress against carbon reduction targets.
    """
    print("\n[4/4] Building executive carbon summary...")

    monthly = carbon_df.groupby('reporting_period').agg(
        shipment_count              = ('order_id',                'count'),
        total_units_shipped         = ('quantity_ordered',        'sum'),
        total_weight_tonnes         = ('weight_tonnes',           'sum'),
        total_carbon_kg_co2e        = ('carbon_kg_co2e',          'sum'),
        total_carbon_tonnes_co2e    = ('carbon_tonnes_co2e',      'sum'),
        carbon_saved_vs_air_kg      = ('carbon_saved_vs_air_kg',  'sum'),
        total_spend_gbp             = ('total_cost_gbp',          'sum'),
        road_shipments              = ('transport_mode', lambda x: (x == 'ROAD').sum()),
        sea_shipments               = ('transport_mode', lambda x: (x == 'SEA').sum()),
        air_shipments               = ('transport_mode', lambda x: (x == 'AIR').sum()),
        rail_shipments              = ('transport_mode', lambda x: (x == 'RAIL').sum()),
    ).reset_index()

    monthly['carbon_intensity_kg_per_unit'] = (
        monthly['total_carbon_kg_co2e'] /
        monthly['total_units_shipped'].clip(lower=1)
    ).round(4)

    monthly['carbon_intensity_kg_per_gbp'] = (
        monthly['total_carbon_kg_co2e'] /
        monthly['total_spend_gbp'].clip(lower=1)
    ).round(6)

    monthly['pct_air_shipments'] = (
        monthly['air_shipments'] /
        monthly['shipment_count'].clip(lower=1) * 100
    ).round(1)

    monthly['carbon_saved_vs_air_tonnes'] = (
        monthly['carbon_saved_vs_air_kg'] / 1000
    ).round(4)

    monthly['total_carbon_kg_co2e']     = monthly['total_carbon_kg_co2e'].round(2)
    monthly['total_carbon_tonnes_co2e'] = monthly['total_carbon_tonnes_co2e'].round(4)

    monthly = monthly.sort_values('reporting_period')

    return monthly


# =============================================================================
# UK SRS EXPORT FORMATTER
# =============================================================================

def format_srs_export(
    scope3_by_supplier: pd.DataFrame,
    company_name:       str = 'Apex Distribution UK',
    reporting_year:     str = '2025'
) -> pd.DataFrame:
    """
    Format the Scope 3 report in UK SRS-aligned structure.
    This is the exact file sent to Tesco and John Lewis.

    Columns match the UK SRS Category 4 disclosure template.
    """
    year_data = scope3_by_supplier[
        scope3_by_supplier['reporting_period'].str.startswith(reporting_year)
    ].copy()

    srs_report = pd.DataFrame({
        'Company':                      company_name,
        'Reporting Standard':           REPORT_STANDARD,
        'Scope Category':               'Scope 3 Category 4 — Upstream Transport',
        'Reporting Period':             year_data['reporting_period'],
        'Supplier Name':                year_data['supplier_name'],
        'Supplier Country':             year_data['country_of_origin'],
        'Supplier Region':              year_data['region'],
        'Transport Mode':               year_data['transport_mode'],
        'Shipment Count':               year_data['shipment_count'],
        'Total Weight (kg)':            year_data['total_weight_kg'].round(2),
        'Total Distance (km)':          year_data['total_distance_km'].round(1),
        'Total Units Shipped':          year_data['total_units_shipped'],
        'Emission Factor (kg CO2e/t/km)': year_data['transport_mode'].map(DEFRA_FACTORS),
        'Total Carbon (kg CO2e)':       year_data['total_carbon_kg_co2e'],
        'Total Carbon (tonnes CO2e)':   year_data['total_carbon_tonnes'],
        'Carbon per Unit (kg CO2e)':    year_data['avg_carbon_per_unit_kg'],
        'DEFRA Source':                 DEFRA_SOURCE,
        'Report Generated':             datetime.now().strftime('%Y-%m-%d'),
        'Methodology':                  'Activity-based: weight x distance x emission factor',
    })

    return srs_report.sort_values(['Reporting Period', 'Total Carbon (kg CO2e)'],
                                   ascending=[True, False])


# =============================================================================
# PRINT SUMMARY
# =============================================================================

def print_carbon_summary(
    carbon_df:      pd.DataFrame,
    executive_df:   pd.DataFrame
):
    total_carbon    = carbon_df['carbon_tonnes_co2e'].sum()
    total_saved     = carbon_df['carbon_saved_vs_air_kg'].sum() / 1000
    air_pct         = (carbon_df['transport_mode'] == 'AIR').mean() * 100
    top_supplier    = (
        carbon_df.groupby('supplier_name')['carbon_kg_co2e']
        .sum().idxmax()
    )

    print("\n" + "=" * 65)
    print("  SCOPE 3 CARBON REPORT — Apex Distribution UK")
    print("  UK SRS Category 4 | DEFRA 2025 Factors")
    print("=" * 65)
    print("")
    print("  TOTAL EMISSIONS (Jan 2024 – Dec 2025)")
    print("  Total Scope 3 Cat 4:    {:>10,.2f} tonnes CO2e".format(total_carbon))
    print("  Carbon saved vs Air:    {:>10,.2f} tonnes CO2e".format(total_saved))
    print("  Air freight usage:      {:>10.1f}% of shipments".format(air_pct))
    print("  Highest emitting supplier: {}".format(top_supplier))
    print("")
    print("  MONTHLY TREND (2025)")
    print("  {:<10} {:>12} {:>14} {:>10}".format(
        'Month', 'Carbon(t)', 'Units Shipped', 'Air Pct%'
    ))
    print("  " + "-" * 50)
    y2025 = executive_df[executive_df['reporting_period'].str.startswith('2025')]
    for _, row in y2025.iterrows():
        print("  {:<10} {:>12,.2f} {:>14,.0f} {:>9.1f}%".format(
            row['reporting_period'],
            row['total_carbon_tonnes_co2e'],
            row['total_units_shipped'],
            row['pct_air_shipments']
        ))
    print("")
    print("  EMISSION FACTORS USED (DEFRA 2025)")
    for mode, factor in DEFRA_FACTORS.items():
        print("  {:<6}: {:>6.3f} kg CO2e per tonne-km".format(mode, factor))
    print("=" * 65)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':

    print("=" * 65)
    print("  CARBON CALCULATOR — Scope 3 Category 4")
    print("  Apex Distribution UK | UK SRS 2026 Compliance")
    print("=" * 65)

    # Load data
    print("\nLoading Phase 1 data...")
    orders_df    = pd.read_csv(os.path.join(PROCESSED_DIR, 'fact_purchase_orders.csv'))
    suppliers_df = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_supplier.csv'))
    products_df  = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_product.csv'))
    distance_df  = pd.read_csv(os.path.join(REFERENCE_DIR, 'shipping_distance_matrix.csv'))

    # Run calculations
    carbon_df       = calculate_all_shipments(orders_df, suppliers_df, products_df, distance_df)
    supplier_report = build_scope3_by_supplier(carbon_df)
    product_report  = build_scope3_by_product(carbon_df)
    executive_df    = build_executive_carbon_summary(carbon_df)
    srs_export      = format_srs_export(supplier_report, reporting_year='2025')

    # Save all outputs
    carbon_df.to_csv(      os.path.join(OUTPUT_DIR, 'carbon_events_all.csv'),        index=False)
    supplier_report.to_csv(os.path.join(OUTPUT_DIR, 'scope3_by_supplier.csv'),       index=False)
    product_report.to_csv( os.path.join(OUTPUT_DIR, 'scope3_by_product.csv'),        index=False)
    executive_df.to_csv(   os.path.join(OUTPUT_DIR, 'carbon_executive_summary.csv'), index=False)
    srs_export.to_csv(     os.path.join(OUTPUT_DIR, 'UK_SRS_Scope3_Export_2025.csv'),index=False)

    # Print summary
    print_carbon_summary(carbon_df, executive_df)

    print("\n  OUTPUT FILES")
    print("  carbon_events_all.csv          — per-shipment carbon ledger")
    print("  scope3_by_supplier.csv         — by supplier and month")
    print("  scope3_by_product.csv          — by product and month")
    print("  carbon_executive_summary.csv   — CFO monthly summary")
    print("  UK_SRS_Scope3_Export_2025.csv  — ready to send to Tesco/John Lewis")
    print("")
    print("  Phase 3C Complete — Carbon Calculator")
    print("  Phase 3 FULLY COMPLETE. Ready for Phase 4 — Streamlit App.")
    print("=" * 65)
