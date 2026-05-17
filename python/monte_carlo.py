"""
=============================================================================
Eco-Streamline 2026 | Apex Distribution UK
FILE: monte_carlo.py
PURPOSE: Probabilistic Inventory Modelling via Monte Carlo Simulation
AUTHOR: Lead Business Transformation Analyst
=============================================================================

WHY MONTE CARLO INSTEAD OF SIMPLE AVERAGES
-------------------------------------------
The current Excel system uses a fixed average lead time (e.g. 21 days).
This ignores the 2026 shipping reality where intercontinental lead times
swing from 18 to 35+ days. A fixed average almost guarantees stock-outs
during spike events.

Monte Carlo runs 10,000 simulations per product, sampling from the actual
probability distribution of both lead time AND demand. The output is not
"order when stock hits X" but "there is a 95% probability you will not
stock out if you order when stock hits X."

This is the difference between hoping and knowing.

OUTPUTS PER PRODUCT
-------------------
- Optimal safety stock (units)
- Optimal Reorder Point / ROP (units)
- Stock-out probability at current ROP
- Stock-out probability at optimised ROP
- Expected demand during lead time (mean + confidence interval)
- Recommended order quantity
=============================================================================
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import poisson, norm, lognorm
import os
import json
import warnings
warnings.filterwarnings('ignore')

# Reproducibility
RANDOM_SEED   = 2026
N_SIMULATIONS = 10_000

np.random.seed(RANDOM_SEED)

# Paths
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
                if '__file__' in dir() else os.path.join(os.getcwd(), 'eco-streamline-2026')
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
OUTPUT_DIR    = os.path.join(BASE_DIR, 'data', 'processed')

# Seasonal multipliers
SEASONAL_MULTIPLIERS = {
    1: 0.75, 2: 0.80, 3: 0.90, 4: 0.95,  5: 1.00,
    6: 1.05, 7: 1.10, 8: 1.05, 9: 1.00,
    10: 1.10, 11: 1.35, 12: 1.50
}


# =============================================================================
# LEAD TIME SAMPLER
# =============================================================================

def sample_lead_times(supplier_row: pd.Series, n: int = N_SIMULATIONS) -> np.ndarray:
    """
    Sample n lead times for a supplier using their distribution profile.

    Domestic/European  → Normal distribution (low variance, symmetric)
    Intercontinental   → Lognormal distribution (right-skewed, long tail)
    Spike events       → 2026 disruption model: 15% probability of +40-80% extension

    Parameters
    ----------
    supplier_row : pd.Series  — row from dim_supplier.csv
    n            : int        — number of simulations

    Returns
    -------
    np.ndarray of lead time samples (integer days)
    """
    lt_avg    = float(supplier_row['lead_time_avg_days'])
    lt_std    = float(supplier_row['lead_time_std_days'])
    lt_min    = int(supplier_row['lead_time_min_days'])
    lt_max    = int(supplier_row['lead_time_max_days'])
    dist      = str(supplier_row['lead_time_distribution'])
    spike_p   = float(supplier_row['spike_probability'])

    if dist == 'lognormal':
        sigma  = lt_std / lt_avg
        mu     = np.log(lt_avg) - 0.5 * sigma ** 2
        samples = np.random.lognormal(mu, sigma, n)
    else:
        samples = np.random.normal(lt_avg, lt_std, n)

    # Apply 2026 spike events
    spike_mask       = np.random.random(n) < spike_p
    spike_multiplier = np.random.uniform(1.40, 1.80, n)
    samples[spike_mask] *= spike_multiplier[spike_mask]

    # Clip to plausible range (allow up to 2x max for extreme spikes)
    samples = np.clip(samples, lt_min, lt_max * 2.0)

    return np.round(samples).astype(int)


# =============================================================================
# DEMAND SAMPLER
# =============================================================================

def sample_daily_demand(
    avg_daily_demand: float,
    n_days: int,
    n_simulations: int = N_SIMULATIONS,
    seasonal_month: int = 6
) -> np.ndarray:
    """
    Sample total demand over n_days for n_simulations runs.

    Uses Poisson distribution — standard for discrete unit sales.
    Applies seasonal multiplier and 3% probability promotional spike.

    Parameters
    ----------
    avg_daily_demand : float  — baseline daily demand (units)
    n_days           : array  — lead time samples (one per simulation)
    n_simulations    : int    — number of Monte Carlo runs
    seasonal_month   : int    — month for seasonal adjustment

    Returns
    -------
    np.ndarray of total demand during lead time (one per simulation)
    """
    seasonal = SEASONAL_MULTIPLIERS.get(seasonal_month, 1.0)
    adj_demand = avg_daily_demand * seasonal

    # Promotional spike: 3% daily probability, 2-4.5x uplift
    spike_days  = np.random.random((n_simulations, max(n_days))) < 0.03
    spike_mult  = np.random.uniform(2.0, 4.5, (n_simulations, max(n_days)))
    daily_lambda= np.where(spike_days, adj_demand * spike_mult, adj_demand)

    # Poisson demand per day, summed over lead time
    total_demand = np.zeros(n_simulations)
    for i in range(n_simulations):
        lt = n_days[i] if hasattr(n_days, '__len__') else int(n_days)
        lt = min(lt, daily_lambda.shape[1])
        total_demand[i] = np.random.poisson(daily_lambda[i, :lt]).sum()

    return total_demand.astype(int)


# =============================================================================
# CORE MONTE CARLO ENGINE
# =============================================================================

def run_monte_carlo(
    product_row:   pd.Series,
    supplier_row:  pd.Series,
    current_month: int = 6,
    n_simulations: int = N_SIMULATIONS
) -> dict:
    """
    Run Monte Carlo simulation for a single product-supplier pair.

    Simulates n_simulations scenarios, each with:
    - A sampled lead time (from supplier distribution + spike probability)
    - A sampled demand during that lead time (Poisson + seasonal)

    Calculates the optimal safety stock and ROP at the product's
    service level target (95% for A-class, 90% for B-class, 85% for C-class).

    Parameters
    ----------
    product_row   : pd.Series — row from dim_product.csv
    supplier_row  : pd.Series — row from dim_supplier.csv
    current_month : int       — month for seasonal adjustment (1-12)
    n_simulations : int       — number of Monte Carlo runs

    Returns
    -------
    dict with full simulation results and recommendations
    """
    pid           = product_row['product_id']
    abc           = product_row['abc_class']
    unit_cost     = float(product_row['unit_cost_gbp'])
    unit_price    = float(product_row['unit_price_gbp'])
    weight_kg     = float(product_row['weight_kg'])
    service_level = float(product_row['service_level_target'])
    moq           = int(product_row['min_order_qty'])

    # Average daily demand (baseline, pre-seasonal)
    abc_scale     = {'A': 1.8, 'B': 1.0, 'C': 0.4}
    avg_daily     = (50 / unit_price) * abc_scale.get(abc, 1.0)
    seasonal_mult = SEASONAL_MULTIPLIERS.get(current_month, 1.0)
    avg_daily_adj = avg_daily * seasonal_mult

    # ── Step 1: Sample lead times ─────────────────────────────────────────────
    lead_times = sample_lead_times(supplier_row, n_simulations)

    # ── Step 2: Sample demand during lead time ────────────────────────────────
    max_lt       = int(np.max(lead_times))
    demand_during_lt = np.zeros(n_simulations)

    for i in range(n_simulations):
        lt = lead_times[i]
        seasonal = SEASONAL_MULTIPLIERS.get(current_month, 1.0)
        adj_d    = avg_daily * seasonal
        daily_d  = np.random.poisson(max(0.01, adj_d), lt)

        # Promotional spike
        spikes   = np.random.random(lt) < 0.03
        multipliers = np.where(spikes, np.random.uniform(2.0, 4.5, lt), 1.0)
        daily_d  = (daily_d * multipliers).astype(int)

        demand_during_lt[i] = daily_d.sum()

    # ── Step 3: Calculate safety stock at service level ───────────────────────
    # Safety stock = percentile of demand_during_lt - mean demand during avg LT
    mean_demand_during_lt = avg_daily_adj * float(supplier_row['lead_time_avg_days'])

    # Service level → percentile of demand distribution
    demand_percentile = np.percentile(demand_during_lt, service_level * 100)
    safety_stock_opt  = max(0, int(np.ceil(demand_percentile - mean_demand_during_lt)))

    # Current safety stock (simple Z-score method — what they had before)
    z_score           = float(product_row.get('z_score', 1.65))
    demand_std        = float(np.std(demand_during_lt))
    safety_stock_curr = int(np.ceil(z_score * demand_std))

    # ── Step 4: Calculate Reorder Points ─────────────────────────────────────
    rop_current   = int(np.ceil(mean_demand_during_lt + safety_stock_curr))
    rop_optimised = int(np.ceil(mean_demand_during_lt + safety_stock_opt))

    # ── Step 5: Stock-out probability at each ROP ─────────────────────────────
    stockout_at_current   = float(np.mean(demand_during_lt > rop_current))
    stockout_at_optimised = float(np.mean(demand_during_lt > rop_optimised))

    # ── Step 6: Optimal order quantity (EOQ-informed) ─────────────────────────
    annual_demand = avg_daily_adj * 365
    holding_cost  = unit_cost * 0.25  # 25% holding cost rate
    order_cost    = 150.0             # Fixed cost per order (GBP)

    if annual_demand > 0 and holding_cost > 0:
        eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost)
    else:
        eoq = moq

    order_qty = max(moq, int(np.ceil(eoq / moq) * moq))

    # ── Step 7: Working capital impact ───────────────────────────────────────
    excess_safety_stock      = max(0, safety_stock_curr - safety_stock_opt)
    working_capital_released = excess_safety_stock * unit_cost

    # ── Step 8: Simulation statistics ────────────────────────────────────────
    lt_p50  = int(np.percentile(lead_times, 50))
    lt_p90  = int(np.percentile(lead_times, 90))
    lt_p95  = int(np.percentile(lead_times, 95))
    dem_p50 = int(np.percentile(demand_during_lt, 50))
    dem_p95 = int(np.percentile(demand_during_lt, 95))

    return {
        'product_id':               pid,
        'supplier_id':              supplier_row['supplier_id'],
        'abc_class':                abc,
        'current_month':            current_month,
        'n_simulations':            n_simulations,

        # Demand profile
        'avg_daily_demand':         round(avg_daily_adj, 2),
        'mean_demand_during_lt':    round(mean_demand_during_lt, 1),
        'demand_std_during_lt':     round(demand_std, 1),
        'demand_p50_during_lt':     dem_p50,
        'demand_p95_during_lt':     dem_p95,

        # Lead time profile
        'lt_avg_simulated':         round(float(np.mean(lead_times)), 1),
        'lt_std_simulated':         round(float(np.std(lead_times)), 1),
        'lt_p50_days':              lt_p50,
        'lt_p90_days':              lt_p90,
        'lt_p95_days':              lt_p95,
        'lt_spike_events_pct':      round(float(np.mean(
                                        lead_times > supplier_row['lead_time_max_days']
                                    )) * 100, 1),

        # Safety stock
        'safety_stock_current':     safety_stock_curr,
        'safety_stock_optimised':   safety_stock_opt,
        'safety_stock_reduction':   max(0, safety_stock_curr - safety_stock_opt),

        # Reorder points
        'rop_current':              rop_current,
        'rop_optimised':            rop_optimised,

        # Service level
        'service_level_target':     service_level,
        'stockout_prob_current':    round(stockout_at_current,   4),
        'stockout_prob_optimised':  round(stockout_at_optimised, 4),
        'service_level_achieved':   round(1 - stockout_at_optimised, 4),

        # Order quantity
        'eoq':                      int(eoq),
        'recommended_order_qty':    order_qty,
        'moq':                      moq,

        # Financial impact
        'unit_cost_gbp':            unit_cost,
        'working_capital_released': round(working_capital_released, 2),
        'annual_holding_cost_curr': round(safety_stock_curr * unit_cost * 0.25, 2),
        'annual_holding_cost_opt':  round(safety_stock_opt  * unit_cost * 0.25, 2),
    }


# =============================================================================
# BATCH RUNNER — All products
# =============================================================================

def run_all_products(
    products_df:  pd.DataFrame,
    suppliers_df: pd.DataFrame,
    sup_prod_df:  pd.DataFrame,
    current_month: int = 6
) -> pd.DataFrame:
    """
    Run Monte Carlo simulation for all 50 products.
    Matches each product to its primary supplier.

    Parameters
    ----------
    products_df   : dim_product data
    suppliers_df  : dim_supplier data
    sup_prod_df   : bridge_supplier_product data
    current_month : month for seasonal adjustment

    Returns
    -------
    DataFrame with simulation results for all products
    """
    print("\n" + "=" * 65)
    print("  MONTE CARLO INVENTORY SIMULATION")
    print("  Apex Distribution UK — {:,} simulations per product".format(N_SIMULATIONS))
    print("=" * 65)

    primary = sup_prod_df[sup_prod_df['is_primary'] == True]
    prod_sup = products_df.merge(
        primary[['product_id', 'supplier_id']], on='product_id'
    ).merge(suppliers_df, on='supplier_id')

    results = []
    total   = len(prod_sup)

    for i, (_, row) in enumerate(prod_sup.iterrows(), 1):
        product_row  = products_df[products_df['product_id'] == row['product_id']].iloc[0]
        supplier_row = suppliers_df[suppliers_df['supplier_id'] == row['supplier_id']].iloc[0]

        result = run_monte_carlo(product_row, supplier_row, current_month)
        results.append(result)

        if i % 10 == 0 or i == total:
            print("  Simulated {:>3}/{} products...".format(i, total))

    df = pd.DataFrame(results)

    # ── Summary statistics ────────────────────────────────────────────────────
    total_wc_released   = df['working_capital_released'].sum()
    total_holding_saved = (
        df['annual_holding_cost_curr'].sum() -
        df['annual_holding_cost_opt'].sum()
    )
    avg_stockout_curr   = df['stockout_prob_current'].mean()
    avg_stockout_opt    = df['stockout_prob_optimised'].mean()

    a_class = df[df['abc_class'] == 'A']

    print("\n" + "-" * 65)
    print("  SIMULATION RESULTS SUMMARY")
    print("-" * 65)
    print("  Products simulated:          {:>6,}".format(len(df)))
    print("  Simulations per product:     {:>6,}".format(N_SIMULATIONS))
    print("")
    print("  WORKING CAPITAL IMPACT")
    print("  Working capital released:    GBP {:>10,.0f}".format(total_wc_released))
    print("  Annual holding cost saved:   GBP {:>10,.0f}".format(total_holding_saved))
    print("")
    print("  STOCK-OUT RISK (all products)")
    print("  Current avg stock-out prob:  {:>9.1f}%".format(avg_stockout_curr * 100))
    print("  Optimised avg stock-out prob:{:>9.1f}%".format(avg_stockout_opt * 100))
    print("")
    print("  A-CLASS PRODUCTS (never stock-out target)")
    print("  Avg current ROP:             {:>6.0f} units".format(a_class['rop_current'].mean()))
    print("  Avg optimised ROP:           {:>6.0f} units".format(a_class['rop_optimised'].mean()))
    print("  Avg LT spike events:         {:>9.1f}%".format(
        a_class['lt_spike_events_pct'].mean()))
    print("-" * 65)

    return df


# =============================================================================
# SENSITIVITY ANALYSIS — What-If module
# =============================================================================

def sensitivity_analysis(
    product_row:    pd.Series,
    supplier_row:   pd.Series,
    scenarios:      dict = None
) -> pd.DataFrame:
    """
    Runs Monte Carlo across multiple scenarios to answer What-If questions.

    Default scenarios match the Streamlit Scenario Planner:
    - Lead time +20%, +40% (shipping disruption)
    - Demand +25%, +50% (promotional / seasonal spike)
    - Combined worst case

    Parameters
    ----------
    product_row  : pd.Series
    supplier_row : pd.Series
    scenarios    : dict of {name: {param: multiplier}}

    Returns
    -------
    DataFrame comparing ROP and stock-out risk across scenarios
    """
    if scenarios is None:
        scenarios = {
            'Baseline':             {'lt_mult': 1.0,  'demand_mult': 1.0},
            'LT +20% (mild delay)': {'lt_mult': 1.2,  'demand_mult': 1.0},
            'LT +40% (disruption)': {'lt_mult': 1.4,  'demand_mult': 1.0},
            'Demand +25%':          {'lt_mult': 1.0,  'demand_mult': 1.25},
            'Demand +50% (peak)':   {'lt_mult': 1.0,  'demand_mult': 1.50},
            'Worst Case':           {'lt_mult': 1.4,  'demand_mult': 1.50},
        }

    rows = []
    base_supplier = supplier_row.copy()
    base_product  = product_row.copy()

    for scenario_name, params in scenarios.items():
        # Adjust supplier lead time parameters
        mod_supplier = base_supplier.copy()
        mod_supplier['lead_time_avg_days'] = (
            base_supplier['lead_time_avg_days'] * params['lt_mult']
        )
        mod_supplier['lead_time_std_days'] = (
            base_supplier['lead_time_std_days'] * params['lt_mult']
        )

        # Adjust product price to simulate demand change (proxy)
        mod_product = base_product.copy()
        orig_price  = float(base_product['unit_price_gbp'])
        mod_product['unit_price_gbp'] = orig_price / params['demand_mult']

        result = run_monte_carlo(mod_product, mod_supplier, n_simulations=2000)

        rows.append({
            'scenario':             scenario_name,
            'lt_multiplier':        params['lt_mult'],
            'demand_multiplier':    params['demand_mult'],
            'rop_optimised':        result['rop_optimised'],
            'safety_stock':         result['safety_stock_optimised'],
            'stockout_prob_pct':    round(result['stockout_prob_optimised'] * 100, 2),
            'service_level_pct':    round(result['service_level_achieved']  * 100, 2),
            'working_capital_gbp':  result['working_capital_released'],
            'lt_p90_days':          result['lt_p90_days'],
            'lt_p95_days':          result['lt_p95_days'],
        })

    return pd.DataFrame(rows)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':

    print("Loading Phase 1 data...")
    products_df  = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_product.csv'))
    suppliers_df = pd.read_csv(os.path.join(PROCESSED_DIR, 'dim_supplier.csv'))
    sup_prod_df  = pd.read_csv(os.path.join(PROCESSED_DIR, 'bridge_supplier_product.csv'))

    # Run full simulation (current month = November — peak season)
    results_df = run_all_products(products_df, suppliers_df, sup_prod_df, current_month=11)

    # Save results
    out_path = os.path.join(OUTPUT_DIR, 'monte_carlo_results.csv')
    results_df.to_csv(out_path, index=False)
    print("\n  Results saved to: monte_carlo_results.csv")

    # Sensitivity analysis on worst-case product (A-class, intercontinental)
    print("\n" + "=" * 65)
    print("  SENSITIVITY ANALYSIS — Worst-case A-class product")
    print("=" * 65)

    a_class_products  = products_df[products_df['abc_class'] == 'A']
    sample_product    = a_class_products.iloc[0]

    primary_sup_id    = sup_prod_df[
        (sup_prod_df['product_id'] == sample_product['product_id']) &
        (sup_prod_df['is_primary'] == True)
    ]['supplier_id'].values[0]

    sample_supplier   = suppliers_df[
        suppliers_df['supplier_id'] == primary_sup_id
    ].iloc[0]

    sensitivity_df = sensitivity_analysis(sample_product, sample_supplier)

    print("\n  Product: {}".format(sample_product['product_name']))
    print("  Supplier: {}".format(sample_supplier['supplier_name']))
    print("")
    print("  {:<25} {:>6} {:>10} {:>12} {:>14}".format(
        'Scenario', 'ROP', 'Safety Stk', 'Stockout%', 'Service Lvl%'
    ))
    print("  " + "-" * 72)
    for _, row in sensitivity_df.iterrows():
        print("  {:<25} {:>6} {:>10} {:>11.2f}% {:>13.2f}%".format(
            row['scenario'],
            row['rop_optimised'],
            row['safety_stock'],
            row['stockout_prob_pct'],
            row['service_level_pct']
        ))

    sensitivity_out = os.path.join(OUTPUT_DIR, 'sensitivity_analysis.csv')
    sensitivity_df.to_csv(sensitivity_out, index=False)
    print("\n  Sensitivity analysis saved to: sensitivity_analysis.csv")

    print("\n  Phase 3A Complete — Monte Carlo Simulation")
    print("  Ready for: green_rop.py")
    print("=" * 65)
