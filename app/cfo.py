"""
CFO Summary Dashboard — Working capital, inventory turnover, ROI tracking
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_loader import load_all, fmt_gbp, fmt_pct, ABC_COLOURS

data     = load_all()
inv      = data["inventory"]
orders   = data["orders"]
products = data["products"]
mc       = data["monte_carlo"]
carbon   = data["carbon_exec"]

st.markdown("# 💼 CFO Summary")
st.markdown(
    "Executive financial overview — working capital, inventory performance, "
    "and ROI tracking against project targets."
)
st.markdown("---")

# ── Headline ROI Metrics ──────────────────────────────────────────────────────
st.markdown("### 💰 Project ROI — Headline Numbers")

r1, r2, r3, r4 = st.columns(4)

with r1:
    st.markdown(
        """
        <div style="background:#1e2130; border:1px solid #16a34a;
                    border-radius:8px; padding:16px; text-align:center;">
            <div style="font-size:32px; font-weight:bold; color:#4ade80;">£42,000</div>
            <div style="color:#e2e8f0; margin-top:4px;">Working Capital Released</div>
            <div style="color:#94a3b8; font-size:12px;">15% of £280k excess stock target</div>
        </div>
        """, unsafe_allow_html=True
    )

with r2:
    st.markdown(
        """
        <div style="background:#1e2130; border:1px solid #ca8a04;
                    border-radius:8px; padding:16px; text-align:center;">
            <div style="font-size:32px; font-weight:bold; color:#fbbf24;">£110,000</div>
            <div style="color:#e2e8f0; margin-top:4px;">Lost Sales Recoverable</div>
            <div style="color:#94a3b8; font-size:12px;">7% → <3% A-class stock-out rate</div>
        </div>
        """, unsafe_allow_html=True
    )

with r3:
    st.markdown(
        """
        <div style="background:#1e2130; border:1px solid #3b82f6;
                    border-radius:8px; padding:16px; text-align:center;">
            <div style="font-size:32px; font-weight:bold; color:#60a5fa;">£35,000</div>
            <div style="color:#e2e8f0; margin-top:4px;">Storage Cost Reduction</div>
            <div style="color:#94a3b8; font-size:12px;">Annual slow-mover holding cost</div>
        </div>
        """, unsafe_allow_html=True
    )

with r4:
    st.markdown(
        """
        <div style="background:#1e2130; border:1px solid #8b5cf6;
                    border-radius:8px; padding:16px; text-align:center;">
            <div style="font-size:32px; font-weight:bold; color:#a78bfa;">£4.8M</div>
            <div style="color:#e2e8f0; margin-top:4px;">Contract Revenue Protected</div>
            <div style="color:#94a3b8; font-size:12px;">40% of £12M via Scope 3 compliance</div>
        </div>
        """, unsafe_allow_html=True
    )

st.markdown("---")

# ── Working Capital Trend ─────────────────────────────────────────────────────
st.markdown("#### 📈 Working Capital Tied Up — Monthly Trend")

if not inv.empty and not products.empty:
    inv_prod = inv.merge(
        products[["product_id", "abc_class"]],
        on="product_id", how="left"
    )
    monthly_wc = inv_prod.groupby("snapshot_date").agg(
        total_stock_value    = ("stock_value_gbp",      "sum"),
        excess_stock_value   = ("excess_stock_value_gbp","sum"),
        slow_mover_value     = ("stock_value_gbp",
                                lambda x: x[inv_prod.loc[x.index, "is_slow_mover"]].sum()),
        stockout_count       = ("is_stock_out",          "sum"),
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly_wc["snapshot_date"],
        y=monthly_wc["total_stock_value"],
        name="Total Stock Value",
        fill="tozeroy",
        line=dict(color="#3b82f6", width=2),
        fillcolor="rgba(59,130,246,0.15)"
    ))
    fig.add_trace(go.Scatter(
        x=monthly_wc["snapshot_date"],
        y=monthly_wc["slow_mover_value"],
        name="Slow-Mover Value (excess)",
        fill="tozeroy",
        line=dict(color="#dc2626", width=2),
        fillcolor="rgba(220,38,38,0.2)"
    ))
    fig.add_hline(
        y=238000,
        line_dash="dash", line_color="#16a34a",
        annotation_text="Target: £238k excess (-15%)"
    )
    fig.update_layout(
        yaxis_title="Value (£)",
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font_color="#e2e8f0",
        legend=dict(bgcolor="#1e2130"),
        margin=dict(t=20, b=60),
        height=360,
        xaxis_tickangle=-45
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Inventory Turnover ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 🔄 Inventory Turnover by ABC Class")

if not inv.empty and not orders.empty:
    ch1, ch2 = st.columns(2)

    with ch1:
        # Avg stock value per ABC class
        inv_abc = inv.groupby("abc_class").agg(
            avg_stock_value = ("stock_value_gbp", "mean"),
            total_stockouts = ("is_stock_out",    "sum"),
            total_snapshots = ("is_stock_out",    "count"),
        ).reset_index()
        inv_abc["stockout_rate"] = (
            inv_abc["total_stockouts"] / inv_abc["total_snapshots"] * 100
        ).round(1)

        fig = px.bar(
            inv_abc,
            x="abc_class",
            y="avg_stock_value",
            color="abc_class",
            color_discrete_map=ABC_COLOURS,
            labels={
                "abc_class": "ABC Class",
                "avg_stock_value": "Avg Stock Value (£)"
            },
            text_auto=".2s"
        )
        fig.update_layout(
            showlegend=False,
            plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
            font_color="#e2e8f0",
            margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        # Stock-out rate by ABC class
        fig2 = px.bar(
            inv_abc,
            x="abc_class",
            y="stockout_rate",
            color="abc_class",
            color_discrete_map=ABC_COLOURS,
            labels={
                "abc_class": "ABC Class",
                "stockout_rate": "Stock-Out Rate (%)"
            },
            text_auto=".1f"
        )
        fig2.add_hline(y=3, line_dash="dash", line_color="#16a34a",
                       annotation_text="Target: <3% (A-class)")
        fig2.add_hline(y=7, line_dash="dash", line_color="#dc2626",
                       annotation_text="Current A-class: ~7%")
        fig2.update_layout(
            showlegend=False,
            plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
            font_color="#e2e8f0",
            margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig2, use_container_width=True)

# ── Order Value Trend ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 💳 Monthly Purchase Order Value")

if not orders.empty:
    orders["order_month"] = orders["order_date"].astype(str).str[:7]
    monthly_orders = orders.groupby("order_month").agg(
        total_value    = ("total_cost_gbp",    "sum"),
        order_count    = ("order_id",          "count"),
        urgent_orders  = ("is_urgent_order",   "sum"),
    ).reset_index()

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=monthly_orders["order_month"],
        y=monthly_orders["total_value"],
        name="Order Value (£)",
        marker_color="#3b82f6",
        opacity=0.8
    ))
    fig3.add_trace(go.Scatter(
        x=monthly_orders["order_month"],
        y=monthly_orders["urgent_orders"],
        name="Urgent Orders",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color="#f97316", width=2),
        marker=dict(size=6)
    ))
    fig3.update_layout(
        yaxis=dict(title="Order Value (£)", color="#3b82f6"),
        yaxis2=dict(title="Urgent Orders", overlaying="y",
                    side="right", color="#f97316"),
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font_color="#e2e8f0",
        legend=dict(bgcolor="#1e2130"),
        margin=dict(t=20, b=60),
        height=340,
        xaxis_tickangle=-45
    )
    st.plotly_chart(fig3, use_container_width=True)
    st.caption(
        "Urgent orders (orange line) indicate reactive purchasing — "
        "using faster/more expensive transport to prevent stock-outs. "
        "Green-ROP reduces these by anticipating demand earlier."
    )

# ── Process Efficiency ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### ⏱️ Process Efficiency — Reporting Time Reduction")

eff_data = {
    "Process":      ["Data Collection", "Validation", "Inventory Report",
                     "Carbon Report",   "Supplier Reports", "Total"],
    "Before (min)": [240, 120, 180, 0, 180, 720],
    "After (min)":  [0,   0,   3,  2, 2,   7],
}
eff_df = pd.DataFrame(eff_data)
eff_df["Time Saved (min)"] = eff_df["Before (min)"] - eff_df["After (min)"]
eff_df["Reduction %"] = (
    eff_df["Time Saved (min)"] / eff_df["Before (min)"].clip(lower=1) * 100
).round(0).astype(int)

fig4 = go.Figure()
fig4.add_trace(go.Bar(
    name="Before (minutes)",
    x=eff_df["Process"],
    y=eff_df["Before (min)"],
    marker_color="#dc2626",
    opacity=0.8
))
fig4.add_trace(go.Bar(
    name="After (minutes)",
    x=eff_df["Process"],
    y=eff_df["After (min)"],
    marker_color="#16a34a",
    opacity=0.9
))
fig4.update_layout(
    barmode="group",
    yaxis_title="Minutes",
    plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
    font_color="#e2e8f0",
    legend=dict(bgcolor="#1e2130"),
    margin=dict(t=20, b=20),
    height=320
)
st.plotly_chart(fig4, use_container_width=True)

st.dataframe(
    eff_df.style.format({
        "Before (min)": "{:.0f}",
        "After (min)":  "{:.0f}",
        "Time Saved (min)": "{:.0f}",
        "Reduction %": "{}%"
    }),
    use_container_width=True, hide_index=True
)

st.success(
    "✅ **Total reporting time: 720 minutes → 7 minutes per week. "
    "A 99% reduction. "
    "That is 37 hours per month returned to the finance team.**"
)

# ── Monte Carlo Safety Stock Financial Impact ─────────────────────────────────
st.markdown("---")
st.markdown("#### 🧮 Monte Carlo — Safety Stock Financial Impact by ABC Class")

if not mc.empty and not products.empty:
    mc_prod = mc.merge(
        products[["product_id", "unit_cost_gbp"]], on="product_id", how="left"
    )
    mc_prod["holding_cost_curr_gbp"] = mc_prod["annual_holding_cost_curr"]
    mc_prod["holding_cost_opt_gbp"]  = mc_prod["annual_holding_cost_opt"]
    mc_prod["holding_saving_gbp"]    = (
        mc_prod["holding_cost_curr_gbp"] - mc_prod["holding_cost_opt_gbp"]
    )

    abc_mc = mc_prod.groupby("abc_class").agg(
        products             = ("product_id",          "count"),
        avg_current_ss       = ("safety_stock_current", "mean"),
        avg_optimised_ss     = ("safety_stock_optimised","mean"),
        total_holding_saving = ("holding_saving_gbp",   "sum"),
        avg_stockout_curr    = ("stockout_prob_current", "mean"),
        avg_stockout_opt     = ("stockout_prob_optimised","mean"),
    ).reset_index()

    abc_mc["avg_stockout_curr_pct"] = (abc_mc["avg_stockout_curr"] * 100).round(1)
    abc_mc["avg_stockout_opt_pct"]  = (abc_mc["avg_stockout_opt"]  * 100).round(1)
    abc_mc["total_holding_saving"]  = abc_mc["total_holding_saving"].apply(fmt_gbp)

    abc_mc.columns = [
        "Class", "Products", "Avg SS (Current)", "Avg SS (Optimised)",
        "Annual Holding Saved", "Stockout% Before", "Stockout% After"
    ]
    st.dataframe(abc_mc, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption(
    "All financial figures are projections based on synthetic data modelling "
    "the Apex Distribution UK business scenario. "
    "Actual results will depend on live implementation and data quality."
)
