"""Phase 10: 6-Year Senior DE Azure Architecture & Interview Gauntlet (Days 57-60)."""

DAYS_57_TO_60 = [
    {
        "day": 57,
        "phase": 10,
        "title": "Day 57 – 6-Year Architecture 1: Hybrid On-Prem SQL + SAP/REST API -> ADLS -> Databricks -> Power BI",
        "estimated_minutes": 100,
        "practice_type": "pyspark",
        "practice_snippet": """# Practice Bronze -> Silver SCD2 deduplication + Gold Mart over shared TPC-H data
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
spark = SparkSession.builder.appName("Day57_ArchMedallion").getOrCreate()
orders = spark.table("demo.practice.orders")
w = Window.partitionBy("o_custkey").orderBy(F.desc("o_orderdate"), F.desc("o_orderkey"))
latest_customer_order = orders.withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn")
print("Unique active customers with latest order:", latest_customer_order.count())
latest_customer_order.show(10)
spark.stop()""",
        "goals": [
            "Draw end-to-end Azure Hybrid Architecture cleanly (SHIR vs CDC, Key Vault, Private Endpoints, Bronze/Silver/Gold)",
            "Justify component choices & costs (ADF for orchestration/copy + Databricks for PySpark/Delta + Databricks SQL / Fabric Direct Lake for BI)",
            "Bake in Data Quality SLAs, Freshness Observability, Backfill Idempotency & Purview/Unity Catalog PII Governance",
        ],
        "lesson_md": """# Day 57 – Enterprise Hybrid Lakehouse Blueprint (Azure)

```text
[On-Prem SQL Server / SAP / SaaS APIs]
       ↓  (ADF + 2-Node HA Self-Hosted IR / Managed VNet Private Endpoint + Key Vault MI)
[ADLS Gen2 Bronze Container (Raw Parquet / JSON, Lifecycle -> Cool @ 30d)]
       ↓  (Databricks Auto Loader cloudFiles + DABs Workflow Job Cluster)
[Unity Catalog Silver Tables (Deduplicated, Schema-Enforced, SCD Type 2, RLS/Column Masks)]
       ↓  (Photon + Liquid Clustering CLUSTER BY (region, order_date))
[Unity Catalog Gold Star Schema] ──> [Databricks SQL Serverless / Power BI DirectQuery/Direct Lake]
```

## Architecture Defense Points (6-Year Level)
- **Why ADF + Databricks (instead of ADF alone or Databricks alone)?** ADF excels at connecting 100+ SaaS/on-prem sources behind corporate firewalls via SHIR; Databricks excels at distributed PySpark/Delta transformations, testing, and Unity Catalog governance.
- **How do you backfill 3 years without blocking today's SLA?** Isolate historical backfill into a separate Job Cluster queue partitioned by `month`, using dynamic `REPLACE WHERE` in Delta Lake so concurrent daily appends never conflict!
""",
        "interview_questions": [
            {"question": "Why does `REPLACE WHERE` in Delta Lake enable safe parallel historical backfills alongside live daily pipelines?", "answer": "Using Delta `option('replaceWhere', \"order_date BETWEEN '2024-01-01' AND '2024-01-31'\")` with Spark guarantees optimistic concurrency control validates only partitions matching that predicate rather than overwriting unrelated partitions.", "scenario": "Backfilling Q1 restatements while today's live ingestion keeps flowing."},
        ],
    },
    {
        "day": 58,
        "phase": 10,
        "title": "Day 58 – 6-Year Architecture 2: Real-Time Event Hubs -> Spark Streaming -> Delta + Low-Latency Serving",
        "estimated_minutes": 95,
        "practice_type": "streaming",
        "practice_snippet": """# Streaming Architecture Blueprint Verified in Unified Studio:
# Producers -> Redpanda (Kafka / Azure Event Hubs) -> Spark Structured Streaming (withWatermark 2m + RocksDB State) -> Delta Gold + Alert DLQ (RabbitMQ)""",
        "goals": [
            "Design sub-5-second streaming analytics + operational alerting in Azure",
            "Split **Hot Serving Path** (Cosmos DB / Azure Redis / Postgres operational) from **Analytical Path** (Delta Lake Gold via Structured Streaming)",
            "Design Schema Evolution (Confluent/Azure Schema Registry Avro/Protobuf), Watermarks, Replayability & DLQ Reprocessing",
        ],
        "lesson_md": """# Day 58 – Real-Time Azure Streaming Architecture (Event Hubs + Spark)

```text
[IoT / Payment Microservices]
       ↓ (Avro + Azure Schema Registry)
[Azure Event Hubs Premium (Partitioned by account_id, Auto Capture -> ADLS Bronze backup)]
       ↓ (Spark Structured Streaming + RocksDB State Store + 5m Watermark)
       ├──> [Delta Lake Silver/Gold] (Forensics, ML features, Power BI SQL)
       ├──> [Azure Cosmos DB / PostgreSQL] (<10ms customer-facing app lookup)
       └──> [Event Hubs / Service Bus DLQ] (Poison pills -> Automated alert & replay pipeline)
```

## Key Senior Decisions
1. **Poison-Pill Resilience:** Wrap deserialization with `from_avro` / `from_json` `PERMISSIVE` mode so **1 bad schema message never crashes the 24/7 stream**—route invalid payloads to a Quarantine DLQ table with schema diff alerts!
2. **State & Latency:** Set RocksDB State Store (`spark.sql.streaming.stateStore.providerClass`) so millions of 15-minute fraud window keys don't OOM Executor JVM heap.
""",
        "interview_questions": [
            {"question": "How do you reprocess the last 48 hours of Event Hubs events after fixing a bug in your Gold streaming aggregation without duplicating rows?", "answer": "Spin up a versioned backfill/recovery checkpoint pointed at Event Hubs `startingOffsets` by exact UTC timestamp (`-48h`), run `.trigger(availableNow=True)` into a Delta staging table, and apply idempotent `MERGE INTO` against Gold (never reuse a corrupted active streaming checkpoint cleanly without isolating offsets).", "scenario": "Real-time fraud/revenue bug recovery during on-call rotation."},
        ],
    },
    {
        "day": 59,
        "phase": 10,
        "title": "Day 59 – 6-Year Senior Troubleshooting Drills: ADF SHIR, Synapse Skew, Databricks OOM & DR",
        "estimated_minutes": 95,
        "practice_type": "pyspark",
        "practice_snippet": """# Live Diagnostic Exercise: Inspect Spark partition skew on shared demo.practice.lineitem
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
spark = SparkSession.builder.appName("Day59_Troubleshooting").getOrCreate()
spark.table("demo.practice.lineitem").groupBy(F.spark_partition_id().alias("partition_id")).count().orderBy(F.desc("count")).show()
spark.stop()""",
        "goals": [
            "Solve Rapid-Fire 6-Year Scenario Prompts: SHIR CPU 100%, Spark Broadcast Timeout, Synapse `DMS` Spill, Unity Catalog 403, ADLS Throttling",
            "Architect Cross-Region Disaster Recovery (RPO / RTO using Delta `DEEP CLONE`, ADLS GRS/RA-GRS, Multi-Region ADF/DABs deploy)",
            "Differentiate symptom vs root cause under interview pressure",
        ],
        "lesson_md": """# Day 59 – 5 Rapid-Fire Senior Troubleshooting Scenarios

1. **ADF Self-Hosted IR stalls copying 40 tables nightly:**
   - Cause: High-concurrency Copy threads saturate single-node SHIR RAM/NIC (`ForEach batchCount=30`). Fix: Scale SHIR to 2–4 node HA pair, cap `batchCount=8`, move heavy transforms out of on-prem VM to Databricks.
2. **Databricks Photon job throws `BroadcastTimeoutException` after 300s:**
   - Cause: Broadcasted side grew past timeout or hit Driver GC pause while collecting. Fix: Increase `spark.sql.broadcastTimeout=600` ONLY if truly small, OR disable auto-broadcast (`-1` or project/filter first) and let AQE SortMergeJoin handle it!
3. **ADLS Gen2 returns `429 ServerBusy` during Spark write:**
   - Cause: Writing thousands of concurrent tiny files/partitions saturates account egress/IOPS limit (20 Gbps / 20k req/s). Fix: Coalesce/repartition cleanly + Azure Storage Queue File Notification instead of directory polling.
4. **Cross-Region Disaster Recovery (`RPO < 1 hr`, `RTO < 30 min`):**
   - Infra deployed via **Terraform + Databricks Asset Bundles** in paired secondary region + incremental **Delta `DEEP CLONE`** scheduled to secondary region RA-GRS/ZRS storage + DNS/Traffic Manager switchover.
""",
        "interview_questions": [
            {"question": "Why is Delta `SHALLOW CLONE` dangerous for Disaster Recovery, whereas `DEEP CLONE` is DR-safe?", "answer": "`SHALLOW CLONE` creates new metadata pointing at the **primary region's physical Parquet files**—if the primary region/storage account goes down, the clone breaks! `DEEP CLONE` copies both metadata and underlying Parquet data incrementally into the independent DR storage account.", "scenario": "Principal/Staff DE Disaster Recovery architecture sign-off."},
        ],
    },
    {
        "day": 60,
        "phase": 10,
        "title": "Day 60 – Final 6-Year Senior DE Mock Interview (Live Coding, Azure Design & Leadership STAR)",
        "estimated_minutes": 110,
        "practice_type": "pyspark",
        "practice_snippet": """# Final 6-Year Live Coding Challenge: Compute Top-2 Revenue Customers per Nation & Month-over-Month Growth on shared Iceberg data!
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
spark = SparkSession.builder.appName("Day60_MockChallenge").getOrCreate()
cust = spark.table("demo.practice.customer")
orders = spark.table("demo.practice.orders")
nation = spark.table("demo.practice.nation")

spend = (
    orders.join(cust, orders.o_custkey == cust.c_custkey)
    .join(F.broadcast(nation), cust.c_nationkey == nation.n_nationkey)
    .groupBy(nation.n_name.alias("nation"), cust.c_custkey, cust.c_name)
    .agg(F.round(F.sum("o_totalprice"), 2).alias("total_spend"))
)
top2 = spend.withColumn("rnk", F.dense_rank().over(Window.partitionBy("nation").orderBy(F.desc("total_spend")))).filter("rnk <= 2")
top2.orderBy("nation", "rnk").show(20, truncate=False)
spark.stop()""",
        "goals": [
            "Solve Top-N-Per-Group + Cohort/Sessionization live in BOTH PySpark & SQL cleanly under 15 minutes",
            "Defend End-to-End Azure Security, Cost (DBU + ADLS + Synapse), Data Quality & Migration decisions",
            "Deliver crisp 6-Year Senior Leadership STAR stories (mentoring, cross-team SLA contracts, multi-TB migrations, FinOps impact)",
        ],
        "lesson_md": """# Day 60 – 6-Year Senior Data Engineer Final Mock Gauntlet

## What Differentiates a 6-Year Senior DE from a 2-Year Mid DE
| Topic | 2-Year Answer | 6-Year Senior Answer |
|---|---|---|
| **PySpark Skew** | "I use `repartition(200)`" | Explains Stage UI stragglers, AQE skew split threshold, NULL filtering, 2-stage random salt, & `maxRecordsPerFile` |
| **Azure Auth** | "Use SAS token or storage key" | Zero-secret **Managed Identities**, Unity Catalog Access Connector, Key Vault RBAC, Private Link, HNS POSIX ACL traversal (`--x`) |
| **Ingestion** | "Scheduled ADF Copy" | Metadata-driven `control.config` table, HA SHIR concurrency limits, Tumbling Window vs Auto Loader File Notification (`O(1)`) |
| **FinOps** | "Make cluster bigger" | Job Compute vs All-Purpose 3x premium, Photon only when not UDF-bound, `availableNow=True`, ADLS Cool/Archive tiering, `system.billing.usage` |
| **Reliability** | "Re-run failed job" | Idempotent `MERGE INTO` / `replaceWhere`, Quarantine DLQ, Data Contracts & Observability SLOs (freshness + error budgets) |

## Final Practical Challenge
Run the Day 60 snippet in **PySpark Studio** AND translate the exact same query into **SQL Studio** (`synapse_dw.customer`, `orders`, `nation`) to confirm matching results!
""",
        "interview_questions": [
            {"question": "Tell me about a time you pushed back on a technical decision or led a platform-wide reliability/cost improvement across teams.", "answer": "Use crisp STAR structure backed by metrics: e.g., audited teams scheduling 24/7 All-Purpose Databricks clusters & raw JSON directory polling, introduced DABs CI/CD templates + Job Compute policies + Auto Loader Event Grid notifications + DQ quarantine SLAs—cutting monthly Azure spend by 55% ($32k/mo saved) while improving 7 AM BI SLA reliability from 89% to 99.8%.", "scenario": "Staff/Senior Lead Behavioral Interview Round."},
            {"question": "Given 500 GB/day arriving in ADLS Gen2 with 10% late updates up to 7 days old and sub-10-second Power BI dashboards needed, sketch the stack and justify tradeoffs.", "answer": "Ingest via ADF/Event Hubs into ADLS Bronze -> Databricks Auto Loader (`trigger(availableNow=True)` every 5 mins or streaming depending on freshness budget) -> Silver Delta `MERGE` partitioned/clustered cleanly (`Liquid Clustering CLUSTER BY`) -> Gold Star Schema served via Databricks SQL Serverless (auto-scaling Photon) or Fabric Direct Lake Shortcuts; enforce unit tests via DABs + Log Analytics SLA alerts.", "scenario": "Final System Design Panel."},
        ],
    },
]

