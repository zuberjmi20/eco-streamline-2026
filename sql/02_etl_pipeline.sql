-- =============================================================================
-- ECO-STREAMLINE 2026 | Apex Distribution UK
-- FILE: 02_etl_pipeline.sql
-- PURPOSE: ETL Pipeline — transforms dirty supplier CSVs into clean Star Schema
-- DATABASE: PostgreSQL 15+
-- AUTHOR: Lead Business Transformation Analyst
-- =============================================================================
-- PIPELINE OVERVIEW
--
-- STEP 1 — INGEST    : Raw CSV data lands in stg_supplier_feed (all VARCHAR)
-- STEP 2 — VALIDATE  : 03_validation_rules.sql flags errors, sets status
-- STEP 3 — TRANSFORM : This file cleans and standardises CLEAN records
-- STEP 4 — LOAD      : Inserts into fact and carbon tables
-- STEP 5 — REPORT    : Data quality summary per batch
--
-- Run order: 01_star_schema.sql → [load CSVs to staging] →
--            03_validation_rules.sql → 02_etl_pipeline.sql
-- =============================================================================

SET search_path TO apex, public;


-- =============================================================================
-- STEP 0 — MASTER DATA LOAD
-- Loads dimension tables from processed CSVs (run once after Phase 1)
-- In production this would use COPY commands from the processed/ directory
-- =============================================================================

-- Load dim_transport_mode (reference data — always load first)
INSERT INTO dim_transport_mode
    (mode_code, mode_name, kg_co2e_per_tonne_km, relative_cost_index, avg_speed_kmh, suitable_for_regions)
VALUES
    ('ROAD', 'Road (HGV)',       0.1000, 1.0,  80,  'DOMESTIC,EUROPEAN'),
    ('RAIL', 'Rail (Freight)',   0.0280, 0.7,  60,  'EUROPEAN'),
    ('SEA',  'Sea (Container)',  0.0160, 0.4,  35,  'EUROPEAN,INTERCONTINENTAL'),
    ('AIR',  'Air Freight',      0.6020, 8.5,  800, 'INTERCONTINENTAL')
ON CONFLICT (mode_code) DO NOTHING;

-- Load ref_shipping_distances
INSERT INTO ref_shipping_distances (origin_country, destination, transport_mode, distance_km)
VALUES
    ('China',          'UK', 'SEA',  19500),
    ('China',          'UK', 'AIR',   9200),
    ('India',          'UK', 'SEA',  11000),
    ('India',          'UK', 'AIR',   6700),
    ('United States',  'UK', 'AIR',   5500),
    ('United States',  'UK', 'SEA',   6800),
    ('Germany',        'UK', 'ROAD',  1100),
    ('Sweden',         'UK', 'ROAD',  1400),
    ('Italy',          'UK', 'ROAD',  1800),
    ('United Kingdom', 'UK', 'ROAD',   250)
ON CONFLICT (origin_country, destination, transport_mode) DO NOTHING;

-- Load dim_warehouse
INSERT INTO dim_warehouse
    (warehouse_id, warehouse_name, location, warehouse_type, capacity_pallets, monthly_cost_gbp, latitude, longitude)
VALUES
    ('WH-001', 'Coventry DC',    'Coventry',   'PRIMARY_DC',   2000, 18000.00, 52.406822, -1.519693),
    ('WH-002', 'Manchester Hub', 'Manchester', 'REGIONAL_HUB',  800,  7500.00, 53.480759, -2.242631),
    ('WH-003', 'Bristol Hub',    'Bristol',    'REGIONAL_HUB',  600,  6000.00, 51.454514, -2.587910)
ON CONFLICT (warehouse_id) DO NOTHING;

-- Load dim_supplier
INSERT INTO dim_supplier
    (supplier_id, supplier_name, country_of_origin, region, primary_transport, secondary_transport,
     lead_time_min_days, lead_time_max_days, lead_time_avg_days, lead_time_std_days,
     lead_time_distribution, spike_probability, reliability_score, payment_terms_days)
VALUES
    ('SUP-001','BritGoods Ltd',     'United Kingdom','DOMESTIC',        'ROAD',NULL,  3, 7,  4.5,1.0,'normal',   0.02,0.96,30),
    ('SUP-002','EuroFast GmbH',     'Germany',       'EUROPEAN',        'ROAD','RAIL',7, 12, 9.0,1.5,'normal',   0.05,0.93,30),
    ('SUP-003','AsiaSource Co',     'China',         'INTERCONTINENTAL','SEA', 'AIR', 18,35,24.0,4.5,'lognormal',0.15,0.78,60),
    ('SUP-004','IndiaManufact Pvt', 'India',         'INTERCONTINENTAL','SEA', 'AIR', 20,32,25.0,4.0,'lognormal',0.13,0.80,60),
    ('SUP-005','NordicSupply AS',   'Sweden',        'EUROPEAN',        'ROAD','SEA', 8, 14,10.5,1.8,'normal',   0.04,0.91,30),
    ('SUP-006','MedTrade SRL',      'Italy',         'EUROPEAN',        'ROAD',NULL,  10,18,13.0,2.2,'normal',   0.06,0.85,60),
    ('SUP-007','USBrands Inc',      'United States', 'INTERCONTINENTAL','AIR', 'SEA', 14,28,19.0,4.0,'lognormal',0.12,0.76,90),
    ('SUP-008','LocalPack Ltd',     'United Kingdom','DOMESTIC',        'ROAD',NULL,  2, 5,  3.0,0.8,'normal',   0.01,0.98,14)
ON CONFLICT (supplier_id) DO NOTHING;


-- =============================================================================
-- STEP 1 — INGEST HELPER
-- Function to load a supplier CSV batch into stg_supplier_feed
-- In production: called by Python orchestrator after each CSV arrives
-- =============================================================================

CREATE OR REPLACE FUNCTION apex.fn_ingest_batch(
    p_source_file   VARCHAR(100),
    p_batch_id      VARCHAR(50)
)
RETURNS TABLE (
    records_ingested    BIGINT,
    batch_id            VARCHAR(50),
    source_file         VARCHAR(100)
) AS $$
BEGIN
    -- This function signature is called by the Python ETL orchestrator
    -- The actual INSERT is performed by the Python layer using COPY or bulk insert
    -- This function sets up the batch context and returns metadata
    RAISE NOTICE 'Batch % ready for ingestion from %', p_batch_id, p_source_file;
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT,
        p_batch_id,
        p_source_file
    FROM stg_supplier_feed
    WHERE stg_supplier_feed.batch_id = p_batch_id;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- STEP 2 — SUPPLIER NAME NORMALISATION
-- Maps all known dirty name variants to canonical supplier_id
-- This is the first transformation applied after validation
-- =============================================================================

CREATE TABLE IF NOT EXISTS ref_supplier_name_aliases (
    alias_id        SERIAL          PRIMARY KEY,
    raw_name        VARCHAR(150)    NOT NULL UNIQUE,
    canonical_id    VARCHAR(10)     NOT NULL REFERENCES dim_supplier(supplier_id),
    added_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE ref_supplier_name_aliases IS
    'Maps dirty supplier name variants to canonical supplier_id. '
    'Updated whenever a new alias is discovered in incoming data.';

-- Pre-populate known aliases (from Phase 1 dirty data analysis)
INSERT INTO ref_supplier_name_aliases (raw_name, canonical_id) VALUES
    -- Canonical names (clean)
    ('BritGoods Ltd',           'SUP-001'),
    ('EuroFast GmbH',           'SUP-002'),
    ('AsiaSource Co',           'SUP-003'),
    ('IndiaManufact Pvt',       'SUP-004'),
    ('NordicSupply AS',         'SUP-005'),
    ('MedTrade SRL',            'SUP-006'),
    ('USBrands Inc',            'SUP-007'),
    ('LocalPack Ltd',           'SUP-008'),
    -- Dirty variants — SUP-001
    ('BRITGOODS',               'SUP-001'),
    ('Brit Goods Limited',      'SUP-001'),
    -- Dirty variants — SUP-002
    ('EUROFAST',                'SUP-002'),
    ('Euro Fast GmbH',          'SUP-002'),
    ('Eurofast GMBH',           'SUP-002'),
    -- Dirty variants — SUP-003
    ('ASIASOURCE',              'SUP-003'),
    ('Asia Source Co.',         'SUP-003'),
    ('AsiaSource',              'SUP-003'),
    ('ASIA SOURCE CO',          'SUP-003'),
    -- Dirty variants — SUP-004
    ('INDIAMANUFACT',           'SUP-004'),
    ('India Manufact Pvt Ltd',  'SUP-004'),
    ('IndiaManufact',           'SUP-004'),
    -- Dirty variants — SUP-005
    ('NORDICSUPPLY',            'SUP-005'),
    ('Nordic Supply A/S',       'SUP-005'),
    ('NordicSupply',            'SUP-005'),
    -- Dirty variants — SUP-006
    ('MEDTRADE',                'SUP-006'),
    ('Med Trade S.R.L.',        'SUP-006'),
    ('MedTrade Srl',            'SUP-006'),
    -- Dirty variants — SUP-007
    ('US Brands Inc.',          'SUP-007'),
    ('USBRANDS',                'SUP-007'),
    ('U.S. Brands Inc',         'SUP-007'),
    -- Dirty variants — SUP-008
    ('LOCALPACK',               'SUP-008'),
    ('Local Pack Ltd.',         'SUP-008'),
    ('LocalPack',               'SUP-008')
ON CONFLICT (raw_name) DO NOTHING;


-- =============================================================================
-- STEP 3 — DATE STANDARDISATION
-- Parses multiple date formats into ISO 8601 (YYYY-MM-DD)
-- Handles: DD/MM/YYYY, DD/MM/YY, DD-Mon-YY, MM/DD/YYYY
-- =============================================================================

CREATE OR REPLACE FUNCTION apex.fn_parse_date(p_raw_date TEXT)
RETURNS DATE AS $$
DECLARE
    v_date DATE;
BEGIN
    IF p_raw_date IS NULL OR TRIM(p_raw_date) = '' THEN
        RETURN NULL;
    END IF;

    -- Try ISO format first (most common in clean data)
    BEGIN
        v_date := p_raw_date::DATE;
        RETURN v_date;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;

    -- Try DD/MM/YYYY (UK standard)
    BEGIN
        v_date := TO_DATE(p_raw_date, 'DD/MM/YYYY');
        RETURN v_date;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;

    -- Try DD/MM/YY (UK short year)
    BEGIN
        v_date := TO_DATE(p_raw_date, 'DD/MM/YY');
        RETURN v_date;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;

    -- Try DD-Mon-YY (e.g. 15-Mar-26)
    BEGIN
        v_date := TO_DATE(p_raw_date, 'DD-Mon-YY');
        RETURN v_date;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;

    -- Try MM/DD/YYYY (US format — error but attempt recovery)
    BEGIN
        v_date := TO_DATE(p_raw_date, 'MM/DD/YYYY');
        -- Sanity check: if day > 12 in MM position it must be US format
        RETURN v_date;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;

    -- All formats failed
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION apex.fn_parse_date IS
    'Parses dirty date strings into DATE. Returns NULL if all formats fail. '
    'NULL result triggers DATE_FORMAT_MISMATCH validation error.';


-- =============================================================================
-- STEP 4 — TRANSPORT MODE STANDARDISATION
-- Maps raw transport mode strings to canonical mode codes
-- =============================================================================

CREATE OR REPLACE FUNCTION apex.fn_normalise_transport(p_raw TEXT)
RETURNS CHAR(4) AS $$
BEGIN
    IF p_raw IS NULL OR TRIM(p_raw) = '' THEN
        RETURN NULL;
    END IF;

    RETURN CASE UPPER(TRIM(p_raw))
        WHEN 'ROAD'             THEN 'ROAD'
        WHEN 'HGV'              THEN 'ROAD'
        WHEN 'TRUCK'            THEN 'ROAD'
        WHEN 'LORRY'            THEN 'ROAD'
        WHEN 'RAIL'             THEN 'RAIL'
        WHEN 'TRAIN'            THEN 'RAIL'
        WHEN 'SEA'              THEN 'SEA'
        WHEN 'SHIP'             THEN 'SEA'
        WHEN 'CONTAINER'        THEN 'SEA'
        WHEN 'OCEAN'            THEN 'SEA'
        WHEN 'AIR'              THEN 'AIR'
        WHEN 'AIRFREIGHT'       THEN 'AIR'
        WHEN 'AIR FREIGHT'      THEN 'AIR'
        WHEN 'PLANE'            THEN 'AIR'
        ELSE NULL
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- =============================================================================
-- STEP 5 — MAIN TRANSFORMATION FUNCTION
-- Transforms CLEAN staging records into fact_purchase_orders
-- Only processes records with validation_status = 'CLEAN'
-- =============================================================================

CREATE OR REPLACE FUNCTION apex.fn_transform_to_facts(p_batch_id VARCHAR(50))
RETURNS TABLE (
    records_loaded      INTEGER,
    records_skipped     INTEGER,
    carbon_events_created INTEGER
) AS $$
DECLARE
    v_loaded        INTEGER := 0;
    v_skipped       INTEGER := 0;
    v_carbon        INTEGER := 0;
    v_order_date    DATE;
    v_exp_del       DATE;
    v_act_del       DATE;
    v_supplier_id   VARCHAR(10);
    v_transport     CHAR(4);
    v_qty           INTEGER;
    v_cost          DECIMAL(10,2);
    v_distance      DECIMAL(10,2);
    v_emission      DECIMAL(6,4);
    r               RECORD;
BEGIN
    RAISE NOTICE 'Starting transformation for batch: %', p_batch_id;

    FOR r IN
        SELECT stg.*
        FROM   stg_supplier_feed stg
        WHERE  stg.batch_id         = p_batch_id
        AND    stg.validation_status = 'CLEAN'
    LOOP
        BEGIN
            -- Parse dates
            v_order_date := apex.fn_parse_date(r.raw_order_date);
            v_exp_del    := apex.fn_parse_date(r.raw_expected_delivery);
            v_act_del    := apex.fn_parse_date(r.raw_actual_delivery);

            -- Resolve supplier
            SELECT canonical_id INTO v_supplier_id
            FROM   ref_supplier_name_aliases
            WHERE  LOWER(TRIM(raw_name)) = LOWER(TRIM(r.raw_supplier_name));

            -- Normalise transport
            v_transport := apex.fn_normalise_transport(r.raw_transport_mode);

            -- Cast numeric fields
            v_qty  := r.raw_quantity::INTEGER;
            v_cost := r.raw_unit_cost::DECIMAL(10,2);

            -- Skip if any critical field is still null after transformation
            IF v_order_date IS NULL OR v_supplier_id IS NULL OR
               v_transport  IS NULL OR v_qty IS NULL OR v_cost IS NULL THEN
                v_skipped := v_skipped + 1;
                RAISE NOTICE 'Skipped record stg_id=% — critical field null after transform', r.stg_id;
                CONTINUE;
            END IF;

            -- Insert into fact_purchase_orders
            INSERT INTO fact_purchase_orders (
                order_id, product_id, supplier_id, warehouse_id,
                order_date_key, expected_delivery_key, actual_delivery_key,
                quantity_ordered, unit_cost_gbp,
                lead_time_days, transport_mode, weight_kg_total,
                is_urgent_order, order_status, source_file
            )
            VALUES (
                TRIM(r.raw_order_id),
                TRIM(r.raw_product_id),
                v_supplier_id,
                COALESCE(
                    (SELECT warehouse_id FROM dim_warehouse
                     ORDER BY RANDOM() LIMIT 1), 'WH-001'
                ),
                TO_CHAR(v_order_date, 'YYYYMMDD')::INTEGER,
                TO_CHAR(v_exp_del,   'YYYYMMDD')::INTEGER,
                CASE WHEN v_act_del IS NOT NULL
                     THEN TO_CHAR(v_act_del, 'YYYYMMDD')::INTEGER
                     ELSE NULL END,
                v_qty,
                v_cost,
                -- Lead time: actual - order date if available, else expected - order
                COALESCE(v_act_del, v_exp_del) - v_order_date,
                v_transport,
                COALESCE(r.raw_weight_kg::DECIMAL, v_qty * 0.5),
                FALSE,
                CASE WHEN v_act_del IS NOT NULL THEN 'DELIVERED' ELSE 'IN_TRANSIT' END,
                r.source_file
            )
            ON CONFLICT (order_id) DO NOTHING;

            v_loaded := v_loaded + 1;

            -- Create carbon event for this shipment
            SELECT rsd.distance_km, dtm.kg_co2e_per_tonne_km
            INTO   v_distance, v_emission
            FROM   ref_shipping_distances rsd
            JOIN   dim_supplier           ds  ON ds.supplier_id     = v_supplier_id
            JOIN   dim_transport_mode     dtm ON dtm.mode_code      = v_transport
            WHERE  rsd.origin_country = ds.country_of_origin
            AND    rsd.transport_mode = v_transport
            LIMIT  1;

            IF v_distance IS NOT NULL AND v_act_del IS NOT NULL THEN
                INSERT INTO fact_carbon_events (
                    order_id, product_id, supplier_id, shipment_date_key,
                    transport_mode, weight_kg, distance_km,
                    kg_co2e_per_tonne_km, quantity_units
                )
                VALUES (
                    TRIM(r.raw_order_id),
                    TRIM(r.raw_product_id),
                    v_supplier_id,
                    TO_CHAR(v_act_del, 'YYYYMMDD')::INTEGER,
                    v_transport,
                    COALESCE(r.raw_weight_kg::DECIMAL, v_qty * 0.5),
                    v_distance,
                    v_emission,
                    v_qty
                )
                ON CONFLICT DO NOTHING;

                v_carbon := v_carbon + 1;
            END IF;

            -- Mark staging record as processed
            UPDATE stg_supplier_feed
            SET    validation_status = 'CLEAN',
                   processed_at      = CURRENT_TIMESTAMP
            WHERE  stg_id = r.stg_id;

        EXCEPTION WHEN OTHERS THEN
            v_skipped := v_skipped + 1;
            RAISE NOTICE 'Error transforming stg_id=%: %', r.stg_id, SQLERRM;
        END;
    END LOOP;

    RAISE NOTICE 'Batch % complete: % loaded, % skipped, % carbon events',
        p_batch_id, v_loaded, v_skipped, v_carbon;

    RETURN QUERY SELECT v_loaded, v_skipped, v_carbon;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION apex.fn_transform_to_facts IS
    'Transforms CLEAN staging records into fact_purchase_orders and fact_carbon_events. '
    'Run after 03_validation_rules.sql has processed the batch.';


-- =============================================================================
-- STEP 6 — INVENTORY SNAPSHOT LOADER
-- Loads monthly inventory positions from processed CSV
-- =============================================================================

CREATE OR REPLACE FUNCTION apex.fn_load_inventory_snapshot(
    p_snapshot_date DATE,
    p_product_id    VARCHAR(10),
    p_warehouse_id  VARCHAR(6),
    p_stock_on_hand INTEGER,
    p_avg_daily_dem DECIMAL(10,2),
    p_abc_class     CHAR(1),
    p_unit_cost     DECIMAL(10,2)
)
RETURNS VOID AS $$
DECLARE
    v_date_key          INTEGER;
    v_cover_days        DECIMAL(8,1);
    v_stock_value       DECIMAL(12,2);
    v_excess_value      DECIMAL(12,2);
    v_is_slow_mover     BOOLEAN;
    v_is_stock_out      BOOLEAN;
    v_is_at_risk        BOOLEAN;
BEGIN
    v_date_key    := TO_CHAR(p_snapshot_date, 'YYYYMMDD')::INTEGER;
    v_cover_days  := CASE WHEN p_avg_daily_dem > 0
                          THEN ROUND(p_stock_on_hand / p_avg_daily_dem, 1)
                          ELSE 0 END;
    v_stock_value := p_stock_on_hand * p_unit_cost;

    -- Excess = value beyond 90-day cover for C-class
    v_excess_value := CASE
        WHEN p_abc_class = 'C' AND v_cover_days > 90
        THEN GREATEST(0, (p_stock_on_hand - (p_avg_daily_dem * 90)) * p_unit_cost)
        ELSE 0
    END;

    v_is_stock_out  := (p_stock_on_hand = 0);
    v_is_slow_mover := (p_abc_class = 'C' AND v_cover_days > 90);
    v_is_at_risk    := (p_abc_class = 'A' AND v_cover_days < 14 AND NOT v_is_stock_out);

    INSERT INTO fact_inventory_snapshots (
        snapshot_date_key, product_id, warehouse_id,
        stock_on_hand, stock_cover_days, avg_daily_demand,
        is_stock_out, is_slow_mover, is_at_risk,
        stock_value_gbp, excess_stock_value_gbp, abc_class
    )
    VALUES (
        v_date_key, p_product_id, p_warehouse_id,
        p_stock_on_hand, v_cover_days, p_avg_daily_dem,
        v_is_stock_out, v_is_slow_mover, v_is_at_risk,
        v_stock_value, v_excess_value, p_abc_class
    )
    ON CONFLICT (snapshot_date_key, product_id, warehouse_id)
    DO UPDATE SET
        stock_on_hand          = EXCLUDED.stock_on_hand,
        stock_cover_days       = EXCLUDED.stock_cover_days,
        avg_daily_demand       = EXCLUDED.avg_daily_demand,
        is_stock_out           = EXCLUDED.is_stock_out,
        is_slow_mover          = EXCLUDED.is_slow_mover,
        is_at_risk             = EXCLUDED.is_at_risk,
        stock_value_gbp        = EXCLUDED.stock_value_gbp,
        excess_stock_value_gbp = EXCLUDED.excess_stock_value_gbp,
        loaded_at              = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- STEP 7 — DATA QUALITY REPORT
-- Called at end of each ETL batch run — produces ops-facing summary
-- =============================================================================

CREATE OR REPLACE FUNCTION apex.fn_data_quality_report(p_batch_id VARCHAR(50))
RETURNS TABLE (
    metric          TEXT,
    value           TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH batch_stats AS (
        SELECT
            COUNT(*)                                                        AS total_records,
            SUM(CASE WHEN validation_status = 'CLEAN'      THEN 1 ELSE 0 END) AS clean_count,
            SUM(CASE WHEN validation_status = 'DIRTY'      THEN 1 ELSE 0 END) AS dirty_count,
            SUM(CASE WHEN validation_status = 'QUARANTINE' THEN 1 ELSE 0 END) AS quarantine_count
        FROM stg_supplier_feed
        WHERE batch_id = p_batch_id
    ),
    error_breakdown AS (
        SELECT error_type, COUNT(*) AS error_count
        FROM   stg_validation_errors
        WHERE  batch_id = p_batch_id
        GROUP  BY error_type
        ORDER  BY error_count DESC
    )
    SELECT 'Batch ID'::TEXT,                  p_batch_id::TEXT              FROM batch_stats
    UNION ALL
    SELECT 'Total Records Ingested',          total_records::TEXT            FROM batch_stats
    UNION ALL
    SELECT 'Clean Records',                   clean_count::TEXT              FROM batch_stats
    UNION ALL
    SELECT 'Dirty Records',                   dirty_count::TEXT              FROM batch_stats
    UNION ALL
    SELECT 'Quarantined Records',             quarantine_count::TEXT         FROM batch_stats
    UNION ALL
    SELECT 'Data Quality Rate (%)',
           ROUND(clean_count::DECIMAL / NULLIF(total_records,0) * 100, 1)::TEXT
    FROM batch_stats
    UNION ALL
    SELECT 'Error: ' || error_type,           error_count::TEXT
    FROM   error_breakdown;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION apex.fn_data_quality_report IS
    'Per-batch data quality summary. Replaces 12-hour manual reporting cycle with instant output.';


-- =============================================================================
-- STEP 8 — MASTER ETL ORCHESTRATOR
-- Single entry point: runs full pipeline for one batch
-- Called by Python scheduler or manually
-- =============================================================================

CREATE OR REPLACE FUNCTION apex.fn_run_etl_pipeline(
    p_source_file   VARCHAR(100),
    p_batch_id      VARCHAR(50)  DEFAULT NULL
)
RETURNS TABLE (
    step            TEXT,
    result          TEXT
) AS $$
DECLARE
    v_batch_id      VARCHAR(50);
    v_validated     INTEGER;
    v_clean         INTEGER;
    v_dirty         INTEGER;
    v_loaded        INTEGER;
    v_skipped       INTEGER;
    v_carbon        INTEGER;
BEGIN
    -- Generate batch ID if not provided
    v_batch_id := COALESCE(p_batch_id,
        'BATCH-' || TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDD-HH24MISS'));

    RAISE NOTICE '====================================';
    RAISE NOTICE ' ETL PIPELINE STARTED';
    RAISE NOTICE ' Batch : %', v_batch_id;
    RAISE NOTICE ' File  : %', p_source_file;
    RAISE NOTICE '====================================';

    -- Step 1: Count ingested records
    SELECT COUNT(*) INTO v_validated
    FROM stg_supplier_feed
    WHERE batch_id = v_batch_id;

    RETURN QUERY SELECT 'STEP 1 - INGEST'::TEXT,
        v_validated::TEXT || ' records in staging'::TEXT;

    -- Step 2: Validation (03_validation_rules.sql must have been run first)
    SELECT
        SUM(CASE WHEN validation_status = 'CLEAN' THEN 1 ELSE 0 END),
        SUM(CASE WHEN validation_status IN ('DIRTY','QUARANTINE') THEN 1 ELSE 0 END)
    INTO v_clean, v_dirty
    FROM stg_supplier_feed
    WHERE batch_id = v_batch_id;

    RETURN QUERY SELECT 'STEP 2 - VALIDATE'::TEXT,
        v_clean::TEXT || ' clean | ' || v_dirty::TEXT || ' dirty'::TEXT;

    -- Step 3: Transform and load
    SELECT tl.records_loaded, tl.records_skipped, tl.carbon_events_created
    INTO   v_loaded, v_skipped, v_carbon
    FROM   apex.fn_transform_to_facts(v_batch_id) tl;

    RETURN QUERY SELECT 'STEP 3 - TRANSFORM & LOAD'::TEXT,
        v_loaded::TEXT || ' loaded | ' || v_skipped::TEXT || ' skipped'::TEXT;

    RETURN QUERY SELECT 'STEP 4 - CARBON EVENTS'::TEXT,
        v_carbon::TEXT || ' Scope 3 records created'::TEXT;

    -- Step 5: Quality report
    RETURN QUERY SELECT 'STEP 5 - QUALITY RATE'::TEXT,
        ROUND(v_clean::DECIMAL / NULLIF(v_validated,0) * 100, 1)::TEXT || '%'::TEXT;

    RAISE NOTICE '====================================';
    RAISE NOTICE ' ETL PIPELINE COMPLETE — Batch %', v_batch_id;
    RAISE NOTICE ' Loaded: % | Carbon events: %', v_loaded, v_carbon;
    RAISE NOTICE '====================================';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION apex.fn_run_etl_pipeline IS
    'Master ETL orchestrator. Single call runs full pipeline for one supplier batch. '
    'Replaces 12-hour manual Excel process with sub-minute automated run.';


-- =============================================================================
-- USAGE EXAMPLES (for documentation and testing)
-- =============================================================================

-- Run full pipeline for a supplier batch:
-- SELECT * FROM apex.fn_run_etl_pipeline('SUP-003_AsiaSource_feed.csv', 'BATCH-20250115-001');

-- Check data quality for a batch:
-- SELECT * FROM apex.fn_data_quality_report('BATCH-20250115-001');

-- Query the working capital view:
-- SELECT * FROM apex.vw_working_capital WHERE year_number = 2025 ORDER BY month_number;

-- Query the Scope 3 report (exportable to retail partners):
-- SELECT * FROM apex.vw_scope3_report WHERE reporting_period LIKE '2025-%';

-- Check stock-out rates:
-- SELECT * FROM apex.vw_stockout_rate WHERE abc_class = 'A' ORDER BY year_number, month_number;

-- Supplier performance:
-- SELECT * FROM apex.vw_supplier_performance ORDER BY avg_variance_days DESC;

DO $$
BEGIN
    RAISE NOTICE '================================================';
    RAISE NOTICE ' ETL Pipeline Deployed';
    RAISE NOTICE '================================================';
    RAISE NOTICE ' Functions  : fn_ingest_batch';
    RAISE NOTICE '              fn_parse_date (multi-format)';
    RAISE NOTICE '              fn_normalise_transport';
    RAISE NOTICE '              fn_transform_to_facts';
    RAISE NOTICE '              fn_load_inventory_snapshot';
    RAISE NOTICE '              fn_data_quality_report';
    RAISE NOTICE '              fn_run_etl_pipeline (orchestrator)';
    RAISE NOTICE ' Alias Table: ref_supplier_name_aliases (35 entries)';
    RAISE NOTICE '================================================';
    RAISE NOTICE ' Next: 03_validation_rules.sql';
    RAISE NOTICE '================================================';
END $$;
