-- =============================================================================
-- ECO-STREAMLINE 2026 | Apex Distribution UK
-- FILE: 03_validation_rules.sql
-- PURPOSE: Automated Data Validation — flags supplier errors before reports
-- DATABASE: PostgreSQL 15+
-- AUTHOR: Lead Business Transformation Analyst
-- =============================================================================
-- VALIDATION OVERVIEW
--
-- 7 error types detected (matching Phase 0 data contracts):
--
--   V01 — SUPPLIER_NAME_MISMATCH  : Name not in approved alias list
--   V02 — DATE_FORMAT_MISMATCH    : Unrecognised or unparseable date format
--   V03 — MISSING_TRANSPORT_MODE  : Transport mode blank or NULL
--   V04 — NEGATIVE_QUANTITY       : Quantity is zero or negative
--   V05 — COST_OUTLIER            : Unit cost deviates >300% from product average
--   V06 — DUPLICATE_ORDER_ID      : Same order_id appears more than once
--   V07 — UNKNOWN_PRODUCT_ID      : Product ID not in dim_product master
--
-- SEVERITY LEVELS:
--   ERROR   — Record quarantined, cannot be loaded
--   WARNING — Record flagged, loaded with note (human review recommended)
--   INFO    — Informational, loaded normally
--
-- OUTCOME:
--   stg_supplier_feed.validation_status updated to CLEAN / DIRTY / QUARANTINE
--   All errors logged to stg_validation_errors with full context
-- =============================================================================

SET search_path TO apex, public;


-- =============================================================================
-- VALIDATION ENGINE
-- Master function: runs all 7 checks against a batch
-- =============================================================================

CREATE OR REPLACE FUNCTION apex.fn_validate_batch(p_batch_id VARCHAR(50))
RETURNS TABLE (
    check_name          TEXT,
    records_checked     BIGINT,
    errors_found        BIGINT,
    severity            TEXT
) AS $$
DECLARE
    v_count_checked     BIGINT;
    v_count_errors      BIGINT;
BEGIN
    RAISE NOTICE 'Starting validation for batch: %', p_batch_id;

    -- Reset all records to PENDING before re-validation
    UPDATE stg_supplier_feed
    SET    validation_status = 'PENDING',
           error_types       = NULL
    WHERE  batch_id = p_batch_id;

    -- -------------------------------------------------------------------------
    -- V01 — SUPPLIER NAME MISMATCH
    -- -------------------------------------------------------------------------
    SELECT COUNT(*) INTO v_count_checked
    FROM   stg_supplier_feed
    WHERE  batch_id = p_batch_id;

    WITH mismatched AS (
        SELECT stg.stg_id, stg.raw_supplier_name
        FROM   stg_supplier_feed stg
        WHERE  stg.batch_id = p_batch_id
        AND    NOT EXISTS (
            SELECT 1 FROM ref_supplier_name_aliases a
            WHERE  LOWER(TRIM(a.raw_name)) = LOWER(TRIM(stg.raw_supplier_name))
        )
        AND    stg.raw_supplier_name IS NOT NULL
        AND    TRIM(stg.raw_supplier_name) != ''
    )
    INSERT INTO stg_validation_errors
        (stg_id, batch_id, error_type, error_field, raw_value,
         expected_format, error_description, severity)
    SELECT
        m.stg_id,
        p_batch_id,
        'SUPPLIER_NAME_MISMATCH',
        'raw_supplier_name',
        m.raw_supplier_name,
        'Must match approved supplier list (see ref_supplier_name_aliases)',
        'Supplier name "' || m.raw_supplier_name || '" not recognised. '
            || 'Check spelling or add new alias to ref_supplier_name_aliases.',
        'ERROR'
    FROM mismatched m;

    GET DIAGNOSTICS v_count_errors = ROW_COUNT;
    RETURN QUERY SELECT 'V01 SUPPLIER_NAME_MISMATCH'::TEXT,
        v_count_checked, v_count_errors, 'ERROR'::TEXT;

    -- Flag affected records
    UPDATE stg_supplier_feed stg
    SET    validation_status = 'DIRTY',
           error_types       = ARRAY_APPEND(COALESCE(error_types, '{}'), 'SUPPLIER_NAME_MISMATCH')
    WHERE  batch_id = p_batch_id
    AND    EXISTS (
        SELECT 1 FROM stg_validation_errors e
        WHERE  e.stg_id     = stg.stg_id
        AND    e.error_type = 'SUPPLIER_NAME_MISMATCH'
    );


    -- -------------------------------------------------------------------------
    -- V02 — DATE FORMAT MISMATCH
    -- -------------------------------------------------------------------------
    WITH bad_dates AS (
        SELECT stg.stg_id, stg.raw_order_date
        FROM   stg_supplier_feed stg
        WHERE  stg.batch_id = p_batch_id
        AND    stg.raw_order_date IS NOT NULL
        AND    apex.fn_parse_date(stg.raw_order_date) IS NULL
    )
    INSERT INTO stg_validation_errors
        (stg_id, batch_id, error_type, error_field, raw_value,
         expected_format, error_description, severity)
    SELECT
        bd.stg_id,
        p_batch_id,
        'DATE_FORMAT_MISMATCH',
        'raw_order_date',
        bd.raw_order_date,
        'YYYY-MM-DD preferred. Also accepts DD/MM/YYYY, DD/MM/YY, DD-Mon-YY',
        'Order date "' || bd.raw_order_date || '" could not be parsed. '
            || 'Accepted formats: YYYY-MM-DD, DD/MM/YYYY, DD/MM/YY, DD-Mon-YY.',
        'ERROR'
    FROM bad_dates bd;

    GET DIAGNOSTICS v_count_errors = ROW_COUNT;
    RETURN QUERY SELECT 'V02 DATE_FORMAT_MISMATCH'::TEXT,
        v_count_checked, v_count_errors, 'ERROR'::TEXT;

    UPDATE stg_supplier_feed stg
    SET    validation_status = 'DIRTY',
           error_types       = ARRAY_APPEND(COALESCE(error_types, '{}'), 'DATE_FORMAT_MISMATCH')
    WHERE  batch_id = p_batch_id
    AND    EXISTS (
        SELECT 1 FROM stg_validation_errors e
        WHERE  e.stg_id     = stg.stg_id
        AND    e.error_type = 'DATE_FORMAT_MISMATCH'
        AND    e.batch_id   = p_batch_id
    );


    -- -------------------------------------------------------------------------
    -- V03 — MISSING TRANSPORT MODE
    -- -------------------------------------------------------------------------
    WITH missing_transport AS (
        SELECT stg.stg_id
        FROM   stg_supplier_feed stg
        WHERE  stg.batch_id = p_batch_id
        AND    (stg.raw_transport_mode IS NULL OR TRIM(stg.raw_transport_mode) = '')
    )
    INSERT INTO stg_validation_errors
        (stg_id, batch_id, error_type, error_field, raw_value,
         expected_format, error_description, severity)
    SELECT
        mt.stg_id,
        p_batch_id,
        'MISSING_TRANSPORT_MODE',
        'raw_transport_mode',
        NULL,
        'One of: ROAD, RAIL, SEA, AIR',
        'Transport mode is missing. Required for Scope 3 carbon calculation. '
            || 'Record will be loaded but carbon event cannot be created.',
        'WARNING'
    FROM missing_transport mt;

    GET DIAGNOSTICS v_count_errors = ROW_COUNT;
    RETURN QUERY SELECT 'V03 MISSING_TRANSPORT_MODE'::TEXT,
        v_count_checked, v_count_errors, 'WARNING'::TEXT;

    -- WARNING only — record still loads but is flagged
    UPDATE stg_supplier_feed stg
    SET    error_types = ARRAY_APPEND(COALESCE(error_types, '{}'), 'MISSING_TRANSPORT_MODE')
    WHERE  batch_id = p_batch_id
    AND    (raw_transport_mode IS NULL OR TRIM(raw_transport_mode) = '');


    -- -------------------------------------------------------------------------
    -- V04 — NEGATIVE QUANTITY
    -- -------------------------------------------------------------------------
    WITH bad_qty AS (
        SELECT stg.stg_id, stg.raw_quantity
        FROM   stg_supplier_feed stg
        WHERE  stg.batch_id = p_batch_id
        AND    stg.raw_quantity ~ '^-?[0-9]+$'           -- Is numeric
        AND    stg.raw_quantity::INTEGER <= 0             -- But zero or negative
    )
    INSERT INTO stg_validation_errors
        (stg_id, batch_id, error_type, error_field, raw_value,
         expected_format, error_description, severity)
    SELECT
        bq.stg_id,
        p_batch_id,
        'NEGATIVE_QUANTITY',
        'raw_quantity',
        bq.raw_quantity,
        'Positive integer greater than 0',
        'Quantity "' || bq.raw_quantity || '" is zero or negative. '
            || 'Likely a data entry error. Record quarantined.',
        'ERROR'
    FROM bad_qty bq;

    GET DIAGNOSTICS v_count_errors = ROW_COUNT;
    RETURN QUERY SELECT 'V04 NEGATIVE_QUANTITY'::TEXT,
        v_count_checked, v_count_errors, 'ERROR'::TEXT;

    UPDATE stg_supplier_feed stg
    SET    validation_status = 'QUARANTINE',
           error_types       = ARRAY_APPEND(COALESCE(error_types, '{}'), 'NEGATIVE_QUANTITY')
    WHERE  batch_id = p_batch_id
    AND    raw_quantity ~ '^-?[0-9]+$'
    AND    raw_quantity::INTEGER <= 0;


    -- -------------------------------------------------------------------------
    -- V05 — COST OUTLIER
    -- Unit cost deviates more than 300% from the batch average for that product
    -- -------------------------------------------------------------------------
    WITH product_avg_cost AS (
        SELECT
            raw_product_id,
            AVG(raw_unit_cost::DECIMAL)     AS avg_cost,
            STDDEV(raw_unit_cost::DECIMAL)  AS std_cost
        FROM   stg_supplier_feed
        WHERE  batch_id    = p_batch_id
        AND    raw_unit_cost ~ '^[0-9]+\.?[0-9]*$'
        GROUP  BY raw_product_id
    ),
    outliers AS (
        SELECT
            stg.stg_id,
            stg.raw_product_id,
            stg.raw_unit_cost,
            pac.avg_cost
        FROM   stg_supplier_feed stg
        JOIN   product_avg_cost  pac ON pac.raw_product_id = stg.raw_product_id
        WHERE  stg.batch_id = p_batch_id
        AND    stg.raw_unit_cost ~ '^[0-9]+\.?[0-9]*$'
        AND    pac.avg_cost > 0
        AND    ABS(stg.raw_unit_cost::DECIMAL - pac.avg_cost) > (pac.avg_cost * 3.0)
    )
    INSERT INTO stg_validation_errors
        (stg_id, batch_id, error_type, error_field, raw_value,
         expected_format, error_description, severity)
    SELECT
        o.stg_id,
        p_batch_id,
        'COST_OUTLIER',
        'raw_unit_cost',
        o.raw_unit_cost,
        'Within 300% of batch average for this product',
        'Unit cost GBP ' || o.raw_unit_cost
            || ' deviates >300% from batch average GBP '
            || ROUND(o.avg_cost, 2)::TEXT
            || '. Possible 10x data entry error. Flagged for human review.',
        'WARNING'
    FROM outliers o;

    GET DIAGNOSTICS v_count_errors = ROW_COUNT;
    RETURN QUERY SELECT 'V05 COST_OUTLIER'::TEXT,
        v_count_checked, v_count_errors, 'WARNING'::TEXT;

    -- WARNING — loads but flagged for finance team review
    UPDATE stg_supplier_feed stg
    SET    error_types = ARRAY_APPEND(COALESCE(error_types, '{}'), 'COST_OUTLIER')
    WHERE  batch_id = p_batch_id
    AND    EXISTS (
        SELECT 1 FROM stg_validation_errors e
        WHERE  e.stg_id     = stg.stg_id
        AND    e.error_type = 'COST_OUTLIER'
        AND    e.batch_id   = p_batch_id
    );


    -- -------------------------------------------------------------------------
    -- V06 — DUPLICATE ORDER ID
    -- Same order_id appears more than once in this batch OR already in facts
    -- -------------------------------------------------------------------------
    WITH dupe_in_batch AS (
        SELECT raw_order_id
        FROM   stg_supplier_feed
        WHERE  batch_id = p_batch_id
        GROUP  BY raw_order_id
        HAVING COUNT(*) > 1
    ),
    dupe_in_facts AS (
        SELECT order_id AS raw_order_id
        FROM   fact_purchase_orders
        WHERE  order_id IN (
            SELECT raw_order_id FROM stg_supplier_feed WHERE batch_id = p_batch_id
        )
    ),
    all_dupes AS (
        SELECT raw_order_id FROM dupe_in_batch
        UNION
        SELECT raw_order_id FROM dupe_in_facts
    ),
    dupe_stg AS (
        SELECT stg.stg_id, stg.raw_order_id,
               ROW_NUMBER() OVER (PARTITION BY stg.raw_order_id
                                  ORDER BY stg.stg_id) AS rn
        FROM   stg_supplier_feed stg
        JOIN   all_dupes         d ON d.raw_order_id = stg.raw_order_id
        WHERE  stg.batch_id = p_batch_id
    )
    INSERT INTO stg_validation_errors
        (stg_id, batch_id, error_type, error_field, raw_value,
         expected_format, error_description, severity)
    SELECT
        ds.stg_id,
        p_batch_id,
        'DUPLICATE_ORDER_ID',
        'raw_order_id',
        ds.raw_order_id,
        'Globally unique order identifier',
        'Order ID "' || ds.raw_order_id || '" appears more than once '
            || '(occurrence #' || ds.rn::TEXT || '). '
            || 'Only the first instance will be loaded.',
        'ERROR'
    FROM dupe_stg ds
    WHERE ds.rn > 1;

    GET DIAGNOSTICS v_count_errors = ROW_COUNT;
    RETURN QUERY SELECT 'V06 DUPLICATE_ORDER_ID'::TEXT,
        v_count_checked, v_count_errors, 'ERROR'::TEXT;

    UPDATE stg_supplier_feed stg
    SET    validation_status = 'DIRTY',
           error_types       = ARRAY_APPEND(COALESCE(error_types, '{}'), 'DUPLICATE_ORDER_ID')
    WHERE  batch_id = p_batch_id
    AND    EXISTS (
        SELECT 1 FROM stg_validation_errors e
        WHERE  e.stg_id     = stg.stg_id
        AND    e.error_type = 'DUPLICATE_ORDER_ID'
        AND    e.batch_id   = p_batch_id
    );


    -- -------------------------------------------------------------------------
    -- V07 — UNKNOWN PRODUCT ID
    -- Product ID not found in dim_product master table
    -- -------------------------------------------------------------------------
    WITH unknown_products AS (
        SELECT stg.stg_id, stg.raw_product_id
        FROM   stg_supplier_feed stg
        WHERE  stg.batch_id = p_batch_id
        AND    stg.raw_product_id IS NOT NULL
        AND    NOT EXISTS (
            SELECT 1 FROM dim_product p
            WHERE  p.product_id = TRIM(stg.raw_product_id)
        )
    )
    INSERT INTO stg_validation_errors
        (stg_id, batch_id, error_type, error_field, raw_value,
         expected_format, error_description, severity)
    SELECT
        up.stg_id,
        p_batch_id,
        'UNKNOWN_PRODUCT_ID',
        'raw_product_id',
        up.raw_product_id,
        'Must exist in dim_product (format: PRD-NNNNN)',
        'Product ID "' || up.raw_product_id
            || '" not found in product master. '
            || 'Check for typos or add product to dim_product before reprocessing.',
        'ERROR'
    FROM unknown_products up;

    GET DIAGNOSTICS v_count_errors = ROW_COUNT;
    RETURN QUERY SELECT 'V07 UNKNOWN_PRODUCT_ID'::TEXT,
        v_count_checked, v_count_errors, 'ERROR'::TEXT;

    UPDATE stg_supplier_feed stg
    SET    validation_status = 'QUARANTINE',
           error_types       = ARRAY_APPEND(COALESCE(error_types, '{}'), 'UNKNOWN_PRODUCT_ID')
    WHERE  batch_id = p_batch_id
    AND    EXISTS (
        SELECT 1 FROM stg_validation_errors e
        WHERE  e.stg_id     = stg.stg_id
        AND    e.error_type = 'UNKNOWN_PRODUCT_ID'
        AND    e.batch_id   = p_batch_id
    );


    -- -------------------------------------------------------------------------
    -- FINALISE — Mark remaining PENDING records as CLEAN
    -- -------------------------------------------------------------------------
    UPDATE stg_supplier_feed
    SET    validation_status = 'CLEAN'
    WHERE  batch_id          = p_batch_id
    AND    validation_status = 'PENDING';

    RAISE NOTICE 'Validation complete for batch: %', p_batch_id;
    RETURN QUERY SELECT 'VALIDATION COMPLETE'::TEXT,
        (SELECT COUNT(*) FROM stg_supplier_feed WHERE batch_id = p_batch_id),
        (SELECT COUNT(*) FROM stg_supplier_feed
         WHERE  batch_id = p_batch_id
         AND    validation_status IN ('DIRTY','QUARANTINE')),
        'SUMMARY'::TEXT;

END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION apex.fn_validate_batch IS
    'Runs all 7 validation checks against a staging batch. '
    'Sets validation_status to CLEAN / DIRTY / QUARANTINE on each record. '
    'All errors logged to stg_validation_errors with full context for ops review.';


-- =============================================================================
-- REAL-TIME VALIDATION REPORT
-- Human-readable summary of what went wrong in a batch
-- =============================================================================

CREATE OR REPLACE VIEW vw_validation_summary AS
SELECT
    e.batch_id,
    e.error_type,
    e.severity,
    COUNT(*)                                    AS error_count,
    COUNT(CASE WHEN e.is_resolved THEN 1 END)   AS resolved_count,
    COUNT(CASE WHEN NOT e.is_resolved THEN 1 END) AS outstanding_count,
    MIN(e.logged_at)                            AS first_seen,
    MAX(e.logged_at)                            AS last_seen,
    -- Example of raw value causing error (first occurrence)
    MIN(e.raw_value)                            AS example_bad_value
FROM stg_validation_errors e
GROUP BY e.batch_id, e.error_type, e.severity
ORDER BY e.batch_id DESC, error_count DESC;

COMMENT ON VIEW vw_validation_summary IS
    'Per-batch validation summary. Ops team uses this to resolve quarantined records.';


-- =============================================================================
-- QUARANTINE REVIEW HELPER
-- Shows all unresolved errors with full context for ops team
-- =============================================================================

CREATE OR REPLACE VIEW vw_quarantine_queue AS
SELECT
    e.error_id,
    e.batch_id,
    e.error_type,
    e.severity,
    e.error_field,
    e.raw_value,
    e.expected_format,
    e.error_description,
    stg.raw_order_id,
    stg.raw_supplier_name,
    stg.raw_product_id,
    stg.source_file,
    e.logged_at
FROM stg_validation_errors e
JOIN stg_supplier_feed     stg ON stg.stg_id = e.stg_id
WHERE e.is_resolved = FALSE
ORDER BY e.severity DESC, e.logged_at ASC;

COMMENT ON VIEW vw_quarantine_queue IS
    'Outstanding validation errors awaiting ops resolution. '
    'Update is_resolved=TRUE when fixed and ready for reprocessing.';


-- =============================================================================
-- VALIDATION HEALTH DASHBOARD QUERY
-- Overall data quality across all batches — used in Streamlit app
-- =============================================================================

CREATE OR REPLACE VIEW vw_data_quality_health AS
SELECT
    DATE_TRUNC('month', e.logged_at)::DATE          AS month,
    COUNT(DISTINCT e.batch_id)                       AS batches_processed,
    COUNT(*)                                         AS total_errors,
    SUM(CASE WHEN e.severity = 'ERROR'   THEN 1 ELSE 0 END) AS critical_errors,
    SUM(CASE WHEN e.severity = 'WARNING' THEN 1 ELSE 0 END) AS warnings,
    SUM(CASE WHEN e.error_type = 'SUPPLIER_NAME_MISMATCH'  THEN 1 ELSE 0 END) AS supplier_name_errors,
    SUM(CASE WHEN e.error_type = 'DATE_FORMAT_MISMATCH'    THEN 1 ELSE 0 END) AS date_format_errors,
    SUM(CASE WHEN e.error_type = 'MISSING_TRANSPORT_MODE'  THEN 1 ELSE 0 END) AS missing_transport,
    SUM(CASE WHEN e.error_type = 'NEGATIVE_QUANTITY'       THEN 1 ELSE 0 END) AS negative_qty_errors,
    SUM(CASE WHEN e.error_type = 'COST_OUTLIER'            THEN 1 ELSE 0 END) AS cost_outliers,
    SUM(CASE WHEN e.error_type = 'DUPLICATE_ORDER_ID'      THEN 1 ELSE 0 END) AS duplicates,
    SUM(CASE WHEN e.error_type = 'UNKNOWN_PRODUCT_ID'      THEN 1 ELSE 0 END) AS unknown_products,
    ROUND(
        SUM(CASE WHEN e.is_resolved THEN 1.0 ELSE 0 END)
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                AS resolution_rate_pct
FROM stg_validation_errors e
GROUP BY 1
ORDER BY 1 DESC;

COMMENT ON VIEW vw_data_quality_health IS
    'Monthly data quality trends. Tracks whether supplier data quality improves over time.';


-- =============================================================================
-- USAGE EXAMPLES
-- =============================================================================

-- Run validation for a batch:
-- SELECT * FROM apex.fn_validate_batch('BATCH-20250115-001');

-- See what failed:
-- SELECT * FROM apex.vw_quarantine_queue WHERE batch_id = 'BATCH-20250115-001';

-- See validation summary:
-- SELECT * FROM apex.vw_validation_summary WHERE batch_id = 'BATCH-20250115-001';

-- Mark an error as resolved (after ops team fixes it):
-- UPDATE stg_validation_errors
-- SET is_resolved = TRUE, resolved_at = NOW(), resolved_by = 'ops_team'
-- WHERE error_id = 42;

-- Overall data quality health:
-- SELECT * FROM apex.vw_data_quality_health;


DO $$
BEGIN
    RAISE NOTICE '================================================';
    RAISE NOTICE ' Validation Rules Deployed';
    RAISE NOTICE '================================================';
    RAISE NOTICE ' Checks     : 7 validation rules';
    RAISE NOTICE '   V01 Supplier Name Mismatch  (ERROR)';
    RAISE NOTICE '   V02 Date Format Mismatch     (ERROR)';
    RAISE NOTICE '   V03 Missing Transport Mode   (WARNING)';
    RAISE NOTICE '   V04 Negative Quantity        (ERROR/QUARANTINE)';
    RAISE NOTICE '   V05 Cost Outlier             (WARNING)';
    RAISE NOTICE '   V06 Duplicate Order ID       (ERROR)';
    RAISE NOTICE '   V07 Unknown Product ID       (ERROR/QUARANTINE)';
    RAISE NOTICE ' Views      : vw_validation_summary';
    RAISE NOTICE '              vw_quarantine_queue';
    RAISE NOTICE '              vw_data_quality_health';
    RAISE NOTICE '================================================';
    RAISE NOTICE ' Phase 2 SQL Complete. Ready for Phase 3 Python.';
    RAISE NOTICE '================================================';
END $$;
