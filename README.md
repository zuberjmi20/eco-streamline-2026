Eco-Streamline 2026
Production-Grade Business Transformation System
Client: Apex Distribution UK — Mid-sized wholesale distributor supplying Tesco & John Lewis
Role: Lead Business Transformation Analyst (Consultant)
---
The Business Problem
A £12M turnover wholesale distributor managing operations through fragmented Excel workbooks, facing three critical failures:
Problem	Financial Impact
£280,000 locked in overstocked slow-movers	£35,000/year in storage & financing costs
7% stock-out rate on high-margin A-list items	£110,000 in lost annual sales
Zero carbon reporting capability	40% of contract value at risk (Tesco & John Lewis mandate)
---
The Solution
A production-ready data and analytics system across three domains:
A — Data Architecture (SQL + ETL)
Migration from flat-file Excel to a relational Star Schema (Single Source of Truth)
Automated Data Validation pipeline flagging supplier input errors before they reach reports
Handles real-world dirty data: name inconsistencies, date format mismatches, duplicate records
B — Analytics Engine (Python)
Monte Carlo Simulation — 10,000 iterations per product modelling 2026 UK shipping volatility
Green-ROP Algorithm — custom reorder logic balancing cost vs carbon (Sea vs Air trade-off)
Scope 3 Carbon Calculator — DEFRA-compliant emission calculations per shipment
C — Executive Business Intelligence (Streamlit + Power BI)
CFO Dashboard — Working capital unlocked, inventory turnover ratios, stock-out costs
Sustainability Portal — Automated UK SRS-aligned Scope 3 report generator
Scenario Planner — What-If analysis for lead time, cost, and demand changes
---
Tech Stack
Layer	Technology
Database	PostgreSQL — Star Schema
ETL & Validation	Python + SQL
Analytics Engine	Python (NumPy, SciPy, Pandas)
Web Application	Streamlit
Business Intelligence	Power BI
Testing	pytest
Data	Synthetic (statistically realistic) + DEFRA public carbon factors
---
Project Structure
```
eco-streamline-2026/
│
├── data/
│   ├── raw/                         # Messy supplier CSVs (~12% error rate)
│   ├── processed/                   # Cleaned master + transactional data
│   └── reference/                   # DEFRA carbon factors, distance matrix
│
├── sql/
│   ├── 01_star_schema.sql           # Full database design
│   ├── 02_etl_pipeline.sql          # Data transformation logic
│   └── 03_validation_rules.sql      # Data quality checks
│
├── python/
│   ├── data_generator.py            # Synthetic data engine (Phase 1)
│   ├── monte_carlo.py               # Probabilistic inventory simulation
│   ├── green_rop.py                 # Custom reorder algorithm
│   └── carbon_calculator.py         # Scope 3 emissions engine
│
├── app/
│   ├── main.py                      # Streamlit app entry point
│   └── pages/
│       ├── inventory.py             # Inventory dashboard
│       ├── sustainability.py        # Carbon reporting
│       └── scenario.py              # What-If planning
│
├── dashboard/
│   ├── mock_data/                   # Pre-aggregated data for Power BI
│   ├── dax_measures.md              # All DAX formulas documented
│   └── dashboard_spec.md            # Layout specifications
│
├── tests/
│   ├── test_monte_carlo.py
│   ├── test_green_rop.py
│   └── test_carbon_calculator.py
│
├── docs/
│   ├── phase0_business_rules.md     # Business rules & data contracts
│   ├── architecture_diagram.png     # System architecture visual
│   └── executive_summary.pdf        # 1-page ROI summary
│
└── README.md
```
---
Build Progress
Phase	Description	Status
0	Business rules & data contracts	✅ Complete
1	Synthetic data generation	✅ Complete
2	SQL Star Schema & ETL pipeline	🔄 In Progress
3	Python analytics engine	⏳ Pending
4	Streamlit web application	⏳ Pending
5	Power BI dashboard layer	⏳ Pending
6	Testing suite	⏳ Pending
7	Documentation & portfolio assets	⏳ Pending
---
Phase 1 Data — What Was Generated
File	Description	Rows
`dim_product.csv`	50 products with ABC classification	50
`dim_supplier.csv`	8 suppliers with lead time parameters	8
`dim_warehouse.csv`	3 UK warehouses (Coventry, Manchester, Bristol)	3
`dim_transport_mode.csv`	4 modes with DEFRA carbon factors	4
`bridge_supplier_product.csv`	Supplier-product links	60
`fact_purchase_orders.csv`	2 years of purchase orders	992
`fact_inventory_snapshots.csv`	Monthly inventory snapshots	1,200
`ALL_SUPPLIERS_combined_raw.csv`	Dirty supplier ingest feed (~12% errors)	1,000+
`_error_manifest.csv`	Error log across 7 error types	115
Simulation period: January 2024 – December 2025
Random seed: 2026 (fully reproducible)
Carbon data: DEFRA GHG Conversion Factors 2025 (UK Government, public domain)
---
Target ROI (Success Metrics)
Metric	Baseline	Target
Excess stock value	£280,000	£238,000 (-15%)
A-list stock-out rate	7%	Under 3%
Carbon reporting	0% automated	100% automated
Weekly reporting time	12 hours manual	Under 10 minutes
---
How to Run the Data Generator
```bash
pip install pandas numpy scipy
python python/data_generator.py
```
Regenerates all Phase 1 data files identically every time (seed: 2026).
---
Portfolio Context
Built as a freelance consulting portfolio piece demonstrating end-to-end data transformation capability for SME clients. Designed to be immediately relatable to small and mid-sized UK businesses facing similar inventory, reporting, and sustainability compliance challenges.
Skills demonstrated: Data engineering · Statistical modelling · Business algorithm design · Regulatory compliance · Full-stack data applications · Executive BI · Consulting communication
---
Built by: Zubair | GitHub: @zuberjmi20
