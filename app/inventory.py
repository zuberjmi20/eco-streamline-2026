"""
Inventory Dashboard — Stock levels, ROP alerts, ABC analysis, slow-movers
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_loader import load_all, fmt_gbp, fmt_pct, ABC_COLOURS

data     = load_all()
inv      = data["inventory"]
products = data["products"]
mc       = data["monte_carlo"]
green    = data["green_rop"]

st.markdown("# 📊 Inventory Dashboard")
st.markdown("Stock positions, reorder alerts, and ABC analysis across all 50 products.")
st.markdown("---")

# ── Filters ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    months = sorted(inv["snapshot_date"].unique()) if not inv.empty else []
    sel_month = st.selectbox("Snapshot Month", months, index=len(months) - 1 if months else 0)
with col_f2:
    abc_filter = st.multiselect("ABC Class", ["A", "B", "C"], default=["A", "B", "C"])
with col_f3:
    status_filter = st.multiselect(
        "Status Filter",
        ["All", "Stock-Out", "At Risk", "Slow Mover"],
        default=["All"]
    )

# Filter inventory to selected month
snap = inv[inv["snapshot_date"] == sel_month].copy() if not inv.empty else pd.DataFrame()
if not snap.empty and abc_filter:
    snap = snap[snap["abc_class"].isin(abc_filter)]
if not snap.empty and "All" not in status_filter:
    mask = pd.Series([False] * len(snap), index=snap.index)
    if "Stock-Out"  in status_filter: mask |= snap["is_stock_out"]
    if "At Risk"    in status_filter: mask |= snap["is_at_risk"]
    if "Slow Mover" in status_filter: mask |= snap["is_slow_mover"]
    snap = snap[mask]

# Merge product names
if not snap.empty and not products.empty:
    snap = snap.merge(
        products[["product_id", "product_name", "unit_price_gbp",
                  "unit_cost_gbp", "category_name"]],
        on="product_id", how="left"
    )

st.markdown("---")

# ── KPI Row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

total_stock_val  = snap["stock_value_gbp"].sum()      if not snap.empty else 0
stockout_count   = snap["is_stock_out"].sum()          if not snap.empty else 0
at_risk_count    = snap["is_at_risk"].sum()            if not snap.empty else 0
slow_mover_val   = snap[snap["is_slow_mover"] == True]["stock_value_gbp"].sum() if not snap.empty else 0
total_products   = len(snap)

with k1:
    st.metric("Total Stock Value",   fmt_gbp(total_stock_val))
with k2:
    st.metric("Products Tracked",    str(total_products))
with k3:
    st.metric("Stock-Outs",          str(int(stockout_count)),
              delta="A-class critical" if stockout_count > 0 else "None",
              delta_color="inverse" if stockout_count > 0 else "normal")
with k4:
    st.metric("At Risk (A-class)",   str(int(at_risk_count)),
              delta="<14 days cover" if at_risk_count > 0 else "All healthy",
              delta_color="inverse" if at_risk_count > 0 else "normal")
with k5:
    st.metric("Slow-Mover Value",    fmt_gbp(slow_mover_val),
              delta="Target: reduce 15%" if slow_mover_val > 0 else "",
              delta_color="inverse")

st.markdown("---")

# ── Charts Row 1 ──────────────────────────────────────────────────────────────
ch1, ch2 = st.columns(2)

with ch1:
    st.markdown("#### Stock Value by ABC Class")
    if not snap.empty:
        abc_val = snap.groupby("abc_class")["stock_value_gbp"].sum().reset_index()
        fig = px.bar(
            abc_val, x="abc_class", y="stock_value_gbp",
            color="abc_class",
            color_discrete_map=ABC_COLOURS,
            labels={"abc_class": "ABC Class", "stock_value_gbp": "Stock Value (£)"},
            text_auto=".2s"
        )
        fig.update_layout(
            plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
            font_color="#e2e8f0", showlegend=False,
            margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

with ch2:
    st.markdown("#### Stock Cover Distribution")
    if not snap.empty:
        fig = px.histogram(
            snap, x="stock_cover_days",
            color="abc_class",
            color_discrete_map=ABC_COLOURS,
            nbins=30,
            labels={"stock_cover_days": "Days of Cover", "count": "Products"},
            barmode="overlay",
            opacity=0.75
        )
        fig.add_vline(x=90, line_dash="dash", line_color="#dc2626",
                      annotation_text="90-day slow-mover threshold")
        fig.add_vline(x=14, line_dash="dash", line_color="#f97316",
                      annotation_text="14-day risk threshold")
        fig.update_layout(
            plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
            font_color="#e2e8f0", margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Monte Carlo ROP Comparison ────────────────────────────────────────────────
st.markdown("#### 🎯 Monte Carlo ROP — Current vs Optimised")
if not mc.empty:
    mc_disp = mc[mc["abc_class"].isin(abc_filter)].copy()
    mc_disp = mc_disp.merge(
        products[["product_id", "product_name"]], on="product_id", how="left"
    ).head(20)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Current ROP",
        x=mc_disp["product_name"],
        y=mc_disp["rop_current"],
        marker_color="#64748b",
        opacity=0.7
    ))
    fig.add_trace(go.Bar(
        name="Optimised ROP",
        x=mc_disp["product_name"],
        y=mc_disp["rop_optimised"],
        marker_color="#4ade80",
        opacity=0.9
    ))
    fig.update_layout(
        barmode="group",
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font_color="#e2e8f0",
        legend=dict(bgcolor="#1e2130"),
        xaxis_tickangle=-45,
        margin=dict(t=20, b=80),
        height=380
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Showing first 20 products. Optimised ROP accounts for lead time volatility and demand seasonality.")

st.markdown("---")

# ── Slow-Mover Alert Table ────────────────────────────────────────────────────
st.markdown("#### 🐢 Slow-Mover Alert — Excess Capital Locked")

if not snap.empty:
    slow = snap[snap["is_slow_mover"] == True].copy()
    if slow.empty:
        st.success("No slow-movers detected in selected period.")
    else:
        slow_disp = slow[[
            "product_name", "abc_class", "category_name",
            "stock_on_hand", "stock_cover_days",
            "avg_daily_demand", "stock_value_gbp"
        ]].copy()
        slow_disp.columns = [
            "Product", "Class", "Category",
            "Stock On Hand", "Cover (Days)",
            "Avg Daily Demand", "Stock Value (£)"
        ]
        slow_disp["Stock Value (£)"] = slow_disp["Stock Value (£)"].apply(
            lambda x: fmt_gbp(x)
        )
        slow_disp["Cover (Days)"] = slow_disp["Cover (Days)"].apply(
            lambda x: "{:.0f}".format(x)
        )
        slow_disp["Avg Daily Demand"] = slow_disp["Avg Daily Demand"].apply(
            lambda x: "{:.1f}".format(x)
        )
        slow_disp = slow_disp.sort_values("Cover (Days)", ascending=False)
        st.dataframe(slow_disp, use_container_width=True, hide_index=True)
        st.info(
            "💡 **Action:** Reduce replenishment orders for C-class items with "
            ">90 days cover. Target: release £42,000 (15% of £280,000 excess)."
        )

# ── Green-ROP Decisions ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 🚦 Green-ROP Transport Decisions")

if not green.empty:
    g_disp = green[green["abc_class"].isin(abc_filter)][[
        "product_name", "abc_class", "supplier_name",
        "recommended_mode", "rop_optimised", "recommended_order_qty",
        "green_decision_made", "carbon_saving_vs_air_kg",
        "requires_human_review"
    ]].copy()
    g_disp.columns = [
        "Product", "Class", "Supplier",
        "Mode", "ROP", "Order Qty",
        "Green Choice", "CO₂ Saved (kg)", "Needs Review"
    ]
    g_disp["CO₂ Saved (kg)"] = g_disp["CO₂ Saved (kg)"].apply(
        lambda x: "{:.1f}".format(x)
    )
    st.dataframe(g_disp, use_container_width=True, hide_index=True)
    review_count = green["requires_human_review"].sum()
    if review_count > 0:
        st.warning(
            "⚠️ {} product(s) require human review — "
            "no transport mode meets service level target.".format(int(review_count))
        )
