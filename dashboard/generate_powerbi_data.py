"""
=============================================================================
Eco-Streamline 2026 | Apex Distribution UK
FILE: dashboard/generate_powerbi_data.py
PURPOSE: Generate pre-aggregated mock data exports for Power BI
AUTHOR: Lead Business Transformation Analyst
=============================================================================
Power BI works best with clean, pre-shaped data rather than raw transactional
CSVs. This script produces 8 optimised tables ready for direct import.

Run from project root: python dashboard/generate_powerbi_data.py
=============================================================================
"""

import pandas as pd
import numpy as np
import os

# Paths
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
                if '__file__' in dir() else os.path.join(os.getcwd(), 'eco-streamline-2026')
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
REFERENCE_DIR = os.path.join(BASE_DIR, 'data', 'reference')
OUTPUT_DIR    = os.path.join(BASE_DIR, 'dashboard', 'mock_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print("  POWER BI MOCK DATA GENERATOR")
print("  Eco-Streamline 2026 | Apex Distribution UK")
print("=" * 60)

# Load source data
products    = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_product.csv'))
suppliers   = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_supplier.csv'))
warehouses  = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_warehouse.csv'))
orders      = pd.read_csv(os.path.join(PROCESSED_DIR, 'fact_purchase_orders.csv'))
inventory   = pd.read_csv(os.path.join(PROCESSED_DIR, 'fact_inventory_snapshots.csv'))
mc          = pd.read_csv(os.path.join(PROCESSED_DIR, 'monte_carlo_results.csv'))
green       = pd.read_csv(os.path.join(PROCESSED_DIR, 'green_rop_decisions.csv'))
carbon_exec = pd.read_csv(os.path.join(PROCESSED_DIR, 'carbon_executive_summary.csv'))
carbon_sup  = pd.read_csv(os.path.join(PROCESSED_DIR, 'scope3_by_supplier.csv'))
srs         = pd.read_csv(os.path.join(PROCESSED_DIR, 'UK_SRS_Scope3_Export_2025.csv'))


# =============================================================================
# TABLE 1 — pbi_dim_date
# Full calendar table — essential for Power BI time intelligence
# =============================================================================
print("\n[1/8] Building pbi_dim_date...")

dates = pd.date_range('2024-01-01', '2025-12-31', freq='D')
seasonal = {1:0.75,2:0.80,3:0.90,4:0.95,5:1.00,6:1.05,
            7:1.10,8:1.05,9:1.00,10:1.10,11:1.35,12:1.50}

dim_date = pd.DataFrame({
    'DateKey':          [int(d.strftime('%Y%m%d')) for d in dates],
    'Date':             [d.strftime('%Y-%m-%d') for d in dates],
    'Year':             [d.year for d in dates],
    'QuarterNumber':    [d.quarter for d in dates],
    'QuarterName':      ['Q' + str(d.quarter) for d in dates],
    'MonthNumber':      [d.month for d in dates],
    'MonthName':        [d.strftime('%B') for d in dates],
    'MonthShort':       [d.strftime('%b') for d in dates],
    'WeekNumber':       [d.isocalendar()[1] for d in dates],
    'DayOfWeek':        [d.isoweekday() for d in dates],
    'DayName':          [d.strftime('%A') for d in dates],
    'IsWeekend':        [d.isoweekday() in [6,7] for d in dates],
    'YearMonth':        [d.strftime('%Y-%m') for d in dates],
    'YearQuarter':      ['{} Q{}'.format(d.year, d.quarter) for d in dates],
    'SeasonalMultiplier': [seasonal[d.month] for d in dates],
    'FiscalYear':       [d.year if d.month >= 4 else d.year - 1 for d in dates],
    'FiscalQuarter':    [
        1 if d.month in [4,5,6] else
        2 if d.month in [7,8,9] else
        3 if d.month in [10,11,12] else 4
        for d in dates
    ],
})
dim_date.to_csv(os.path.join(OUTPUT_DIR, 'pbi_dim_date.csv'), index=False)
print("    OK {:,} rows".format(len(dim_date)))


# =============================================================================
# TABLE 2 — pbi_dim_product
# Product dimension with all attributes for slicing
# =============================================================================
print("\n[2/8] Building pbi_dim_product...")

pbi_product = products[[
    'product_id', 'product_name', 'category_code', 'category_name',
    'abc_class', 'unit_cost_gbp', 'unit_price_gbp',
    'gross_margin_pct', 'weight_kg', 'service_level_target'
]].copy()

pbi_product['abc_sort_order'] = pbi_product['abc_class'].map({'A':1,'B':2,'C':3})
pbi_product['margin_band'] = pd.cut(
    pbi_product['gross_margin_pct'],
    bins=[0, 20, 35, 100],
    labels=['Low (<20%)', 'Medium (20-35%)', 'High (>35%)']
)
pbi_product.to_csv(os.path.join(OUTPUT_DIR, 'pbi_dim_product.csv'), index=False)
print("    OK {:,} rows".format(len(pbi_product)))


# =============================================================================
# TABLE 3 — pbi_dim_supplier
# Supplier dimension
# =============================================================================
print("\n[3/8] Building pbi_dim_supplier...")

pbi_supplier = suppliers[[
    'supplier_id', 'supplier_name', 'country_of_origin', 'region',
    'primary_transport', 'lead_time_avg_days', 'lead_time_min_days',
    'lead_time_max_days', 'spike_probability', 'reliability_score',
    'payment_terms_days'
]].copy()
pbi_supplier['reliability_band'] = pd.cut(
    pbi_supplier['reliability_score'],
    bins=[0, 0.8, 0.9, 1.0],
    labels=['Low (<80%)', 'Medium (80-90%)', 'High (>90%)']
)
pbi_supplier.to_csv(os.path.join(OUTPUT_DIR, 'pbi_dim_supplier.csv'), index=False)
print("    OK {:,} rows".format(len(pbi_supplier)))


# =============================================================================
# TABLE 4 — pbi_fact_inventory_monthly
# Monthly inventory positions — core for CFO dashboard
# =============================================================================
print("\n[4/8] Building pbi_fact_inventory_monthly...")

inv_merged = inventory.merge(
    products[['product_id','product_name','category_name',
              'unit_cost_gbp','unit_price_gbp','gross_margin_pct']],
    on='product_id', how='left'
)

# Parse snapshot date to get DateKey
inv_merged['snapshot_date'] = pd.to_datetime(inv_merged['snapshot_date'])
inv_merged['DateKey']       = inv_merged['snapshot_date'].dt.strftime('%Y%m%d').astype(int)
inv_merged['YearMonth']     = inv_merged['snapshot_date'].dt.strftime('%Y-%m')
inv_merged['Year']          = inv_merged['snapshot_date'].dt.year
inv_merged['MonthNumber']   = inv_merged['snapshot_date'].dt.month

# Financial metrics
inv_merged['potential_revenue']   = inv_merged['stock_on_hand'] * inv_merged['unit_price_gbp']
inv_merged['gross_margin_value']  = (
    inv_merged['stock_value_gbp'] * inv_merged['gross_margin_pct'] / 100
)
inv_merged['days_cover_band'] = pd.cut(
    inv_merged['stock_cover_days'],
    bins=[-1, 0, 14, 30, 60, 90, 9999],
    labels=['Stock-Out','Critical (<14d)','Low (14-30d)',
            'Healthy (30-60d)','Excess (60-90d)','Slow-Mover (>90d)']
)

inv_merged['excess_stock_value_gbp'] = inv_merged.apply(
    lambda r: max(0, r['stock_value_gbp'] - (r['avg_daily_demand'] * 90 * r['unit_cost_gbp']))
    if r['abc_class'] == 'C' and r['stock_cover_days'] > 90 else 0, axis=1
)

pbi_inv = inv_merged[[
    'DateKey','YearMonth','Year','MonthNumber',
    'product_id','product_name','category_name',
    'warehouse_id','abc_class',
    'stock_on_hand','stock_cover_days','avg_daily_demand',
    'stock_value_gbp','excess_stock_value_gbp',
    'potential_revenue','gross_margin_value',
    'is_stock_out','is_slow_mover','is_at_risk',
    'days_cover_band'
]]
pbi_inv.to_csv(os.path.join(OUTPUT_DIR, 'pbi_fact_inventory_monthly.csv'), index=False)
print("    OK {:,} rows".format(len(pbi_inv)))


# =============================================================================
# TABLE 5 — pbi_fact_purchase_orders
# Order facts with all keys for relationship building
# =============================================================================
print("\n[5/8] Building pbi_fact_purchase_orders...")

orders_merged = orders.merge(
    products[['product_id','category_name','abc_class']], on='product_id', how='left'
).merge(
    suppliers[['supplier_id','supplier_name','region','country_of_origin']],
    on='supplier_id', how='left'
)

orders_merged['order_date']  = pd.to_datetime(orders_merged['order_date'])
orders_merged['DateKey']     = orders_merged['order_date'].dt.strftime('%Y%m%d').astype(int)
orders_merged['YearMonth']   = orders_merged['order_date'].dt.strftime('%Y-%m')
orders_merged['Year']        = orders_merged['order_date'].dt.year
orders_merged['MonthNumber'] = orders_merged['order_date'].dt.month

# Lead time variance band
orders_merged['variance_days'] = orders_merged.get(
    'lead_time_variance_days',
    pd.Series([0] * len(orders_merged))
)
orders_merged['lead_time_performance'] = pd.cut(
    orders_merged['lead_time_days'] - orders_merged['lead_time_days'].mean(),
    bins=[-999, -5, 0, 5, 999],
    labels=['Early (>5d)', 'On Time', 'Slightly Late (<5d)', 'Late (>5d)']
)

pbi_orders = orders_merged[[
    'order_id','DateKey','YearMonth','Year','MonthNumber',
    'product_id','supplier_id','supplier_name','warehouse_id',
    'category_name','abc_class','region','country_of_origin',
    'quantity_ordered','unit_cost_gbp','total_cost_gbp',
    'lead_time_days','transport_mode','weight_kg_total',
    'is_urgent_order','order_status','lead_time_performance'
]]
pbi_orders.to_csv(os.path.join(OUTPUT_DIR, 'pbi_fact_purchase_orders.csv'), index=False)
print("    OK {:,} rows".format(len(pbi_orders)))


# =============================================================================
# TABLE 6 — pbi_fact_carbon_monthly
# Monthly carbon aggregation for Sustainability Portal
# =============================================================================
print("\n[6/8] Building pbi_fact_carbon_monthly...")

carbon_monthly = carbon_exec.copy()
carbon_monthly['Year']        = carbon_monthly['reporting_period'].str[:4].astype(int)
carbon_monthly['MonthNumber'] = carbon_monthly['reporting_period'].str[5:7].astype(int)

# Parse first day of month as DateKey
carbon_monthly['DateKey'] = (
    carbon_monthly['reporting_period'].str.replace('-','') + '01'
).astype(int)

carbon_monthly['carbon_intensity_per_order'] = (
    carbon_monthly['total_carbon_kg_co2e'] /
    carbon_monthly['shipment_count'].clip(lower=1)
).round(4)

carbon_monthly['pct_sea_shipments']  = (
    carbon_monthly['sea_shipments'] /
    carbon_monthly['shipment_count'].clip(lower=1) * 100
).round(1)

carbon_monthly['pct_road_shipments'] = (
    carbon_monthly['road_shipments'] /
    carbon_monthly['shipment_count'].clip(lower=1) * 100
).round(1)

carbon_monthly.to_csv(os.path.join(OUTPUT_DIR, 'pbi_fact_carbon_monthly.csv'), index=False)
print("    OK {:,} rows".format(len(carbon_monthly)))


# =============================================================================
# TABLE 7 — pbi_fact_carbon_by_supplier
# Supplier-level Scope 3 data for UK SRS report visual
# =============================================================================
print("\n[7/8] Building pbi_fact_carbon_by_supplier...")

carbon_sup_merged = carbon_sup.merge(
    suppliers[['supplier_id','reliability_score','spike_probability']],
    on='supplier_id', how='left'
)

carbon_sup_merged['Year']        = carbon_sup_merged['reporting_period'].str[:4].astype(int)
carbon_sup_merged['MonthNumber'] = carbon_sup_merged['reporting_period'].str[5:7].astype(int)
carbon_sup_merged['DateKey']     = (
    carbon_sup_merged['reporting_period'].str.replace('-','') + '01'
).astype(int)

# Carbon efficiency score (lower = better)
carbon_sup_merged['carbon_per_unit_kg'] = (
    carbon_sup_merged['total_carbon_kg_co2e'] /
    carbon_sup_merged['total_units_shipped'].clip(lower=1)
).round(4)

# Mode label
mode_labels = {
    'ROAD': 'Road (HGV)',
    'SEA':  'Sea (Container)',
    'AIR':  'Air Freight',
    'RAIL': 'Rail (Freight)'
}
carbon_sup_merged['transport_mode_label'] = (
    carbon_sup_merged['transport_mode'].map(mode_labels)
)

pbi_carbon_sup = carbon_sup_merged[[
    'DateKey','reporting_period','Year','MonthNumber',
    'supplier_id','supplier_name','country_of_origin','region',
    'transport_mode','transport_mode_label',
    'shipment_count','total_weight_kg','total_units_shipped',
    'total_carbon_kg_co2e','total_carbon_tonnes',
    'carbon_per_unit_kg','carbon_saved_vs_air_kg',
    'total_order_value_gbp','reliability_score'
]]
pbi_carbon_sup.to_csv(os.path.join(OUTPUT_DIR, 'pbi_fact_carbon_by_supplier.csv'), index=False)
print("    OK {:,} rows".format(len(pbi_carbon_sup)))


# =============================================================================
# TABLE 8 — pbi_fact_monte_carlo_summary
# Monte Carlo results for inventory optimisation visuals
# =============================================================================
print("\n[8/8] Building pbi_fact_monte_carlo_summary...")

mc_merged = mc.merge(
    products[['product_id','product_name','category_name']],
    on='product_id', how='left'
).merge(
    green[['product_id','recommended_mode','green_decision_made',
           'carbon_saving_vs_air_kg','decision_rationale']],
    on='product_id', how='left'
)

mc_merged['safety_stock_value_current']   = mc_merged['working_capital_released'].clip(lower=0).round(2)
mc_merged['safety_stock_value_optimised'] = 0
mc_merged['working_capital_saved_gbp']    = mc_merged['working_capital_released'].clip(lower=0).round(2)
mc_merged['stockout_improvement_pct']     = (
    (mc_merged['stockout_prob_current'] - mc_merged['stockout_prob_optimised'])
    / mc_merged['stockout_prob_current'].clip(lower=0.001) * 100
).round(1)

pbi_mc = mc_merged[[
    'product_id','product_name','category_name','abc_class',
    'supplier_id','recommended_mode','green_decision_made',
    'avg_daily_demand','mean_demand_during_lt',
    'lt_avg_simulated','lt_p90_days','lt_p95_days','lt_spike_events_pct',
    'safety_stock_current','safety_stock_optimised',
    'rop_current','rop_optimised',
    'stockout_prob_current','stockout_prob_optimised',
    'service_level_target','service_level_achieved',
    'safety_stock_value_current','safety_stock_value_optimised',
    'working_capital_saved_gbp','working_capital_released',
    'annual_holding_cost_curr','annual_holding_cost_opt',
    'carbon_saving_vs_air_kg','stockout_improvement_pct'
]]
pbi_mc.to_csv(os.path.join(OUTPUT_DIR, 'pbi_fact_monte_carlo_summary.csv'), index=False)
print("    OK {:,} rows".format(len(pbi_mc)))


# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
print("  POWER BI MOCK DATA — Generation Complete")
print("=" * 60)
files = os.listdir(OUTPUT_DIR)
total_rows = 0
for f in sorted(files):
    if f.endswith('.csv'):
        df = pd.read_csv(os.path.join(OUTPUT_DIR, f))
        total_rows += len(df)
        print("  {:<45} {:>6,} rows".format(f, len(df)))
print("  " + "-" * 55)
print("  Total rows across all tables:  {:>10,}".format(total_rows))
print("=" * 60)
print("\n  Files saved to: dashboard/mock_data/")
print("  Import all 8 CSVs into Power BI Desktop")
print("  then apply DAX measures from dax_measures.md")
print("=" * 60)
