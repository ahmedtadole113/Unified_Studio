"""Phase 4: Orchestration (Airflow) & Streaming (Redpanda/Kafka & RabbitMQ) (Days 19-23)."""

DAYS_19_TO_23 = [
    {
        "day": 19,
        "phase": 4,
        "title": "Day 19 – Apache Airflow Architecture & DAG Design",
        "estimated_minutes": 80,
        "practice_type": "airflow",
        "practice_snippet": """SELECT 'Check Airflow tab for project1_adf_batch_pipeline, project3_adf_incremental_load, pyspark_daily_sales_dag' AS next_step;""",
        "goals": [
            "Airflow Components: Webserver, Scheduler, Executor, Metadata DB, Triggerer",
            "DAGs, Tasks, Operators, Hooks, Connections, XComs",
            "Sensors vs Deferrable Operators",
        ],
        "lesson_md": """# Day 19 – Apache Airflow Architecture

- **Scheduler:** Parses DAGs, evaluates schedules/dependencies, schedules TaskInstances.
- **Executor:** Runs tasks (`SequentialExecutor`, `LocalExecutor`, `CeleryExecutor`, `KubernetesExecutor`).
- **XComs:** Small metadata passing between tasks (IDs, file paths, watermarks—NEVER pass large DataFrames via XCom!).
- **Deferrable Operators:** Release worker slots while waiting for external APIs/jobs, avoiding worker starvation.
""",
        "interview_questions": [
            {"question": "Why shouldn't you pass 500 MB of data through Airflow XComs?", "answer": "XComs serialize data into Airflow's metadata database (Postgres/SQLite), bloating DB size and crashing the scheduler/webserver. Pass an S3/MinIO path or table reference in XCom instead.", "scenario": "Classic Airflow production outage caused by passing Pandas DataFrames in XCom."},
        ],
    },
    {
        "day": 20,
        "phase": 4,
        "title": "Day 20 – Production Airflow Patterns (Idempotency, Backfills & SLAs)",
        "estimated_minutes": 80,
        "practice_type": "airflow",
        "practice_snippet": """-- Inspect DAG-loaded DW tables
SELECT COUNT(*) AS customer_revenue_rows FROM synapse_dw.fact_customer_revenue;""",
        "goals": [
            "Idempotent DAG Design using `{{ ds }}` logical execution dates",
            "Catchup, Backfills, Retries, Exponential Backoff & `on_failure_callback`",
            "Dynamic Task Mapping (`expand()`) & Airflow SLA Misses",
        ],
        "lesson_md": """# Day 20 – Production Airflow Patterns

**Golden Rule of Airflow:** Every DAG run for logical date `{{ ds }}` must produce the exact same result if re-run 10 times (**Idempotency**).
- Never use `datetime.now()` inside SQL filters—use Airflow's `data_interval_start` / `{{ ds }}` so historical backfills work deterministically!
- Replace `INSERT` with `DELETE WHERE dt = '{{ ds }}' + INSERT` or Delta `replaceWhere` / `MERGE`.
""",
        "interview_questions": [
            {"question": "How do you make an Airflow pipeline idempotent for safe backfills?", "answer": "Parameterize reads/writes by Airflow's logical `{{ ds }}` / `data_interval_start` (not `datetime.now()`), and use atomic partition overwrites (`replaceWhere` / `INSERT OVERWRITE`) or `MERGE` upserts so re-running never creates duplicate rows.", "scenario": "Re-running a failed Tuesday partition backfill cleanly replaces Tuesday's slice without duplicating data."},
        ],
    },
    {
        "day": 21,
        "phase": 4,
        "title": "Day 21 – Kafka / Redpanda Internals (Partitions, Offsets & Consumer Lag)",
        "estimated_minutes": 90,
        "practice_type": "streaming",
        "practice_snippet": """# Check Streaming -> Kafka/Redpanda tab in Unified Studio to create a topic, produce messages, and inspect consumer group lag.""",
        "goals": [
            "Topics, Partitions, Replicas, ISR (In-Sync Replicas), & `acks=all`",
            "Partition Key Ordering Guarantee & Consumer Group Rebalancing",
            "Consumer Lag Monitoring & Retention vs Log Compaction",
        ],
        "lesson_md": """# Day 21 – Kafka & Redpanda Internals

- **Ordering Guarantee:** Ordering is guaranteed **only within a single Partition**, NOT across a whole topic! Use `key = customer_id` or `order_id` so all events for one entity land on the same partition in order.
- **Parallelism Limit:** Max active consumers in one Consumer Group = number of partitions.
- **Log Compaction:** Retains the latest value per key forever—ideal for CDC/lookup state topics.
""",
        "interview_questions": [
            {"question": "You have a Kafka topic with 4 partitions and deploy 8 consumers in the same consumer group. How many consumers process messages?", "answer": "Only 4 consumers receive partitions; the remaining 4 sit idle as hot standbys! To scale to 8 parallel consumers, increase topic partitions to at least 8.", "scenario": "Common misconception when scaling consumer pods during traffic spikes."},
        ],
    },
    {
        "day": 22,
        "phase": 4,
        "title": "Day 22 – RabbitMQ Messaging vs Kafka Event Streaming",
        "estimated_minutes": 75,
        "practice_type": "streaming",
        "practice_snippet": """# Check Streaming -> RabbitMQ tab in Unified Studio to inspect exchanges, queues, DLQs, and test message routing.""",
        "goals": [
            "Smart Broker / Dumb Consumer (RabbitMQ) vs Dumb Broker / Smart Consumer (Kafka/Redpanda)",
            "Exchanges (Direct, Topic, Fanout), Queues, Bindings, Ack/Nack",
            "Dead-Letter Exchanges (DLX) & Poison Pill Handling",
        ],
        "lesson_md": """# Day 22 – RabbitMQ vs Kafka/Redpanda

| Dimension | RabbitMQ (Service Bus) | Redpanda / Kafka (Event Hub) |
|---|---|---|
| Pattern | Task queues, complex routing, RPC | High-throughput event log, replayable streams |
| Message Lifecycle | Deleted after consumer `ACK` | Retained by time/size; replayable by offset |
| Routing | Rich Exchanges (Topic, Header, Direct) | Partition key hashing |
| Failure Isolation | Dead-Letter Queue (DLQ) per message | DLQ topic + offset skip/alert |
""",
        "interview_questions": [
            {"question": "When would you choose RabbitMQ over Kafka/Redpanda, and vice versa?", "answer": "Choose RabbitMQ for per-message routing, priority queues, request/reply task workers, and automatic deletion after ACK. Choose Kafka/Redpanda for high-throughput event streaming, multiple independent consumer groups, and time-travel offset replay.", "scenario": "Order checkout email tasks -> RabbitMQ; Clickstream + CDC lakehouse ingestion -> Redpanda/Kafka."},
        ],
    },
    {
        "day": 23,
        "phase": 4,
        "title": "Day 23 – End-to-End Streaming + CDC Lakehouse Pipeline",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """import json, pathlib
nb = json.loads(pathlib.Path('/home/iceberg/notebooks/notebooks/project4_cdc_pipeline.ipynb').read_text())
print('Project 4 CDC cells:', len(nb.get('cells', [])))""",
        "goals": [
            "Connecting Postgres WAL -> Redpanda -> Spark Structured Streaming -> Delta/Iceberg",
            "Handling Out-of-Order CDC Events (`MERGE` with sequence/LSN check)",
            "Compaction & Freshness SLAs on Streaming Tables",
        ],
        "lesson_md": """# Day 23 – End-to-End Streaming + CDC

Combine everything from Phase 2–4:
1. Capture CDC events in Redpanda (`project4_cdc_pipeline.ipynb`).
2. Read stream in PySpark using `foreachBatch`.
3. Inside `foreachBatch`, deduplicate by `(pk, lsn)` keeping latest event, and run Delta `MERGE INTO` handling `op = 'd'` (DELETE) and `op IN ('c','u')` (UPSERT).
""",
        "interview_questions": [
            {"question": "How do you prevent stale out-of-order updates in a CDC `MERGE`?", "answer": "Include a monotonic source sequence/LSN or `updated_at` timestamp guard inside the `WHEN MATCHED AND source.lsn > target.lsn THEN UPDATE` clause, and deduplicate within each micro-batch first.", "scenario": "Replay or network retry delivers an older UPDATE after a newer one."},
        ],
    },
]

