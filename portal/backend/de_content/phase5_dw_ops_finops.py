"""Phase 5: Cloud Warehousing, Pipeline SRE Observability, FinOps & Security (Days 24-27)."""

DAYS_24_TO_27 = [
    {
        "day": 24,
        "phase": 5,
        "title": "Day 24 – Data Warehouse Internals & Query Performance (EXPLAIN ANALYZE)",
        "estimated_minutes": 80,
        "practice_type": "sql",
        "practice_snippet": """EXPLAIN (ANALYZE, BUFFERS)
SELECT table_schema, COUNT(*)
FROM information_schema.tables
GROUP BY table_schema;""",
        "goals": [
            "Reading `EXPLAIN (ANALYZE, BUFFERS)`: Seq Scan vs Index Scan vs Hash Join",
            "Table Partitioning (Range/List/Hash) & Materialized Views",
            "PostgreSQL Vacuum, Statistics (`ANALYZE`), & Connection Pool Saturation",
        ],
        "lesson_md": """# Day 24 – Warehouse Performance & `EXPLAIN ANALYZE`

- **Estimated vs Actual Rows:** Huge mismatch (`rows=1` estimated, `rows=500000` actual) means stale table statistics → run `ANALYZE table_name;`!
- **Hash Join vs Nested Loop:** Nested Loop on 1M × 1M rows causes catastrophic latency; Hash Join or Merge Join scales cleanly.
- **Connection Exhaustion:** Data tools opening hundreds of idle connections saturate Postgres `max_connections` → use connection pooling (PgBouncer) and monitor `pg_stat_activity`.
""",
        "interview_questions": [
            {"question": "A dashboard query suddenly slowed down from 200ms to 45s after a 10M-row load. How do you diagnose it?", "answer": "Run `EXPLAIN (ANALYZE, BUFFERS)` to compare planner row estimates vs actual rows, check if an index scan flipped to a sequential scan or nested loop due to stale statistics (`ANALYZE`), check lock contention (`pg_stat_activity`), and check temp disk spill.", "scenario": "Stale statistics after massive bulk load caused planner to pick Nested Loop over Hash Join."},
        ],
    },
    {
        "day": 25,
        "phase": 5,
        "title": "Day 25 – Data Engineering Observability & Pipeline SRE Correlation",
        "estimated_minutes": 85,
        "practice_type": "sql",
        "practice_snippet": """-- Check SRE Ops -> Incidents & SLOs in Unified Studio to inspect DE<->SRE correlated failures!
SELECT NOW() AS checked_at;""",
        "goals": [
            "The 4 Data Observability Pillars: Freshness, Volume, Schema, Quality",
            "SLOs for Data Engineers: DAG Success Rate, Spark Success Rate, Data Freshness, Pipeline Latency",
            "Correlating Airflow/Spark Failures to K8s/Docker/Prometheus/Loki Evidence",
        ],
        "lesson_md": """# Day 25 – Data Engineering + SRE Correlation

In real production teams, Data Engineers and SREs debug the **same outage** from two views:
- **DE View:** `Airflow DAG failed -> Spark task failed -> Gold table stale by 3 hours`.
- **SRE View:** `K8s pod OOMKilled / Container restarted -> Prometheus memory > 90% -> Loki shows java.lang.OutOfMemoryError`.

Our Unified Studio's **Correlation Engine** (`/api/v1/incidents/correlate`) automatically links both perspectives on a single Incident timeline!
""",
        "interview_questions": [
            {"question": "What SLOs would you define for a critical daily revenue pipeline?", "answer": "(1) Pipeline Freshness SLO (Gold mart updated before 07:00 UTC 99.5% of days), (2) DAG Success Rate SLO (>= 99%), (3) Data Completeness/Quality SLO (null PKs = 0%, row-count variance within 3-sigma), and (4) Pipeline Latency SLO (< 45m).", "scenario": "Business SLA says Finance dashboard must be ready by 8 AM."},
        ],
    },
    {
        "day": 26,
        "phase": 5,
        "title": "Day 26 – Data FinOps & Compute/Storage Cost Optimization",
        "estimated_minutes": 75,
        "practice_type": "pyspark",
        "practice_snippet": """# Visit FinOps tab in Unified Studio to inspect measured container RAM/CPU and idle service detection.""",
        "goals": [
            "Compute FinOps: Right-sizing clusters, Spot/Preemptible workers, Auto-termination",
            "Query FinOps: Partition pruning, Z-Order/Clustering, avoiding `SELECT *` on columnar stores",
            "Storage FinOps: `VACUUM` retention, S3 lifecycle tiering, eliminating duplicate pipelines",
        ],
        "lesson_md": """# Day 26 – Data FinOps & Cost Optimization

Top 5 real-world cloud DE cost savings:
1. Replace `SELECT *` on Parquet/BigQuery/Snowflake with explicit column projection (-70% scan cost).
2. Add partition pruning filters (`WHERE order_date >= current_date - 7`).
3. Compact small files & run `VACUUM` with sensible retention.
4. Auto-stop idle interactive clusters / unused compose profiles (as implemented in Unified Studio's M4 8GB Profile Advisor!).
5. Consolidate duplicated brokers/engines (e.g., 1 Redpanda + 1 Spark cluster instead of 2).
""",
        "interview_questions": [
            {"question": "Your cloud data warehouse bill doubled this month. How do you investigate and reduce it?", "answer": "Audit top-cost queries/jobs by bytes scanned & slot/DBU hours, look for full-table scans missing partition filters, runaway `SELECT *` dashboards refreshing every minute, uncompacted small files, and idle all-purpose clusters left running overnight.", "scenario": "A single BI report refreshing every 60s without partition filters accounted for 45% of Snowflake/BigQuery spend."},
        ],
    },
    {
        "day": 27,
        "phase": 5,
        "title": "Day 27 – Data Governance, Security, PII Masking & Lineage",
        "estimated_minutes": 75,
        "practice_type": "sql",
        "practice_snippet": """-- Example Dynamic PII Masking View in PostgreSQL DW
CREATE OR REPLACE VIEW de_practice.v_customers_masked AS
SELECT customer_id, LEFT(name, 1) || '***' AS masked_name, city
FROM de_practice.customers;
SELECT * FROM de_practice.v_customers_masked;""",
        "goals": [
            "RBAC & Least Privilege across Storage, Compute, and BI",
            "PII Protection: Tokenization, SHA-256 Hashing, Dynamic Masking Views, Row-Level Security",
            "Column-Level Lineage, Audit Logging & Secrets Hygiene (No Hardcoded Credentials)",
        ],
        "lesson_md": """# Day 27 – Data Security, PII & Governance

- **Never store plaintext secrets** in notebooks, DAGs, or `users.json`—use `.env` / Vault / Secret Managers and PBKDF2/Argon2 hashing.
- **PII Handling:** Hash/tokenize emails & SSNs in Silver; expose masked/aggregated Gold views to general analysts while restricting raw PII tables to privileged roles.
- **Auditability:** Every schema change, secret access, and query/service action should emit an immutable audit log entry.
""",
        "interview_questions": [
            {"question": "How do you handle GDPR 'Right to be Forgotten' (deletion requests) in an immutable S3/Delta Lakehouse?", "answer": "Separate PII into a keyed lookup table or use Delta/Iceberg `DELETE FROM table WHERE user_id = ...` followed by `VACUUM` after retention window (or crypto-shredding: encrypt each user's PII with a per-user key and delete the key).", "scenario": "Rewriting 100 TB of Parquet for 1 deleted user is slow—partitioning/clustering or crypto-shredding makes compliance fast."},
        ],
    },
]

