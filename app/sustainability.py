"""
Sustainability Portal — UK SRS Scope 3 Category 4 Carbon Report
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_loader import load_all, fmt_gbp, fmt_co2, MODE_COLOURS

data        = load_all()
carbon_exec = data["carbon_exec"]
carbon_sup  = data["carbon_supplier"]
carbon_prod = data["carbon_product"]
srs_export  = data["srs_export"]
transport   = data["transport"]

DEFRA_FACTORS = {"ROAD": 0.100, "RAIL": 0.028, "SEA": 0.016, "AIR": 0.602}

st.markdown("# 🌱 Sustainability Portal")
st.markdown(
    "UK SRS-aligned Scope 3 Category 4 reporting — "
    "automated carbon tracking per shipment, supplier, and month."
)
st.markdown("---")

# ── Headline KPIs ─────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

total_co2   = carbon_exec["total_carbon_tonnes_co2e"].sum() if not carbon_exec.empty else 0
saved_vs_air= carbon_exec["carbon_saved_vs_air_kg"].sum() / 1000 if not carbon_exec.empty else 0
air_pct     = carbon_exec["pct_air_shipments"].mean()  if not carbon_exec.empty else 0
shipments   = carbon_exec["shipment_count"].sum()       if not carbon_exec.empty else 0

with k1:
    st.metric("Total Scope 3 Cat 4", "{:.2f} t CO₂e".format(total_co2),
              delta="Jan 2024 – Dec 2025")
with k2:
    st.metric("CO₂ Saved vs All-Air", "{:.2f} t CO₂e".format(saved_vs_air),
              delta="By choosing Sea/Road")
with k3:
    st.metric("Air Freight Usage",   "{:.1f}%".format(air_pct),
              delta="of all shipments",
              delta_color="inverse" if air_pct > 15 else "normal")
with k4:
    st.metric("Shipments Tracked",   "{:,.0f}".format(shipments),
              delta="100% automated")

st.markdown("---")

# ── Monthly Carbon Trend ──────────────────────────────────────────────────────
st.markdown("#### 📈 Monthly Carbon Emissions Trend")

if not carbon_exec.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=carbon_exec["reporting_period"],
        y=carbon_exec["total_carbon_tonnes_co2e"],
        name="Carbon (t CO₂e)",
        marker_color="#4ade80",
        opacity=0.85
    ))
    fig.add_trace(go.Scatter(
        x=carbon_exec["reporting_period"],
        y=carbon_exec["pct_air_shipments"],
        name="Air Freight %",
        yaxis="y2",
        line=dict(color="#f97316", width=2),
        mode="lines+markers"
    ))
    fig.update_layout(
        yaxis=dict(title="Tonnes CO₂e", color="#4ade80"),
        yaxis2=dict(
            title="Air Freight %",
            overlaying="y", side="right",
            color="#f97316"
        ),
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font_color="#e2e8f0",
        legend=dict(bgcolor="#1e2130"),
        margin=dict(t=20, b=60),
        height=360,
        xaxis_tickangle=-45
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Emissions by Transport Mode ───────────────────────────────────────────────
ch1, ch2 = st.columns(2)

with ch1:
    st.markdown("#### 🚢 Emissions by Transport Mode")
    if not carbon_sup.empty:
        mode_totals = carbon_sup.groupby("transport_mode")[
            "total_carbon_kg_co2e"
        ].sum().reset_index()
        mode_totals["total_carbon_tonnes"] = mode_totals["total_carbon_kg_co2e"] / 1000
        fig = px.pie(
            mode_totals,
            values="total_carbon_tonnes",
            names="transport_mode",
            color="transport_mode",
            color_discrete_map=MODE_COLOURS,
            hole=0.45
        )
        fig.update_layout(
            plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
            font_color="#e2e8f0",
            margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

with ch2:
    st.markdown("#### 🏭 Top Emitting Suppliers")
    if not carbon_sup.empty:
        top_sup = (
            carbon_sup.groupby("supplier_name")["total_carbon_kg_co2e"]
            .sum()
            .reset_index()
            .sort_values("total_carbon_kg_co2e", ascending=True)
            .tail(8)
        )
        top_sup["total_carbon_tonnes"] = top_sup["total_carbon_kg_co2e"] / 1000
        fig = px.bar(
            top_sup,
            x="total_carbon_tonnes",
            y="supplier_name",
            orientation="h",
            labels={
                "total_carbon_tonnes": "t CO₂e",
                "supplier_name": ""
            },
            color="total_carbon_tonnes",
            color_continuous_scale="RdYlGn_r"
        )
        fig.update_layout(
            plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
            font_color="#e2e8f0",
            coloraxis_showscale=False,
            margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

# ── DEFRA Factor Reference ────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 📋 DEFRA 2025 Emission Factors — Mode Comparison")

mode_compare = []
example_weight_kg  = 1000
example_distance_km= 5000

for mode, factor in DEFRA_FACTORS.items():
    carbon_kg = (example_weight_kg / 1000) * example_distance_km * factor
    mode_compare.append({
        "Transport Mode":           mode,
        "kg CO₂e / tonne-km":      factor,
        "Example: 1t over 5,000km (kg CO₂e)": round(carbon_kg, 1),
        "Relative to Air":          "{:.1f}x cheaper".format(
            DEFRA_FACTORS["AIR"] / factor
        ) if mode != "AIR" else "Baseline (worst)",
        "Source": "DEFRA GHG Factors 2025"
    })

st.dataframe(
    pd.DataFrame(mode_compare),
    use_container_width=True,
    hide_index=True
)

# ── UK SRS Export ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 📤 UK SRS Scope 3 Export — Ready to Send to Retail Partners")

st.success(
    "✅ **Compliance Status:** 100% automated. "
    "This report is generated instantly from live shipment data. "
    "Previously required 12 hours of manual Excel work per week."
)

year_sel = st.selectbox("Reporting Year", ["2025", "2024"], index=0)

if not srs_export.empty:
    year_data = srs_export[
        srs_export["Reporting Period"].astype(str).str.startswith(year_sel)
    ] if "Reporting Period" in srs_export.columns else srs_export

    if not year_data.empty:
        st.dataframe(year_data, use_container_width=True, hide_index=True)

        csv = year_data.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download UK SRS Scope 3 Report ({})".format(year_sel),
            data=csv,
            file_name="UK_SRS_Scope3_Apex_Distribution_{}.csv".format(year_sel),
            mime="text/csv",
        )
        st.caption(
            "Format: UK Sustainability Reporting Standards — "
            "Scope 3 Category 4 (Upstream Transportation & Distribution). "
            "Send directly to Tesco and John Lewis sustainability teams."
        )
    else:
        st.info("No data for selected year.")
else:
    st.info("Run carbon_calculator.py to generate the SRS export.")

# ── Carbon by Product Category ────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 📦 Carbon Intensity by Product Category")

if not carbon_prod.empty:
    cat_carbon = (
        carbon_prod.groupby("category_code")
        .agg(
            total_carbon_kg  = ("total_carbon_kg_co2e", "sum"),
            total_units      = ("total_units_shipped",  "sum")
        )
        .reset_index()
    )
    cat_carbon["carbon_per_unit_g"] = (
        cat_carbon["total_carbon_kg"] / cat_carbon["total_units"].clip(lower=1) * 1000
    ).round(2)

    fig = px.bar(
        cat_carbon,
        x="category_code",
        y="carbon_per_unit_g",
        labels={
            "category_code": "Product Category",
            "carbon_per_unit_g": "Carbon per Unit (g CO₂e)"
        },
        color="carbon_per_unit_g",
        color_continuous_scale="RdYlGn_r",
        text_auto=".1f"
    )
    fig.update_layout(
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font_color="#e2e8f0",
        coloraxis_showscale=False,
        margin=dict(t=20, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "HHE=Household Essentials, PCA=Personal Care, "
        "FBV=Food & Beverage, SGF=Seasonal & Gifting, CLN=Cleaning Products"
    )
