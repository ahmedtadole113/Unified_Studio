"""Phase 1: SQL & Data Modeling Foundations (Days 1-6)."""

DAYS_1_TO_6 = [
    {
        "day": 1,
        "phase": 1,
        "title": "Day 1 – SQL Foundations for Data Engineering (Deep Dive)",
        "estimated_minutes": 90,
        "practice_type": "sql",
        "practice_snippet": """CREATE SCHEMA IF NOT EXISTS de_practice;
CREATE TABLE IF NOT EXISTS de_practice.customers (
    customer_id INT PRIMARY KEY,
    name VARCHAR(100),
    city VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS de_practice.orders (
    order_id INT PRIMARY KEY,
    customer_id INT REFERENCES de_practice.customers(customer_id),
    product VARCHAR(100),
    amount DECIMAL(10,2)
);
INSERT INTO de_practice.customers VALUES (101, 'Riyaz', 'Hyderabad'), (102, 'Aariz', 'Bengaluru') ON CONFLICT DO NOTHING;
INSERT INTO de_practice.orders VALUES (1001, 101, 'Laptop', 50000.00), (1002, 101, 'Monitor', 15000.00), (1003, 102, 'Keyboard', 4500.00) ON CONFLICT DO NOTHING;
SELECT c.name, c.city, COUNT(o.order_id) AS orders_count, SUM(o.amount) AS total_spend
FROM de_practice.customers c
JOIN de_practice.orders o ON c.customer_id = o.customer_id
GROUP BY c.name, c.city;""",
        "goals": [
            "What is OLTP and OLAP?",
            "Why do Data Engineers work mostly with OLAP systems?",
            "What is a Row Store vs Column Store database?",
            "What is Normalization vs Denormalization?",
            "Why do Data Warehouses prefer denormalized models?",
            "How these concepts relate to Databricks, Delta Lake, Synapse, and modern Lakehouse architectures",
        ],
        "lesson_md": """# Day 1 – SQL Foundations for Data Engineering (Deep Dive)

## Goal of Day 1
By the end of today, you should be able to explain:
1. What is OLTP and OLAP?
2. Why do Data Engineers work mostly with OLAP systems?
3. What is a Row Store vs Column Store database?
4. What is Normalization vs Denormalization?
5. Why do Data Warehouses prefer denormalized models?
6. How these concepts connect to Spark, Delta Lake, Iceberg, PostgreSQL DW, and BI tools.

---

## Part 1: Why Data Engineering Exists
Imagine an e-commerce company every second:
```text
Customers place orders -> Customers browse products -> Customers make payments
```
The company has two very different needs:
- **Need 1 (Run the business):** Create Order, Update Customer, Process Payment → requires fast single-row transactions.
- **Need 2 (Analyze the business):** Monthly Revenue, Top Products, Sales Trend, Customer Retention → requires scanning millions of historical rows.

---

## Part 2: OLTP (Online Transaction Processing)
OLTP systems power day-to-day application transactions (banking, e-commerce checkout, order management).
```sql
INSERT INTO Orders VALUES (1001, 101, 'Laptop', 50000);
SELECT * FROM Customers WHERE CustomerID = 101;
```
**Characteristics:** Small single-record reads, frequent `INSERT`/`UPDATE`/`DELETE`, strict ACID consistency, thousands of concurrent users, highly normalized schemas (PostgreSQL, SQL Server, MySQL, Oracle).

---

## Part 3: OLAP (Online Analytical Processing)
OLAP systems power analytics across historical data (Databricks, Snowflake, Synapse, BigQuery, Redshift, DuckDB).
```sql
SELECT Region, ProductCategory, SUM(SalesAmount)
FROM Sales
GROUP BY Region, ProductCategory;
```
**Characteristics:** Large multi-year reads (millions/billions of rows), complex `SUM`/`AVG`/`COUNT`/`GROUP BY` aggregations, read-heavy workloads, denormalized schemas.

### OLTP vs OLAP
| Feature | OLTP | OLAP |
|---|---|---|
| Purpose | Transactions | Analytics |
| Users | App Users | Analysts / BI / ML |
| Data Size | Operational (GBs) | Historical (TBs-PBs) |
| Queries | Simple point lookups | Complex multi-table aggregations |
| Writes | Very Frequent | Batch / Streaming Append & Merge |
| Schema | Normalized (3NF) | Denormalized (Star / Medallion Gold) |

---

## Part 4 & 5: Row Store vs Column Store
- **Row Store (PostgreSQL, MySQL):** Stores `1, John, 1000` contiguously on disk. Ideal for `WHERE ID = 2` (reads 1 row).
- **Column Store (Parquet, Delta Lake, Iceberg, Snowflake):** Stores `ID: [1,2,3]`, `Name: [John,Sarah,Mike]`, `Salary: [1000,2000,3000]` separately. For `SELECT SUM(Salary)`, only the `Salary` column is read — skipping 90%+ of disk I/O and enabling dictionary/RLE compression!

---

## Part 6 & 7: Normalization vs Denormalization
- **Normalization (3NF):** Splits Customers and Orders to eliminate duplicate city/name storage so updates happen in one place with zero anomalies.
- **Denormalization:** Pre-joins Customer + Product + Region + Sales into wide analytical Gold tables so 500M-row BI dashboards avoid expensive runtime multi-way joins.

---

## How This Connects to Our Unified Studio Architecture
```text
PostgreSQL (OLTP) -> Airflow / Redpanda -> MinIO Bronze -> PySpark 4.2 + Delta/Iceberg Silver -> Gold Fact/Dim Marts -> SQL Studio / BI
```

---

## Homework (30 Minutes)
Design a simple e-commerce system with `Customers`, `Orders`, and `Products`:
1. Create a **normalized 3NF schema** in SQL Studio above.
2. Write a `CREATE TABLE AS SELECT` creating a **denormalized reporting mart** `de_practice.gold_customer_orders`.
""",
        "interview_questions": [
            {"question": "Can we point Power BI / Tableau directly at a production OLTP database?", "answer": "Technically yes, but strongly discouraged in production. Heavy analytical scans lock rows, saturate I/O and connection pools, and degrade checkout/API latency. Extract into a Warehouse or Lakehouse (Bronze -> Silver -> Gold) instead.", "scenario": "Real Production Scenario: 500M sales records queried every 5 minutes -> Choose Denormalized OLAP Gold schema over 3NF OLTP."},
            {"question": "Why is Parquet / Delta Lake faster for analytics than CSV or Row-store tables?", "answer": "Parquet is columnar with min/max row-group statistics, dictionary encoding, and vectorized reads. Spark reads only referenced columns and skips entire row groups via predicate pushdown.", "scenario": "Querying 2 columns out of 80 in a 10 TB table scans ~2.5% of data instead of 100%."},
            {"question": "What problem does Normalization solve vs why do Warehouses denormalize?", "answer": "Normalization removes update/insert/delete redundancy in OLTP. Warehouses denormalize into Star Schemas / wide Gold tables to minimize shuffle-heavy joins on read-heavy aggregations.", "scenario": "Updating a customer's city in OLTP updates 1 row; in Gold analytical marts it's refreshed via batch/SCD2 merge."},
        ],
    },
    {
        "day": 2,
        "phase": 1,
        "title": "Day 2 – Keys, Constraints, Referential Integrity & Indexing",
        "estimated_minutes": 75,
        "practice_type": "sql",
        "practice_snippet": """CREATE TABLE IF NOT EXISTS de_practice.dim_products (
    product_sk SERIAL PRIMARY KEY,
    product_bk VARCHAR(32) UNIQUE NOT NULL,
    product_name VARCHAR(120) NOT NULL,
    category VARCHAR(60) NOT NULL,
    unit_price NUMERIC(10,2) CHECK (unit_price > 0)
);
CREATE INDEX IF NOT EXISTS idx_dim_products_cat ON de_practice.dim_products(category);
INSERT INTO de_practice.dim_products (product_bk, product_name, category, unit_price)
VALUES ('SKU-100', 'MacBook M4', 'Electronics', 1599.00), ('SKU-200', 'Spark Guide', 'Books', 49.00)
ON CONFLICT (product_bk) DO NOTHING;
EXPLAIN SELECT * FROM de_practice.dim_products WHERE category = 'Electronics';""",
        "goals": [
            "Natural Key vs Surrogate Key vs Business Key",
            "Primary Key, Foreign Key, Unique, Check, and NOT NULL constraints",
            "B-Tree vs Hash vs Composite Indexes & Index Selectivity",
            "Why Cloud Warehouses/Lakehouses use informational constraints instead of enforced FKs",
        ],
        "lesson_md": """# Day 2 – Keys, Constraints, Referential Integrity & Indexing

## 1. Key Types in Data Engineering
- **Natural / Business Key:** Comes from source system (`email`, `SKU-100`, `o_orderkey`). Can change or collide across merged source systems!
- **Surrogate Key:** Warehouse-generated integer/UUID (`product_sk SERIAL` or `xxhash64`/`monotonically_increasing_id`). Essential for **SCD Type 2** (multiple historical versions of the same business key) and compact integer joins.
- **Composite Key:** Multi-column uniqueness (`(tenant_id, order_id)`).

## 2. Indexes: Speeding Up Reads (and Slowing Down Writes)
- **B-Tree Index (Default in PostgreSQL):** Balanced tree supporting `=`, `<`, `>`, `BETWEEN`, `ORDER BY`.
- **Composite Index Rule (Leftmost Prefix):** An index on `(region, order_date)` accelerates `WHERE region = 'APAC'` and `WHERE region = 'APAC' AND order_date >= '2026-01-01'`, but NOT `WHERE order_date >= '2026-01-01'` alone!
- **Trade-off:** Every index speeds up `SELECT` and slows down `INSERT`/`UPDATE`/`DELETE` because index pages must also be maintained.

## 3. Lakehouse Reality (Delta / Iceberg / Snowflake)
Distributed warehouses often treat `PRIMARY KEY` / `FOREIGN KEY` as **informational/RELY** metadata rather than enforced locks—because enforcing row-level uniqueness across 100 TB distributed Parquet files would destroy parallel write throughput. Data Engineers enforce uniqueness via **deduplication + Data Quality gates + Delta `MERGE`**.

## Homework (30 Minutes)
Inspect `synapse_dw.fact_transactions` in SQL Studio, add a composite index on `(customer_id, timestamp)`, and compare `EXPLAIN ANALYZE` before and after.
""",
        "interview_questions": [
            {"question": "Why do Data Warehouses use Surrogate Keys instead of Natural Keys?", "answer": "Surrogate keys (1) isolate the warehouse from source-system key format changes, (2) allow SCD Type 2 history where one business key has multiple rows over time, and (3) enable faster integer joins across multi-billion row fact tables.", "scenario": "Company acquires a competitor with overlapping Customer IDs 1..10000 -> Surrogate keys prevent collisions cleanly."},
            {"question": "When can an index hurt database performance?", "answer": "During bulk ETL loads or high-write OLTP workloads (extra index maintenance I/O), or on low-cardinality columns (like boolean flags) where sequential scans are faster.", "scenario": "Best practice for bulk warehouse loads: drop/disable non-unique indexes or load via staging, then rebuild/analyze."},
        ],
    },
    {
        "day": 3,
        "phase": 1,
        "title": "Day 3 – Advanced SQL: Joins, CTEs, Subqueries & Execution Order",
        "estimated_minutes": 90,
        "practice_type": "sql",
        "practice_snippet": """WITH customer_spend AS (
    SELECT customer_id, SUM(amount) AS total_spent, COUNT(*) AS order_cnt
    FROM de_practice.orders
    GROUP BY customer_id
)
SELECT c.customer_id, c.name, COALESCE(cs.total_spent, 0) AS total_spent, COALESCE(cs.order_cnt, 0) AS order_cnt
FROM de_practice.customers c
LEFT JOIN customer_spend cs ON c.customer_id = cs.customer_id
ORDER BY total_spent DESC;""",
        "goals": [
            "Logical SQL Query Execution Order (FROM -> JOIN -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY -> LIMIT)",
            "INNER, LEFT, RIGHT, FULL OUTER, CROSS, and SELF Joins (plus NULL behavior)",
            "CTEs vs Subqueries vs Temp Tables & Recursive CTEs",
            "Detecting accidental Cartesian fan-out joins",
        ],
        "lesson_md": """# Day 3 – Advanced SQL: Joins, CTEs & Execution Order

## 1. Logical Execution Order (Interview Favorite!)
You write `SELECT ... FROM ... WHERE ... GROUP BY ... HAVING ... ORDER BY ... LIMIT`, but the SQL engine executes:
1. `FROM` & `JOIN` (builds working dataset)
2. `WHERE` (filters individual rows before grouping)
3. `GROUP BY` (aggregates groups)
4. `HAVING` (filters aggregated groups)
5. `SELECT` & Window Functions (computes expressions/aliases)
6. `DISTINCT`
7. `ORDER BY`
8. `LIMIT / OFFSET`
*Why this matters:* You cannot reference a `SELECT` alias in `WHERE`, because `WHERE` runs before `SELECT`!

## 2. Join Pitfall: `WHERE` vs `ON` in `LEFT JOIN`
```sql
-- WRONG: turns LEFT JOIN into INNER JOIN because NULL rows fail WHERE!
SELECT c.name, o.amount FROM Customers c LEFT JOIN Orders o ON c.id = o.cust_id WHERE o.status = 'COMPLETED';
-- RIGHT: filter right table inside ON clause
SELECT c.name, o.amount FROM Customers c LEFT JOIN Orders o ON c.id = o.cust_id AND o.status = 'COMPLETED';
```

## 3. CTEs (`WITH`) & Recursive CTEs
CTEs improve readability and modularity in multi-step Medallion SQL transforms. Recursive CTEs traverse org charts, bill-of-materials, or generate date spines (`generate_series` / recursive anchor + union all).

## Homework
Write a SQL query returning customers who have **never** placed an order using BOTH `LEFT JOIN ... WHERE o.order_id IS NULL` and `NOT EXISTS` (avoiding `NOT IN` when NULLs may exist!).
""",
        "interview_questions": [
            {"question": "Why is `NOT IN (SELECT col FROM B)` dangerous compared to `NOT EXISTS`?", "answer": "In SQL three-valued logic, if the subquery returns even ONE `NULL` value, `x NOT IN (1, 2, NULL)` evaluates to UNKNOWN for every row and returns 0 rows! `NOT EXISTS` handles NULLs safely.", "scenario": "Production pipeline silently dropped all incremental rows because an optional foreign key column contained a single NULL."},
            {"question": "What happens when you put a right-table filter in `WHERE` after a `LEFT JOIN`?", "answer": "Non-matching left rows have NULL for right-table columns, so `WHERE right.col = 'val'` filters them out—silently converting your LEFT JOIN into an INNER JOIN.", "scenario": "Common BI bug causing missing zero-sales stores in monthly reports."},
        ],
    },
    {
        "day": 4,
        "phase": 1,
        "title": "Day 4 – Window Functions Mastery (Top-N, Deduplication & Running Totals)",
        "estimated_minutes": 90,
        "practice_type": "sql",
        "practice_snippet": """WITH ranked_orders AS (
    SELECT
        order_id,
        customer_id,
        product,
        amount,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC) AS rn,
        SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
        LAG(amount) OVER (PARTITION BY customer_id ORDER BY order_id) AS prev_order_amount
    FROM de_practice.orders
)
SELECT * FROM ranked_orders;""",
        "goals": [
            "ROW_NUMBER vs RANK vs DENSE_RANK",
            "LAG, LEAD, FIRST_VALUE, LAST_VALUE",
            "Frame Clauses: ROWS BETWEEN vs RANGE BETWEEN",
            "Production Deduplication & Top-N per Partition",
        ],
        "lesson_md": """# Day 4 – Window Functions Mastery

Window functions compute across a sliding set of rows (`OVER (PARTITION BY ... ORDER BY ...)`) **without collapsing rows** like `GROUP BY`.

## 1. Ranking Functions: `100, 100, 90`
- `ROW_NUMBER()`: `1, 2, 3` (always unique; ideal for deterministic **CDC / event deduplication**)
- `RANK()`: `1, 1, 3` (leaves gaps on ties)
- `DENSE_RANK()`: `1, 1, 2` (no gaps; ideal for **Top-N salaries/products** where ties count as same rank)

## 2. Deduplication Pattern (Used in Almost Every DE Pipeline)
```sql
WITH dedup AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY updated_at DESC) AS rn
    FROM bronze_transactions
)
SELECT * FROM dedup WHERE rn = 1;
```

## 3. Rolling Windows (`ROWS` vs `RANGE`)
`ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` calculates a true 7-row moving average; `RANGE` groups peers with equal `ORDER BY` values and can unexpectedly include tied rows.

## Homework
Write a SQL query to find the **second highest** order amount per customer and compute a 3-order moving average.
""",
        "interview_questions": [
            {"question": "Explain the difference between ROW_NUMBER, RANK, and DENSE_RANK.", "answer": "For ties (100, 100, 90): ROW_NUMBER assigns 1,2,3; RANK assigns 1,1,3 (gap); DENSE_RANK assigns 1,1,2 (no gap).", "scenario": "Top 3 highest paid employees per department -> Use DENSE_RANK() <= 3; Deduplicating Kafka duplicate events -> Use ROW_NUMBER() = 1."},
            {"question": "How do you calculate Month-over-Month (MoM) revenue growth in SQL?", "answer": "Aggregate monthly revenue in a CTE, then use `LAG(rev) OVER (ORDER BY month)` and compute `(rev - prev_rev) / NULLIF(prev_rev, 0) * 100`.", "scenario": "Always wrap denominator in `NULLIF(..., 0)` to avoid division-by-zero in ANSI SQL mode (Spark 4.2 default!)."},
        ],
    },
    {
        "day": 5,
        "phase": 1,
        "title": "Day 5 – Dimensional Modeling: Star Schema, Snowflake & Fact Types",
        "estimated_minutes": 80,
        "practice_type": "sql",
        "practice_snippet": """CREATE SCHEMA IF NOT EXISTS dw_model;
CREATE TABLE IF NOT EXISTS dw_model.dim_date (date_key INT PRIMARY KEY, full_date DATE, year INT, month INT, quarter INT);
CREATE TABLE IF NOT EXISTS dw_model.fact_sales (
    sales_sk BIGSERIAL PRIMARY KEY,
    date_key INT REFERENCES dw_model.dim_date(date_key),
    customer_id INT,
    quantity INT,
    net_amount NUMERIC(12,2)
);
SELECT table_name FROM information_schema.tables WHERE table_schema = 'dw_model';""",
        "goals": [
            "Kimball Dimensional Modeling: Grain declaration first",
            "Fact Tables: Transaction, Periodic Snapshot, Accumulating Snapshot, Factless Fact",
            "Star Schema vs Snowflake Schema trade-offs",
            "Conformed Dimensions & Degenerate Dimensions",
        ],
        "lesson_md": """# Day 5 – Dimensional Modeling (Kimball)

## 1. Step 1 of Any Fact Table: Declare the Grain!
Grain = what ONE row represents (e.g., *"One row per line item on a customer order"*). Mixing grains in one fact table causes double-counting bugs.

## 2. Four Fact Table Types
1. **Transaction Fact:** One row per event (`fact_orders`, `fact_clicks`). Most granular.
2. **Periodic Snapshot:** One row per entity per time period (`daily_account_balance`).
3. **Accumulating Snapshot:** One row per lifecycle (`order_placed_dt`, `shipped_dt`, `delivered_dt`) updated as milestones complete.
4. **Factless Fact:** Captures events with no numeric measures (student attendance, promotion eligibility).

## 3. Star vs Snowflake
- **Star Schema:** Fact at center surrounded by denormalized Dimensions (`dim_product` contains category & brand). Fewer joins, faster BI queries.
- **Snowflake Schema:** Normalizes dimensions (`dim_product -> dim_subcategory -> dim_category`). Saves tiny dimension storage at the cost of extra joins.

## Homework
Look at the TPC-H tables (`customer`, `orders`, `lineitem`, `part`, `supplier`, `nation`, `region`) in `data/` and design a Star Schema with `fact_line_sales` and 4 dimensions.
""",
        "interview_questions": [
            {"question": "What is a Conformed Dimension?", "answer": "A dimension (like `dim_date` or `dim_customer`) shared consistently across multiple fact tables (`fact_sales`, `fact_returns`, `fact_support`) so cross-process metrics drill across cleanly.", "scenario": "Finance and Marketing both report by `dim_date` fiscal calendar without mismatched week boundaries."},
            {"question": "What are Additive, Semi-Additive, and Non-Additive facts?", "answer": "Additive: sum across all dimensions (`sales_amount`). Semi-additive: sum across some dimensions like products/stores, NOT time (`account_balance` -> use AVG or LAST_VALUE over time). Non-additive: ratios/percentages (`unit_price`, `margin_pct` -> sum numerator & denominator separately).", "scenario": "Summing daily bank balances across 30 days gives 30x inflated assets!"},
        ],
    },
    {
        "day": 6,
        "phase": 1,
        "title": "Day 6 – Slowly Changing Dimensions (SCD Types 1, 2, 3, 4, 6)",
        "estimated_minutes": 85,
        "practice_type": "sql",
        "practice_snippet": """CREATE TABLE IF NOT EXISTS dw_model.dim_customer_scd2 (
    customer_sk SERIAL PRIMARY KEY,
    customer_id INT NOT NULL,
    city VARCHAR(100),
    effective_from DATE NOT NULL,
    effective_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL
);
INSERT INTO dw_model.dim_customer_scd2 (customer_id, city, effective_from, effective_to, is_current)
VALUES (101, 'Hyderabad', '2025-01-01', '2026-05-31', FALSE), (101, 'Bengaluru', '2026-06-01', '9999-12-31', TRUE)
ON CONFLICT DO NOTHING;
SELECT * FROM dw_model.dim_customer_scd2 ORDER BY customer_id, effective_from;""",
        "goals": [
            "SCD Type 1 (Overwrite) vs Type 2 (Full History Rows) vs Type 3 (Previous Value Column)",
            "SCD Type 4 (Mini-Dimension) & Type 6 (Hybrid 1+2+3)",
            "Implementing SCD Type 2 via Delta Lake MERGE / PostgreSQL Upsert",
            "Handling Late-Arriving Facts & Dimensions",
        ],
        "lesson_md": """# Day 6 – Slowly Changing Dimensions (SCD)

Suppose Customer 101 moves from `Hyderabad` to `Bengaluru`. How should historical orders be attributed?
- **SCD Type 1:** Overwrite `city = 'Bengaluru'`. No history kept; past sales now appear under Bengaluru.
- **SCD Type 2 (Gold Standard):** Expire the old row (`effective_to = '2026-05-31', is_current = FALSE`) and insert a new row with a new surrogate key (`effective_from = '2026-06-01', effective_to = '9999-12-31', is_current = TRUE`). Historical facts join to the surrogate key active on `order_date`!
- **SCD Type 3:** Add `prev_city` column. Tracks only 1 prior state.
- **SCD Type 4:** Split fast-changing attributes (e.g., credit score band) into a separate mini-dimension to prevent huge `dim_customer` row explosion.

## Implementing SCD Type 2 with Delta Lake `MERGE`
1. Stage incoming changes and join against current `is_current = true` records where hash of tracked attributes changed.
2. Union staged rows twice: once with `mergeKey = customer_id` (to expire existing current row) and once with `mergeKey = NULL` (to force INSERT of the new active version).

## Homework
Write a SQL query joining `fact_sales` to `dim_customer_scd2` by both `is_current = TRUE` (as-is reporting) and point-in-time `order_date BETWEEN effective_from AND effective_to` (as-was reporting).
""",
        "interview_questions": [
            {"question": "How do you implement SCD Type 2 cleanly in Spark / Delta Lake without two passes?", "answer": "Use the two-row union trick in `MERGE INTO`: match existing current rows on a non-null `mergeKey` to set `is_current = false, effective_to = current_date`, and include a second row with `mergeKey = NULL` so `WHEN NOT MATCHED` inserts the new active row in one atomic ACID transaction.", "scenario": "Prevents partial updates where old row is expired but new row fails to insert."},
            {"question": "How do you handle a Late-Arriving Fact when the Dimension record doesn't exist yet?", "answer": "Insert an 'inferred/placeholder' dimension row with default attributes (`Unknown`), link the fact to its surrogate key, and backfill attributes later via SCD Type 1 update when the dimension record arrives.", "scenario": "Clickstream arrives 2 minutes before new user registration syncs from OLTP."},
        ],
    },
]

