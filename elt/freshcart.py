"""FreshCart baseline and assignment extensions adapted from the course notebook.
No instructor credentials are retained. Call connect_snowflake() before running SQL.
"""
import os
from pathlib import Path
conn = None
LANDING_DIR = os.environ.get('FRESHCART_LANDING_DIR', str(Path('.local/landing').resolve()))

# Define deliberately messy sample API data so we can demonstrate cleaning, deduplication, and enrichment.
# ---- Website orders: flat JSON ----
MOCK_WEB_ORDERS = [
    # ORD-1001: email has spaces and capitals, amount has a comma
    {"order_id": "ORD-1001", "cust_email": " Priya.R@Gmail.com ", "cust_name": "priya r",
     "order_date": "2026-09-01", "amount": "1,250.00", "currency": "INR", "pincode": "600041",
     "updated_at": "2026-09-01 10:02:00"},
    # ORD-1003: amount is missing (the mobile copy below has it)
    {"order_id": "ORD-1003", "cust_email": "meera@outlook.com", "cust_name": "MEERA S",
     "order_date": "2026-09-02", "amount": None, "currency": "INR", "pincode": "400050",
     "updated_at": "2026-09-02 09:10:00"},
    # ORD-1002: a dollar order (also sent by the mobile app = duplicate)
    {"order_id": "ORD-1002", "cust_email": "Arjun.K@Yahoo.in ", "cust_name": "Arjun K",
     "order_date": "2026-09-01", "amount": "42.50", "currency": "USD", "pincode": "560034",
     "updated_at": "2026-09-01 11:15:00"},
    # ORD-1004: negative amount -> will be rejected
    {"order_id": "ORD-1004", "cust_email": "rahul.m@gmail.com", "cust_name": "Rahul M",
     "order_date": "Sep 3, 2026", "amount": "-500", "currency": "INR", "pincode": "110001",
     "updated_at": "2026-09-03 12:00:00"},
    # ORD-1005: rupee sign in the amount, lowercase currency, dot after the name
    {"order_id": "ORD-1005", "cust_email": "priya.r@gmail.com", "cust_name": "Priya R.",
     "order_date": "2026-09-03", "amount": "₹ 899", "currency": "inr", "pincode": "600041",
     "updated_at": "2026-09-03 16:45:00"},
    # ORD-1006: bad email and 5-digit pincode -> will be rejected
    {"order_id": "ORD-1006", "cust_email": "vikram@@mail", "cust_name": "Vikram",
     "order_date": "2026-09-04", "amount": 30, "currency": "EUR", "pincode": "99999",
     "updated_at": "2026-09-04 08:30:00"},
]

# ---- Mobile app orders: nested JSON, different field names, day-first dates ----
MOCK_MOBILE_ORDERS = [
    # ORD-1002 again (same as the web copy)
    {"orderId": "ORD-1002", "customer": {"email": "arjun.k@yahoo.in", "name": "Arjun K"},
     "orderDate": "01/09/2026", "total": {"value": "42.50", "currency": "usd"},
     "deliveryPin": "560034", "updatedAt": "2026-09-01T11:15:00"},
    # ORD-1003 again, newer and with the amount filled in
    {"orderId": "ORD-1003", "customer": {"email": "Meera@Outlook.com", "name": "Meera S"},
     "orderDate": "02/09/2026", "total": {"value": "2,100.00", "currency": "INR"},
     "deliveryPin": "400050", "updatedAt": "2026-09-02T18:40:00"},
]

# ---- Customer tier changes (Priya moves from Silver to Gold on 3 Sept) ----
MOCK_CRM_TIER_EVENTS = [
    {"cust_id": "CUST-01", "email": "priya.r@gmail.com", "tier": "Silver", "effective_from": "2023-04-10"},
    {"cust_id": "CUST-01", "email": "priya.r@gmail.com", "tier": "Gold", "effective_from": "2026-09-03"},
    {"cust_id": "CUST-02", "email": "arjun.k@yahoo.in", "tier": "Silver", "effective_from": "2024-01-15"},
    {"cust_id": "CUST-03", "email": "meera@outlook.com", "tier": "Platinum", "effective_from": "2022-11-01"},
]

# ---- Exchange rates: rupees per 1 US dollar, per day ----
MOCK_FX_RESPONSES = [
    {"amount": 1.0, "base": "USD", "start_date": "2026-09-01", "end_date": "2026-09-03",
     "rates": {"2026-09-01": {"INR": 83.20}, "2026-09-02": {"INR": 83.35}, "2026-09-03": {"INR": 83.10}}},
]

# ---- Pincodes: pincode -> (city, state) ----
MOCK_PINCODES = {"600041": ("Chennai", "Tamil Nadu"), "560034": ("Bengaluru", "Karnataka"),
                 "400050": ("Mumbai", "Maharashtra")}


def mock_pincode_response(pin):
    """Reply in the same shape the India Post API uses."""
    if pin not in MOCK_PINCODES:
        return [{"Message": "No records found", "Status": "Error", "PostOffice": None}]
    district, state = MOCK_PINCODES[pin]
    return [{"Message": "Number of pincode(s) found:1", "Status": "Success",
             "PostOffice": [{"Name": district, "District": district, "State": state,
                             "Country": "India", "Pincode": pin}]}]

# Define raw-file writing so each source is saved with run metadata before any transformations.
import gzip, json  # Import tools for gzip compression and JSON conversion.
from datetime import date, datetime, timezone  # Import date/time tools; date is unused here.
from pathlib import Path  # Import Path to work with folders and file paths.


def write_landing(source, records, run_id):  # Define a function to save records from one source.
    """Save source records in a compressed JSON Lines file and return its path."""
    folder = Path(LANDING_DIR) / source  # Build the source folder path; LANDING_DIR must already be defined.
    folder.mkdir(parents=True, exist_ok=True)  # Create the folder and missing parent folders if needed.
    path = folder / f"{source}__{run_id}.json.gz"  # Create a filename containing the source and run ID.
    now = datetime.now(timezone.utc).isoformat()  # Capture the current UTC extraction time.
    with gzip.open(path, "wt", encoding="utf-8") as f:  # Open a compressed file for writing UTF-8 text.
        for rec in records:  # Process each input record.
            envelope = {"source": source, "run_id": run_id, "extracted_at": now, "data": rec}  # Attach extraction metadata to the record.
            f.write(json.dumps(envelope, ensure_ascii=False) + "\n")  # Write one JSON record per line while preserving Unicode characters.
    print(f"   {source}: {len(records)} records -> {path}")  # Display the record count and saved file path.
    return path  # Return the saved file path.

# Define SQL and file-loading helpers so the pipeline can upload raw files and inspect Snowflake tables.
import pandas as pd  # Import pandas to display query results as tables.


def run_sql(sql_text):  # Define a helper to execute multiple SQL statements.
    """Run a SQL script that contains several statements."""
    conn.execute_string(sql_text, remove_comments=True)  # Execute the SQL script after removing comments.


def query(sql):  # Define a helper to execute SQL and retrieve its results.
    """Run one query and return its rows."""
    with conn.cursor() as cur:  # Open a cursor that closes automatically when the block ends.
        cur.execute(sql)  # Execute the supplied SQL statement.
        return cur.fetchall()  # Return all result rows as a list of tuples.


def show(sql):  # Define a helper to return SQL results as a pandas table.
    """Run one query and return the result as a table."""
    with conn.cursor() as cur:  # Open a cursor to interact with Snowflake.
        cur.execute(sql)  # Execute the supplied query.
        return pd.DataFrame(
            cur.fetchall(),  # Retrieve all result rows.
            columns=[c[0] for c in cur.description]  # Use the query's column names as table headings.
        )


def load_file(local_path, table, stage_dir):  # Define a helper to upload a file and load its records.
    """Upload one raw file to Snowflake, then copy its records into a bronze table."""
    uri = "file://" + Path(local_path).resolve().as_posix()  # Convert the local path into an absolute file URI.
    query(
        f"PUT '{uri}' @bronze.landing/{stage_dir}/ AUTO_COMPRESS=FALSE OVERWRITE=FALSE"
    )  # Upload the file to the stage without additional compression or overwriting existing files.
    rows = query(f"""
        -- Load records from the specified stage folder into the target table.
        COPY INTO {table} (source, raw, run_id, extracted_at, src_file, src_row)
        FROM (
          -- Extract JSON fields and capture the source filename and row number.
          SELECT $1:source::STRING, $1:data, $1:run_id::STRING,
                 $1:extracted_at::TIMESTAMP_TZ, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
          -- Read staged files from this folder.
          FROM @bronze.landing/{stage_dir}/
        )
        -- Parse files using the predefined newline-delimited JSON format.
        FILE_FORMAT = (FORMAT_NAME = 'bronze.ff_ndjson')
        -- Abort the COPY statement if a loading error occurs.
        ON_ERROR = 'ABORT_STATEMENT'
    """)  # Execute COPY INTO and collect its loading results.
    loaded = sum(int(r[3]) for r in rows if len(r) > 3)  # Sum the rows loaded from the fourth column of each COPY result.
    print(f"   {loaded} rows -> {table}")  # Display the total loaded rows and destination table.

# Store setup SQL for later execution so the warehouse, schemas, stage, and tables are ready before loading.
SQL_00_SETUP = r"""
-- =====================================================================
-- Setup: creates the warehouse, database, schemas and empty tables.
-- Safe to re-run: everything is IF NOT EXISTS, except the two small seed tables.
-- =====================================================================
CREATE WAREHOUSE IF NOT EXISTS FRESHCART_WH
  WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE;
USE WAREHOUSE FRESHCART_WH;

CREATE DATABASE IF NOT EXISTS FRESHCART;
USE DATABASE FRESHCART;

CREATE SCHEMA IF NOT EXISTS bronze;      -- raw API responses, unchanged
CREATE SCHEMA IF NOT EXISTS silver;      -- cleaned, typed, deduplicated
CREATE SCHEMA IF NOT EXISTS dim;         -- dimensions (customers)
CREATE SCHEMA IF NOT EXISTS ref;         -- reference data (fx, pincodes, tiers)
CREATE SCHEMA IF NOT EXISTS gold;        -- business-ready tables
CREATE SCHEMA IF NOT EXISTS quarantine;  -- rows that failed validation

-- Landing area inside Snowflake for the files Python uploads
CREATE FILE FORMAT IF NOT EXISTS bronze.ff_ndjson TYPE = JSON COMPRESSION = AUTO;
CREATE STAGE IF NOT EXISTS bronze.landing FILE_FORMAT = bronze.ff_ndjson;

-- ---------- BRONZE: one table per source, raw JSON in a VARIANT column ----------
CREATE TABLE IF NOT EXISTS bronze.orders_raw (
  ingest_seq   NUMBER AUTOINCREMENT START 1 INCREMENT 1 ORDER,   -- arrival order
  source       STRING,          -- 'web' or 'mobile'
  raw          VARIANT,         -- the API record exactly as received
  run_id       STRING,
  extracted_at TIMESTAMP_TZ,
  src_file     STRING,
  src_row      NUMBER,
  loaded_at    TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);
CREATE TABLE IF NOT EXISTS bronze.customers_raw (
  ingest_seq NUMBER AUTOINCREMENT START 1 INCREMENT 1 ORDER, source STRING, raw VARIANT,
  run_id STRING, extracted_at TIMESTAMP_TZ, src_file STRING, src_row NUMBER,
  loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);
CREATE TABLE IF NOT EXISTS bronze.fx_raw (
  ingest_seq NUMBER AUTOINCREMENT START 1 INCREMENT 1 ORDER, source STRING, raw VARIANT,
  run_id STRING, extracted_at TIMESTAMP_TZ, src_file STRING, src_row NUMBER,
  loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);
CREATE TABLE IF NOT EXISTS bronze.pincode_raw (
  ingest_seq NUMBER AUTOINCREMENT START 1 INCREMENT 1 ORDER, source STRING, raw VARIANT,
  run_id STRING, extracted_at TIMESTAMP_TZ, src_file STRING, src_row NUMBER,
  loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ---------- REF: small hand-maintained seed tables ----------
CREATE OR REPLACE TABLE ref.tier_multiplier AS
SELECT * FROM VALUES ('Silver', 1), ('Gold', 2), ('Platinum', 3) AS v(tier, multiplier);

CREATE OR REPLACE TABLE ref.state_region AS
SELECT * FROM VALUES
  ('Tamil Nadu','South'), ('Karnataka','South'), ('Kerala','South'), ('Andhra Pradesh','South'),
  ('Telangana','South'), ('Puducherry','South'),
  ('Maharashtra','West'), ('Gujarat','West'), ('Goa','West'), ('Rajasthan','West'),
  ('Delhi','North'), ('Haryana','North'), ('Punjab','North'), ('Uttar Pradesh','North'),
  ('Himachal Pradesh','North'), ('Jammu and Kashmir','North'), ('Uttarakhand','North'),
  ('West Bengal','East'), ('Odisha','East'), ('Bihar','East'), ('Jharkhand','East'), ('Assam','East'),
  ('Madhya Pradesh','Central'), ('Chhattisgarh','Central')
  AS v(state, region);

-- Filled incrementally from the India Post API (see SQL_32_PINCODE_GEO)
CREATE TABLE IF NOT EXISTS ref.pincode_geo (
  pincode STRING PRIMARY KEY, city STRING, state STRING, region STRING,
  updated_at TIMESTAMP_LTZ
);

-- ---------- QUARANTINE, GOLD ----------
CREATE TABLE IF NOT EXISTS quarantine.orders (
  run_id STRING, quarantined_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
  ingest_seq NUMBER, source STRING, order_id STRING, reasons ARRAY, row_data VARIANT
);

CREATE TABLE IF NOT EXISTS gold.fct_orders (
  order_id STRING PRIMARY KEY, order_date DATE, cust_id STRING, email STRING,
  tier STRING, multiplier NUMBER, amount NUMBER(12,2), currency STRING,
  fx_rate NUMBER(12,4), amount_inr NUMBER(14,2), loyalty_points NUMBER,
  is_high_value BOOLEAN, city STRING, state STRING, region STRING,
  updated_at TIMESTAMP_NTZ, row_hash NUMBER, published_at TIMESTAMP_LTZ
);
"""

# Store cleaning SQL for later execution so web/mobile fields are standardized and invalid orders are quarantined.
SQL_10_ORDERS_CLEAN_BASELINE = r"""
-- =====================================================================
-- SILVER 1: unify the two order APIs, cleanse, validate, quarantine.
-- Input : bronze.orders_raw (raw JSON from 'web' and 'mobile')
-- Output: silver.orders_checked (all rows + reasons), silver.orders_clean (good rows),
--         quarantine.orders (bad rows, appended once per row)
-- =====================================================================
CREATE OR REPLACE TRANSIENT TABLE silver.orders_checked AS
WITH unified AS (
  -- The two APIs name and nest fields differently; map both to one set of columns.
  SELECT ingest_seq, source,
         raw:order_id::STRING   AS order_id,
         raw:cust_email::STRING AS cust_email,
         raw:cust_name::STRING  AS cust_name,
         raw:order_date::STRING AS order_date,
         raw:amount::STRING     AS amount,
         raw:currency::STRING   AS currency,
         raw:pincode::STRING    AS pincode,
         raw:updated_at::STRING AS updated_at
  FROM bronze.orders_raw WHERE source = 'web'
  UNION ALL
  SELECT ingest_seq, source,
         raw:orderId::STRING, raw:customer.email::STRING, raw:customer.name::STRING,
         raw:orderDate::STRING, raw:total.value::STRING, raw:total.currency::STRING,
         raw:deliveryPin::STRING, raw:updatedAt::STRING
  FROM bronze.orders_raw WHERE source = 'mobile'
),
typed AS (
  SELECT
    ingest_seq, source,
    TRIM(order_id)                                    AS order_id,
    LOWER(TRIM(cust_email))                           AS email,
    INITCAP(RTRIM(TRIM(cust_name), '.'))              AS name,
    COALESCE(
      TRY_TO_DATE(order_date, 'YYYY-MM-DD'),
      TRY_TO_DATE(order_date, 'DD/MM/YYYY'),          -- mobile API sends day first
      TRY_TO_DATE(order_date, 'MON DD, YYYY')
    )                                                 AS order_date,
    TRY_TO_DECIMAL(REGEXP_REPLACE(amount, '[^0-9.-]', ''), 12, 2) AS amount,
    UPPER(TRIM(currency))                             AS currency,
    TRIM(pincode)                                     AS pincode,
    TRY_TO_TIMESTAMP_NTZ(updated_at)                  AS updated_at
  FROM unified
)
SELECT *,
  ARRAY_CONSTRUCT_COMPACT(
    IFF(order_id IS NULL, 'missing_order_id', NULL),
    IFF(email IS NULL OR NOT REGEXP_LIKE(email, '^[^@\\s]+@[^@\\s]+\\.[a-z]{2,}$'), 'bad_email', NULL),
    IFF(pincode IS NULL OR NOT REGEXP_LIKE(pincode, '^[1-9][0-9]{5}$'), 'bad_pincode', NULL),
    IFF(order_date IS NULL, 'unparseable_date', NULL),
    IFF(updated_at IS NULL, 'unparseable_updated_at', NULL),
    IFF(amount <= 0, 'non_positive_amount', NULL)          -- NULL amount is allowed (flagged below)
  ) AS reasons
FROM typed;

-- Good rows
CREATE OR REPLACE TABLE silver.orders_clean AS
SELECT * EXCLUDE reasons, (amount IS NULL) AS amount_missing
FROM silver.orders_checked
WHERE ARRAY_SIZE(reasons) = 0;

-- Bad rows: kept with their reasons. The NOT EXISTS stops the same bad record being
-- quarantined again when a later run re-extracts it (same source, order, version).
INSERT INTO quarantine.orders (run_id, ingest_seq, source, order_id, reasons, row_data)
SELECT $run_id, c.ingest_seq, c.source, c.order_id, c.reasons, OBJECT_CONSTRUCT(*)
FROM silver.orders_checked c
WHERE ARRAY_SIZE(c.reasons) > 0
  AND NOT EXISTS (
        SELECT 1 FROM quarantine.orders q
        WHERE q.source = c.source
          AND EQUAL_NULL(q.order_id, c.order_id)
          AND EQUAL_NULL(q.row_data:UPDATED_AT::TIMESTAMP_NTZ, c.updated_at))   -- key is UPPERCASE: OBJECT_CONSTRUCT(*) names keys after the columns
QUALIFY ROW_NUMBER() OVER (PARTITION BY c.source, c.order_id, c.updated_at
                           ORDER BY c.ingest_seq DESC) = 1;
"""


# B3 extension. The standardized currency is UPPER(TRIM(currency)).
# A missing currency is also unsupported instead of silently passing SQL NULL logic.
SQL_10_ORDERS_CLEAN = SQL_10_ORDERS_CLEAN_BASELINE.replace(
    "    IFF(amount <= 0, 'non_positive_amount', NULL)",
    "    IFF(currency IS NULL OR currency NOT IN ('INR', 'USD'), 'unsupported_currency', NULL),\n"
    "    IFF(amount <= 0, 'non_positive_amount', NULL)",
)

# Store deduplication SQL for later execution so each order keeps only its newest valid version.
SQL_20_ORDERS_DEDUP = r"""
-- =====================================================================
-- SILVER 2: one row per order_id, newest version wins.
-- Ties on updated_at are broken by arrival order, so reruns give the same answer.
-- =====================================================================
CREATE OR REPLACE TABLE silver.orders_dedup AS
SELECT *
FROM silver.orders_clean
QUALIFY ROW_NUMBER() OVER (
          PARTITION BY order_id
          ORDER BY updated_at DESC, ingest_seq DESC
        ) = 1;
"""

# Store customer-history SQL for later execution so each order can use the customer tier valid on its date.
SQL_30_CUSTOMERS_SCD2 = r"""
-- =====================================================================
-- DIM: build the SCD Type 2 customer table from the CRM's tier-change log.
-- Each change starts a period; the period ends the day before the next change.
-- =====================================================================
CREATE OR REPLACE TABLE dim.customers_scd2 AS
WITH events AS (
  SELECT raw:cust_id::STRING                 AS cust_id,
         LOWER(TRIM(raw:email::STRING))      AS email,
         INITCAP(TRIM(raw:tier::STRING))     AS tier,
         TRY_TO_DATE(raw:effective_from::STRING) AS valid_from,
         loaded_at, ingest_seq
  FROM bronze.customers_raw
  -- the same event may be extracted on many runs; keep the latest copy
  QUALIFY ROW_NUMBER() OVER (PARTITION BY cust_id, valid_from
                             ORDER BY loaded_at DESC, ingest_seq DESC) = 1
)
SELECT cust_id, email, tier, valid_from,
       COALESCE(DATEADD(day, -1, LEAD(valid_from) OVER (PARTITION BY cust_id ORDER BY valid_from)),
                '9999-12-31'::DATE)                                       AS valid_to,
       LEAD(valid_from) OVER (PARTITION BY cust_id ORDER BY valid_from) IS NULL AS is_current
FROM events
WHERE cust_id IS NOT NULL AND valid_from IS NOT NULL;
"""

# Store daily exchange-rate SQL for later execution so orders can be converted to INR even on missing-rate days.
SQL_31_FX_DAILY = r"""
-- =====================================================================
-- REF: daily FX rates to INR, with no gaps.
-- 1. Flatten the API's {"rates": {"2026-09-01": {"INR": 83.2}, ...}} into rows.
-- 2. Rates are not published on weekends/holidays: fill each missing day with the
--    previous published rate, so every order date finds a rate.
-- 3. Add INR = 1.0 for every day, so rupee orders join like any other.
-- =====================================================================
CREATE OR REPLACE TABLE ref.fx_daily AS
WITH published AS (
  SELECT r.raw:base::STRING          AS currency,
         f.key::DATE                 AS rate_date,
         f.value:INR::NUMBER(12,4)   AS rate_to_inr
  FROM bronze.fx_raw r, LATERAL FLATTEN(input => r.raw:rates) f
  QUALIFY ROW_NUMBER() OVER (PARTITION BY currency, rate_date
                             ORDER BY r.loaded_at DESC, r.ingest_seq DESC) = 1
),
bounds AS (
  SELECT MIN(rate_date) AS d0, GREATEST(MAX(rate_date), CURRENT_DATE()) AS d1 FROM published
),
spine AS (                                   -- one row per calendar day d0..d1
  SELECT DATEADD(day, ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1, b.d0) AS d
  FROM bounds b, TABLE(GENERATOR(ROWCOUNT => 4000))
  QUALIFY d <= (SELECT d1 FROM bounds)
),
filled AS (
  SELECT c.currency, s.d AS rate_date,
         LAST_VALUE(p.rate_to_inr) IGNORE NULLS OVER (
           PARTITION BY c.currency ORDER BY s.d
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS rate_to_inr,
         p.rate_to_inr IS NULL AS is_carried_forward
  FROM spine s
  CROSS JOIN (SELECT DISTINCT currency FROM published) c
  LEFT JOIN published p ON p.currency = c.currency AND p.rate_date = s.d
)
SELECT currency, rate_date, rate_to_inr, is_carried_forward FROM filled
UNION ALL
SELECT 'INR', d, 1.0, FALSE FROM spine;
"""

# Store pincode-lookup SQL for later execution so orders can be enriched with city, state, and sales region.
SQL_32_PINCODE_GEO = r"""
-- =====================================================================
-- REF: add newly looked-up pincodes to ref.pincode_geo.
-- India Post gives district and state; the company's sales region comes from
-- the ref.state_region seed table.
-- =====================================================================
MERGE INTO ref.pincode_geo t
USING (
  SELECT p.pincode, p.city, p.state, sr.region
  FROM (
    SELECT raw:pincode::STRING                                  AS pincode,
           raw:response[0]:PostOffice[0]:District::STRING       AS city,
           raw:response[0]:PostOffice[0]:State::STRING          AS state,
           loaded_at, ingest_seq
    FROM bronze.pincode_raw
    WHERE raw:response[0]:Status::STRING = 'Success'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY pincode ORDER BY loaded_at DESC, ingest_seq DESC) = 1
  ) p
  LEFT JOIN ref.state_region sr ON sr.state = p.state
) s
ON t.pincode = s.pincode
WHEN MATCHED AND (t.city <> s.city OR t.state <> s.state OR NVL(t.region,'') <> NVL(s.region,''))
  THEN UPDATE SET city = s.city, state = s.state, region = s.region, updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED
  THEN INSERT (pincode, city, state, region, updated_at)
       VALUES (s.pincode, s.city, s.state, s.region, CURRENT_TIMESTAMP());
"""

# Store enrichment and publishing SQL for later execution so clean orders become business-ready gold records.
SQL_40_GOLD = r"""
-- =====================================================================
-- ENRICH + PUBLISH
-- 1. silver.orders_enriched: point-in-time joins to customer tier and FX rate,
--    computed columns, geography. LEFT JOINs so no order is silently lost.
-- 2. gold.fct_orders: idempotent MERGE. Re-running changes nothing unless a
--    value actually changed (row_hash).
-- =====================================================================
CREATE OR REPLACE TABLE silver.orders_enriched AS
SELECT o.*,
       c.cust_id, c.tier,
       m.multiplier,
       fx.rate_to_inr                              AS fx_rate,
       ROUND(o.amount * fx.rate_to_inr, 2)         AS amount_inr,
       FLOOR(amount_inr / 100) * m.multiplier      AS loyalty_points,
       amount_inr >= 2000                          AS is_high_value,
       g.city, g.state, g.region
FROM silver.orders_dedup o
LEFT JOIN dim.customers_scd2 c
       ON  c.email = o.email
       AND o.order_date BETWEEN c.valid_from AND c.valid_to     -- tier ON the order date
LEFT JOIN ref.tier_multiplier m ON m.tier = c.tier
LEFT JOIN ref.fx_daily fx
       ON  fx.currency = o.currency AND fx.rate_date = o.order_date  -- rate OF the order date
LEFT JOIN ref.pincode_geo g ON g.pincode = o.pincode;

MERGE INTO gold.fct_orders t
USING (
  SELECT order_id, order_date, cust_id, email, tier, multiplier, amount, currency, fx_rate,
         amount_inr, loyalty_points, is_high_value, city, state, region, updated_at,
         HASH(order_date, cust_id, email, tier, multiplier, amount, currency, fx_rate,
              amount_inr, loyalty_points, is_high_value, city, state, region, updated_at) AS row_hash
  FROM silver.orders_enriched
) s
ON t.order_id = s.order_id
WHEN MATCHED AND t.row_hash <> s.row_hash THEN UPDATE SET
  order_date = s.order_date, cust_id = s.cust_id, email = s.email, tier = s.tier,
  multiplier = s.multiplier, amount = s.amount, currency = s.currency, fx_rate = s.fx_rate,
  amount_inr = s.amount_inr, loyalty_points = s.loyalty_points, is_high_value = s.is_high_value,
  city = s.city, state = s.state, region = s.region, updated_at = s.updated_at,
  row_hash = s.row_hash, published_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT
  (order_id, order_date, cust_id, email, tier, multiplier, amount, currency, fx_rate, amount_inr,
   loyalty_points, is_high_value, city, state, region, updated_at, row_hash, published_at)
VALUES
  (s.order_id, s.order_date, s.cust_id, s.email, s.tier, s.multiplier, s.amount, s.currency,
   s.fx_rate, s.amount_inr, s.loyalty_points, s.is_high_value, s.city, s.state, s.region,
   s.updated_at, s.row_hash, CURRENT_TIMESTAMP());
"""

# Define pipeline orchestration and checks so extraction, loading, transformation, and validation run in order.
# Check completeness and uniqueness so data problems are visible before using gold results.
def quality_checks():
    """Each of these numbers should be 0."""
    checks = {
        "rows gained or lost while enriching":
            "SELECT (SELECT COUNT(*) FROM silver.orders_enriched) - (SELECT COUNT(*) FROM silver.orders_dedup)",
        "duplicate orders in gold":
            "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM gold.fct_orders",
        "orders with no customer match":
            "SELECT COUNT_IF(cust_id IS NULL) FROM silver.orders_enriched",
        "orders with an amount but no FX rate":
            "SELECT COUNT_IF(amount IS NOT NULL AND fx_rate IS NULL) FROM silver.orders_enriched",
        "orders dated in the future":
            "SELECT COUNT(*) FROM silver.orders_dedup WHERE order_date > CURRENT_DATE()",
        "orders with no city":
            "SELECT COUNT_IF(city IS NULL) FROM silver.orders_enriched",
    }
    values = {}
    for name, sql in checks.items():
        value = query(sql)[0][0]
        values[name] = int(value or 0)
        print(f"   {name:38s} {value}   {'OK' if value == 0 else 'PROBLEM'}")
    rejected = query("SELECT COUNT_IF(ARRAY_SIZE(reasons) > 0) / NULLIF(COUNT(*), 0) FROM silver.orders_checked")[0][0]
    print(f"   {'share of rows rejected':38s} {float(rejected or 0):.0%}")
    return values


# Orchestrate the dependent stages so each step receives the output of the preceding step.
def run_pipeline():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")      # a unique name for this run
    print("run_id:", run_id)

    # EXTRACT: preserve source records in files so ingestion has an auditable raw input.
    print("1. EXTRACT: sample data -> raw files")
    web_file    = write_landing("web",    MOCK_WEB_ORDERS,      run_id)
    mobile_file = write_landing("mobile", MOCK_MOBILE_ORDERS,   run_id)
    crm_file    = write_landing("crm",    MOCK_CRM_TIER_EVENTS, run_id)
    fx_file     = write_landing("fx",     MOCK_FX_RESPONSES,    run_id)

    # LOAD: upload files and populate bronze so SQL can transform the raw records.
    print("2. LOAD: raw files -> bronze tables")
    load_file(web_file,    "bronze.orders_raw",    f"orders_web/{run_id}")
    load_file(mobile_file, "bronze.orders_raw",    f"orders_mobile/{run_id}")
    load_file(crm_file,    "bronze.customers_raw", f"crm/{run_id}")
    load_file(fx_file,     "bronze.fx_raw",        f"fx/{run_id}")

    # TRANSFORM: clean and deduplicate orders before joining customer and reference data.
    print("3. TRANSFORM: bronze -> silver -> gold")
    query(f"SET run_id = '{run_id}'")          # SQL_10 stamps rejected rows with $run_id
    run_sql(SQL_10_ORDERS_CLEAN)
    run_sql(SQL_20_ORDERS_DEDUP)

    # Pincodes: look up only the ones seen in the orders that we don't know yet
    pins = [row[0] for row in query("""
        SELECT DISTINCT o.pincode FROM silver.orders_dedup o
        WHERE NOT EXISTS (SELECT 1 FROM ref.pincode_geo g WHERE g.pincode = o.pincode)""")]
    print("   new pincodes to look up:", pins)
    if pins:
        lookups = [{"pincode": pin, "response": mock_pincode_response(pin)} for pin in pins]
        pin_file = write_landing("pincode", lookups, run_id)
        load_file(pin_file, "bronze.pincode_raw", f"pincode/{run_id}")

    # Build customer history and reference lookups before enriching and publishing orders.
    run_sql(SQL_30_CUSTOMERS_SCD2)
    run_sql(SQL_31_FX_DAILY)
    run_sql(SQL_32_PINCODE_GEO)
    run_sql(SQL_40_GOLD)

    # CHECK: report missing matches and duplicates so the final output can be reviewed.
    print("4. CHECK")
    quality_checks()
    orders, revenue, points = query("SELECT COUNT(*), SUM(amount_inr), SUM(loyalty_points) FROM gold.fct_orders")[0]
    print(f"GOLD: {orders} orders, revenue ₹{revenue}, {points} loyalty points")

def connect_snowflake(account=None, user=None, authenticator='externalbrowser'):
    """Use an ordinary browser sign-in by default; no password is written to disk."""
    import snowflake.connector
    global conn
    account = account or os.environ.get('SNOWFLAKE_ACCOUNT')
    user = user or os.environ.get('SNOWFLAKE_USER')
    if not account or not user:
        raise ValueError('Set SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER to your own trial details')
    conn = snowflake.connector.connect(account=account, user=user, authenticator=authenticator,
        role=os.environ.get('SNOWFLAKE_ROLE','ACCOUNTADMIN'), client_session_keep_alive=False)
    print('Connected to own trial:', query('SELECT CURRENT_USER(), CURRENT_ROLE()')[0])
    return conn


def transform_existing(run_id):
    """Transform already loaded records, without extracting another baseline batch."""
    query(f"SET run_id = '{run_id}'")
    for sql in [SQL_10_ORDERS_CLEAN, SQL_20_ORDERS_DEDUP, SQL_30_CUSTOMERS_SCD2,
                SQL_31_FX_DAILY, SQL_32_PINCODE_GEO, SQL_40_GOLD]:
        run_sql(sql)
    return quality_checks()


def gold_totals():
    orders, revenue, points = query('SELECT COUNT(*), SUM(amount_inr), SUM(loyalty_points) FROM gold.fct_orders')[0]
    return {'orders':int(orders), 'revenue_inr':str(revenue), 'loyalty_points':int(points)}
