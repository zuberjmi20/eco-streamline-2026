"""
=============================================================================
Eco-Streamline 2026 — Synthetic Data Generator
Client: Apex Distribution UK
Author: Lead Business Transformation Analyst
=============================================================================

Generates three layers of realistic synthetic data:
  Layer 1 — Clean Master Data   : Products, Suppliers, Warehouses, Transport
  Layer 2 — Transactional Data  : Orders, Shipments, Stock movements (2 years)
  Layer 3 — Dirty Ingest CSVs   : Messy supplier files with ~12% error rate

Statistical properties match 2026 UK distribution realities:
  - Lead times: right-skewed with intercontinental spike events
  - Demand: Poisson with seasonal multipliers + random promotional spikes
  - Stock-outs cluster around peak months (Nov-Dec)
  - Slow-movers accumulate realistically over time
=============================================================================
"""

import pandas as pd
import numpy as np
from scipy import stats
import os
import json
import random
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Reproducibility
RANDOM_SEED = 2026
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# Output Paths — compatible with Colab, Jupyter, and standard Python
try:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    # Running in Colab or Jupyter — save to /content/eco-streamline-2026
    BASE_DIR = os.path.join(os.getcwd(), "eco-streamline-2026")

RAW_DIR       = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
REFERENCE_DIR = os.path.join(BASE_DIR, "data", "reference")

for d in [RAW_DIR, PROCESSED_DIR, REFERENCE_DIR]:
    os.makedirs(d, exist_ok=True)

# Simulation Period
SIM_START = datetime(2024, 1, 1)
SIM_END   = datetime(2025, 12, 31)

# Seasonal Demand Multipliers
SEASONAL_MULTIPLIERS = {
    1: 0.75, 2: 0.80, 3: 0.90, 4: 0.95,  5: 1.00,
    6: 1.05, 7: 1.10, 8: 1.05, 9: 1.00,
    10: 1.10, 11: 1.35, 12: 1.50
}

print("=" * 65)
print("  ECO-STREAMLINE 2026 -- Synthetic Data Generator")
print("  Apex Distribution UK")
print("=" * 65)


# =============================================================================
# LAYER 1 - MASTER DATA
# =============================================================================

def generate_products():
    print("\n[1/8] Generating product master data...")

    categories = {
        "HHE": {
            "name": "Household Essentials",
            "margin_range": (0.12, 0.22),
            "weight_range": (0.3, 2.5),
            "price_range":  (2.50, 18.00),
            "shelf_life":   None,
            "products": [
                "Premium Kitchen Roll 6-Pack", "Aluminium Foil 30m Roll",
                "Cling Film 100m", "Bin Bags 40L 50-Pack", "Washing Up Liquid 500ml",
                "Dishwasher Tablets 60-Pack", "Kitchen Cleaner Spray 750ml",
                "Toilet Cleaner 750ml", "Bathroom Cleaner 500ml",
                "Multi-Surface Wipes 80-Pack", "Sponge Scourers 10-Pack",
                "Paper Towels 12-Roll", "Rubber Gloves Medium Pair",
                "Oven Cleaner 300ml", "Drain Unblocker 500ml"
            ]
        },
        "PCA": {
            "name": "Personal Care",
            "margin_range": (0.25, 0.45),
            "weight_range": (0.1, 0.8),
            "price_range":  (3.00, 22.00),
            "shelf_life":   730,
            "products": [
                "Moisturising Hand Cream 100ml", "Daily Shampoo 400ml",
                "Conditioner 400ml", "Body Lotion 250ml",
                "Shower Gel 500ml", "Deodorant Roll-On 50ml",
                "Facial Cleanser 150ml", "Lip Balm SPF15",
                "Hand Sanitiser 500ml", "Toothpaste Whitening 100ml",
                "Mouthwash Fresh Mint 500ml", "Cotton Buds 200-Pack"
            ]
        },
        "FBV": {
            "name": "Food and Beverage",
            "margin_range": (0.15, 0.30),
            "weight_range": (0.2, 2.0),
            "price_range":  (1.50, 12.00),
            "shelf_life":   365,
            "products": [
                "Premium Ground Coffee 250g", "English Breakfast Tea 80-Pack",
                "Instant Hot Chocolate 400g", "Organic Honey 340g",
                "Extra Virgin Olive Oil 500ml", "Apple Cider Vinegar 500ml",
                "Protein Granola 500g", "Mixed Nuts 200g",
                "Herbal Tea Variety 40-Pack", "Sparkling Water 12x500ml"
            ]
        },
        "SGF": {
            "name": "Seasonal and Gifting",
            "margin_range": (0.35, 0.55),
            "weight_range": (0.2, 1.5),
            "price_range":  (8.00, 45.00),
            "shelf_life":   None,
            "products": [
                "Luxury Bath Gift Set", "Premium Scented Candle Set",
                "Artisan Chocolate Selection Box", "Spa Pamper Set",
                "Aromatherapy Diffuser Kit", "Premium Notebook and Pen Set",
                "Personalised Mug Gift Box", "Festive Reed Diffuser"
            ]
        },
        "CLN": {
            "name": "Cleaning Products",
            "margin_range": (0.10, 0.20),
            "weight_range": (0.5, 5.0),
            "price_range":  (2.00, 14.00),
            "shelf_life":   None,
            "products": [
                "Professional Floor Cleaner 5L", "Industrial Degreaser 2L",
                "Antibacterial Surface Spray 1L", "Laundry Detergent 2.5kg",
                "Fabric Softener 1.5L"
            ]
        }
    }

    rows           = []
    product_counter = 1
    abc_assignment = []

    for cat_code, cat_data in categories.items():
        for product_name in cat_data["products"]:
            pid        = "PRD-{:05d}".format(product_counter)
            unit_price = round(np.random.uniform(*cat_data["price_range"]), 2)
            margin     = np.random.uniform(*cat_data["margin_range"])
            unit_cost  = round(unit_price * (1 - margin), 2)
            weight     = round(np.random.uniform(*cat_data["weight_range"]), 3)
            min_order  = random.choice([6, 12, 24, 48, 100])

            rows.append({
                "product_id":       pid,
                "product_name":     product_name,
                "category_code":    cat_code,
                "category_name":    cat_data["name"],
                "unit_cost_gbp":    unit_cost,
                "unit_price_gbp":   unit_price,
                "gross_margin_pct": round(margin * 100, 1),
                "weight_kg":        weight,
                "min_order_qty":    min_order,
                "shelf_life_days":  cat_data["shelf_life"],
                "is_active":        True
            })
            abc_assignment.append((pid, unit_price * 500))
            product_counter += 1

    df = pd.DataFrame(rows)

    # ABC Classification - Fixed-count rule per business spec
    # A = top 10 products (20%), B = next 15 (30%), C = remaining 25 (50%)
    abc_assignment.sort(key=lambda x: -x[1])
    abc_map = {}
    for i, (pid, rev) in enumerate(abc_assignment):
        if i < 10:
            abc_map[pid] = "A"
        elif i < 25:
            abc_map[pid] = "B"
        else:
            abc_map[pid] = "C"

    df["abc_class"]            = df["product_id"].map(abc_map)
    df["service_level_target"] = df["abc_class"].map({"A": 0.95, "B": 0.90, "C": 0.85})

    print("    OK {} products | ABC: A:{} B:{} C:{}".format(
        len(df),
        (df.abc_class=="A").sum(),
        (df.abc_class=="B").sum(),
        (df.abc_class=="C").sum()
    ))
    return df


def generate_suppliers():
    print("\n[2/8] Generating supplier master data...")

    data = [
        ("SUP-001","BritGoods Ltd",      "United Kingdom","DOMESTIC",        "ROAD", None,  3,  7,  4.5, 1.0, "normal",    0.02, 0.96, 30),
        ("SUP-002","EuroFast GmbH",      "Germany",       "EUROPEAN",        "ROAD", "RAIL",7,  12,  9.0, 1.5, "normal",    0.05, 0.93, 30),
        ("SUP-003","AsiaSource Co",      "China",         "INTERCONTINENTAL","SEA",  "AIR", 18, 35, 24.0, 4.5, "lognormal", 0.15, 0.78, 60),
        ("SUP-004","IndiaManufact Pvt",  "India",         "INTERCONTINENTAL","SEA",  "AIR", 20, 32, 25.0, 4.0, "lognormal", 0.13, 0.80, 60),
        ("SUP-005","NordicSupply AS",    "Sweden",        "EUROPEAN",        "ROAD", "SEA", 8,  14, 10.5, 1.8, "normal",    0.04, 0.91, 30),
        ("SUP-006","MedTrade SRL",       "Italy",         "EUROPEAN",        "ROAD", None,  10, 18, 13.0, 2.2, "normal",    0.06, 0.85, 60),
        ("SUP-007","USBrands Inc",       "United States", "INTERCONTINENTAL","AIR",  "SEA", 14, 28, 19.0, 4.0, "lognormal", 0.12, 0.76, 90),
        ("SUP-008","LocalPack Ltd",      "United Kingdom","DOMESTIC",        "ROAD", None,  2,  5,  3.0,  0.8, "normal",    0.01, 0.98, 14),
    ]

    cols = [
        "supplier_id","supplier_name","country_of_origin","region",
        "primary_transport","secondary_transport",
        "lead_time_min_days","lead_time_max_days","lead_time_avg_days",
        "lead_time_std_days","lead_time_distribution","spike_probability",
        "reliability_score","payment_terms_days"
    ]

    df = pd.DataFrame(data, columns=cols)
    df["is_active"] = True
    print("    OK {} suppliers | Regions: {}".format(len(df), df.region.value_counts().to_dict()))
    return df


def generate_warehouses():
    print("\n[3/8] Generating warehouse master data...")
    data = [
        ("WH-001","Coventry DC",   "Coventry",   "PRIMARY_DC",    2000, 18000, 52.4068, -1.5197),
        ("WH-002","Manchester Hub","Manchester",  "REGIONAL_HUB",   800,  7500, 53.4808, -2.2426),
        ("WH-003","Bristol Hub",   "Bristol",     "REGIONAL_HUB",   600,  6000, 51.4545, -2.5879),
    ]
    df = pd.DataFrame(data, columns=[
        "warehouse_id","warehouse_name","location","type",
        "capacity_pallets","monthly_cost_gbp","latitude","longitude"
    ])
    df["is_active"] = True
    print("    OK {} warehouses".format(len(df)))
    return df


def generate_transport_modes():
    print("\n[4/8] Generating transport mode reference data...")
    data = [
        ("ROAD","Road (HGV)",      0.100, 1.0,  80,  "DOMESTIC,EUROPEAN"),
        ("RAIL","Rail (Freight)",  0.028, 0.7,  60,  "EUROPEAN"),
        ("SEA", "Sea (Container)", 0.016, 0.4,  35,  "EUROPEAN,INTERCONTINENTAL"),
        ("AIR", "Air Freight",     0.602, 8.5,  800, "INTERCONTINENTAL"),
    ]
    df = pd.DataFrame(data, columns=[
        "mode_code","mode_name","kg_co2e_per_tonne_km",
        "relative_cost_index","avg_speed_kmh","suitable_for_regions"
    ])
    df["defra_source"] = "DEFRA GHG Conversion Factors 2025"
    print("    OK {} transport modes with DEFRA carbon factors".format(len(df)))
    return df


def generate_supplier_product_links(products_df, suppliers_df):
    print("\n[5/8] Generating supplier-product relationships...")

    cat_supplier_map = {
        "HHE": ["SUP-001","SUP-008","SUP-002","SUP-006"],
        "PCA": ["SUP-003","SUP-004","SUP-002","SUP-005"],
        "FBV": ["SUP-006","SUP-002","SUP-005","SUP-001"],
        "SGF": ["SUP-003","SUP-004","SUP-007","SUP-006"],
        "CLN": ["SUP-001","SUP-008","SUP-002"],
    }

    rows = []
    for _, product in products_df.iterrows():
        pool    = cat_supplier_map[product["category_code"]]
        primary = random.choice(pool)
        rows.append({"product_id": product["product_id"], "supplier_id": primary, "is_primary": True})
        if random.random() < 0.40:
            secondary_pool = [s for s in pool if s != primary]
            if secondary_pool:
                rows.append({
                    "product_id": product["product_id"],
                    "supplier_id": random.choice(secondary_pool),
                    "is_primary": False
                })

    df = pd.DataFrame(rows)
    print("    OK {} links | {} secondary suppliers".format(len(df), (df.is_primary == False).sum()))
    return df


# =============================================================================
# LAYER 2 - TRANSACTIONAL DATA
# =============================================================================

def sample_lead_time(supplier_row):
    lt_avg  = supplier_row["lead_time_avg_days"]
    lt_std  = supplier_row["lead_time_std_days"]
    lt_min  = int(supplier_row["lead_time_min_days"])
    lt_max  = int(supplier_row["lead_time_max_days"])
    dist    = supplier_row["lead_time_distribution"]
    spike_p = supplier_row["spike_probability"]

    if random.random() < spike_p:
        base = lt_avg * np.random.uniform(1.40, 1.80)
        lt   = int(np.clip(base + np.random.normal(0, lt_std), lt_min, lt_max * 1.5))
    elif dist == "lognormal":
        sigma = lt_std / lt_avg
        mu    = np.log(lt_avg) - 0.5 * sigma ** 2
        lt    = int(np.clip(np.random.lognormal(mu, sigma), lt_min, lt_max))
    else:
        lt    = int(np.clip(np.random.normal(lt_avg, lt_std), lt_min, lt_max))

    return max(lt_min, lt)


def generate_purchase_orders(products_df, suppliers_df, sup_prod_df):
    print("\n[6/8] Generating purchase orders and shipments...")

    primary_links = sup_prod_df[sup_prod_df["is_primary"] == True].copy()
    prod_sup = (
        products_df
        .merge(primary_links[["product_id","supplier_id"]], on="product_id")
        .merge(suppliers_df, on="supplier_id")
    )

    all_orders    = []
    order_counter = 1
    order_cycle   = {"A": 30, "B": 45, "C": 60}
    abc_scale     = {"A": 1.8, "B": 1.0, "C": 0.4}

    for _, row in prod_sup.iterrows():
        pid = row["product_id"]
        sid = row["supplier_id"]
        abc = row["abc_class"]
        moq = row["min_order_qty"]

        current_date    = SIM_START
        next_order_date = SIM_START + timedelta(days=random.randint(0, 30))

        while current_date <= SIM_END:
            if current_date >= next_order_date:
                cycle       = order_cycle[abc]
                avg_daily   = (50 / row["unit_price_gbp"]) * abc_scale[abc]
                qty_needed  = int(avg_daily * cycle * SEASONAL_MULTIPLIERS[current_date.month])
                qty_ordered = max(moq, round(qty_needed / moq) * moq)

                lt_days = sample_lead_time(row)

                sec_transport = row["secondary_transport"]
                use_secondary = (
                    pd.notna(sec_transport) and
                    lt_days > row["lead_time_max_days"] * 0.85 and
                    abc == "A" and
                    random.random() < 0.30
                )
                transport_used = sec_transport if use_secondary else row["primary_transport"]

                order_date   = current_date
                expected_del = order_date + timedelta(days=lt_days)
                actual_del   = expected_del + timedelta(days=random.randint(-1, 3))
                actual_cost  = round(row["unit_cost_gbp"] * np.random.normal(1.0, 0.02), 2)

                status = "DELIVERED" if actual_del <= datetime(2025, 12, 31) else "IN_TRANSIT"

                all_orders.append({
                    "order_id":              "PO-{:06d}".format(order_counter),
                    "product_id":            pid,
                    "supplier_id":           sid,
                    "warehouse_id":          random.choice(["WH-001","WH-002","WH-003"]),
                    "quantity_ordered":       qty_ordered,
                    "unit_cost_gbp":          actual_cost,
                    "total_cost_gbp":         round(qty_ordered * actual_cost, 2),
                    "order_date":             order_date.strftime("%Y-%m-%d"),
                    "expected_delivery_date": expected_del.strftime("%Y-%m-%d"),
                    "actual_delivery_date":   actual_del.strftime("%Y-%m-%d"),
                    "lead_time_days":         lt_days,
                    "transport_mode":         transport_used,
                    "weight_kg_total":        round(qty_ordered * row["weight_kg"], 2),
                    "is_urgent_order":        use_secondary,
                    "order_status":           status,
                })
                order_counter  += 1
                next_order_date = current_date + timedelta(
                    days=max(7, cycle + random.randint(-5, 5))
                )

            current_date += timedelta(days=1)

    df = pd.DataFrame(all_orders)
    print("    OK {:,} purchase orders | Total value: GBP {:,.0f}".format(
        len(df), df["total_cost_gbp"].sum()
    ))
    print("    OK Urgent orders: {}".format(df["is_urgent_order"].sum()))
    return df


def generate_inventory_snapshots(products_df, suppliers_df, sup_prod_df, orders_df):
    print("\n[7/8] Generating inventory snapshots...")

    primary_links = sup_prod_df[sup_prod_df["is_primary"] == True]
    prod_sup      = products_df.merge(
        primary_links[["product_id","supplier_id"]], on="product_id"
    )
    abc_scale = {"A": 1.8, "B": 1.0, "C": 0.4}
    snapshots = []

    for snap_date in pd.date_range(SIM_START, SIM_END, freq="MS"):
        snap_str = snap_date.strftime("%Y-%m-%d")

        for _, prow in prod_sup.iterrows():
            pid = prow["product_id"]
            abc = prow["abc_class"]

            delivered = orders_df[
                (orders_df["product_id"] == pid) &
                (orders_df["actual_delivery_date"] <= snap_str) &
                (orders_df["order_status"] == "DELIVERED")
            ]["quantity_ordered"].sum()

            avg_daily    = (50 / prow["unit_price_gbp"]) * abc_scale[abc]
            days_elapsed = (snap_date - SIM_START).days
            seas_list    = [
                SEASONAL_MULTIPLIERS[(SIM_START + timedelta(d)).month]
                for d in range(days_elapsed + 1)
            ]
            seas_avg     = float(np.mean(seas_list))
            cum_demand   = int(avg_daily * days_elapsed * seas_avg * np.random.normal(1.0, 0.08))

            initial_stock = int(avg_daily * 60)
            stock_on_hand = max(0, initial_stock + int(delivered) - cum_demand)
            avg_daily_now = avg_daily * SEASONAL_MULTIPLIERS[snap_date.month]
            cover_days    = stock_on_hand / max(avg_daily_now, 0.1)

            is_slow_mover = bool(abc == "C" and cover_days > 90)
            is_stock_out  = bool(stock_on_hand == 0)
            is_at_risk    = bool(cover_days < 14 and abc == "A" and not is_stock_out)

            # Simulate 7% A-class stock-out problem in peak months
            if abc == "A" and snap_date.month in [11, 12] and random.random() < 0.08:
                is_stock_out  = True
                stock_on_hand = 0

            snapshots.append({
                "snapshot_date":    snap_str,
                "product_id":       pid,
                "warehouse_id":     random.choice(["WH-001","WH-002","WH-003"]),
                "stock_on_hand":    stock_on_hand,
                "stock_cover_days": round(cover_days, 1),
                "avg_daily_demand": round(avg_daily_now, 2),
                "is_stock_out":     is_stock_out,
                "is_slow_mover":    is_slow_mover,
                "is_at_risk":       is_at_risk,
                "stock_value_gbp":  round(stock_on_hand * prow["unit_cost_gbp"], 2),
                "abc_class":        abc,
            })

    df = pd.DataFrame(snapshots)
    print("    OK {:,} snapshots | Stock-outs: {} | Slow-movers: {}".format(
        len(df), df["is_stock_out"].sum(), df["is_slow_mover"].sum()
    ))
    return df


# =============================================================================
# LAYER 3 - DIRTY INGEST CSVs
# =============================================================================

def generate_dirty_supplier_csvs(orders_df, products_df, suppliers_df):
    print("\n[8/8] Generating dirty supplier ingest files...")

    name_variants = {
        "AsiaSource Co":     ["ASIASOURCE","Asia Source Co.","AsiaSource","ASIA SOURCE CO"],
        "IndiaManufact Pvt": ["INDIAMANUFACT","India Manufact Pvt Ltd","IndiaManufact"],
        "USBrands Inc":      ["US Brands Inc.","USBRANDS","U.S. Brands Inc"],
        "EuroFast GmbH":     ["EUROFAST","Euro Fast GmbH","Eurofast GMBH"],
        "MedTrade SRL":      ["MEDTRADE","Med Trade S.R.L.","MedTrade Srl"],
        "NordicSupply AS":   ["NORDICSUPPLY","Nordic Supply A/S","NordicSupply"],
        "BritGoods Ltd":     ["BRITGOODS","Brit Goods Limited","BritGoods"],
        "LocalPack Ltd":     ["LOCALPACK","Local Pack Ltd.","LocalPack"],
    }

    date_fmts = [
        lambda d: d.strftime("%d/%m/%Y"),
        lambda d: d.strftime("%d/%m/%y"),
        lambda d: d.strftime("%d-%b-%y"),
        lambda d: d.strftime("%m/%d/%Y"),
    ]

    full = (
        orders_df
        .merge(suppliers_df[["supplier_id","supplier_name"]], on="supplier_id")
        .merge(products_df[["product_id","product_name","weight_kg"]], on="product_id")
    )

    rows      = []
    error_log = []
    clean_n   = 0
    dirty_n   = 0
    seen_ids  = set()

    for _, row in full.iterrows():
        rec = {
            "order_id":          row["order_id"],
            "supplier_name":     row["supplier_name"],
            "supplier_id":       row["supplier_id"],
            "product_id":        row["product_id"],
            "product_name":      row["product_name"],
            "quantity":          row["quantity_ordered"],
            "unit_cost":         row["unit_cost_gbp"],
            "order_date":        row["order_date"],
            "expected_delivery": row["expected_delivery_date"],
            "actual_delivery":   row["actual_delivery_date"],
            "transport_mode":    row["transport_mode"],
            "weight_kg_total":   row["weight_kg_total"],
        }

        roll       = random.random()
        error_type = None

        if roll < 0.04:
            variants = name_variants.get(row["supplier_name"], [])
            if variants:
                rec["supplier_name"] = random.choice(variants)
                error_type = "SUPPLIER_NAME_MISMATCH"

        elif roll < 0.06:
            try:
                d = datetime.strptime(str(row["order_date"]), "%Y-%m-%d")
                rec["order_date"] = random.choice(date_fmts)(d)
                error_type = "DATE_FORMAT_MISMATCH"
            except Exception:
                pass

        elif roll < 0.08:
            rec["transport_mode"] = ""
            error_type = "MISSING_TRANSPORT_MODE"

        elif roll < 0.09:
            rec["quantity"] = -abs(rec["quantity"])
            error_type = "NEGATIVE_QUANTITY"

        elif roll < 0.10:
            rec["unit_cost"] = round(rec["unit_cost"] * 10, 2)
            error_type = "COST_OUTLIER"

        elif roll < 0.11:
            if row["order_id"] not in seen_ids:
                seen_ids.add(row["order_id"])
                rows.append(dict(rec))
                rec["quantity"] = max(1, rec["quantity"] + random.randint(-2, 2))
                error_type = "DUPLICATE_ORDER_ID"

        elif roll < 0.12:
            rec["product_id"] = "PRD-{:05d}".format(random.randint(90000, 99999))
            error_type = "UNKNOWN_PRODUCT_ID"

        if error_type:
            dirty_n += 1
            error_log.append({"order_id": rec["order_id"], "error_type": error_type})
        else:
            clean_n += 1

        rows.append(rec)

    dirty_df     = pd.DataFrame(rows)
    error_log_df = pd.DataFrame(error_log)

    # Save per-supplier files
    for _, sup in suppliers_df.iterrows():
        sub = dirty_df[dirty_df["supplier_id"] == sup["supplier_id"]]
        if not sub.empty:
            safe_name = sup["supplier_name"].replace(" ","_").replace(".","").replace("/","")
            fname = "{}_{}_feed.csv".format(sup["supplier_id"], safe_name)
            sub.drop(columns=["supplier_id"]).to_csv(
                os.path.join(RAW_DIR, fname), index=False
            )

    dirty_df.to_csv(
        os.path.join(RAW_DIR, "ALL_SUPPLIERS_combined_raw.csv"), index=False
    )
    error_log_df.to_csv(
        os.path.join(RAW_DIR, "_error_manifest.csv"), index=False
    )

    total   = clean_n + dirty_n
    err_pct = round(dirty_n / total * 100, 1) if total else 0
    print("    OK {:,} records | Clean: {:,} | Dirty: {:,} ({:.1f}%)".format(
        total, clean_n, dirty_n, err_pct
    ))
    print("    OK {} supplier files + combined file saved".format(len(suppliers_df)))
    print("    OK Error manifest: {} entries".format(len(error_log_df)))
    return dirty_df, error_log_df


def generate_reference_data():
    carbon = pd.DataFrame([
        ("ROAD","Road HGV",       0.100,"DEFRA GHG Conversion Factors 2025"),
        ("RAIL","Rail Freight",   0.028,"DEFRA GHG Conversion Factors 2025"),
        ("SEA", "Sea Container",  0.016,"DEFRA GHG Conversion Factors 2025"),
        ("AIR", "Air Freight",    0.602,"DEFRA GHG Conversion Factors 2025"),
    ], columns=["mode_code","mode_name","kg_co2e_per_tonne_km","source"])

    distances = pd.DataFrame([
        ("China",         "UK","SEA",19500),
        ("China",         "UK","AIR", 9200),
        ("India",         "UK","SEA",11000),
        ("India",         "UK","AIR", 6700),
        ("United States", "UK","AIR", 5500),
        ("United States", "UK","SEA", 6800),
        ("Germany",       "UK","ROAD",1100),
        ("Sweden",        "UK","ROAD",1400),
        ("Italy",         "UK","ROAD",1800),
        ("United Kingdom","UK","ROAD", 250),
    ], columns=["origin_country","destination","transport_mode","distance_km"])

    carbon.to_csv(
        os.path.join(REFERENCE_DIR, "defra_carbon_factors.csv"), index=False
    )
    distances.to_csv(
        os.path.join(REFERENCE_DIR, "shipping_distance_matrix.csv"), index=False
    )


def save_all(products, suppliers, warehouses, transport, sup_prod, orders, inventory):
    print("\n-- Saving all datasets --")
    files = {
        "dim_product.csv":              products,
        "dim_supplier.csv":             suppliers,
        "dim_warehouse.csv":            warehouses,
        "dim_transport_mode.csv":       transport,
        "bridge_supplier_product.csv":  sup_prod,
        "fact_purchase_orders.csv":     orders,
        "fact_inventory_snapshots.csv": inventory,
    }
    for fname, df in files.items():
        path = os.path.join(PROCESSED_DIR, fname)
        df.to_csv(path, index=False)
        print("    OK  {:<45}  {:>7,} rows".format(fname, len(df)))

    data_dict = {
        name: {"rows": len(df), "columns": list(df.columns)}
        for name, df in files.items()
    }
    with open(os.path.join(PROCESSED_DIR, "_data_dictionary.json"), "w") as f:
        json.dump(data_dict, f, indent=2)
    print("    OK  _data_dictionary.json")


def print_summary(products, orders, inventory):
    print("\n" + "=" * 65)
    print("  GENERATION COMPLETE")
    print("=" * 65)
    print("")
    print("  MASTER DATA")
    print("  Products:        {:>5,}  (A:{} B:{} C:{})".format(
        len(products),
        (products.abc_class=="A").sum(),
        (products.abc_class=="B").sum(),
        (products.abc_class=="C").sum()
    ))
    print("  Suppliers:       {:>5,}  (Domestic:2 European:3 Intercontinental:3)".format(8))
    print("  Warehouses:      {:>5,}  (Coventry, Manchester, Bristol)".format(3))
    print("  Transport Modes: {:>5,}  (Road, Rail, Sea, Air + DEFRA factors)".format(4))
    print("")
    print("  TRANSACTIONAL DATA  Jan 2024 - Dec 2025")
    print("  Purchase Orders: {:>7,}".format(len(orders)))
    print("  Total Value:     GBP {:>10,.0f}".format(orders["total_cost_gbp"].sum()))
    print("  Urgent Orders:   {:>7,}  (secondary transport)".format(orders["is_urgent_order"].sum()))
    print("  Inventory Snaps: {:>7,}  (monthly per product)".format(len(inventory)))
    print("")
    print("  PROBLEM INDICATORS  Pre-System Baseline")
    print("  Slow-mover events:{:>6,}".format(inventory["is_slow_mover"].sum()))
    print("  Stock-out events: {:>6,}".format(inventory["is_stock_out"].sum()))
    print("  At-risk events:   {:>6,}  (A-class low stock)".format(inventory["is_at_risk"].sum()))
    print("")
    print("  RANDOM SEED: {}  (reproducible)".format(RANDOM_SEED))
    print("  CARBON DATA: DEFRA GHG Conversion Factors 2025")
    print("")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":

    products   = generate_products()
    suppliers  = generate_suppliers()
    warehouses = generate_warehouses()
    transport  = generate_transport_modes()
    sup_prod   = generate_supplier_product_links(products, suppliers)

    orders    = generate_purchase_orders(products, suppliers, sup_prod)
    inventory = generate_inventory_snapshots(products, suppliers, sup_prod, orders)

    dirty_df, error_log = generate_dirty_supplier_csvs(orders, products, suppliers)

    generate_reference_data()

    save_all(products, suppliers, warehouses, transport, sup_prod, orders, inventory)

    print_summary(products, orders, inventory)

    print("  Files saved to:")
    print("    " + PROCESSED_DIR)
    print("    " + RAW_DIR)
    print("    " + REFERENCE_DIR)
    print("")
    print("  Phase 1 Complete. Ready for Phase 2 - SQL Architecture.")
    print("=" * 65)
