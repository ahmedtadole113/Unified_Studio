"""Phase 2: Python, PySpark 4.2 & Distributed Computing (Days 7-13)."""

DAYS_7_TO_13 = [
    {
        "day": 7,
        "phase": 2,
        "title": "Day 7 – Python for Data Engineering (Generators, APIs & S3/Postgres)",
        "estimated_minutes": 75,
        "practice_type": "pyspark",
        "practice_snippet": """import os, boto3
s3 = boto3.client('s3', endpoint_url='http://minio:9000', aws_access_key_id='admin', aws_secret_access_key='password')
buckets = [b['Name'] for b in s3.list_buckets().get('Buckets', [])]
print('Connected MinIO buckets:', buckets)""",
        "goals": [
            "Memory-efficient streaming with Python generators (`yield`)",
            "Resilient REST API ingestion (pagination, retries, exponential backoff, rate limits)",
            "Batch loading into PostgreSQL (`execute_values` vs row-by-row `INSERT`)",
            "S3 / MinIO object upload & multipart streaming with `boto3`",
        ],
        "lesson_md": """# Day 7 – Python for Data Engineering

## 1. Generators & Constant-Memory Processing
Never load a 4 GB CSV/JSONL into a Python `list` (`O(N)` RAM—will OOM an 8 GB container!). Use generators (`yield`) to stream chunk-by-chunk in `O(1)` memory.

## 2. Resilient API Ingestion
Look at `airflow/dags/project3_incremental_load.py` in this repo:
- Fetch watermark (`MAX(transaction_id)`) from target DW.
- Poll REST endpoint with `timeout=10`, retries with exponential backoff (`2^attempt`), and `raise_for_status()`.
- Stage raw JSON in MinIO (`silver/`) before upserting into PostgreSQL using `psycopg2.extras.execute_values` (100x faster than looping `cursor.execute`).

## Homework
Review `airflow/dags/project1_adf_pipeline.py` and trace how `boto3` and `execute_values` achieve idempotent upserts.
""",
        "interview_questions": [
            {"question": "Why is `psycopg2.extras.execute_values` vastly faster than calling `cursor.execute()` in a loop?", "answer": "Looping sends N network round-trips and N transaction/parse cycles; `execute_values` batches hundreds/thousands of rows into a single multi-row `INSERT ... VALUES (...), (...) ON CONFLICT DO UPDATE` statement.", "scenario": "Loading 50,000 incremental transactions dropped from 42 seconds to 0.4 seconds."},
        ],
    },
    {
        "day": 8,
        "phase": 2,
        "title": "Day 8 – Apache Spark Architecture Deep Dive",
        "estimated_minutes": 90,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day8_Architecture").getOrCreate()
df = spark.range(0, 100000).repartition(4)
agg = df.selectExpr("id % 10 as grp", "id").groupBy("grp").count()
agg.explain(True)
agg.show()
spark.stop()""",
        "goals": [
            "Driver vs Executors vs Cluster Manager",
            "Jobs, Stages, Shuffle Boundaries & Tasks",
            "Narrow (`map`, `filter`, `select`) vs Wide (`groupBy`, `join`, `repartition`) Transformations",
            "Lazy Evaluation & the DAG Scheduler",
        ],
        "lesson_md": """# Day 8 – Apache Spark Architecture Deep Dive

## 1. Execution Hierarchy
```text
Driver (SparkContext + Catalyst + DAGScheduler)
  └── Action (e.g. .count(), .write()) -> triggers Job
        └── Wide transformation boundary (Shuffle) -> splits Job into Stages
              └── 1 Partition per Task -> executed in parallel on Executor slots
```
- **Narrow Transformation (`filter`, `withColumn`):** Each output partition depends on only ONE input partition → pipelined in memory inside a single Stage.
- **Wide Transformation (`groupBy`, `join`, `distinct`):** Requires shuffling data across network/disk between executors → creates a Stage boundary!

## 2. Catalyst Optimizer & Tungsten
Spark builds an Unresolved Logical Plan → Resolved Logical Plan (Catalog) → Optimized Logical Plan (Predicate Pushdown, Constant Folding) → Physical Plan (Cost-Based + AQE) → Whole-Stage Codegen (Java bytecode).

## Homework
Run the Day 8 snippet in PySpark Studio and identify `Exchange hashpartitioning` in the physical plan—that is your shuffle boundary!
""",
        "interview_questions": [
            {"question": "What is the difference between a Job, a Stage, and a Task in Spark?", "answer": "One Action (like `.write()` or `.count()`) creates a Job. Every shuffle boundary splits a Job into Stages. Each Stage executes one Task per data partition.", "scenario": "A job with 200 shuffle partitions and 2 wide transformations creates 3 stages and up to 600 tasks."},
            {"question": "Why does Spark use Lazy Evaluation?", "answer": "Deferring execution until an Action lets Catalyst combine filters, push predicates into Parquet/Delta, prune unused columns, and avoid materializing intermediate results.", "scenario": "Filter applied after reading 50 columns pushes down to read only 2 columns and skip 80% of Parquet row groups."},
        ],
    },
    {
        "day": 9,
        "phase": 2,
        "title": "Day 9 – PySpark 4.2 DataFrames, ANSI SQL & VARIANT Type",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql.functions import col, parse_json
spark = SparkSession.builder.appName("Day9_Spark42").config("spark.sql.ansi.enabled", "true").getOrCreate()
df = spark.createDataFrame([('{"event":"order","amount":125.5}',)], ["raw_json"])
df.select(parse_json(col("raw_json")).alias("v")).selectExpr("v:event::string as event", "v:amount::double as amount").show()
spark.stop()""",
        "goals": [
            "Spark 4.2 ANSI SQL mode (strict overflow & divide-by-zero safety)",
            "Spark 4.2 native `VARIANT` type for semi-structured JSON",
            "Built-in Spark functions vs Python UDFs vs Pandas Arrow UDFs",
        ],
        "lesson_md": """# Day 9 – PySpark 4.2, ANSI Mode & VARIANT

## 1. Why Built-In Functions Beat Python UDFs
Python UDFs force JVM → Python pickle/IPC serialization for every row and defeat Catalyst optimization. Always prefer `pyspark.sql.functions` (`F.when`, `F.expr`, `F.regexp_extract`) or vectorized Arrow Pandas UDFs.

## 2. Spark 4.2 Highlights Enabled in This Studio (`spark-defaults.conf`)
- `spark.sql.ansi.enabled=true`: Catches silent data corruption (overflows, invalid casts) early instead of silently returning NULL.
- Native `VARIANT` type: Query evolving JSON payloads (`v:customer.city::string`) without brittle upfront schema definitions.

## Homework
Run the `VARIANT` snippet in PySpark Studio and test casting an invalid string `'abc'` to `INT` under ANSI mode vs `TRY_CAST`.
""",
        "interview_questions": [
            {"question": "Why should you avoid Python UDFs in PySpark whenever possible?", "answer": "Python UDFs serialize rows out of the JVM Executor into a Python worker process, disabling Catalyst Whole-Stage Codegen and adding massive serialization CPU overhead. Use native Spark SQL functions or Arrow-backed Pandas UDFs instead.", "scenario": "Replacing a 5-line Python UDF with `F.when/F.regexp_replace` sped up a 100M-row Silver job from 18 minutes to 55 seconds."},
        ],
    },
    {
        "day": 10,
        "phase": 2,
        "title": "Day 10 – Spark Joins, Skew Handling & Shuffle Tuning",
        "estimated_minutes": 95,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql.functions import broadcast
spark = SparkSession.builder.appName("Day10_Joins").config("spark.sql.adaptive.enabled", "true").getOrCreate()
orders = spark.range(0, 50000).selectExpr("id as order_id", "id % 5 as region_id", "id * 1.5 as amount")
regions = spark.createDataFrame([(0,"NA"),(1,"EU"),(2,"APAC"),(3,"LATAM"),(4,"MEA")], ["region_id","region_name"])
joined = orders.join(broadcast(regions), "region_id")
joined.explain()
print("Joined count:", joined.count())
spark.stop()""",
        "goals": [
            "Broadcast Hash Join vs Shuffle Hash Join vs Sort Merge Join",
            "Adaptive Query Execution (AQE): dynamic coalescing & skew join splitting",
            "Fixing Data Skew manually with Key Salting",
            "`repartition(N)` vs `coalesce(N)`",
        ],
        "lesson_md": """# Day 10 – Spark Joins, Skew & Shuffle Tuning

## 1. Join Strategies
- **Broadcast Hash Join (BHJ):** Copies small table (<10MB default, `autoBroadcastJoinThreshold`) to every executor—**zero shuffle** on the large table!
- **Sort Merge Join (SMJ):** Default for two large tables; shuffles & sorts both sides by join key.

## 2. Detecting & Fixing Data Skew
Symptom: 199/200 tasks finish in 5 seconds, 1 task runs for 40 minutes or hits Executor OOM (`NULL` or `'guest'` key holds 80% of rows!).
Fixes:
1. Enable **AQE Skew Join** (`spark.sql.adaptive.skewJoin.enabled=true`).
2. Filter/handle `NULL` keys before joining.
3. **Key Salting:** Append `salt = rand() % 10` to the skewed large table key and explode `0..9` on the small table so the hot key spreads across 10 tasks!

## 3. `repartition` vs `coalesce`
- `repartition(N)`: Full shuffle; can increase or decrease partitions evenly.
- `coalesce(N)`: Reduces partitions **without full shuffle** by merging adjacent partitions (great before writing final files).
""",
        "interview_questions": [
            {"question": "99% of Spark tasks finish in 10 seconds, and 1 task hangs for 30 minutes and fails with OOM. What happened and how do you fix it?", "answer": "Classic Data Skew—one partition key (often NULL, -1, or a mega-merchant) receives disproportionate data. Fix by filtering NULLs before join, enabling AQE skew join optimization, broadcasting the small table, or salting the join key.", "scenario": "Real-world #1 Spark interview question."},
            {"question": "Why is `coalesce(1)` dangerous on a huge DataFrame before `.write()`?", "answer": "`coalesce` pushes upstream stages to execute on 1 partition/core, eliminating parallelism and risking OOM. Use `repartition(N)` or AQE maxRecordsPerFile instead.", "scenario": "Downstream task runs 1 core instead of 32 cores."},
        ],
    },
    {
        "day": 11,
        "phase": 2,
        "title": "Day 11 – Spark Memory Management & OOM Troubleshooting",
        "estimated_minutes": 80,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day11_Memory").getOrCreate()
for k, v in sorted(spark.sparkContext.getConf().getAll()):
    if any(x in k for x in ("memory", "shuffle", "adaptive", "ansi")):
        print(f"{k} = {v}")
spark.stop()""",
        "goals": [
            "Driver OOM vs Executor OOM vs Container OOMKilled (Exit Code 137)",
            "Unified Memory Manager (Execution vs Storage vs User/Reserved memory)",
            "JVM Overhead (`spark.executor.memoryOverhead`) & Spill to Disk",
            "Tuning Spark for 8 GB MacBook M4 (`spark.driver.memory=768m`, `shuffle.partitions=10`)",
        ],
        "lesson_md": """# Day 11 – Spark Memory Management & OOM Debugging

## 1. Driver OOM vs Executor OOM
- **Driver OOM:** Caused by `.collect()`, `.toPandas()`, or broadcasting a huge DataFrame (`spark.sql.autoBroadcastJoinThreshold` set too high).
- **Executor OOM / Container Exit 137 (OOMKilled):** Caused by data skew, huge `cache()` without `MEMORY_AND_DISK`, exploding `explode()` arrays, or Python UDF memory leaks outside JVM heap (`memoryOverhead`).

## 2. Unified Memory Model
Inside Executor Heap: `300MB Reserved` + `60% Spark Unified (Execution for shuffles/joins/sorts + Storage for cache)` + `40% User Memory`. Execution can borrow unused Storage memory and evict cached blocks if needed!

## Homework
Inspect `spark-defaults.conf` in this repository and explain why `spark.sql.shuffle.partitions=10` is critical on an 8 GB machine compared to Spark's default `200`.
""",
        "interview_questions": [
            {"question": "A Spark job fails with Kubernetes Exit Code 137 (`OOMKilled`) even though JVM heap didn't throw `OutOfMemoryError`. Why?", "answer": "The Linux cgroup killed the container because total process memory (JVM Heap + off-heap + Python worker + Netty buffers) exceeded the container/pod memory limit. Increase `spark.executor.memoryOverhead` or reduce partition size / Python UDF footprint.", "scenario": "Directly ties Data Engineering Spark jobs to SRE Kubernetes OOMKilled alerts!"},
        ],
    },
    {
        "day": 12,
        "phase": 2,
        "title": "Day 12 – PySpark Structured Streaming (Watermarks & Checkpoints)",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """# Inspect Project 2 Streaming Notebook structure
import json, pathlib
nb = json.loads(pathlib.Path('/home/iceberg/notebooks/notebooks/project2_eventhub_streaming.ipynb').read_text())
print('Project 2 cells:', len(nb.get('cells', [])))""",
        "goals": [
            "Unbounded Table abstraction & Micro-Batch vs Continuous Processing",
            "Event Time vs Processing Time & Late Data",
            "Watermarking (`withWatermark`) to bound state store memory",
            "Checkpointing & Idempotent Delta Sinks for Exactly-Once Processing",
        ],
        "lesson_md": """# Day 12 – PySpark Structured Streaming

## 1. Event Time vs Processing Time
An order placed at `10:00:00` (event time) arrives via mobile offline sync at `10:12:00` (processing time). Without **Watermarking**, Spark must keep all historical window state in executor RAM forever → eventual OOM!
```python
df.withWatermark("event_time", "10 minutes") \
  .groupBy(window("event_time", "5 minutes"), "merchant") \
  .sum("amount")
```
Spark tracks `max(event_time) - 10m` and safely drops older window state.

## 2. Exactly-Once End-to-End
1. Replayable source (Redpanda/Kafka offsets).
2. `checkpointLocation` in durable storage (saves Kafka offsets + state store snapshots).
3. Idempotent sink (Delta Lake transaction log commits batch IDs atomically).
""",
        "interview_questions": [
            {"question": "What happens if you run a streaming `groupBy(window(...))` without `withWatermark`?", "answer": "Spark maintains unbounded state in executor memory/RocksDB for every time window since start of stream, leading to steadily growing latency and eventual state store OOM.", "scenario": "Classic memory leak in streaming pipelines after 3-5 days uptime."},
        ],
    },
    {
        "day": 13,
        "phase": 2,
        "title": "Day 13 – Data Quality Engineering & Pipeline Contracts",
        "estimated_minutes": 75,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql.functions import col
spark = SparkSession.builder.appName("Day13_DQ").getOrCreate()
df = spark.createDataFrame([("u1","a@b.com",25),("u2",None,30),("u3","bad",-5)], ["user_id","email","age"])
valid = df.filter(col("email").isNotNull() & (col("age") > 0))
quarantine = df.subtract(valid)
print("Valid:", valid.count(), "Quarantined:", quarantine.count())
quarantine.show()
spark.stop()""",
        "goals": [
            "Completeness, Uniqueness, Validity, Timeliness, Consistency",
            "Fail-Fast vs Dead-Letter / Quarantine Table pattern",
            "Schema Enforcement & Schema Evolution",
        ],
        "lesson_md": """# Day 13 – Data Quality Engineering

Never silently load corrupt rows into Gold marts—and never break an entire 10M-row pipeline for 3 bad rows unless a critical contract is breached!
- **Tier 1 (Critical Contract Breach):** Primary key NULL, duplicate rate > 5%, source empty → **Fail task & page via Incident Engine**.
- **Tier 2 (Row-Level Quarantine):** Negative age or malformed email → Route bad records to `quarantine.bad_records` with `error_reason` + `batch_id`, and allow clean rows into Silver!

## Homework
Inspect `airflow/dags/spark_jobs/data_quality_check.py` in this repo and enhance it to separate valid vs quarantined rows.
""",
        "interview_questions": [
            {"question": "How do you handle bad records in a production pipeline without losing data or blocking SLA?", "answer": "Implement the Quarantine / Dead-Letter Table pattern: validate against schema and business rules, route invalid rows with failure metadata to a quarantine table for reprocessing, emit a DQ metric/alert, and promote valid rows only if error % is below threshold.", "scenario": "Upstream mobile app bug sends negative prices on 0.2% of events."},
        ],
    },
]

