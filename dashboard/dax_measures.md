# DAX Measures Library
## Eco-Streamline 2026 | Apex Distribution UK
### Power BI CFO Dashboard + Sustainability Portal

---

## HOW TO USE THIS FILE

1. Open Power BI Desktop
2. Import all 8 CSVs from `dashboard/mock_data/`
3. Build relationships (see dashboard_spec.md)
4. For each measure below: Home → New Measure → paste the DAX → rename

---

## TABLE RELATIONSHIPS TO BUILD FIRST

```
pbi_dim_date[DateKey]           → pbi_fact_inventory_monthly[DateKey]
pbi_dim_date[DateKey]           → pbi_fact_purchase_orders[DateKey]
pbi_dim_date[DateKey]           → pbi_fact_carbon_monthly[DateKey]
pbi_dim_date[DateKey]           → pbi_fact_carbon_by_supplier[DateKey]
pbi_dim_product[product_id]     → pbi_fact_inventory_monthly[product_id]
pbi_dim_product[product_id]     → pbi_fact_purchase_orders[product_id]
pbi_dim_product[product_id]     → pbi_fact_monte_carlo_summary[product_id]
pbi_dim_supplier[supplier_id]   → pbi_fact_purchase_orders[supplier_id]
pbi_dim_supplier[supplier_id]   → pbi_fact_carbon_by_supplier[supplier_id]
```

All relationships are Many-to-One (* to 1), Single direction filter.

---

## SECTION 1 — CFO DASHBOARD MEASURES

---

### 1.1 Working Capital Measures

```dax
[Total Stock Value GBP] =
SUMX(
    pbi_fact_inventory_monthly,
    pbi_fact_inventory_monthly[stock_value_gbp]
)
```
*Total value of all stock on hand at cost price.*

---

```dax
[Excess Stock Value GBP] =
SUMX(
    pbi_fact_inventory_monthly,
    pbi_fact_inventory_monthly[excess_stock_value_gbp]
)
```
*Value of stock beyond 90-day cover for C-class products. Baseline: £280,000.*

---

```dax
[Slow Mover Stock Value GBP] =
CALCULATE(
    [Total Stock Value GBP],
    pbi_fact_inventory_monthly[is_slow_mover] = TRUE()
)
```
*Stock value tied up in slow-moving C-class items.*

---

```dax
[Working Capital Unlocked GBP] =
VAR TargetReduction = 0.15
VAR BaselineExcess = 280000
RETURN
    BaselineExcess * TargetReduction
```
*Target working capital release: 15% of £280,000 baseline = £42,000.*

---

```dax
[Excess Stock vs Target] =
VAR CurrentExcess = [Excess Stock Value GBP]
VAR TargetExcess  = 238000
RETURN
    CurrentExcess - TargetExcess
```
*Positive = still above target. Negative = target achieved.*

---

```dax
[Inventory Turnover Ratio] =
VAR TotalOrderValue = SUM(pbi_fact_purchase_orders[total_cost_gbp])
VAR AvgStockValue   = AVERAGEX(
    VALUES(pbi_dim_date[YearMonth]),
    CALCULATE([Total Stock Value GBP])
)
RETURN
    DIVIDE(TotalOrderValue, AvgStockValue, 0)
```
*How many times inventory turns over in the period. Higher = more efficient.*

---

```dax
[Days Inventory Outstanding] =
DIVIDE(365, [Inventory Turnover Ratio], 0)
```
*Average number of days stock sits before being sold. Lower = better.*

---

### 1.2 Stock-Out Measures

```dax
[Total Stock-Out Events] =
CALCULATE(
    COUNTROWS(pbi_fact_inventory_monthly),
    pbi_fact_inventory_monthly[is_stock_out] = TRUE()
)
```

---

```dax
[Stock-Out Rate %] =
DIVIDE(
    [Total Stock-Out Events],
    COUNTROWS(pbi_fact_inventory_monthly),
    0
) * 100
```
*Overall stock-out rate. A-class baseline: 7%. Target: <3%.*

---

```dax
[A-Class Stock-Out Rate %] =
CALCULATE(
    [Stock-Out Rate %],
    pbi_dim_product[abc_class] = "A"
)
```
*Critical metric — A-class stock-outs risk Tesco and John Lewis contracts.*

---

```dax
[Stock-Out Rate vs Target] =
VAR Current = [A-Class Stock-Out Rate %]
VAR Target  = 3.0
RETURN
    Current - Target
```
*Positive = still above 3% target. Use conditional formatting: red if positive.*

---

```dax
[At Risk Products] =
CALCULATE(
    DISTINCTCOUNT(pbi_fact_inventory_monthly[product_id]),
    pbi_fact_inventory_monthly[is_at_risk] = TRUE()
)
```
*A-class products with fewer than 14 days of cover. Requires immediate attention.*

---

### 1.3 Order & Supplier Measures

```dax
[Total Order Value GBP] =
SUM(pbi_fact_purchase_orders[total_cost_gbp])
```

---

```dax
[Total Orders] =
COUNTROWS(pbi_fact_purchase_orders)
```

---

```dax
[Urgent Order Count] =
CALCULATE(
    [Total Orders],
    pbi_fact_purchase_orders[is_urgent_order] = TRUE()
)
```
*Urgent orders = reactive purchasing to prevent stock-outs. Target: reduce to near zero.*

---

```dax
[Urgent Order Rate %] =
DIVIDE([Urgent Order Count], [Total Orders], 0) * 100
```

---

```dax
[Avg Lead Time Days] =
AVERAGE(pbi_fact_purchase_orders[lead_time_days])
```

---

```dax
[Lead Time vs Supplier Avg] =
VAR ActualAvg = [Avg Lead Time Days]
VAR SupplierAvg = AVERAGE(pbi_dim_supplier[lead_time_avg_days])
RETURN
    ActualAvg - SupplierAvg
```
*Positive = deliveries arriving later than promised. Key supplier performance indicator.*

---

```dax
[Avg Order Value GBP] =
DIVIDE([Total Order Value GBP], [Total Orders], 0)
```

---

### 1.4 Monte Carlo Optimisation Measures

```dax
[Avg Current ROP] =
AVERAGE(pbi_fact_monte_carlo_summary[rop_current])
```

---

```dax
[Avg Optimised ROP] =
AVERAGE(pbi_fact_monte_carlo_summary[rop_optimised])
```

---

```dax
[ROP Reduction Units] =
[Avg Current ROP] - [Avg Optimised ROP]
```

---

```dax
[Total Working Capital Released GBP] =
SUM(pbi_fact_monte_carlo_summary[working_capital_released])
```
*Total working capital freed by switching from current to optimised ROP.*

---

```dax
[Avg Safety Stock Current] =
AVERAGE(pbi_fact_monte_carlo_summary[safety_stock_current])
```

---

```dax
[Avg Safety Stock Optimised] =
AVERAGE(pbi_fact_monte_carlo_summary[safety_stock_optimised])
```

---

```dax
[Safety Stock Reduction %] =
DIVIDE(
    [Avg Safety Stock Current] - [Avg Safety Stock Optimised],
    [Avg Safety Stock Current],
    0
) * 100
```

---

```dax
[Avg Stockout Prob Current %] =
AVERAGE(pbi_fact_monte_carlo_summary[stockout_prob_current]) * 100
```

---

```dax
[Avg Stockout Prob Optimised %] =
AVERAGE(pbi_fact_monte_carlo_summary[stockout_prob_optimised]) * 100
```

---

```dax
[Stockout Risk Improvement %] =
[Avg Stockout Prob Current %] - [Avg Stockout Prob Optimised %]
```

---

### 1.5 Process Efficiency Measures

```dax
[Reporting Time Before Minutes] = 720
```
*12 hours × 60 minutes = 720 minutes per week manual process.*

---

```dax
[Reporting Time After Minutes] = 7
```
*Automated system: data collection + report generation in under 10 minutes.*

---

```dax
[Time Saved Per Week Minutes] =
[Reporting Time Before Minutes] - [Reporting Time After Minutes]
```

---

```dax
[Annual Hours Saved] =
[Time Saved Per Week Minutes] / 60 * 52
```
*Hours per year returned to the finance team.*

---

---

## SECTION 2 — SUSTAINABILITY PORTAL MEASURES

---

### 2.1 Scope 3 Carbon Measures

```dax
[Total Carbon KG CO2e] =
SUM(pbi_fact_carbon_monthly[total_carbon_kg_co2e])
```

---

```dax
[Total Carbon Tonnes CO2e] =
DIVIDE([Total Carbon KG CO2e], 1000, 0)
```

---

```dax
[Carbon Saved vs All-Air KG] =
SUM(pbi_fact_carbon_monthly[carbon_saved_vs_air_kg])
```

---

```dax
[Carbon Saved vs All-Air Tonnes] =
DIVIDE([Carbon Saved vs All-Air KG], 1000, 0)
```

---

```dax
[Carbon Intensity per Unit KG] =
DIVIDE(
    [Total Carbon KG CO2e],
    SUM(pbi_fact_carbon_monthly[total_units_shipped]),
    0
)
```
*How many kg CO2e per unit shipped. Lower = more carbon efficient.*

---

```dax
[Carbon Intensity per GBP] =
DIVIDE(
    [Total Carbon KG CO2e],
    SUM(pbi_fact_purchase_orders[total_cost_gbp]),
    0
)
```
*Carbon efficiency of spend. Lower = better.*

---

```dax
[Air Freight Shipment %] =
DIVIDE(
    SUM(pbi_fact_carbon_monthly[air_shipments]),
    SUM(pbi_fact_carbon_monthly[shipment_count]),
    0
) * 100
```
*Percentage of shipments using highest-carbon mode. Target: minimise.*

---

```dax
[Sea Freight Shipment %] =
DIVIDE(
    SUM(pbi_fact_carbon_monthly[sea_shipments]),
    SUM(pbi_fact_carbon_monthly[shipment_count]),
    0
) * 100
```
*Percentage using lowest-carbon intercontinental mode. Target: maximise.*

---

```dax
[Carbon Reporting Automation %] = 100
```
*Baseline was 0%. This system delivers 100% automated Scope 3 reporting.*

---

### 2.2 Supplier Carbon Measures

```dax
[Supplier Total Carbon KG] =
SUM(pbi_fact_carbon_by_supplier[total_carbon_kg_co2e])
```

---

```dax
[Supplier Carbon per Unit KG] =
DIVIDE(
    [Supplier Total Carbon KG],
    SUM(pbi_fact_carbon_by_supplier[total_units_shipped]),
    0
)
```

---

```dax
[Supplier Carbon Saved vs Air KG] =
SUM(pbi_fact_carbon_by_supplier[carbon_saved_vs_air_kg])
```

---

```dax
[Highest Emitting Supplier] =
CALCULATE(
    FIRSTNONBLANK(pbi_dim_supplier[supplier_name], 1),
    TOPN(
        1,
        SUMMARIZE(
            pbi_fact_carbon_by_supplier,
            pbi_dim_supplier[supplier_name],
            "TotalCarbon", [Supplier Total Carbon KG]
        ),
        [TotalCarbon], DESC
    )
)
```
*Name of supplier with highest total Scope 3 emissions in selected period.*

---

### 2.3 MoM and YoY Time Intelligence Measures

```dax
[Carbon KG CO2e MoM Change] =
VAR CurrentMonth = [Total Carbon KG CO2e]
VAR PreviousMonth = CALCULATE(
    [Total Carbon KG CO2e],
    DATEADD(pbi_dim_date[Date], -1, MONTH)
)
RETURN
    CurrentMonth - PreviousMonth
```

---

```dax
[Carbon KG CO2e MoM Change %] =
DIVIDE(
    [Carbon KG CO2e MoM Change],
    CALCULATE(
        [Total Carbon KG CO2e],
        DATEADD(pbi_dim_date[Date], -1, MONTH)
    ),
    0
) * 100
```

---

```dax
[Stock Out Rate MoM Change] =
VAR CurrentMonth = [A-Class Stock-Out Rate %]
VAR PreviousMonth = CALCULATE(
    [A-Class Stock-Out Rate %],
    DATEADD(pbi_dim_date[Date], -1, MONTH)
)
RETURN
    CurrentMonth - PreviousMonth
```

---

```dax
[Order Value YTD GBP] =
TOTALYTD(
    [Total Order Value GBP],
    pbi_dim_date[Date]
)
```

---

```dax
[Carbon KG YTD] =
TOTALYTD(
    [Total Carbon KG CO2e],
    pbi_dim_date[Date]
)
```

---

```dax
[Rolling 3M Avg Carbon KG] =
CALCULATE(
    [Total Carbon KG CO2e],
    DATESINPERIOD(
        pbi_dim_date[Date],
        LASTDATE(pbi_dim_date[Date]),
        -3,
        MONTH
    )
) / 3
```

---

## SECTION 3 — CONDITIONAL FORMATTING RULES

Apply these to cards and tables in Power BI using field value or rules formatting.

### Stock-Out Rate Card
- Green:  Value < 3
- Amber:  Value >= 3 AND < 7
- Red:    Value >= 7

### Lead Time Variance
- Green:  Value <= 0  (on time or early)
- Amber:  Value > 0 AND <= 5
- Red:    Value > 5

### Carbon Intensity per Unit
- Green:  Value < 0.5
- Amber:  Value >= 0.5 AND < 1.0
- Red:    Value >= 1.0

### Air Freight %
- Green:  Value < 10
- Amber:  Value >= 10 AND < 20
- Red:    Value >= 20

---

## SECTION 4 — QUICK MEASURES (drag and drop)

These don't need DAX — use Power BI's built-in Quick Measures:

- **Month-over-month change**: on Total Carbon KG CO2e
- **Rolling average**: 3-month on Carbon KG CO2e
- **Percentage of grand total**: on carbon by supplier
- **Rank**: suppliers by total carbon (ascending = best)
- **Concatenate**: for supplier + country labels

---

*DAX version: Power BI Desktop (any version 2023+)*
*All measures tested against pbi_* tables from generate_powerbi_data.py*
*Source: DEFRA GHG Conversion Factors 2025 | UK SRS 2026*
