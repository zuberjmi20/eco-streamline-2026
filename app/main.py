"""
=============================================================================
Eco-Streamline 2026 | Apex Distribution UK
FILE: app/main.py
PURPOSE: Streamlit Application — Main Entry Point
AUTHOR: Lead Business Transformation Analyst
=============================================================================
Run with: streamlit run app/main.py
=============================================================================
"""

import streamlit as st

st.set_page_config(
    page_title  = "Eco-Streamline 2026 | Apex Distribution UK",
    page_icon   = "📦",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #0f1117; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background-color: #1e2130;
        border: 1px solid #2d3250;
        border-radius: 8px;
        padding: 16px;
    }

    /* Headers */
    h1 { color: #4ade80; }
    h2 { color: #e2e8f0; }
    h3 { color: #94a3b8; }

    /* Divider */
    hr { border-color: #2d3250; }

    /* Status badges */
    .badge-a { background:#16a34a; color:white; padding:2px 8px;
                border-radius:4px; font-size:12px; font-weight:bold; }
    .badge-b { background:#ca8a04; color:white; padding:2px 8px;
                border-radius:4px; font-size:12px; font-weight:bold; }
    .badge-c { background:#dc2626; color:white; padding:2px 8px;
                border-radius:4px; font-size:12px; font-weight:bold; }
    .badge-ok  { background:#059669; color:white; padding:2px 8px;
                  border-radius:4px; font-size:12px; }
    .badge-warn{ background:#d97706; color:white; padding:2px 8px;
                  border-radius:4px; font-size:12px; }
    .badge-risk{ background:#dc2626; color:white; padding:2px 8px;
                  border-radius:4px; font-size:12px; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar Navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 Eco-Streamline 2026")
    st.markdown("**Apex Distribution UK**")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        options=[
            "🏠  Home",
            "📊  Inventory Dashboard",
            "🌱  Sustainability Portal",
            "🎛️  Scenario Planner",
            "💼  CFO Summary",
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("**Data Period**")
    st.markdown("Jan 2024 – Dec 2025")
    st.markdown("**Carbon Standard**")
    st.markdown("UK SRS | DEFRA 2025")
    st.markdown("**Model**")
    st.markdown("Monte Carlo 10,000 runs")
    st.markdown("---")
    st.caption("Eco-Streamline 2026 v1.0")
    st.caption("Built for portfolio demonstration")


# ── Page Routing ──────────────────────────────────────────────────────────────
if   "Home"         in page: exec(open("app/pages/home.py").read())
elif "Inventory"    in page: exec(open("app/pages/inventory.py").read())
elif "Sustainability" in page: exec(open("app/pages/sustainability.py").read())
elif "Scenario"     in page: exec(open("app/pages/scenario.py").read())
elif "CFO"          in page: exec(open("app/pages/cfo.py").read())
