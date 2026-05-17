"""
Home page — project overview and headline KPIs
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_loader import load_all, fmt_gbp, fmt_pct, fmt_co2, ABC_COLOURS

data = load_all()
inv  = data["inventory"]
orders = data["orders"]
carbon = data["carbon_exec"]
mc     = data["monte_carlo"]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📦 Eco-Streamline 2026")
st.markdown("### Business Transformation System — Apex Distribution UK")
st.markdown(
    "Transforming a £12M wholesale distributor from fragmented Excel workbooks "
    "to a production-grade data and analytics platform — solving three critical business failures."
)
st.markdown("---")

# ── Problem Statement ─────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 💰 Capital Deadlock")
    excess = inv[inv["is_slow_mover"] == True]["stock_value_gbp"].sum()
    st.metric(
        "Excess Stock Tied Up",
        fmt_gbp(280000),
        delta="£35k/yr storage cost",
        delta_color="inverse"
    )
    st.caption("C-class slow-movers holding capital that should be working.")

with col2:
    st.markdown("#### 📉 Revenue Leakage")
    stockout_rate = inv[inv["abc_class"] == "A"]["is_stock_out"].mean() * 100
    st.metric(
        "A-Class Stock-Out Rate",
        fmt_pct(stockout_rate),
        delta="£110k lost sales/yr",
        delta_color="inverse"
    )
    st.caption("High-margin items running out during peak demand periods.")

with col3:
    st.markdown("#### 🌱 Compliance Risk")
    total_carbon = carbon["total_carbon_tonnes_co2e"].sum() if not carbon.empty else 0
    st.metric(
        "Carbon Reporting",
        "0% Automated",
        delta="40% contract value at risk",
        delta_color="inverse"
    )
    st.caption("Tesco & John Lewis mandate Scope 3 data by Q4 2026.")

st.markdown("---")

# ── Solution Overview ─────────────────────────────────────────────────────────
st.markdown("## ✅ What This System Delivers")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("**🗄️ Data Architecture**")
    st.markdown("""
- Star Schema database (Single Source of Truth)
- ETL pipeline with 7 automated validation checks
- Transforms 12 hours of manual Excel work into seconds
    """)

with c2:
    st.markdown("**🧮 Analytics Engine**")
    st.markdown("""
- Monte Carlo simulation (10,000 runs per product)
- Green-ROP: reorder logic balancing cost + carbon
- DEFRA-compliant Scope 3 carbon calculator
    """)

with c3:
    st.markdown("**📊 Business Intelligence**")
    st.markdown("""
- CFO Dashboard: working capital + inventory KPIs
- Sustainability Portal: UK SRS Scope 3 reporting
- Scenario Planner: What-If analysis for any variable
    """)

st.markdown("---")

# ── Live Results ──────────────────────────────────────────────────────────────
st.markdown("## 📈 Live Results from Phase 1-3 Data")

r1, r2, r3, r4 = st.columns(4)

with r1:
    opt_rop  = mc["rop_optimised"].mean()  if not mc.empty else 0
    curr_rop = mc["rop_current"].mean()    if not mc.empty else 0
    st.metric("Avg Optimised ROP", "{:.0f} units".format(opt_rop),
              delta="{:+.0f} vs baseline".format(opt_rop - curr_rop))

with r2:
    curr_so  = mc["stockout_prob_current"].mean()   * 100 if not mc.empty else 0
    opt_so   = mc["stockout_prob_optimised"].mean() * 100 if not mc.empty else 0
    st.metric("Stock-Out Risk (optimised)", fmt_pct(opt_so),
              delta="{:+.1f}% vs current".format(opt_so - curr_so),
              delta_color="inverse")

with r3:
    tot_co2 = carbon["total_carbon_tonnes_co2e"].sum() if not carbon.empty else 0
    st.metric("Total Scope 3 Emissions", "{:.1f} t CO₂e".format(tot_co2),
              delta="100% now automated")

with r4:
    saved = carbon["carbon_saved_vs_air_kg"].sum() / 1000 if not carbon.empty else 0
    st.metric("CO₂ Saved vs All-Air",
              "{:.1f} t CO₂e".format(saved),
              delta="By choosing Sea/Road over Air")

st.markdown("---")

# ── ROI Target Tracker ────────────────────────────────────────────────────────
st.markdown("## 🎯 ROI Target Tracker")

targets = {
    "Excess Stock Reduction":    {"target": 15.0,  "current": 0.0,  "unit": "%",  "status": "In Progress"},
    "A-Class Stock-Out Rate":    {"target": 3.0,   "current": stockout_rate, "unit": "%", "status": "Measured"},
    "Carbon Reporting Automation":{"target": 100.0, "current": 100.0, "unit": "%", "status": "Complete"},
    "Weekly Reporting Time":     {"target": 10.0,  "current": 720.0, "unit": "min","status": "Baseline"},
}

for metric, vals in targets.items():
    col_a, col_b, col_c = st.columns([3, 1, 1])
    with col_a:
        st.markdown("**{}**".format(metric))
        if vals["unit"] == "%":
            progress = min(1.0, vals["current"] / max(vals["target"], 0.01))
        else:
            progress = min(1.0, vals["target"] / max(vals["current"], 0.01))
        st.progress(progress)
    with col_b:
        st.markdown("Target: **{} {}**".format(vals["target"], vals["unit"]))
        st.markdown("Current: **{:.1f} {}**".format(vals["current"], vals["unit"]))
    with col_c:
        colour = "#16a34a" if vals["status"] == "Complete" else "#ca8a04"
        st.markdown(
            '<span style="color:{}; font-weight:bold;">{}</span>'.format(
                colour, vals["status"]
            ),
            unsafe_allow_html=True
        )

st.markdown("---")
st.markdown("## 🗺️ System Architecture")

arch_cols = st.columns(5)
steps = [
    ("📁 Raw Data", "Dirty supplier CSVs\n~12% error rate\n8 suppliers"),
    ("🔧 ETL Pipeline", "7 validation checks\nName normalisation\nDate parsing"),
    ("🗄️ Star Schema", "5 dimensions\n3 fact tables\n4 views"),
    ("🧮 Analytics", "Monte Carlo\nGreen-ROP\nCarbon Calc"),
    ("📊 Dashboards", "CFO Summary\nSustainability\nScenario Planner"),
]

for col, (title, detail) in zip(arch_cols, steps):
    with col:
        st.markdown(
            """
            <div style="background:#1e2130; border:1px solid #2d3250;
                        border-radius:8px; padding:12px; text-align:center;">
                <div style="font-size:24px;">{}</div>
                <div style="font-weight:bold; margin:8px 0; color:#e2e8f0;">{}</div>
                <div style="font-size:12px; color:#94a3b8; white-space:pre-line;">{}</div>
            </div>
            """.format(title.split()[0], title.split(" ", 1)[1], detail),
            unsafe_allow_html=True
        )

st.markdown("---")
st.caption(
    "Data period: Jan 2024 – Dec 2025 | "
    "Carbon standard: UK SRS | DEFRA GHG Conversion Factors 2025 | "
    "Monte Carlo seed: 2026 (reproducible)"
)
