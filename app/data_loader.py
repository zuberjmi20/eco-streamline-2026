"""
Shared data loader — cached so every page reuses the same DataFrames.
Import with: from app.utils.data_loader import load_all
"""

import streamlit as st
import pandas as pd
import os

# Resolve data paths whether running from project root or app/ subfolder
def _find_base():
    for candidate in [
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        os.path.join(os.getcwd(), "eco-streamline-2026"),
        os.getcwd(),
    ]:
        if os.path.exists(os.path.join(candidate, "data", "processed")):
            return candidate
    return os.getcwd()

BASE_DIR      = _find_base()
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
REFERENCE_DIR = os.path.join(BASE_DIR, "data", "reference")


@st.cache_data(show_spinner=False)
def load_all() -> dict:
    """Load all datasets once and cache them."""

    def safe_read(fname, folder=PROCESSED_DIR):
        path = os.path.join(folder, fname)
        if os.path.exists(path):
            return pd.read_csv(path)
        return pd.DataFrame()

    return {
        "products":         safe_read("dim_product.csv"),
        "suppliers":        safe_read("dim_supplier.csv"),
        "warehouses":       safe_read("dim_warehouse.csv"),
        "transport":        safe_read("dim_transport_mode.csv"),
        "orders":           safe_read("fact_purchase_orders.csv"),
        "inventory":        safe_read("fact_inventory_snapshots.csv"),
        "monte_carlo":      safe_read("monte_carlo_results.csv"),
        "green_rop":        safe_read("green_rop_decisions.csv"),
        "carbon_all":       safe_read("carbon_events_all.csv"),
        "carbon_supplier":  safe_read("scope3_by_supplier.csv"),
        "carbon_product":   safe_read("scope3_by_product.csv"),
        "carbon_exec":      safe_read("carbon_executive_summary.csv"),
        "srs_export":       safe_read("UK_SRS_Scope3_Export_2025.csv"),
        "sensitivity":      safe_read("sensitivity_analysis.csv"),
        "distances":        safe_read("shipping_distance_matrix.csv", REFERENCE_DIR),
    }


def fmt_gbp(value: float, decimals: int = 0) -> str:
    """Format a number as GBP string."""
    if decimals == 0:
        return "£{:,.0f}".format(value)
    return "£{:,.{}f}".format(value, decimals)


def fmt_pct(value: float, decimals: int = 1) -> str:
    """Format a number as percentage string."""
    return "{:.{}f}%".format(value, decimals)


def fmt_co2(value: float) -> str:
    """Format kg CO2e."""
    if value >= 1000:
        return "{:,.2f} t CO₂e".format(value / 1000)
    return "{:,.2f} kg CO₂e".format(value)


ABC_COLOURS = {"A": "#16a34a", "B": "#ca8a04", "C": "#dc2626"}
MODE_COLOURS = {
    "ROAD": "#3b82f6",
    "SEA":  "#06b6d4",
    "AIR":  "#f97316",
    "RAIL": "#8b5cf6",
}
