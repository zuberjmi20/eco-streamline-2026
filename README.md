# eco-streamline-2026
Production-grade inventory &amp; sustainability analytics system for UK wholesale distribution
Phase 0 — Business Rules & Data Contracts
Eco-Streamline 2026 | Apex Distribution UK
---
1. Company Profile (Simulation Parameters)
Parameter	Value	Rationale
Annual Turnover	£12,000,000	Per project brief
Excess Stock Tied Up	£280,000	Per project brief
Annual Storage Cost	£35,000	Per project brief
Stock-out Rate (A-list)	7%	Per project brief
Lost Sales (stock-outs)	£110,000	Per project brief
Reporting Cycle (current)	12 hours/week manual	Per project brief
Tier-1 Partners	Tesco, John Lewis	Per project brief
Compliance Deadline	Q4 2026	UK SRS mandate
---
2. Product Catalogue Rules
2.1 Product Categories
Category	Code	Count	Margin Profile	Demand Pattern
Household Essentials	HHE	15 products	Low margin, high volume	Stable year-round
Personal Care	PCA	12 products	Medium margin	Slight summer peak
Food & Beverage	FBV	10 products	Medium margin	Christmas peak (Nov-Dec)
Seasonal / Gifting	SGF	8 products	High margin	Strong Christmas peak
Cleaning Products	CLN	5 products	Low margin, high volume	Stable year-round
Total: 50 products
2.2 Product Classification (ABC Analysis)
Class	Label	% of Products	Criteria	Priority
A	A-list / High Value	20% (10 products)	Top 80% of revenue	Never stock out
B	Mid-tier	30% (15 products)	Next 15% of revenue	Manage carefully
C	Slow-movers	50% (25 products)	Bottom 5% of revenue	Reduce overstock
2.3 Product Master Fields
```
product_id          VARCHAR(10)     e.g. "PRD-00001"
product_name        VARCHAR(100)
category_code       VARCHAR(3)
abc_class           CHAR(1)         A / B / C
unit_cost_gbp       DECIMAL(10,2)   Purchase cost per unit
unit_price_gbp      DECIMAL(10,2)   Sale price per unit
weight_kg           DECIMAL(6,3)    Per unit — needed for carbon calc
min_order_qty       INTEGER         Supplier minimum
shelf_life_days     INTEGER         NULL if non-perishable
is_active           BOOLEAN
```
---
3. Supplier Rules
3.1 Supplier Profiles
Supplier ID	Name	Origin	Transport Modes	Reliability	Lead Time (days)
SUP-001	BritGoods Ltd	UK Domestic	Road	High	3–7
SUP-002	EuroFast GmbH	Germany	Road / Rail	High	7–12
SUP-003	AsiaSource Co	China	Sea / Air	Medium	18–35
SUP-004	IndiaManufact Pvt	India	Sea / Air	Medium	20–32
SUP-005	NordicSupply AS	Sweden	Road / Sea	High	8–14
SUP-006	MedTrade SRL	Italy	Road	Medium	10–18
SUP-007	USBrands Inc	USA	Air / Sea	Low	14–28
SUP-008	LocalPack Ltd	UK Domestic	Road	Very High	2–5
3.2 Supplier Lead Time Distribution (2026 Volatility Model)
Domestic (SUP-001, SUP-008): Normal distribution, low variance
European (SUP-002, SUP-005, SUP-006): Slightly right-skewed, occasional port delays
Intercontinental (SUP-003, SUP-004, SUP-007): Heavily right-skewed, spike probability 15%
Spike defined as: lead time exceeding 90th percentile by >40%
Reflects 2026 global shipping disruptions per project brief
3.3 Supplier Master Fields
```
supplier_id         VARCHAR(10)     e.g. "SUP-001"
supplier_name       VARCHAR(100)
country_of_origin   VARCHAR(50)
region              VARCHAR(20)     DOMESTIC / EUROPEAN / INTERCONTINENTAL
primary_transport   VARCHAR(20)     ROAD / SEA / AIR / RAIL
secondary_transport VARCHAR(20)     nullable
lead_time_min_days  INTEGER
lead_time_max_days  INTEGER
lead_time_avg_days  DECIMAL(5,1)
reliability_score   DECIMAL(3,2)    0.00 to 1.00
payment_terms_days  INTEGER         30 / 60 / 90
is_active           BOOLEAN
```
---
4. Warehouse Rules
4.1 Warehouse Profiles
Warehouse ID	Location	Type	Capacity (pallets)	Monthly Cost £
WH-001	Coventry	Primary DC	2,000	£18,000
WH-002	Manchester	Regional Hub	800	£7,500
WH-003	Bristol	Regional Hub	600	£6,000
Total monthly storage cost: £31,500 (£378,000/year — we use £35k for excess only)
---
5. Transport Mode Rules
5.1 Transport Modes & Carbon Factors
Source: UK DEFRA Greenhouse Gas Conversion Factors 2025 (public data)
Mode	Code	kg CO2e per tonne-km	Relative Cost	Speed
Road (HGV)	ROAD	0.10	Medium	Fast
Rail	RAIL	0.028	Low	Medium
Sea (Container)	SEA	0.016	Lowest	Slow
Air Freight	AIR	0.602	Highest	Fastest
5.2 Distance Matrix (approximate, km)
Route	Distance (km)
China → UK (Sea)	19,500
China → UK (Air)	9,200
India → UK (Sea)	11,000

India → UK (Air)	6,700
USA → UK (Air)	5,500
USA → UK (Sea)	6,800
Germany → UK (Road)	1,100
Sweden → UK (Road/Sea)	1,400
Italy → UK (Road)	1,800
UK Domestic (Road)	250
---
6. Demand Rules
6.1 Seasonal Demand Multipliers (by month)
Month	Multiplier	Driver
January	0.75	Post-Christmas slump
February	0.80	Low season
March	0.90	Spring pickup
April	0.95	Stable
May	1.00	Baseline
June	1.05	Summer start
July	1.10	Summer peak
August	1.05	Summer wind-down
September	1.00	Back-to-school
October	1.10	Pre-Christmas build
November	1.35	Black Friday / early Christmas
December	1.50	Christmas peak
6.2 Demand Distribution Model
Base demand: Poisson distribution (realistic for discrete unit sales)
A-class products: Higher mean, lower coefficient of variation
C-class products: Lower mean, higher coefficient of variation (unpredictable slow-movers)
Random spike events: 3% probability per week per product (promotional uplift)
---
7. Data Contract — Supplier Ingest CSV (Intentionally Dirty)
7.1 What clean supplier data SHOULD look like:
```
order_id, supplier_id, product_id, quantity, unit_cost, order_date, expected_delivery, actual_delivery, transport_mode, weight_kg_total
```
7.2 Errors intentionally injected (~12% dirty records):
Error Type	Frequency	Example
Supplier name inconsistency	4%	"AsiaSource Co" vs "ASIASOURCE" vs "Asia Source Co."
Date format mismatch	2%	"01/03/2026" vs "2026-03-01" vs "1-Mar-26"
Missing transport mode	2%	NULL or empty string
Negative quantity	1%	-24 (data entry error)
Unit cost outlier	1%	10x normal price (fat finger)
Duplicate order ID	1%	Same order_id, slightly different values
Product ID not in master	1%	"PRD-99999" — doesn't exist
7.3 ETL must:
Detect and flag all above error types
Quarantine dirty records to an error log table
Process clean records without interruption
Produce a data quality report per ingest run
---
8. Key Business Logic Rules
8.1 Reorder Point (Standard)
```
ROP = (Average Daily Demand × Lead Time) + Safety Stock
Safety Stock = Z-score × σ(demand) × √(lead time)
Z-score = 1.65 (95% service level for A-class)
Z-score = 1.28 (90% service level for B-class)
Z-score = 1.04 (85% service level for C-class)
```
8.2 Green-ROP Decision Logic
```
IF carbon_cost(AIR) - carbon_cost(SEA) > carbon_budget_threshold:
    RECOMMEND SEA unless:
        stockout_probability(SEA lead time) > 0.10 AND
        stockout_cost > air_freight_premium * 3
    THEN: flag for human decision with full cost/carbon breakdown
```
8.3 Scope 3 Carbon Calculation (per shipment)
```
carbon_kg_CO2e = weight_tonnes × distance_km × emission_factor(transport_mode)
carbon_kg_CO2e_per_unit = carbon_kg_CO2e / quantity_units
```
8.4 Working Capital Tied Up
```
working_capital_tied = slow_mover_units × unit_cost
slow_mover = product where stock_cover_days > 90
stock_cover_days = current_stock / avg_daily_demand
```
---
9. Simulation Period
Data range: 1 January 2024 — 31 December 2025 (2 full years)
Forecast period: 2026 Q1–Q4 (used in Monte Carlo)
Reporting baseline: 2025 full year
---
10. Success Metrics (How we'll prove ROI in the dashboard)
Metric	Baseline	Target	Measurement
Excess stock value	£280,000	£238,000 (-15%)	Working capital report
Stock-out rate (A-list)	7%	<3%	Fulfilment rate tracker
Carbon reporting	0% automated	100% automated	Scope 3 report generator
Weekly reporting time	12 hours	<10 minutes	Process log
Inventory turnover ratio	Calculated from data	Improved trend	CFO dashboard
