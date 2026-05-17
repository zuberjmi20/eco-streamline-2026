"""
Scenario Planner — What-If analysis for lead time, demand, and cost shocks
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_loader import load_all, fmt_gbp, ABC_COLOURS

data     = load_all()
products = data["products"]
suppliers= data["suppliers"]
sup_prod = data["monte_carlo"]
mc       = data["monte_carlo"]
green    = data["green_rop"]

DEFRA_FACTORS = {"ROAD": 0.100, "RAIL": 0.028, "SEA": 0.016, "AIR": 0.602}
SEASONAL = {1:0.75,2:0.80,3:0.90,4:0.95,5:1.00,6:1.05,
            7:1.10,8:1.05,9:1.00,10:1.10,11:1.35,12:1.50}


def run_quick_mc(avg_daily, lt_avg, lt_std, spike_p, service_level,
                 lt_mult=1.0, demand_mult=1.0, n=3000):
    """Lightweight Monte Carlo for real-time scenario response."""
    np.random.seed(42)
    adj_lt_avg = lt_avg * lt_mult
    adj_lt_std = lt_std * lt_mult
    lt_samples = np.random.normal(adj_lt_avg, adj_lt_std, n).clip(1)
    spikes     = np.random.random(n) < spike_p
    lt_samples[spikes] *= np.random.uniform(1.4, 1.8, spikes.sum())
    lt_samples  = lt_samples.clip(1).astype(int)

    adj_demand = avg_daily * demand_mult
    demand_lt  = np.array([
        np.random.poisson(max(0.01, adj_demand), lt).sum()
        for lt in lt_samples
    ])

    mean_d   = adj_demand * adj_lt_avg
    pct_val  = np.percentile(demand_lt, service_level * 100)
    ss       = max(0, int(np.ceil(pct_val - mean_d)))
    rop      = int(np.ceil(mean_d + ss))
    so_prob  = float(np.mean(demand_lt > rop))
    lt_p90   = int(np.percentile(lt_samples, 90))
    lt_p95   = int(np.percentile(lt_samples, 95))

    return {
        "rop": rop, "safety_stock": ss,
        "stockout_prob": so_prob,
        "service_level": 1 - so_prob,
        "lt_p90": lt_p90, "lt_p95": lt_p95,
        "mean_demand_lt": round(mean_d, 1)
    }


st.markdown("# 🎛️ Scenario Planner")
st.markdown(
    "Real-time What-If analysis. Adjust lead time, demand, or cost parameters "
    "and see the impact on ROP, stock-out risk, and carbon instantly."
)
st.markdown("---")

# ── Product Selection ─────────────────────────────────────────────────────────
if not products.empty:
    prod_options = {
        "{} — {} [{}]".format(r["product_id"], r["product_name"], r["abc_class"]): r
        for _, r in products.iterrows()
    }
    sel_label   = st.selectbox("Select Product", list(prod_options.keys()))
    sel_product = prod_options[sel_label]

    # Find primary supplier
    if not mc.empty:
        mc_row = mc[mc["product_id"] == sel_product["product_id"]]
        has_mc = not mc_row.empty
        if has_mc:
            mc_row = mc_row.iloc[0]
else:
    st.error("Product data not found. Run data_generator.py first.")
    st.stop()

st.markdown("---")

# ── Scenario Controls ─────────────────────────────────────────────────────────
st.markdown("#### ⚙️ Scenario Controls")

s1, s2, s3 = st.columns(3)

with s1:
    st.markdown("**Lead Time Shock**")
    lt_mult = st.slider("Lead Time Multiplier", 0.8, 2.0, 1.0, 0.05,
                        help="1.0 = baseline, 1.4 = 40% longer lead time")
    st.caption(
        "Baseline avg: **{:.0f} days** → Scenario: **{:.0f} days**".format(
            mc_row["lt_avg_simulated"] if has_mc else 14,
            mc_row["lt_avg_simulated"] * lt_mult if has_mc else 14 * lt_mult
        )
    )

with s2:
    st.markdown("**Demand Shock**")
    demand_mult = st.slider("Demand Multiplier", 0.5, 3.0, 1.0, 0.05,
                            help="1.0 = baseline, 1.5 = 50% higher demand")
    month_sel   = st.selectbox("Month", list(range(1, 13)),
                               format_func=lambda m: [
                                   "Jan","Feb","Mar","Apr","May","Jun",
                                   "Jul","Aug","Sep","Oct","Nov","Dec"
                               ][m-1],
                               index=10)  # November default
    st.caption(
        "Seasonal multiplier for selected month: **{:.2f}x**".format(
            SEASONAL[month_sel]
        )
    )

with s3:
    st.markdown("**Transport Override**")
    transport_override = st.selectbox(
        "Force Transport Mode", ["Auto (Green-ROP)", "ROAD", "SEA", "AIR", "RAIL"]
    )
    carbon_price = st.slider(
        "Carbon Price (£/t CO₂e)", 0, 150, 45,
        help="UK ETS reference price. Affects Green-ROP cost calculation."
    )

st.markdown("---")

# ── Run Scenarios ─────────────────────────────────────────────────────────────
if has_mc:
    abc    = sel_product["abc_class"]
    price  = float(sel_product["unit_price_gbp"])
    cost   = float(sel_product["unit_cost_gbp"])
    weight = float(sel_product["weight_kg"])
    sl     = float(sel_product["service_level_target"])

    abc_scale = {"A": 1.8, "B": 1.0, "C": 0.4}
    avg_daily = (50 / price) * abc_scale.get(abc, 1.0) * SEASONAL[month_sel]

    lt_avg  = float(mc_row["lt_avg_simulated"])
    lt_std  = float(mc_row["lt_std_simulated"])

    # Get spike probability from supplier data
    sup_id  = str(mc_row.get("supplier_id", "SUP-001"))
    sup_row = data["suppliers"][data["suppliers"]["supplier_id"] == sup_id]
    spike_p = float(sup_row["spike_probability"].iloc[0]) if not sup_row.empty else 0.05
    country = str(sup_row["country_of_origin"].iloc[0]) if not sup_row.empty else "United Kingdom"

    # Baseline scenario
    baseline = run_quick_mc(avg_daily, lt_avg, lt_std, spike_p, sl)

    # User scenario
    scenario = run_quick_mc(
        avg_daily, lt_avg, lt_std, spike_p, sl,
        lt_mult=lt_mult, demand_mult=demand_mult
    )

    # Predefined comparison scenarios
    scenarios_df = []
    for name, lm, dm in [
        ("Baseline",           1.0, 1.0),
        ("LT +20%",           1.2, 1.0),
        ("LT +40%",           1.4, 1.0),
        ("Demand +25%",        1.0, 1.25),
        ("Demand +50%",        1.0, 1.50),
        ("Your Scenario",      lt_mult, demand_mult),
        ("Worst Case",         1.4, 1.50),
    ]:
        r = run_quick_mc(avg_daily, lt_avg, lt_std, spike_p, sl, lm, dm)
        scenarios_df.append({
            "Scenario":          name,
            "LT Mult":          lm,
            "Demand Mult":      dm,
            "ROP (units)":      r["rop"],
            "Safety Stock":     r["safety_stock"],
            "Stock-Out Risk %": round(r["stockout_prob"] * 100, 2),
            "Service Level %":  round(r["service_level"] * 100, 2),
            "LT P90 (days)":    r["lt_p90"],
        })
    sc_df = pd.DataFrame(scenarios_df)

    # ── Results KPIs ──────────────────────────────────────────────────────────
    st.markdown("#### 📊 Scenario Results")

    m1, m2, m3, m4 = st.columns(4)
    rop_delta    = scenario["rop"] - baseline["rop"]
    ss_delta     = scenario["safety_stock"] - baseline["safety_stock"]
    so_delta     = (scenario["stockout_prob"] - baseline["stockout_prob"]) * 100
    wc_impact    = ss_delta * cost

    with m1:
        st.metric("Optimised ROP",
                  "{} units".format(scenario["rop"]),
                  delta="{:+d} vs baseline".format(rop_delta))
    with m2:
        st.metric("Safety Stock",
                  "{} units".format(scenario["safety_stock"]),
                  delta="{:+d} units".format(ss_delta))
    with m3:
        st.metric("Stock-Out Risk",
                  "{:.1f}%".format(scenario["stockout_prob"] * 100),
                  delta="{:+.1f}% vs baseline".format(so_delta),
                  delta_color="inverse")
    with m4:
        st.metric("Working Capital Impact",
                  fmt_gbp(abs(wc_impact)),
                  delta="{} vs baseline".format(
                      "extra stock cost" if wc_impact > 0 else "capital released"
                  ),
                  delta_color="inverse" if wc_impact > 0 else "normal")

    # ── Scenario Comparison Chart ──────────────────────────────────────────────
    st.markdown("#### 📉 Scenario Comparison — ROP and Stock-Out Risk")

    fig = go.Figure()
    colours = ["#64748b","#64748b","#64748b","#64748b",
               "#64748b","#4ade80","#dc2626"]

    fig.add_trace(go.Bar(
        name="ROP (units)",
        x=sc_df["Scenario"],
        y=sc_df["ROP (units)"],
        marker_color=colours,
        opacity=0.85,
        yaxis="y"
    ))
    fig.add_trace(go.Scatter(
        name="Stock-Out Risk %",
        x=sc_df["Scenario"],
        y=sc_df["Stock-Out Risk %"],
        mode="lines+markers",
        line=dict(color="#f97316", width=2),
        marker=dict(size=8),
        yaxis="y2"
    ))
    fig.update_layout(
        yaxis=dict(title="ROP (units)", color="#e2e8f0"),
        yaxis2=dict(title="Stock-Out Risk %", overlaying="y",
                    side="right", color="#f97316"),
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font_color="#e2e8f0",
        legend=dict(bgcolor="#1e2130"),
        margin=dict(t=20, b=40),
        height=360
    )
    st.plotly_chart(fig, use_container_width=True)

    # Highlight user's scenario row
    st.dataframe(
        sc_df.style.apply(
            lambda row: ["background-color: #1a3a2a" if row["Scenario"] == "Your Scenario"
                         else "" for _ in row],
            axis=1
        ),
        use_container_width=True, hide_index=True
    )

    # ── Carbon Trade-Off ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🌱 Carbon Trade-Off — Transport Mode Comparison")
    st.markdown(
        "For this product shipped from **{}** — how does transport mode "
        "affect cost and carbon?".format(country)
    )

    dist_df   = data["distances"]
    mode_data = []
    dist_row  = dist_df[dist_df["origin_country"] == country]

    for mode, factor in DEFRA_FACTORS.items():
        mode_dist = dist_row[dist_row["transport_mode"] == mode]
        distance  = float(mode_dist["distance_km"].iloc[0]) if not mode_dist.empty else 1000.0
        order_qty = int(mc_row.get("recommended_order_qty", 100))
        shipment_wt = weight * order_qty
        carbon_kg = (shipment_wt / 1000) * distance * factor
        carbon_cost= (carbon_kg / 1000) * carbon_price

        cost_idx  = {"ROAD": 1.0, "RAIL": 0.7, "SEA": 0.4, "AIR": 8.5}.get(mode, 1.0)
        freight   = shipment_wt * distance * 0.0008 * cost_idx

        mode_data.append({
            "Mode":                 mode,
            "Distance (km)":        distance,
            "Freight Cost (£)":     round(freight, 0),
            "Carbon (kg CO₂e)":     round(carbon_kg, 2),
            "Carbon Cost (£)":      round(carbon_cost, 2),
            "Total Cost (£)":       round(freight + carbon_cost, 0),
            "vs Air Carbon (%)":    round(
                (DEFRA_FACTORS["AIR"] - factor) / DEFRA_FACTORS["AIR"] * 100, 1
            ),
        })

    mode_df = pd.DataFrame(mode_data).sort_values("Carbon (kg CO₂e)")

    fig2 = px.scatter(
        mode_df,
        x="Carbon (kg CO₂e)",
        y="Total Cost (£)",
        color="Mode",
        size="Carbon (kg CO₂e)",
        text="Mode",
        color_discrete_map={"ROAD":"#3b82f6","SEA":"#06b6d4",
                            "AIR":"#f97316","RAIL":"#8b5cf6"},
        title="Cost vs Carbon — Transport Mode Trade-Off"
    )
    fig2.update_traces(textposition="top center")
    fig2.update_layout(
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font_color="#e2e8f0",
        margin=dict(t=40, b=20),
        height=380
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(mode_df, use_container_width=True, hide_index=True)

    # ── Lead Time Spike Visualisation ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ⚡ 2026 Lead Time Volatility — Simulated Distribution")

    np.random.seed(2026)
    lt_base = np.random.normal(lt_avg, lt_std, 2000).clip(1)
    spikes_mask = np.random.random(2000) < spike_p
    lt_base[spikes_mask] *= np.random.uniform(1.4, 1.8, spikes_mask.sum())

    lt_scen = np.random.normal(lt_avg * lt_mult, lt_std * lt_mult, 2000).clip(1)
    sp2 = np.random.random(2000) < spike_p
    lt_scen[sp2] *= np.random.uniform(1.4, 1.8, sp2.sum())

    fig3 = go.Figure()
    fig3.add_trace(go.Histogram(
        x=lt_base, name="Baseline", opacity=0.6,
        marker_color="#64748b", nbinsx=40
    ))
    fig3.add_trace(go.Histogram(
        x=lt_scen, name="Your Scenario ({:.1f}x)".format(lt_mult),
        opacity=0.7, marker_color="#4ade80", nbinsx=40
    ))
    fig3.add_vline(x=np.percentile(lt_base, 90), line_dash="dash",
                   line_color="#94a3b8",
                   annotation_text="Baseline P90: {}d".format(
                       int(np.percentile(lt_base, 90))
                   ))
    fig3.add_vline(x=np.percentile(lt_scen, 90), line_dash="dash",
                   line_color="#4ade80",
                   annotation_text="Scenario P90: {}d".format(
                       int(np.percentile(lt_scen, 90))
                   ))
    fig3.update_layout(
        barmode="overlay",
        xaxis_title="Lead Time (days)",
        yaxis_title="Frequency",
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font_color="#e2e8f0",
        legend=dict(bgcolor="#1e2130"),
        margin=dict(t=20, b=20),
        height=320
    )
    st.plotly_chart(fig3, use_container_width=True)
    st.caption(
        "Spike events (2026 shipping disruptions) create the long right tail. "
        "Simple average-based ROP misses these entirely. Monte Carlo accounts for them."
    )
else:
    st.warning(
        "Monte Carlo results not found. "
        "Run monte_carlo.py first then reload the app."
    )
