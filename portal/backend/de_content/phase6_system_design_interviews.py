"""Phase 6: System Design & Data Engineering Interview Crack Playbook (Days 28-30)."""

DAYS_28_TO_30 = [
    {
        "day": 28,
        "phase": 6,
        "title": "Day 28 – System Design 1: Real-Time E-Commerce Clickstream & Fraud Pipeline",
        "estimated_minutes": 95,
        "practice_type": "streaming",
        "practice_snippet": """# System Design Blueprint: Producers -> Redpanda -> Spark Structured Streaming (Watermarks) -> Delta Gold + Fraud Alerts""",
        "goals": [
            "End-to-End Architecture for 100k events/sec",
            "Lambda Architecture vs Kappa Architecture",
            "Handling Late Data, Idempotent Sinks & Sub-Second Fraud Scoring",
        ],
        "lesson_md": """# Day 28 – System Design: Real-Time Clickstream & Fraud

## Prompt: Design a pipeline processing 100,000 click/payment events per second with <5s fraud alerting and hourly BI reporting.

```text
Web/Mobile SDK -> API Gateway -> Redpanda/Kafka (partitioned by user_id)
                                     ├── Spark Structured Streaming (5m sliding window + 2m watermark) -> Fraud Alert Queue (RabbitMQ)
                                     └── Delta Lake Bronze -> Hourly/Streaming Compaction Silver -> Gold BI Mart
```

### Key Design Decisions to Explain in Interviews
1. **Partition Key:** `user_id` keeps all user clicks/payments ordered in one partition for sessionization & velocity fraud checks.
2. **Lambda vs Kappa:** Prefer **Kappa** (single streaming engine + replayable Kafka/Delta log) over Lambda (maintaining duplicate batch + streaming codebases).
3. **Backpressure & Observability:** Monitor Kafka consumer lag (`slo-kafka-lag`), Spark batch duration vs trigger interval, and DLQ rate.
""",
        "interview_questions": [
            {"question": "Compare Lambda Architecture vs Kappa Architecture. Which do modern teams prefer?", "answer": "Lambda runs parallel batch (accuracy) and speed/streaming (low latency) layers, requiring duplicate business logic. Kappa uses a single streaming pipeline over a replayable log (Kafka/Delta), simplifying maintenance. Modern Lakehouse (Delta/Iceberg) adopts a unified Kappa-style engine.", "scenario": "Maintaining identical fraud rules in both Hive SQL and Flink caused metric drift."},
        ],
    },
    {
        "day": 29,
        "phase": 6,
        "title": "Day 29 – System Design 2: Enterprise Lakehouse Migration (OLTP + APIs -> Gold)",
        "estimated_minutes": 95,
        "practice_type": "sql",
        "practice_snippet": """-- Verify Gold marts & schema readiness in PostgreSQL DW
SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('synapse_dw', 'dw_model', 'de_practice');""",
        "goals": [
            "Migrating Legacy On-Prem SQL Server + REST APIs to Cloud/Local Lakehouse",
            "Zero-Downtime Cutover & Parallel Shadow Reconciliation",
            "Capacity Estimation, Partitioning Strategy & Cost Controls",
        ],
        "lesson_md": """# Day 29 – System Design: Enterprise Lakehouse Migration

## 5-Step Principal Engineer Migration Framework
1. **Discovery & Contracts:** Inventory source OLTP tables, daily growth rates, SLAs, and PII fields.
2. **Ingestion Split:** Bulk historical snapshot (JDBC/Spark parallel partitioned read using `numPartitions` + `partitionColumn`) + ongoing CDC (Debezium/Kafka) + API watermarks (Airflow).
3. **Medallion Transformation:** Bronze (raw Parquet/Delta) → Silver (SCD Type 2 + Data Quality) → Gold (Star Schema).
4. **Shadow Validation:** Run legacy and new Gold pipelines in parallel for 14 days; assert automated row-count & financial sum parity (<0.001% variance).
5. **Cutover & Governance:** Flip BI views to Gold, enforce RBAC & FinOps budgets, decommission legacy ETL.
""",
        "interview_questions": [
            {"question": "How do you extract a 500 GB PostgreSQL/SQL Server table into Spark quickly without overloading the source DB?", "answer": "Use JDBC partitioned parallel reads (`partitionColumn`, `lowerBound`, `upperBound`, `numPartitions` capped safely e.g. 8–16) against a **read replica**, then switch to incremental CDC afterwards so the 500 GB extract runs only once.", "scenario": "Single-threaded JDBC read took 14 hours and failed on network blip; replica partitioned read finished in 35 minutes."},
        ],
    },
    {
        "day": 30,
        "phase": 6,
        "title": "Day 30 – Final DE Mock Interview: SQL Puzzles, Spark RCA & Behavioral STAR",
        "estimated_minutes": 100,
        "practice_type": "sql",
        "practice_snippet": """-- Mock SQL Challenge: Find consecutive / multi-order customers and rank by lifetime spend
WITH totals AS (
    SELECT customer_id, SUM(amount) AS lifetime_spend, COUNT(*) AS orders
    FROM de_practice.orders
    GROUP BY customer_id
)
SELECT c.name, t.lifetime_spend, t.orders, DENSE_RANK() OVER (ORDER BY t.lifetime_spend DESC) AS spend_rank
FROM totals t JOIN de_practice.customers c ON t.customer_id = c.customer_id;""",
        "goals": [
            "Solve Top 5 FAANG/Enterprise DE SQL Coding Patterns under 15 minutes",
            "Debug a Live Spark + Airflow + Kubernetes Failure Scenario (RCA)",
            "Structure STAR Behavioral Answers for Senior/Lead DE Roles",
        ],
        "lesson_md": """# Day 30 – Final Data Engineering Mock Interview

## Round 1: Live SQL Coding Drills
Practice solving these in SQL Studio without hints:
1. **Consecutive Days / Streaks:** `date - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY date)` islands-and-gaps trick.
2. **Sessionization:** Use `LAG(event_ts)` and cumulative `SUM(CASE WHEN gap > 30m THEN 1 ELSE 0 END) OVER (...)` to assign session IDs.
3. **Retention / Cohort:** Self-join or `MIN(order_date) OVER (PARTITION BY user_id)` for Month-0 cohort vs Month-N retention.

## Round 2: Production Incident RCA Drill
*"Our 6 AM Airflow PySpark job failed after 40 minutes with Kubernetes `OOMKilled` (Exit 137) after running fine for 6 months."*
Walk the interviewer through:
1. Check recent volume spike / upstream schema change / skewed join key (`NULL` burst).
2. Inspect Spark UI stage skew & spill metrics + Loki driver/executor logs.
3. Immediate mitigation: filter/salt skewed key, tune `shuffle.partitions` & `memoryOverhead`, re-run idempotent DAG.
4. Long-term fix: add DQ volume/skew gate + SRE memory saturation alert!
""",
        "interview_questions": [
            {"question": "How do you compute user sessions in SQL when a session times out after 30 minutes of inactivity?", "answer": "Use `LAG(ts) OVER (PARTITION BY user_id ORDER BY ts)` to detect gaps > 30 minutes (`is_new_session = 1 else 0`), then take a running `SUM(is_new_session) OVER (PARTITION BY user_id ORDER BY ts)` to generate a unique `session_id` per user.", "scenario": "Classic Senior Data Engineer SQL live-coding question."},
            {"question": "Tell me about the hardest data pipeline failure you solved (STAR format).", "answer": "Structure concisely: Situation (scale + SLA), Task (ownership), Action (root cause via Spark UI/logs/metrics + exact technical fix like salting/AQE/idempotent MERGE), Result (quantified speedup, cost saved, and preventive SLO/DQ check added).", "scenario": "Practice with real numbers from this Unified Studio's TPC-H & Chaos drills!"},
        ],
    },
]

