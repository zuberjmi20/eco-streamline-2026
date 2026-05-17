-- =============================================================================
-- ECO-STREAMLINE 2026 | Apex Distribution UK
-- FILE: 01_star_schema.sql
-- PURPOSE: Full relational Star Schema — Single Source of Truth
-- DATABASE: PostgreSQL 15+
-- AUTHOR: Lead Business Transformation Analyst
-- =============================================================================
-- SCHEMA OVERVIEW
--
-- DIMENSION TABLES (descriptive, slowly changing):
--   dim_date             — Calendar dimension with UK fiscal periods
--   dim_product          — 50 products with ABC classification
--   dim_supplier         — 8 suppliers with lead time profiles
--   dim_warehouse        — 3 UK warehouse locations
--   dim_transport_mode   — 4 modes with DEFRA carbon factors
--
-- FACT TABLES (transactional, high volume):
--   fact_purchase_orders     — Every inbound order from suppliers
--   fact_inventory_snapshots — Monthly stock positions per product/warehouse
--   fact_carbon_events       — Scope 3 emissions per shipment (UK SRS)
--
-- BRIDGE TABLE:
--   bridge_supplier_product  — Many-to-many: products to suppliers
--
-- STAGING TABLES (ETL landing zone — dirty data lands here first):
--   stg_supplier_feed        — Raw ingest from supplier CSVs
--   stg_validation_errors    — Quarantine for failed validation
-- =============================================================================

-- -----------------------------------------------------------------------------
-- SETUP
-- -----------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS apex;
SET search_path TO apex, public;

-- Clean slate for development (comment out in production)
DROP TABLE IF EXISTS fact_carbon_events         CASCADE;
DROP TABLE IF EXISTS fact_inventory_snapshots   CASCADE;
DROP TABLE IF EXISTS fact_purchase_orders       CASCADE;
DROP TABLE IF EXISTS bridge_supplier_product    CASCADE;
DROP TABLE IF EXISTS stg_validation_errors      CASCADE;
DROP TABLE IF EXISTS stg_supplier_feed          CASCADE;
DROP TABLE IF EXISTS ref_shipping_distances     CASCADE;
DROP TABLE IF EXISTS dim_transport_mode         CASCADE;
DROP TABLE IF EXISTS dim_warehouse              CASCADE;
DROP TABLE IF EXISTS dim_supplier               CASCADE;
DROP TABLE IF EXISTS dim_product                CASCADE;
DROP TABLE IF EXISTS dim_date                   CASCADE;


-- =============================================================================
-- DIMENSION TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- dim_date — Calendar dimension
-- Pre-populated for 2024-2026 covering simulation + forecast period
-- -----------------------------------------------------------------------------
CREATE TABLE dim_date (
    date_key                INTEGER         PRIMARY KEY,  -- YYYYMMDD e.g. 20240115
    full_date               DATE            NOT NULL UNIQUE,
    day_of_week             SMALLINT        NOT NULL,     -- 1=Monday 7=Sunday
    day_name                VARCHAR(10)     NOT NULL,
    day_of_month            SMALLINT        NOT NULL,
    day_of_year             SMALLINT        NOT NULL,
    week_of_year            SMALLINT        NOT NULL,
    month_number            SMALLINT        NOT NULL,
    month_name              VARCHAR(10)     NOT NULL,
    month_short             CHAR(3)         NOT NULL,
    quarter_number          SMALLINT        NOT NULL,
    quarter_name            CHAR(2)         NOT NULL,
    year_number             SMALLINT        NOT NULL,
    is_weekend              BOOLEAN         NOT NULL DEFAULT FALSE,
    is_uk_bank_holiday      BOOLEAN         NOT NULL DEFAULT FALSE,
    seasonal_multiplier     DECIMAL(4,2)    NOT NULL DEFAULT 1.00,
    fiscal_year             SMALLINT        NOT NULL,
    fiscal_quarter          SMALLINT        NOT NULL,
    fiscal_month            SMALLINT        NOT NULL
);

COMMENT ON TABLE  dim_date IS 'Calendar dimension 2024-2026. seasonal_multiplier drives demand modelling.';
COMMENT ON COLUMN dim_date.seasonal_multiplier IS 'Jan=0.75 to Dec=1.50 per Phase 0 business rules.';

-- Populate dim_date for 2024-01-01 to 2026-12-31
INSERT INTO dim_date
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER                             AS date_key,
    d::DATE                                                      AS full_date,
    EXTRACT(ISODOW  FROM d)::SMALLINT                            AS day_of_week,
    TO_CHAR(d, 'Day')                                            AS day_name,
    EXTRACT(DAY     FROM d)::SMALLINT                            AS day_of_month,
    EXTRACT(DOY     FROM d)::SMALLINT                            AS day_of_year,
    EXTRACT(WEEK    FROM d)::SMALLINT                            AS week_of_year,
    EXTRACT(MONTH   FROM d)::SMALLINT                            AS month_number,
    TO_CHAR(d, 'Month')                                          AS month_name,
    TO_CHAR(d, 'Mon')                                            AS month_short,
    EXTRACT(QUARTER FROM d)::SMALLINT                            AS quarter_number,
    'Q' || EXTRACT(QUARTER FROM d)::TEXT                         AS quarter_name,
    EXTRACT(YEAR    FROM d)::SMALLINT                            AS year_number,
    EXTRACT(ISODOW  FROM d) IN (6,7)                             AS is_weekend,
    FALSE                                                        AS is_uk_bank_holiday,
    CASE EXTRACT(MONTH FROM d)::INTEGER
        WHEN 1  THEN 0.75   WHEN 2  THEN 0.80   WHEN 3  THEN 0.90
        WHEN 4  THEN 0.95   WHEN 5  THEN 1.00   WHEN 6  THEN 1.05
        WHEN 7  THEN 1.10   WHEN 8  THEN 1.05   WHEN 9  THEN 1.00
        WHEN 10 THEN 1.10   WHEN 11 THEN 1.35   WHEN 12 THEN 1.50
    END                                                          AS seasonal_multiplier,
    CASE WHEN EXTRACT(MONTH FROM d) >= 4
         THEN EXTRACT(YEAR  FROM d)::SMALLINT
         ELSE (EXTRACT(YEAR FROM d) - 1)::SMALLINT
    END                                                          AS fiscal_year,
    CASE
        WHEN EXTRACT(MONTH FROM d) IN (4,5,6)    THEN 1
        WHEN EXTRACT(MONTH FROM d) IN (7,8,9)    THEN 2
        WHEN EXTRACT(MONTH FROM d) IN (10,11,12) THEN 3
        ELSE 4
    END                                                          AS fiscal_quarter,
    CASE WHEN EXTRACT(MONTH FROM d) >= 4
         THEN (EXTRACT(MONTH FROM d) - 3)::SMALLINT
         ELSE (EXTRACT(MONTH FROM d) + 9)::SMALLINT
    END                                                          AS fiscal_month
FROM GENERATE_SERIES('2024-01-01'::DATE, '2026-12-31'::DATE, '1 day'::INTERVAL) AS d;

-- UK Bank Holidays 2024-2026
UPDATE dim_date SET is_uk_bank_holiday = TRUE
WHERE full_date IN (
    '2024-01-01','2024-03-29','2024-04-01','2024-05-06',
    '2024-05-27','2024-08-26','2024-12-25','2024-12-26',
    '2025-01-01','2025-04-18','2025-04-21','2025-05-05',
    '2025-05-26','2025-08-25','2025-12-25','2025-12-26',
    '2026-01-01','2026-04-03','2026-04-06','2026-05-04',
    '2026-05-25','2026-08-31','2026-12-25','2026-12-28'
);


-- -----------------------------------------------------------------------------
-- dim_product — Product master with ABC classification
-- -----------------------------------------------------------------------------
CREATE TABLE dim_product (
    product_id              VARCHAR(10)     PRIMARY KEY,
    product_name            VARCHAR(150)    NOT NULL,
    category_code           CHAR(3)         NOT NULL,
    category_name           VARCHAR(50)     NOT NULL,
    abc_class               CHAR(1)         NOT NULL CHECK (abc_class IN ('A','B','C')),
    unit_cost_gbp           DECIMAL(10,2)   NOT NULL CHECK (unit_cost_gbp > 0),
    unit_price_gbp          DECIMAL(10,2)   NOT NULL CHECK (unit_price_gbp > 0),
    gross_margin_pct        DECIMAL(5,2)    NOT NULL,
    weight_kg               DECIMAL(8,3)    NOT NULL CHECK (weight_kg > 0),
    min_order_qty           INTEGER         NOT NULL CHECK (min_order_qty > 0),
    shelf_life_days         INTEGER         NULL,
    service_level_target    DECIMAL(4,2)    NOT NULL CHECK (service_level_target BETWEEN 0.5 AND 1.0),
    z_score                 DECIMAL(5,3)    NOT NULL DEFAULT 1.65,
    is_active               BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  dim_product IS '50 products across 5 categories. ABC class drives service levels and reorder logic.';
COMMENT ON COLUMN dim_product.abc_class IS 'A=top 80pct revenue (never stock-out) | B=next 15pct | C=bottom 5pct (reduce excess)';
COMMENT ON COLUMN dim_product.z_score IS 'A=1.65 (95pct SL) | B=1.28 (90pct SL) | C=1.04 (85pct SL). Used in Monte Carlo.';

CREATE OR REPLACE FUNCTION apex.fn_set_product_z_score()
RETURNS TRIGGER AS $$
BEGIN
    NEW.z_score := CASE NEW.abc_class
        WHEN 'A' THEN 1.65
        WHEN 'B' THEN 1.28
        WHEN 'C' THEN 1.04
        ELSE 1.28
    END;
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_product_z_score
    BEFORE INSERT OR UPDATE ON dim_product
    FOR EACH ROW EXECUTE FUNCTION apex.fn_set_product_z_score();


-- -----------------------------------------------------------------------------
-- dim_supplier — Supplier master with lead time distribution parameters
-- -----------------------------------------------------------------------------
CREATE TABLE dim_supplier (
    supplier_id                 VARCHAR(10)     PRIMARY KEY,
    supplier_name               VARCHAR(100)    NOT NULL UNIQUE,
    country_of_origin           VARCHAR(50)     NOT NULL,
    region                      VARCHAR(20)     NOT NULL
                                CHECK (region IN ('DOMESTIC','EUROPEAN','INTERCONTINENTAL')),
    primary_transport           CHAR(4)         NOT NULL
                                CHECK (primary_transport IN ('ROAD','SEA','AIR','RAIL')),
    secondary_transport         CHAR(4)         NULL
                                CHECK (secondary_transport IN ('ROAD','SEA','AIR','RAIL')),
    lead_time_min_days          SMALLINT        NOT NULL,
    lead_time_max_days          SMALLINT        NOT NULL,
    lead_time_avg_days          DECIMAL(5,1)    NOT NULL,
    lead_time_std_days          DECIMAL(5,2)    NOT NULL,
    lead_time_distribution      VARCHAR(10)     NOT NULL
                                CHECK (lead_time_distribution IN ('normal','lognormal')),
    spike_probability           DECIMAL(4,2)    NOT NULL DEFAULT 0.05
                                CHECK (spike_probability BETWEEN 0 AND 1),
    reliability_score           DECIMAL(4,2)    NOT NULL
                                CHECK (reliability_score BETWEEN 0 AND 1),
    payment_terms_days          SMALLINT        NOT NULL,
    is_active                   BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_lead_time_range CHECK (lead_time_min_days < lead_time_max_days)
);

COMMENT ON TABLE  dim_supplier IS '8 suppliers across 3 regions. Lead time params feed Monte Carlo simulation.';
COMMENT ON COLUMN dim_supplier.spike_probability IS '2026 shipping disruption spike probability. Intercontinental = 12-15pct.';
COMMENT ON COLUMN dim_supplier.lead_time_distribution IS 'normal=domestic/EU | lognormal=intercontinental (right-skewed).';


-- -----------------------------------------------------------------------------
-- dim_warehouse — UK warehouse locations
-- -----------------------------------------------------------------------------
CREATE TABLE dim_warehouse (
    warehouse_id            VARCHAR(6)      PRIMARY KEY,
    warehouse_name          VARCHAR(50)     NOT NULL,
    location                VARCHAR(50)     NOT NULL,
    warehouse_type          VARCHAR(15)     NOT NULL
                            CHECK (warehouse_type IN ('PRIMARY_DC','REGIONAL_HUB')),
    capacity_pallets        INTEGER         NOT NULL,
    monthly_cost_gbp        DECIMAL(10,2)   NOT NULL,
    latitude                DECIMAL(9,6)    NULL,
    longitude               DECIMAL(9,6)    NULL,
    is_active               BOOLEAN         NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE dim_warehouse IS '3 UK sites: Coventry (primary), Manchester, Bristol. Cost feeds working capital dashboard.';


-- -----------------------------------------------------------------------------
-- dim_transport_mode — Transport modes with DEFRA carbon factors
-- -----------------------------------------------------------------------------
CREATE TABLE dim_transport_mode (
    mode_code                   CHAR(4)         PRIMARY KEY,
    mode_name                   VARCHAR(30)     NOT NULL,
    kg_co2e_per_tonne_km        DECIMAL(6,4)    NOT NULL,
    relative_cost_index         DECIMAL(5,2)    NOT NULL,
    avg_speed_kmh               SMALLINT        NOT NULL,
    suitable_for_regions        VARCHAR(60)     NOT NULL,
    defra_source                VARCHAR(60)     NOT NULL DEFAULT 'DEFRA GHG Conversion Factors 2025'
);

COMMENT ON TABLE  dim_transport_mode IS 'DEFRA 2025 emission factors. kg_co2e_per_tonne_km drives all Scope 3 carbon calculations.';
COMMENT ON COLUMN dim_transport_mode.kg_co2e_per_tonne_km IS 'ROAD=0.10 | RAIL=0.028 | SEA=0.016 | AIR=0.602';


-- =============================================================================
-- BRIDGE TABLE
-- =============================================================================

CREATE TABLE bridge_supplier_product (
    bridge_id                   SERIAL          PRIMARY KEY,
    product_id                  VARCHAR(10)     NOT NULL REFERENCES dim_product(product_id),
    supplier_id                 VARCHAR(10)     NOT NULL REFERENCES dim_supplier(supplier_id),
    is_primary                  BOOLEAN         NOT NULL DEFAULT TRUE,
    lead_time_override_days     SMALLINT        NULL,
    created_at                  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_supplier UNIQUE (product_id, supplier_id)
);

COMMENT ON TABLE bridge_supplier_product IS 'Each product has 1 primary and optionally 1 secondary supplier.';


-- =============================================================================
-- REFERENCE TABLE — Shipping Distance Matrix
-- =============================================================================

CREATE TABLE ref_shipping_distances (
    route_id                SERIAL          PRIMARY KEY,
    origin_country          VARCHAR(50)     NOT NULL,
    destination             VARCHAR(10)     NOT NULL DEFAULT 'UK',
    transport_mode          CHAR(4)         NOT NULL REFERENCES dim_transport_mode(mode_code),
    distance_km             DECIMAL(10,2)   NOT NULL,
    CONSTRAINT uq_route UNIQUE (origin_country, destination, transport_mode)
);

COMMENT ON TABLE ref_shipping_distances IS 'Distance matrix for Scope 3 carbon calculation: weight_tonnes * distance_km * emission_factor.';


-- =============================================================================
-- FACT TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- fact_purchase_orders — Every inbound purchase order
-- -----------------------------------------------------------------------------
CREATE TABLE fact_purchase_orders (
    order_sk                    BIGSERIAL       PRIMARY KEY,
    order_id                    VARCHAR(12)     NOT NULL UNIQUE,
    product_id                  VARCHAR(10)     NOT NULL REFERENCES dim_product(product_id),
    supplier_id                 VARCHAR(10)     NOT NULL REFERENCES dim_supplier(supplier_id),
    warehouse_id                VARCHAR(6)      NOT NULL REFERENCES dim_warehouse(warehouse_id),
    order_date_key              INTEGER         NOT NULL REFERENCES dim_date(date_key),
    expected_delivery_key       INTEGER         NOT NULL REFERENCES dim_date(date_key),
    actual_delivery_key         INTEGER         NULL     REFERENCES dim_date(date_key),
    quantity_ordered            INTEGER         NOT NULL CHECK (quantity_ordered > 0),
    unit_cost_gbp               DECIMAL(10,2)   NOT NULL CHECK (unit_cost_gbp > 0),
    total_cost_gbp              DECIMAL(12,2)   NOT NULL,
    lead_time_days              SMALLINT        NOT NULL CHECK (lead_time_days > 0),
    lead_time_variance_days     SMALLINT        NULL,
    transport_mode              CHAR(4)         NOT NULL REFERENCES dim_transport_mode(mode_code),
    weight_kg_total             DECIMAL(10,2)   NOT NULL,
    is_urgent_order             BOOLEAN         NOT NULL DEFAULT FALSE,
    order_status                VARCHAR(12)     NOT NULL
                                CHECK (order_status IN ('DELIVERED','IN_TRANSIT','CANCELLED')),
    source_file                 VARCHAR(100)    NULL,
    loaded_at                   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  fact_purchase_orders IS 'Core transactional fact. One row per purchase order. Basis for carbon events and supplier performance.';
COMMENT ON COLUMN fact_purchase_orders.is_urgent_order IS 'Secondary/faster transport used to prevent stock-out. High frequency signals Green-ROP is needed.';
COMMENT ON COLUMN fact_purchase_orders.lead_time_variance_days IS 'Actual minus expected delivery. Feeds Monte Carlo calibration.';

CREATE OR REPLACE FUNCTION apex.fn_calc_order_derived()
RETURNS TRIGGER AS $$
BEGIN
    NEW.total_cost_gbp := NEW.quantity_ordered * NEW.unit_cost_gbp;
    IF NEW.actual_delivery_key IS NOT NULL THEN
        NEW.lead_time_variance_days :=
            (SELECT full_date FROM dim_date WHERE date_key = NEW.actual_delivery_key) -
            (SELECT full_date FROM dim_date WHERE date_key = NEW.expected_delivery_key);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_derived
    BEFORE INSERT OR UPDATE ON fact_purchase_orders
    FOR EACH ROW EXECUTE FUNCTION apex.fn_calc_order_derived();


-- -----------------------------------------------------------------------------
-- fact_inventory_snapshots — Monthly stock position per product per warehouse
-- -----------------------------------------------------------------------------
CREATE TABLE fact_inventory_snapshots (
    snapshot_sk                 BIGSERIAL       PRIMARY KEY,
    snapshot_date_key           INTEGER         NOT NULL REFERENCES dim_date(date_key),
    product_id                  VARCHAR(10)     NOT NULL REFERENCES dim_product(product_id),
    warehouse_id                VARCHAR(6)      NOT NULL REFERENCES dim_warehouse(warehouse_id),
    stock_on_hand               INTEGER         NOT NULL DEFAULT 0,
    stock_cover_days            DECIMAL(8,1)    NOT NULL DEFAULT 0,
    avg_daily_demand            DECIMAL(10,2)   NOT NULL DEFAULT 0,
    reorder_point_current       INTEGER         NULL,
    reorder_point_optimised     INTEGER         NULL,
    safety_stock_current        INTEGER         NULL,
    safety_stock_optimised      INTEGER         NULL,
    is_stock_out                BOOLEAN         NOT NULL DEFAULT FALSE,
    is_slow_mover               BOOLEAN         NOT NULL DEFAULT FALSE,
    is_at_risk                  BOOLEAN         NOT NULL DEFAULT FALSE,
    is_below_rop                BOOLEAN         NOT NULL DEFAULT FALSE,
    stock_value_gbp             DECIMAL(12,2)   NOT NULL DEFAULT 0,
    excess_stock_value_gbp      DECIMAL(12,2)   NOT NULL DEFAULT 0,
    abc_class                   CHAR(1)         NOT NULL,
    loaded_at                   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_snapshot UNIQUE (snapshot_date_key, product_id, warehouse_id)
);

COMMENT ON TABLE  fact_inventory_snapshots IS 'Monthly stock positions. Core for CFO dashboard and working capital KPIs.';
COMMENT ON COLUMN fact_inventory_snapshots.reorder_point_optimised IS 'Populated by Phase 3 Green-ROP Python engine. NULL until Phase 3 runs.';
COMMENT ON COLUMN fact_inventory_snapshots.excess_stock_value_gbp  IS 'Value beyond 90-day cover for C-class. Target: reduce by 15pct (save GBP 42k).';


-- -----------------------------------------------------------------------------
-- fact_carbon_events — Scope 3 Category 4 emissions per shipment (UK SRS)
-- -----------------------------------------------------------------------------
CREATE TABLE fact_carbon_events (
    carbon_sk                   BIGSERIAL       PRIMARY KEY,
    order_id                    VARCHAR(12)     NOT NULL REFERENCES fact_purchase_orders(order_id),
    product_id                  VARCHAR(10)     NOT NULL REFERENCES dim_product(product_id),
    supplier_id                 VARCHAR(10)     NOT NULL REFERENCES dim_supplier(supplier_id),
    shipment_date_key           INTEGER         NOT NULL REFERENCES dim_date(date_key),
    transport_mode              CHAR(4)         NOT NULL REFERENCES dim_transport_mode(mode_code),
    weight_kg                   DECIMAL(10,2)   NOT NULL CHECK (weight_kg > 0),
    weight_tonnes               DECIMAL(10,4)   NOT NULL,
    distance_km                 DECIMAL(10,2)   NOT NULL CHECK (distance_km > 0),
    kg_co2e_per_tonne_km        DECIMAL(6,4)    NOT NULL,
    -- Derived by trigger: weight_tonnes * distance_km * kg_co2e_per_tonne_km
    carbon_kg_co2e              DECIMAL(12,4)   NOT NULL DEFAULT 0,
    carbon_kg_co2e_per_unit     DECIMAL(10,6)   NOT NULL DEFAULT 0,
    quantity_units              INTEGER         NOT NULL,
    scope_category              SMALLINT        NOT NULL DEFAULT 4,
    reporting_period            CHAR(7)         NOT NULL DEFAULT '2024-01',
    is_reported                 BOOLEAN         NOT NULL DEFAULT FALSE,
    reported_at                 TIMESTAMP       NULL,
    loaded_at                   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  fact_carbon_events IS 'Scope 3 Cat 4 per shipment. Exported monthly to satisfy Tesco and John Lewis UK SRS mandate.';
COMMENT ON COLUMN fact_carbon_events.carbon_kg_co2e IS 'Auto-calculated: weight_tonnes * distance_km * kg_co2e_per_tonne_km (DEFRA 2025).';

CREATE OR REPLACE FUNCTION apex.fn_calc_carbon()
RETURNS TRIGGER AS $$
BEGIN
    NEW.weight_tonnes           := NEW.weight_kg / 1000.0;
    NEW.carbon_kg_co2e          := ROUND(NEW.weight_tonnes * NEW.distance_km * NEW.kg_co2e_per_tonne_km, 4);
    NEW.carbon_kg_co2e_per_unit := CASE
        WHEN NEW.quantity_units > 0 THEN ROUND(NEW.carbon_kg_co2e / NEW.quantity_units, 6)
        ELSE 0
    END;
    NEW.reporting_period := TO_CHAR(
        (SELECT full_date FROM dim_date WHERE date_key = NEW.shipment_date_key),
        'YYYY-MM'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_carbon_calc
    BEFORE INSERT OR UPDATE ON fact_carbon_events
    FOR EACH ROW EXECUTE FUNCTION apex.fn_calc_carbon();


-- =============================================================================
-- STAGING TABLES — ETL Landing Zone
-- =============================================================================

CREATE TABLE stg_supplier_feed (
    stg_id                  BIGSERIAL       PRIMARY KEY,
    raw_order_id            VARCHAR(50)     NULL,
    raw_supplier_name       VARCHAR(150)    NULL,
    raw_product_id          VARCHAR(50)     NULL,
    raw_product_name        VARCHAR(200)    NULL,
    raw_quantity            VARCHAR(20)     NULL,
    raw_unit_cost           VARCHAR(20)     NULL,
    raw_order_date          VARCHAR(30)     NULL,
    raw_expected_delivery   VARCHAR(30)     NULL,
    raw_actual_delivery     VARCHAR(30)     NULL,
    raw_transport_mode      VARCHAR(20)     NULL,
    raw_weight_kg           VARCHAR(20)     NULL,
    source_file             VARCHAR(100)    NOT NULL,
    batch_id                VARCHAR(50)     NOT NULL,
    ingested_at             TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    validation_status       VARCHAR(10)     NOT NULL DEFAULT 'PENDING'
                            CHECK (validation_status IN ('PENDING','CLEAN','DIRTY','QUARANTINE')),
    error_types             TEXT[]          NULL,
    processed_at            TIMESTAMP       NULL
);

COMMENT ON TABLE stg_supplier_feed IS 'Raw landing zone. All fields VARCHAR to accept dirty data without rejection. ETL validates and transforms.';


CREATE TABLE stg_validation_errors (
    error_id                BIGSERIAL       PRIMARY KEY,
    stg_id                  BIGINT          NOT NULL REFERENCES stg_supplier_feed(stg_id),
    batch_id                VARCHAR(50)     NOT NULL,
    error_type              VARCHAR(40)     NOT NULL,
    error_field             VARCHAR(40)     NOT NULL,
    raw_value               TEXT            NULL,
    expected_format         TEXT            NULL,
    error_description       TEXT            NOT NULL,
    severity                VARCHAR(8)      NOT NULL CHECK (severity IN ('ERROR','WARNING','INFO')),
    is_resolved             BOOLEAN         NOT NULL DEFAULT FALSE,
    resolved_at             TIMESTAMP       NULL,
    resolved_by             VARCHAR(50)     NULL,
    logged_at               TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stg_validation_errors IS 'Validation failures quarantined here. Ops team reviews. Feeds data quality report.';


-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX idx_po_product         ON fact_purchase_orders(product_id);
CREATE INDEX idx_po_supplier        ON fact_purchase_orders(supplier_id);
CREATE INDEX idx_po_order_date      ON fact_purchase_orders(order_date_key);
CREATE INDEX idx_po_status          ON fact_purchase_orders(order_status);
CREATE INDEX idx_po_urgent          ON fact_purchase_orders(is_urgent_order) WHERE is_urgent_order = TRUE;

CREATE INDEX idx_inv_product        ON fact_inventory_snapshots(product_id);
CREATE INDEX idx_inv_date           ON fact_inventory_snapshots(snapshot_date_key);
CREATE INDEX idx_inv_stockout       ON fact_inventory_snapshots(is_stock_out)  WHERE is_stock_out  = TRUE;
CREATE INDEX idx_inv_slowmover      ON fact_inventory_snapshots(is_slow_mover) WHERE is_slow_mover = TRUE;
CREATE INDEX idx_inv_abc            ON fact_inventory_snapshots(abc_class);

CREATE INDEX idx_carbon_supplier    ON fact_carbon_events(supplier_id);
CREATE INDEX idx_carbon_period      ON fact_carbon_events(reporting_period);
CREATE INDEX idx_carbon_mode        ON fact_carbon_events(transport_mode);
CREATE INDEX idx_carbon_reported    ON fact_carbon_events(is_reported);

CREATE INDEX idx_stg_batch          ON stg_supplier_feed(batch_id);
CREATE INDEX idx_stg_status         ON stg_supplier_feed(validation_status);
CREATE INDEX idx_err_batch          ON stg_validation_errors(batch_id);
CREATE INDEX idx_err_resolved       ON stg_validation_errors(is_resolved);


-- =============================================================================
-- ANALYTICAL VIEWS
-- =============================================================================

-- CFO Dashboard: Working capital by month and ABC class
CREATE OR REPLACE VIEW vw_working_capital AS
SELECT
    d.year_number,
    d.month_number,
    d.month_name,
    d.quarter_name,
    p.abc_class,
    p.category_name,
    COUNT(*)                                                        AS product_count,
    SUM(i.stock_value_gbp)                                          AS total_stock_value_gbp,
    SUM(i.excess_stock_value_gbp)                                   AS excess_stock_value_gbp,
    SUM(CASE WHEN i.is_slow_mover THEN i.stock_value_gbp  ELSE 0 END) AS slow_mover_value_gbp,
    SUM(CASE WHEN i.is_stock_out  THEN 1                  ELSE 0 END) AS stockout_count,
    SUM(CASE WHEN i.is_at_risk    THEN 1                  ELSE 0 END) AS at_risk_count
FROM fact_inventory_snapshots i
JOIN dim_date    d ON d.date_key   = i.snapshot_date_key
JOIN dim_product p ON p.product_id = i.product_id
GROUP BY 1,2,3,4,5,6;

COMMENT ON VIEW vw_working_capital IS 'CFO Dashboard: monthly working capital by ABC class. Baseline excess = GBP280k. Target -15pct.';


-- Sustainability Portal: UK SRS Scope 3 report by supplier and month
CREATE OR REPLACE VIEW vw_scope3_report AS
SELECT
    ce.reporting_period,
    s.supplier_name,
    s.country_of_origin,
    s.region,
    ce.transport_mode,
    tm.mode_name,
    p.category_name,
    COUNT(*)                                            AS shipment_count,
    SUM(ce.weight_kg)                                   AS total_weight_kg,
    ROUND(SUM(ce.carbon_kg_co2e), 2)                    AS total_carbon_kg_co2e,
    ROUND(SUM(ce.carbon_kg_co2e) / 1000.0, 4)          AS total_carbon_tonnes_co2e,
    SUM(ce.quantity_units)                              AS total_units_shipped,
    ROUND(AVG(ce.carbon_kg_co2e_per_unit), 6)           AS avg_carbon_per_unit_kg
FROM fact_carbon_events    ce
JOIN dim_supplier          s  ON s.supplier_id  = ce.supplier_id
JOIN dim_transport_mode    tm ON tm.mode_code   = ce.transport_mode
JOIN dim_product           p  ON p.product_id   = ce.product_id
GROUP BY 1,2,3,4,5,6,7
ORDER BY 1, total_carbon_kg_co2e DESC;

COMMENT ON VIEW vw_scope3_report IS 'UK SRS Scope 3 Cat 4 report. Export monthly to Tesco and John Lewis. 100pct automated.';


-- Stock-out rate tracker by ABC class
CREATE OR REPLACE VIEW vw_stockout_rate AS
SELECT
    d.year_number,
    d.month_number,
    d.month_name,
    i.abc_class,
    COUNT(*)                                                            AS total_snapshots,
    SUM(CASE WHEN i.is_stock_out THEN 1 ELSE 0 END)                    AS stockout_count,
    ROUND(SUM(CASE WHEN i.is_stock_out THEN 1.0 ELSE 0 END)
          / NULLIF(COUNT(*), 0) * 100, 2)                              AS stockout_rate_pct
FROM fact_inventory_snapshots i
JOIN dim_date d ON d.date_key = i.snapshot_date_key
GROUP BY 1,2,3,4
ORDER BY 1,2,4;

COMMENT ON VIEW vw_stockout_rate IS 'Stock-out rate by ABC class and month. Baseline A-class=7pct. Target <3pct.';


-- Supplier lead time performance
CREATE OR REPLACE VIEW vw_supplier_performance AS
SELECT
    s.supplier_name,
    s.region,
    s.primary_transport,
    s.reliability_score,
    COUNT(*)                                                AS total_orders,
    ROUND(AVG(po.lead_time_days), 1)                        AS avg_actual_lead_time,
    s.lead_time_avg_days                                    AS expected_avg_lead_time,
    ROUND(AVG(po.lead_time_variance_days), 1)               AS avg_variance_days,
    MAX(po.lead_time_days)                                  AS max_lead_time_days,
    SUM(CASE WHEN po.is_urgent_order THEN 1 ELSE 0 END)     AS urgent_orders,
    ROUND(SUM(po.total_cost_gbp), 2)                        AS total_spend_gbp
FROM fact_purchase_orders po
JOIN dim_supplier         s ON s.supplier_id = po.supplier_id
WHERE po.order_status = 'DELIVERED'
GROUP BY s.supplier_name, s.region, s.primary_transport,
         s.reliability_score, s.lead_time_avg_days
ORDER BY avg_variance_days DESC;

COMMENT ON VIEW vw_supplier_performance IS 'Supplier reliability. High variance suppliers = Green-ROP air-freight candidates.';


-- =============================================================================
-- COMPLETION NOTICE
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '================================================';
    RAISE NOTICE ' ECO-STREAMLINE 2026 | Star Schema Deployed';
    RAISE NOTICE '================================================';
    RAISE NOTICE ' Dimensions : 5  (date, product, supplier, warehouse, transport)';
    RAISE NOTICE ' Facts      : 3  (purchase_orders, inventory_snapshots, carbon_events)';
    RAISE NOTICE ' Bridge     : 1  (supplier_product)';
    RAISE NOTICE ' Staging    : 2  (supplier_feed, validation_errors)';
    RAISE NOTICE ' Reference  : 1  (shipping_distances)';
    RAISE NOTICE ' Views      : 4  (working_capital, scope3, stockout_rate, supplier_perf)';
    RAISE NOTICE ' Triggers   : 3  (z_score, order_derived, carbon_calc)';
    RAISE NOTICE ' Indexes    : 16';
    RAISE NOTICE '================================================';
    RAISE NOTICE ' Next: 02_etl_pipeline.sql';
    RAISE NOTICE '================================================';
END $$;
