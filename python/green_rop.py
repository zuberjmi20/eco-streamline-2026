"""
=============================================================================
Eco-Streamline 2026 | Apex Distribution UK
FILE: green_rop.py
PURPOSE: Green-ROP Algorithm — Reorder Point optimised for cost AND carbon
AUTHOR: Lead Business Transformation Analyst
=============================================================================

THE CORE BUSINESS QUESTION THIS MODULE ANSWERS
-----------------------------------------------
"Should we ship by Sea to save CO2, or by Air to prevent a stock-out?"

This is the Apex Distribution dilemma. Their Tier-1 partners (Tesco, John
Lewis) have issued TWO conflicting mandates:

  1. Provide granular Scope 3 carbon data per shipment (UK SRS, Q4 2026)
     → Incentivises Sea freight (16x lower emissions than Air)

  2. Never stock out on A-list products or face contract termination
     → Sometimes forces Air freight when Sea lead times cause risk

The Green-ROP algorithm resolves this tension by calculating the FULL cost
of each transport decision — financial cost + carbon cost — and making a
transparent, auditable recommendation with a complete trade-off breakdown.

HOW IT WORKS
------------
For each product, given current stock level and supplier options:

  Step 1: Calculate ROP for each available transport mode
          (using Monte Carlo output as input)

  Step 2: Calculate total cost per mode:
          - Freight cost (relative cost index * weight * distance)
          - Stock-out cost (probability * lost margin * avg order value)
          - Carbon cost (kg CO2e * carbon price — optional)
          - Holding cost (days saved/lost * daily holding rate)

  Step 3: Apply decision logic:
          IF carbon saving > threshold AND stock-out risk acceptable:
              RECOMMEND slower/greener mode
          ELIF stock-out risk too high:
              RECOMMEND faster mode + flag carbon impact
          ELSE:
              RECOMMEND on cost alone + show carbon breakdown

  Step 4: Output full trade-off report — never a black box

CARBON PRICING
--------------
Uses UK Emissions Trading Scheme (ETS) reference price.
Default: GBP 45 per tonne CO2e (conservative 2026 estimate).
Configurable — set to 0 to make decisions on cost only.
=============================================================================
"""

import numpy as np
import pandas as pd
import os
import json
from dataclasses import dataclass, asdict
from typing import Optional
import warnings
warnings.filterwarnings('ignore')

# Paths
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
                if '__file__' in dir() else os.path.join(os.getcwd(), 'eco-streamline-2026')
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
REFERENCE_DIR = os.path.join(BASE_DIR, 'data', 'reference')

# Carbon pricing
UK_ETS_CARBON_PRICE_GBP_PER_TONNE = 45.0   # GBP per tonne CO2e (UK ETS 2026 estimate)
CARBON_BUDGET_THRESHOLD_KG        = 500.0   # kg CO2e per shipment — above this, flag it

# Stock-out cost parameters
STOCKOUT_COST_MULTIPLIER = 2.5   # Lost margin * 2.5 (lost sale + relationship damage)
MAX_ACCEPTABLE_STOCKOUT_RISK = {
    'A': 0.05,   # A-class: max 5% stock-out probability
    'B': 0.10,   # B-class: max 10%
    'C': 0.15,   # C-class: max 15%
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TransportOption:
    """Represents one transport mode option for a shipment decision."""
    mode_code:              str
    mode_name:              str
    lead_time_days:         int
    freight_cost_gbp:       float
    stockout_probability:   float
    stockout_cost_gbp:      float
    carbon_kg_co2e:         float
    carbon_cost_gbp:        float
    total_cost_gbp:         float
    is_feasible:            bool     # meets service level target
    feasibility_reason:     str


@dataclass
class GreenROPDecision:
    """Full output of the Green-ROP algorithm for one product."""
    product_id:             str
    product_name:           str
    abc_class:              str
    supplier_id:            str
    supplier_name:          str
    current_stock:          int
    rop_optimised:          int
    is_reorder_triggered:   bool

    # Recommended option
    recommended_mode:       str
    recommended_rop:        int
    recommended_order_qty:  int
    decision_rationale:     str

    # All options evaluated
    options:                list

    # Carbon trade-off summary
    carbon_saving_vs_air_kg:    float
    cost_premium_vs_cheapest:   float
    green_decision_made:        bool     # True if carbon influenced the decision

    # Flags
    requires_human_review:  bool
    review_reason:          str


# =============================================================================
# COST CALCULATORS
# =============================================================================

def calc_freight_cost(
    weight_kg:          float,
    distance_km:        float,
    mode_cost_index:    float,
    base_rate_per_kg_km: float = 0.0008
) -> float:
    """
    Estimate freight cost for a shipment.

    Parameters
    ----------
    weight_kg        : total shipment weight
    distance_km      : shipping distance
    mode_cost_index  : relative cost multiplier (ROAD=1.0, AIR=8.5)
    base_rate        : GBP per kg per km (Road baseline)

    Returns
    -------
    float: estimated freight cost in GBP
    """
    return round(weight_kg * distance_km * base_rate_per_kg_km * mode_cost_index, 2)


def calc_carbon_emissions(
    weight_kg:              float,
    distance_km:            float,
    kg_co2e_per_tonne_km:   float
) -> float:
    """
    Calculate Scope 3 Category 4 carbon emissions.
    Formula: weight_tonnes * distance_km * emission_factor

    This is the DEFRA-compliant calculation used in the UK SRS report.
    """
    weight_tonnes = weight_kg / 1000.0
    return round(weight_tonnes * distance_km * kg_co2e_per_tonne_km, 4)


def calc_stockout_cost(
    stockout_probability:   float,
    avg_order_value_gbp:    float,
    gross_margin_pct:       float
) -> float:
    """
    Estimate expected cost of a stock-out event.

    Cost = P(stockout) * lost margin * multiplier
    Multiplier accounts for lost sale + relationship/contract risk.
    """
    expected_lost_margin = (
        avg_order_value_gbp *
        (gross_margin_pct / 100) *
        STOCKOUT_COST_MULTIPLIER
    )
    return round(stockout_probability * expected_lost_margin, 2)


# =============================================================================
# TRANSPORT OPTION EVALUATOR
# =============================================================================

def evaluate_transport_options(
    product_row:        pd.Series,
    supplier_row:       pd.Series,
    mc_result:          dict,
    distance_df:        pd.DataFrame,
    transport_df:       pd.DataFrame,
    order_qty:          int,
    current_stock:      int
) -> list:
    """
    Evaluate all viable transport modes for a product-supplier pair.

    For each available transport mode:
    1. Calculate lead time impact (faster = lower stock-out risk)
    2. Calculate freight cost
    3. Calculate carbon emissions
    4. Calculate total cost (freight + stock-out risk + carbon cost)
    5. Assess feasibility against service level target

    Returns
    -------
    List of TransportOption objects, sorted by total cost
    """
    options = []
    abc     = product_row['abc_class']
    margin  = float(product_row['gross_margin_pct'])
    price   = float(product_row['unit_price_gbp'])
    cost    = float(product_row['unit_cost_gbp'])
    weight  = float(product_row['weight_kg']) * order_qty
    country = str(supplier_row['country_of_origin'])
    max_risk = MAX_ACCEPTABLE_STOCKOUT_RISK.get(abc, 0.10)

    avg_order_value = price * order_qty

    # Available modes for this supplier's region
    available_modes = [supplier_row['primary_transport']]
    if pd.notna(supplier_row['secondary_transport']):
        available_modes.append(supplier_row['secondary_transport'])

    # Also consider alternatives if region allows
    region = supplier_row['region']
    if region == 'INTERCONTINENTAL':
        for m in ['SEA', 'AIR']:
            if m not in available_modes:
                available_modes.append(m)
    elif region == 'EUROPEAN':
        for m in ['ROAD', 'RAIL', 'SEA']:
            if m not in available_modes:
                available_modes.append(m)

    available_modes = list(dict.fromkeys(available_modes))  # deduplicate, preserve order

    for mode_code in available_modes:
        # Get transport mode details
        mode_row = transport_df[transport_df['mode_code'] == mode_code]
        if mode_row.empty:
            continue
        mode_row = mode_row.iloc[0]

        # Get distance for this route + mode
        dist_row = distance_df[
            (distance_df['origin_country'] == country) &
            (distance_df['transport_mode'] == mode_code)
        ]
        if dist_row.empty:
            # Fallback: use primary mode distance if available
            dist_row = distance_df[
                (distance_df['origin_country'] == country)
            ]
            if dist_row.empty:
                continue
        distance_km = float(dist_row.iloc[0]['distance_km'])

        # Adjust lead time by mode speed ratio
        primary_mode = supplier_row['primary_transport']
        primary_speed = float(transport_df[
            transport_df['mode_code'] == primary_mode
        ]['avg_speed_kmh'].iloc[0]) if not transport_df[
            transport_df['mode_code'] == primary_mode
        ].empty else 80.0

        mode_speed   = float(mode_row['avg_speed_kmh'])
        speed_ratio  = primary_speed / mode_speed if mode_speed > 0 else 1.0

        # Adjusted lead time
        base_lt      = float(mc_result['lt_avg_simulated'])
        adj_lt       = max(1, int(np.round(base_lt * speed_ratio)))

        # Stock-out probability: approximate from MC output
        # Faster mode = lower lead time = lower demand during LT = lower stockout risk
        base_stockout = mc_result['stockout_prob_optimised']
        lt_ratio      = adj_lt / max(base_lt, 1)
        stockout_prob = max(0.0, min(1.0, base_stockout * lt_ratio))

        # Costs
        freight_cost  = calc_freight_cost(
            weight, distance_km, float(mode_row['relative_cost_index'])
        )
        stockout_cost = calc_stockout_cost(stockout_prob, avg_order_value, margin)
        carbon_kg     = calc_carbon_emissions(
            weight, distance_km, float(mode_row['kg_co2e_per_tonne_km'])
        )
        carbon_cost   = round(
            (carbon_kg / 1000.0) * UK_ETS_CARBON_PRICE_GBP_PER_TONNE, 2
        )
        total_cost    = freight_cost + stockout_cost + carbon_cost

        # Feasibility
        is_feasible   = (stockout_prob <= max_risk)
        if not is_feasible:
            reason = (
                "Stock-out risk {:.1f}% exceeds {}-class limit of {:.0f}%".format(
                    stockout_prob * 100, abc, max_risk * 100
                )
            )
        else:
            reason = "Meets {:.0f}% service level target".format(
                (1 - max_risk) * 100
            )

        options.append(TransportOption(
            mode_code            = mode_code,
            mode_name            = str(mode_row['mode_name']),
            lead_time_days       = adj_lt,
            freight_cost_gbp     = freight_cost,
            stockout_probability = round(stockout_prob, 4),
            stockout_cost_gbp    = stockout_cost,
            carbon_kg_co2e       = carbon_kg,
            carbon_cost_gbp      = carbon_cost,
            total_cost_gbp       = total_cost,
            is_feasible          = is_feasible,
            feasibility_reason   = reason,
        ))

    # Sort: feasible first, then by total cost
    options.sort(key=lambda x: (not x.is_feasible, x.total_cost_gbp))
    return options


# =============================================================================
# CORE GREEN-ROP DECISION ENGINE
# =============================================================================

def make_green_rop_decision(
    product_row:    pd.Series,
    supplier_row:   pd.Series,
    mc_result:      dict,
    distance_df:    pd.DataFrame,
    transport_df:   pd.DataFrame,
    current_stock:  int = None
) -> GreenROPDecision:
    """
    Make the Green-ROP transport and reorder decision for one product.

    Decision hierarchy:
    1. If reorder not triggered → no decision needed (return status only)
    2. If only one feasible option → recommend it, flag if high carbon
    3. If multiple feasible options:
       a. If greener option within 15% of cheapest cost → recommend green
       b. If greener option significantly more expensive → recommend cheapest
          but show full carbon trade-off
       c. If decisions conflict badly → escalate to human review

    Parameters
    ----------
    current_stock : int — current stock on hand. If None, assumes at ROP.
    """
    pid         = str(product_row['product_id'])
    pname       = str(product_row['product_name'])
    abc         = str(product_row['abc_class'])
    sid         = str(supplier_row['supplier_id'])
    sname       = str(supplier_row['supplier_name'])
    rop         = int(mc_result['rop_optimised'])
    order_qty   = int(mc_result['recommended_order_qty'])

    if current_stock is None:
        current_stock = rop  # Assume reorder just triggered

    is_triggered = (current_stock <= rop)

    # Evaluate all transport options
    options = evaluate_transport_options(
        product_row, supplier_row, mc_result,
        distance_df, transport_df, order_qty, current_stock
    )

    if not options:
        return GreenROPDecision(
            product_id=pid, product_name=pname, abc_class=abc,
            supplier_id=sid, supplier_name=sname,
            current_stock=current_stock, rop_optimised=rop,
            is_reorder_triggered=is_triggered,
            recommended_mode='ROAD', recommended_rop=rop,
            recommended_order_qty=order_qty,
            decision_rationale='No transport options available — defaulting to ROAD.',
            options=[], carbon_saving_vs_air_kg=0.0,
            cost_premium_vs_cheapest=0.0, green_decision_made=False,
            requires_human_review=True,
            review_reason='No viable transport options found for this supplier route.'
        )

    feasible_options = [o for o in options if o.is_feasible]

    # ── Decision Logic ────────────────────────────────────────────────────────

    requires_review = False
    review_reason   = ''
    green_decision  = False

    if not feasible_options:
        # No option meets service level — recommend fastest, flag urgently
        recommended = sorted(options, key=lambda x: x.lead_time_days)[0]
        rationale   = (
            "WARNING: No transport mode meets the {}-class service level target. "
            "Fastest available mode selected. Immediate review required. "
            "Consider emergency procurement or demand smoothing.".format(abc)
        )
        requires_review = True
        review_reason   = "No feasible transport option meets {} service level.".format(abc)

    elif len(feasible_options) == 1:
        recommended = feasible_options[0]
        rationale   = (
            "Only one feasible option for {}-class service level. "
            "Selected {} (stockout risk: {:.1f}%).".format(
                abc, recommended.mode_name,
                recommended.stockout_probability * 100
            )
        )

    else:
        # Multiple feasible options — apply Green-ROP logic
        cheapest = min(feasible_options, key=lambda x: x.total_cost_gbp)
        greenest = min(feasible_options, key=lambda x: x.carbon_kg_co2e)

        cost_premium_pct = (
            (greenest.total_cost_gbp - cheapest.total_cost_gbp) /
            max(cheapest.total_cost_gbp, 0.01) * 100
        )

        carbon_saving_pct = (
            (cheapest.carbon_kg_co2e - greenest.carbon_kg_co2e) /
            max(cheapest.carbon_kg_co2e, 0.01) * 100
        ) if cheapest.mode_code != greenest.mode_code else 0

        if cheapest.mode_code == greenest.mode_code:
            # Same option is both cheapest AND greenest
            recommended = cheapest
            rationale   = (
                "{} is both the lowest cost (GBP {:.0f}) and lowest carbon "
                "({:.1f} kg CO2e) option. Clear recommendation.".format(
                    recommended.mode_name,
                    recommended.total_cost_gbp,
                    recommended.carbon_kg_co2e
                )
            )

        elif cost_premium_pct <= 15.0:
            # Greener option costs within 15% — recommend green
            recommended   = greenest
            green_decision = True
            rationale     = (
                "GREEN CHOICE: {} saves {:.1f} kg CO2e vs {} "
                "at only {:.1f}% cost premium (GBP {:.0f} vs GBP {:.0f}). "
                "Carbon saving justifies the premium. "
                "UK SRS benefit: lower Scope 3 footprint reported to Tesco/John Lewis.".format(
                    greenest.mode_name,
                    cheapest.carbon_kg_co2e - greenest.carbon_kg_co2e,
                    cheapest.mode_name,
                    cost_premium_pct,
                    greenest.total_cost_gbp,
                    cheapest.total_cost_gbp
                )
            )

        elif cost_premium_pct > 15.0 and abc == 'A':
            # High cost premium, but A-class — cost wins, flag carbon impact
            recommended = cheapest
            rationale   = (
                "COST PRIORITY: {}-class product. {} selected as lowest total cost "
                "(GBP {:.0f}). {} would save {:.0f} kg CO2e "
                "but at {:.1f}% cost premium (GBP {:.0f} extra). "
                "Flag for sustainability review.".format(
                    abc,
                    cheapest.mode_name,
                    cheapest.total_cost_gbp,
                    greenest.mode_name,
                    cheapest.carbon_kg_co2e - greenest.carbon_kg_co2e,
                    cost_premium_pct,
                    greenest.total_cost_gbp - cheapest.total_cost_gbp
                )
            )

        else:
            # C/B class with significant premium — recommend cheapest
            recommended = cheapest
            rationale   = (
                "{} selected: lowest total cost (GBP {:.0f}). "
                "Greener alternative {} costs {:.1f}% more. "
                "Carbon saving: {:.1f} kg CO2e.".format(
                    cheapest.mode_name,
                    cheapest.total_cost_gbp,
                    greenest.mode_name,
                    cost_premium_pct,
                    cheapest.carbon_kg_co2e - greenest.carbon_kg_co2e
                )
            )

    # Carbon saving vs theoretical air freight
    air_option = next((o for o in options if o.mode_code == 'AIR'), None)
    carbon_saving_vs_air = (
        air_option.carbon_kg_co2e - recommended.carbon_kg_co2e
        if air_option and air_option.mode_code != recommended.mode_code
        else 0.0
    )

    cost_premium = (
        recommended.total_cost_gbp -
        min(o.total_cost_gbp for o in feasible_options)
        if feasible_options else 0.0
    )

    return GreenROPDecision(
        product_id              = pid,
        product_name            = pname,
        abc_class               = abc,
        supplier_id             = sid,
        supplier_name           = sname,
        current_stock           = current_stock,
        rop_optimised           = rop,
        is_reorder_triggered    = is_triggered,
        recommended_mode        = recommended.mode_code,
        recommended_rop         = rop,
        recommended_order_qty   = order_qty,
        decision_rationale      = rationale,
        options                 = [asdict(o) for o in options],
        carbon_saving_vs_air_kg = round(carbon_saving_vs_air, 2),
        cost_premium_vs_cheapest= round(cost_premium, 2),
        green_decision_made     = green_decision,
        requires_human_review   = requires_review,
        review_reason           = review_reason,
    )


# =============================================================================
# BATCH RUNNER — All products
# =============================================================================

def run_all_green_rop(
    products_df:    pd.DataFrame,
    suppliers_df:   pd.DataFrame,
    sup_prod_df:    pd.DataFrame,
    mc_results_df:  pd.DataFrame,
    distance_df:    pd.DataFrame,
    transport_df:   pd.DataFrame
) -> pd.DataFrame:
    """Run Green-ROP decision engine for all products."""

    print("\n" + "=" * 65)
    print("  GREEN-ROP DECISION ENGINE")
    print("  Apex Distribution UK — Cost + Carbon optimisation")
    print("=" * 65)

    primary  = sup_prod_df[sup_prod_df['is_primary'] == True]
    prod_sup = products_df.merge(
        primary[['product_id', 'supplier_id']], on='product_id'
    ).merge(suppliers_df, on='supplier_id')

    decisions       = []
    green_choices   = 0
    review_required = 0

    for _, row in prod_sup.iterrows():
        pid = row['product_id']
        sid = row['supplier_id']

        mc_row = mc_results_df[mc_results_df['product_id'] == pid]
        if mc_row.empty:
            continue
        mc_result    = mc_row.iloc[0].to_dict()
        product_row  = products_df[products_df['product_id'] == pid].iloc[0]
        supplier_row = suppliers_df[suppliers_df['supplier_id'] == sid].iloc[0]

        decision = make_green_rop_decision(
            product_row, supplier_row, mc_result,
            distance_df, transport_df
        )

        if decision.green_decision_made:
            green_choices += 1
        if decision.requires_human_review:
            review_required += 1

        # Flatten for CSV output
        decisions.append({
            'product_id':               decision.product_id,
            'product_name':             decision.product_name,
            'abc_class':                decision.abc_class,
            'supplier_id':              decision.supplier_id,
            'supplier_name':            decision.supplier_name,
            'rop_optimised':            decision.rop_optimised,
            'recommended_mode':         decision.recommended_mode,
            'recommended_order_qty':    decision.recommended_order_qty,
            'green_decision_made':      decision.green_decision_made,
            'carbon_saving_vs_air_kg':  decision.carbon_saving_vs_air_kg,
            'cost_premium_vs_cheapest': decision.cost_premium_vs_cheapest,
            'requires_human_review':    decision.requires_human_review,
            'review_reason':            decision.review_reason,
            'decision_rationale':       decision.decision_rationale,
        })

    df = pd.DataFrame(decisions)

    print("\n  DECISIONS SUMMARY")
    print("  " + "-" * 40)
    print("  Total products evaluated:  {:>4}".format(len(df)))
    print("  Green transport chosen:    {:>4}".format(green_choices))
    print("  Requires human review:     {:>4}".format(review_required))
    print("")
    print("  MODE RECOMMENDATIONS")
    if not df.empty:
        mode_counts = df['recommended_mode'].value_counts()
        for mode, count in mode_counts.items():
            print("    {:<6}: {:>3} products".format(mode, count))

    print("")
    print("  CARBON SAVINGS vs ALL-AIR BASELINE")
    if not df.empty:
        total_saving = df['carbon_saving_vs_air_kg'].sum()
        print("  Total CO2e saved:   {:>10,.1f} kg".format(total_saving))
        print("  Equivalent to:      {:>10,.1f} tonnes CO2e".format(total_saving / 1000))
    print("=" * 65)

    return df


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':

    print("Loading data...")
    products_df  = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_product.csv'))
    suppliers_df = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_supplier.csv'))
    sup_prod_df  = pd.read_csv(os.path.join(PROCESSED_DIR, 'bridge_supplier_product.csv'))
    transport_df = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_transport_mode.csv'))
    distance_df  = pd.read_csv(os.path.join(REFERENCE_DIR, 'shipping_distance_matrix.csv'))

    mc_path = os.path.join(PROCESSED_DIR, 'monte_carlo_results.csv')
    if not os.path.exists(mc_path):
        print("Monte Carlo results not found. Run monte_carlo.py first.")
        exit(1)
    mc_results_df = pd.read_csv(mc_path)

    # Run Green-ROP for all products
    decisions_df = run_all_green_rop(
        products_df, suppliers_df, sup_prod_df,
        mc_results_df, distance_df, transport_df
    )

    out_path = os.path.join(PROCESSED_DIR, 'green_rop_decisions.csv')
    decisions_df.to_csv(out_path, index=False)
    print("\n  Decisions saved to: green_rop_decisions.csv")

    # Show a sample decision in detail
    print("\n" + "=" * 65)
    print("  SAMPLE DECISION — First A-class product")
    print("=" * 65)

    a_decisions = decisions_df[decisions_df['abc_class'] == 'A']
    if not a_decisions.empty:
        sample = a_decisions.iloc[0]
        print("\n  Product:   {}".format(sample['product_name']))
        print("  Supplier:  {}".format(sample['supplier_name']))
        print("  ABC Class: {}".format(sample['abc_class']))
        print("")
        print("  Optimised ROP:     {} units".format(sample['rop_optimised']))
        print("  Recommended Mode:  {}".format(sample['recommended_mode']))
        print("  Order Quantity:    {} units".format(sample['recommended_order_qty']))
        print("  Green Decision:    {}".format(sample['green_decision_made']))
        print("  CO2 Saved vs Air:  {:.1f} kg".format(sample['carbon_saving_vs_air_kg']))
        print("")
        print("  Rationale:")
        for line in str(sample['decision_rationale']).split('. '):
            if line.strip():
                print("    " + line.strip() + ".")

    print("\n  Phase 3B Complete — Green-ROP Algorithm")
    print("  Ready for: carbon_calculator.py")
    print("=" * 65)
