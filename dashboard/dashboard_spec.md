# Dashboard Specification
## Eco-Streamline 2026 | Apex Distribution UK
### Power BI CFO Dashboard + Sustainability Portal

---

## SETUP INSTRUCTIONS

### Step 1 — Install Power BI Desktop
Download free from: https://powerbi.microsoft.com/desktop

### Step 2 — Import the 8 CSV files
1. Open Power BI Desktop
2. Home → Get Data → Text/CSV
3. Import each file from `dashboard/mock_data/`:
   - `pbi_dim_date.csv`
   - `pbi_dim_product.csv`
   - `pbi_dim_supplier.csv`
   - `pbi_fact_inventory_monthly.csv`
   - `pbi_fact_purchase_orders.csv`
   - `pbi_fact_carbon_monthly.csv`
   - `pbi_fact_carbon_by_supplier.csv`
   - `pbi_fact_monte_carlo_summary.csv`
4. For each: click Load (not Transform)

### Step 3 — Build relationships
Go to Model view (left sidebar icon). Create these relationships:

| From Table + Column | To Table + Column | Cardinality |
|---|---|---|
| pbi_dim_date[DateKey] | pbi_fact_inventory_monthly[DateKey] | 1:* |
| pbi_dim_date[DateKey] | pbi_fact_purchase_orders[DateKey] | 1:* |
| pbi_dim_date[DateKey] | pbi_fact_carbon_monthly[DateKey] | 1:* |
| pbi_dim_date[DateKey] | pbi_fact_carbon_by_supplier[DateKey] | 1:* |
| pbi_dim_product[product_id] | pbi_fact_inventory_monthly[product_id] | 1:* |
| pbi_dim_product[product_id] | pbi_fact_purchase_orders[product_id] | 1:* |
| pbi_dim_product[product_id] | pbi_fact_monte_carlo_summary[product_id] | 1:* |
| pbi_dim_supplier[supplier_id] | pbi_fact_purchase_orders[supplier_id] | 1:* |
| pbi_dim_supplier[supplier_id] | pbi_fact_carbon_by_supplier[supplier_id] | 1:* |

### Step 4 — Add DAX measures
Copy each measure from `dax_measures.md` into Power BI:
Home → New Measure → paste DAX → Enter

### Step 5 — Build dashboards
Follow the layout specs below for each page.

---

---

# DASHBOARD 1 — CFO DASHBOARD

**Purpose:** Executive financial overview for the CFO and Finance Director.
**Audience:** Non-technical. Numbers, trends, and alerts only.
**Page size:** 1280 × 720px (widescreen 16:9)
**Theme:** Dark (use Power BI built-in "Midnight" theme or import custom)

---

## PAGE LAYOUT — CFO Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER ROW                                                     │
│  Logo placeholder │ "CFO Dashboard — Apex Distribution UK"     │
│  Data period: Jan 2024 – Dec 2025                               │
├──────────┬──────────┬──────────┬──────────┬────────────────────┤
│  CARD 1  │  CARD 2  │  CARD 3  │  CARD 4  │  CARD 5           │
│ Total    │ Excess   │ A-Class  │ Urgent   │ Working Capital    │
│ Stock    │ Stock    │ Stockout │ Orders   │ Released           │
│ Value    │ Value    │ Rate %   │ Count    │ Target             │
├──────────┴──────────┴──────────┴──────────┴────────────────────┤
│  CHART 1 (60% width)          │  CHART 2 (40% width)           │
│  Working Capital Trend         │  Stock Value by ABC Class      │
│  Line chart — monthly          │  Bar chart — A / B / C        │
│  Show: Total Stock Value       │                                │
│        Slow-Mover Value        │                                │
│        Target line at £238k    │                                │
├───────────────────────────────┼────────────────────────────────┤
│  CHART 3 (50% width)          │  CHART 4 (50% width)           │
│  Stock-Out Rate by Month       │  ROP Current vs Optimised      │
│  Line chart — A/B/C coloured   │  Clustered bar — top 15 prods │
│  Target line at 3%             │  Grey = current, Green = optim │
├───────────────────────────────┼────────────────────────────────┤
│  CHART 5 (50% width)          │  CHART 6 (50% width)           │
│  Monthly Order Value           │  Process Efficiency            │
│  Clustered bar + line          │  Grouped bar: Before vs After  │
│  Bar = order value             │  Categories: each process step │
│  Line = urgent order count     │                                │
├───────────────────────────────┴────────────────────────────────┤
│  SLICER ROW                                                     │
│  Year slicer │ Month slicer │ ABC Class slicer │ Category      │
└─────────────────────────────────────────────────────────────────┘
```

---

## VISUAL SPECIFICATIONS — CFO Dashboard

### KPI Cards (Row 1)

**Card 1 — Total Stock Value**
- Measure: `[Total Stock Value GBP]`
- Format: £ currency, 0 decimal places
- Conditional format: none (informational)

**Card 2 — Excess Stock Value**
- Measure: `[Excess Stock Value GBP]`
- Format: £ currency
- Conditional format: Red if > £238,000 (above target)
- Subtitle: "Target: £238,000 (-15%)"

**Card 3 — A-Class Stock-Out Rate**
- Measure: `[A-Class Stock-Out Rate %]`
- Format: % 1 decimal
- Conditional format: Green < 3%, Amber 3-7%, Red > 7%
- Subtitle: "Target: < 3%"

**Card 4 — Urgent Orders**
- Measure: `[Urgent Order Count]`
- Format: whole number
- Conditional format: Amber if > 5, Red if > 15
- Subtitle: "Reactive purchasing indicator"

**Card 5 — Working Capital Released**
- Measure: `[Working Capital Unlocked GBP]`
- Format: £ currency
- Conditional format: Green (always positive target)
- Subtitle: "Monte Carlo optimisation target"

---

### Chart 1 — Working Capital Trend (Line Chart)

- **Visual type:** Line chart
- **X-axis:** `pbi_dim_date[YearMonth]` (sort by MonthNumber)
- **Y-axis:** `[Total Stock Value GBP]`
- **Secondary line:** `[Slow Mover Stock Value GBP]`
- **Reference line:** Constant value £238,000 (target excess)
- **Legend:** Total Stock Value | Slow-Mover Value | Target
- **Colours:** Blue = Total, Red = Slow-Mover, Green dashed = Target
- **Title:** "Working Capital — Monthly Stock Value"

---

### Chart 2 — Stock Value by ABC Class (Bar Chart)

- **Visual type:** Clustered bar chart
- **X-axis:** `pbi_dim_product[abc_class]`
- **Y-axis:** `[Total Stock Value GBP]`
- **Colours:** A = Green (#16a34a), B = Amber (#ca8a04), C = Red (#dc2626)
- **Data labels:** On, £ format
- **Title:** "Stock Value by ABC Class"
- **Sort:** A → B → C (use abc_sort_order column)

---

### Chart 3 — Stock-Out Rate by Month (Line Chart)

- **Visual type:** Line chart with markers
- **X-axis:** `pbi_dim_date[YearMonth]`
- **Y-axis:** `[Stock-Out Rate %]`
- **Legend:** ABC Class (A/B/C — three lines)
- **Reference line:** 3% (target for A-class)
- **Reference line:** 7% (current A-class baseline)
- **Colours:** A = Green, B = Amber, C = Red
- **Title:** "Stock-Out Rate by ABC Class — Monthly"

---

### Chart 4 — ROP Current vs Optimised (Clustered Bar)

- **Visual type:** Clustered bar chart
- **Data source:** `pbi_fact_monte_carlo_summary`
- **X-axis:** `product_name` (top 15 by working_capital_released descending)
- **Y-axis 1:** `rop_current` (grey bars)
- **Y-axis 2:** `rop_optimised` (green bars)
- **Filter:** Top 15 products by `[Total Working Capital Released GBP]`
- **Title:** "Monte Carlo ROP — Current vs Optimised (Top 15 Products)"
- **Subtitle:** "Optimised accounts for 2026 lead time volatility"

---

### Chart 5 — Monthly Order Value (Combo Chart)

- **Visual type:** Line and clustered column chart
- **X-axis:** `pbi_dim_date[YearMonth]`
- **Column:** `[Total Order Value GBP]` (blue bars)
- **Line:** `[Urgent Order Count]` (orange line, secondary axis)
- **Title:** "Monthly Purchase Order Value + Urgent Order Trend"
- **Subtitle:** "Urgent orders signal reactive purchasing — target: reduce"

---

### Chart 6 — Process Efficiency (Grouped Bar)

- **Visual type:** Clustered bar chart (horizontal)
- **Data:** Enter manually (not from CSV):

| Process | Before (min) | After (min) |
|---|---|---|
| Data Collection | 240 | 0 |
| Validation | 120 | 0 |
| Inventory Report | 180 | 3 |
| Carbon Report | 0 | 2 |
| Supplier Reports | 180 | 2 |
| Total | 720 | 7 |

- **Y-axis:** Process name
- **X-axis:** Minutes
- **Colours:** Before = Red (#dc2626), After = Green (#16a34a)
- **Title:** "Reporting Time: Before vs After (minutes per week)"

---

---

# DASHBOARD 2 — SUSTAINABILITY PORTAL

**Purpose:** UK SRS Scope 3 compliance reporting for retail partners.
**Audience:** Sustainability team + Tesco / John Lewis partner contacts.
**Page size:** 1280 × 720px
**Theme:** Dark with green accent — use "Accessible default" then override

---

## PAGE LAYOUT — Sustainability Portal

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER                                                         │
│  🌱 Sustainability Portal │ UK SRS Scope 3 Category 4           │
│  DEFRA GHG Conversion Factors 2025 │ 100% Automated            │
├──────────┬──────────┬──────────┬──────────┬────────────────────┤
│  CARD 1  │  CARD 2  │  CARD 3  │  CARD 4  │  CARD 5           │
│ Total    │ CO2 Saved│ Air      │ Shipments│ Carbon per Unit    │
│ Scope 3  │ vs Air   │ Freight% │ Tracked  │ (kg CO2e)          │
│ Tonnes   │ Tonnes   │          │          │                    │
├──────────┴──────────┴──────────┴──────────┴────────────────────┤
│  CHART 1 (60% width)          │  CHART 2 (40% width)           │
│  Monthly Carbon Emissions      │  Emissions by Transport Mode   │
│  Bar chart + Air% line         │  Donut chart                   │
│  Show CO2e trend over time     │  ROAD/SEA/AIR/RAIL segments    │
├───────────────────────────────┼────────────────────────────────┤
│  CHART 3 (50% width)          │  CHART 4 (50% width)           │
│  Top Emitting Suppliers        │  Carbon per Unit by Category   │
│  Horizontal bar chart          │  Bar chart — 5 categories      │
│  Sort descending by tonnes     │  grams CO2e per unit           │
├───────────────────────────────┴────────────────────────────────┤
│  TABLE — UK SRS Scope 3 Export                                  │
│  Full supplier × month × mode breakdown                         │
│  Columns: Period │ Supplier │ Country │ Mode │                  │
│           Shipments │ Weight │ Carbon (kg) │ Carbon (t)        │
│  Download button via report subscription                        │
├─────────────────────────────────────────────────────────────────┤
│  SLICER ROW                                                     │
│  Year │ Month │ Supplier │ Transport Mode │ Region             │
└─────────────────────────────────────────────────────────────────┘
```

---

## VISUAL SPECIFICATIONS — Sustainability Portal

### KPI Cards (Row 1)

**Card 1 — Total Scope 3 Emissions**
- Measure: `[Total Carbon Tonnes CO2e]`
- Format: 2 decimal places, suffix " t CO₂e"
- Conditional format: None (informational baseline)
- Subtitle: "Scope 3 Category 4 — Upstream Transport"

**Card 2 — CO2 Saved vs All-Air Baseline**
- Measure: `[Carbon Saved vs All-Air Tonnes]`
- Format: 2 decimal places, suffix " t CO₂e"
- Conditional format: Always green (saving is good)
- Subtitle: "By choosing Sea/Road over Air freight"

**Card 3 — Air Freight %**
- Measure: `[Air Freight Shipment %]`
- Format: 1 decimal place, suffix "%"
- Conditional format: Green < 10%, Amber 10-20%, Red > 20%
- Subtitle: "Highest carbon mode — minimise"

**Card 4 — Shipments Tracked**
- Measure: `COUNTROWS(pbi_fact_purchase_orders)`
- Format: Whole number with comma separator
- Conditional format: Always green
- Subtitle: "100% automated — zero manual entry"

**Card 5 — Carbon per Unit**
- Measure: `[Carbon Intensity per Unit KG]`
- Format: 4 decimal places, suffix " kg CO₂e"
- Conditional format: Green < 0.5, Amber 0.5-1.0, Red > 1.0
- Subtitle: "Average across all shipments"

---

### Chart 1 — Monthly Carbon Emissions (Combo Chart)

- **Visual type:** Line and clustered column chart
- **X-axis:** `pbi_fact_carbon_monthly[reporting_period]`
- **Column:** `[Total Carbon Tonnes CO2e]` — green bars
- **Line:** `[Air Freight Shipment %]` — orange line, secondary axis
- **Reference line:** Rolling average (use DAX: `[Rolling 3M Avg Carbon KG]` / 1000)
- **Title:** "Monthly Scope 3 Emissions (t CO₂e) + Air Freight %"
- **Subtitle:** "DEFRA GHG Conversion Factors 2025"

---

### Chart 2 — Emissions by Transport Mode (Donut)

- **Visual type:** Donut chart
- **Legend:** `pbi_fact_carbon_by_supplier[transport_mode_label]`
- **Values:** `[Supplier Total Carbon KG]`
- **Colours:**
  - Road (HGV) = Blue (#3b82f6)
  - Sea (Container) = Cyan (#06b6d4)
  - Air Freight = Orange (#f97316)
  - Rail (Freight) = Purple (#8b5cf6)
- **Detail labels:** Mode name + % of total
- **Title:** "Carbon Emissions by Transport Mode"

---

### Chart 3 — Top Emitting Suppliers (Horizontal Bar)

- **Visual type:** Horizontal bar chart
- **Y-axis:** `pbi_dim_supplier[supplier_name]`
- **X-axis:** `[Supplier Total Carbon KG]` / 1000 (tonnes)
- **Sort:** Descending by value
- **Colour:** Gradient — green (low) to red (high)
- **Data labels:** On, 2 decimal places + " t"
- **Title:** "Top Emitting Suppliers — Total Scope 3 (t CO₂e)"
- **Subtitle:** "Intercontinental air freight suppliers dominate"

---

### Chart 4 — Carbon per Unit by Category (Bar)

- **Visual type:** Clustered bar chart
- **X-axis:** `pbi_dim_product[category_code]`
- **Y-axis:** `[Carbon Intensity per Unit KG]` × 1000 (grams)
- **Colour:** Gradient — green to red by value
- **Title:** "Carbon Intensity per Unit by Product Category (g CO₂e)"
- **Tooltip:** Include category_name for readability

---

### Table — UK SRS Scope 3 Export

- **Visual type:** Table
- **Columns:**
  1. `reporting_period` — "Period"
  2. `supplier_name` — "Supplier"
  3. `country_of_origin` — "Country"
  4. `transport_mode_label` — "Transport Mode"
  5. `shipment_count` — "Shipments"
  6. `total_weight_kg` — "Weight (kg)" format: 0 dp
  7. `total_carbon_kg_co2e` — "Carbon (kg CO₂e)" format: 2 dp
  8. `total_carbon_tonnes` — "Carbon (t CO₂e)" format: 4 dp
  9. `carbon_per_unit_kg` — "Per Unit (kg CO₂e)" format: 6 dp
- **Sort:** reporting_period ASC, total_carbon_kg_co2e DESC
- **Conditional formatting on Carbon (kg CO₂e):** Green → Red gradient
- **Title:** "UK SRS Scope 3 Category 4 — Export Ready"
- **Subtitle:** "Filter by year and export via Power BI subscription"

---

## SLICERS — Both Dashboards

### Year Slicer
- **Field:** `pbi_dim_date[Year]`
- **Style:** Dropdown
- **Default:** All (or 2025)

### Month Slicer
- **Field:** `pbi_dim_date[MonthName]`
- **Style:** List (vertical)
- **Sort by:** MonthNumber

### ABC Class Slicer (CFO only)
- **Field:** `pbi_dim_product[abc_class]`
- **Style:** Button / tile
- **Options:** A | B | C
- **Default:** All selected

### Transport Mode Slicer (Sustainability only)
- **Field:** `pbi_fact_carbon_by_supplier[transport_mode_label]`
- **Style:** Dropdown
- **Default:** All

### Supplier Slicer (Sustainability only)
- **Field:** `pbi_dim_supplier[supplier_name]`
- **Style:** Dropdown with search
- **Default:** All

---

## COLOUR PALETTE

| Usage | Hex | RGB |
|---|---|---|
| Primary Green (A-class, positive) | #16a34a | 22, 163, 74 |
| Light Green (charts) | #4ade80 | 74, 222, 128 |
| Amber (B-class, warning) | #ca8a04 | 202, 138, 4 |
| Red (C-class, critical) | #dc2626 | 220, 38, 38 |
| Blue (orders, neutral) | #3b82f6 | 59, 130, 246 |
| Orange (air freight, urgent) | #f97316 | 249, 115, 22 |
| Cyan (sea freight) | #06b6d4 | 6, 182, 212 |
| Purple (rail) | #8b5cf6 | 139, 92, 246 |
| Dark background | #0f1117 | 15, 17, 23 |
| Card background | #1e2130 | 30, 33, 48 |
| Text primary | #e2e8f0 | 226, 232, 240 |
| Text secondary | #94a3b8 | 148, 163, 184 |

---

## PUBLISHING FOR PORTFOLIO

Once built locally in Power BI Desktop:

1. **Export PDF:** File → Export → PDF — use as static portfolio attachment
2. **Publish to Power BI Service:** Requires free Power BI account (powerbi.com)
   - Sign in with Microsoft account
   - Home → Publish → select workspace
   - Share the report link on LinkedIn / Upwork profile
3. **Screenshot key visuals** for GitHub README and CV

---

*Spec version: 1.0 | Phase 5 — Eco-Streamline 2026*
*Built for portfolio demonstration — Apex Distribution UK (synthetic data)*
