"""Phase 7: PySpark Zero-to-Advance Mastery for 6-Year Senior Data Engineers (Days 31-42)."""

DAYS_31_TO_42 = [
    {
        "day": 31,
        "phase": 7,
        "title": "Day 31 – PySpark Zero to Core: SparkSession, Catalyst, Tungsten & DataFrames",
        "estimated_minutes": 90,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day31_SparkCore").getOrCreate()
df = spark.table("demo.practice.customer")
print("Partitions:", df.rdd.getNumPartitions(), "Count:", df.count())
df.select("c_custkey", "c_name", "c_mktsegment", "c_acctbal").filter("c_acctbal > 9000").explain(True)
spark.stop()""",
        "goals": [
            "Understand RDD vs DataFrame vs Dataset APIs and why DataFrames win (Catalyst + Tungsten)",
            "Trace the 4 Catalyst planning phases (Analysis, Logical Optimization, Physical Planning, Codegen)",
            "Inspect partition layout, Spark UI jobs/stages, and Driver vs Executor separation",
        ],
        "lesson_md": """# Day 31 – PySpark Zero to Core (6-Year Senior Depth)

## 1. Why DataFrames Beat Python/RDDs by 10x–100x
- **RDD API:** Opaque Python objects; Spark cannot inspect fields inside lambdas → zero predicate pushdown, high JVM↔Python serialization overhead, heavy GC.
- **DataFrame API:** Schema-aware tabular abstraction routed through **Catalyst Optimizer** + **Tungsten** off-heap binary memory encoding + **Whole-Stage Codegen** (compiled JVM bytecode, zero Python serialization for built-in expressions).

## 2. Catalyst 4-Stage Pipeline
```text
SQL / DataFrame API
   ↓ (Unresolved Logical Plan)
[1. Analysis] -> Catalog resolves table & column types
   ↓ (Logical Plan)
[2. Logical Optimization] -> Predicate Pushdown, Column Pruning, Constant Folding
   ↓ (Optimized Logical Plan)
[3. Physical Planning] -> Selects SortMergeJoin vs BroadcastHashJoin + Exchange
   ↓ (Cost Model / AQE)
[4. Code Generation] -> Tungsten off-heap UnsafeRow + JVM bytecode
```

## 3. Hands-On Practice
Run the snippet against our live Iceberg `demo.practice.customer` table and read the `PushedFilters` and `ReadSchema` lines in the Physical Plan!
""",
        "interview_questions": [
            {"question": "At a 6-year level, explain how Project Tungsten eliminates JVM Garbage Collection pauses in Spark.", "answer": "Tungsten stores rows in compact binary `UnsafeRow` format inside off-heap/managed memory (`sun.misc.Unsafe`) instead of heavy boxed Java/Python objects, uses cache-friendly pointer arrays for sorting without deserializing whole rows, and emits Whole-Stage Codegen bytecode.", "scenario": "Migrating legacy RDD `.map()` ETL to native DataFrame expressions eliminated 40-minute full-GC stalls and cut cluster cost by 65%."},
            {"question": "Why should `df.collect()` never be called on unbounded tables in production?", "answer": "`.collect()` pulls every partition across executors into the single Driver JVM heap, causing instant `OutOfMemoryError: Java heap space` on the Driver.", "scenario": "Candidate replacing `.collect()` with `.toLocalIterator()` or `.writeTo()` / `limit(N)`."},
        ],
    },
    {
        "day": 32,
        "phase": 7,
        "title": "Day 32 – PySpark Transformations, Column Expressions, Null Semantics & Sorting",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql import functions as F
spark = SparkSession.builder.appName("Day32_Expr").getOrCreate()
orders = spark.table("demo.practice.orders")
cleaned = (
    orders
    .withColumn("order_year", F.year("o_orderdate"))
    .withColumn("tier", F.when(F.col("o_totalprice") >= 250000, "VIP")
                         .when(F.col("o_totalprice") >= 100000, "HIGH")
                         .otherwise("STANDARD"))
)
cleaned.groupBy("order_year", "tier").agg(F.count("*").alias("cnt"), F.round(F.avg("o_totalprice"), 2).alias("avg_val")).orderBy("order_year", "tier").show(15)
spark.stop()""",
        "goals": [
            "Master `select`, `selectExpr`, `withColumn`, `withColumns` (single projection optimization!)",
            "Avoid repeated `withColumn()` in a loop (stack overflow in Catalyst Plan analyzer!)",
            "Handle `NULL`-safe equality (`eqNullSafe` / `<=>`), `coalesce`, and `sortWithinPartitions` vs `orderBy`",
        ],
        "lesson_md": """# Day 32 – Transformations, Expressions & Senior Pitfalls

## Critical 6-Year Pitfall: `.withColumn()` Inside a Python Loop
If you loop `for c in cols: df = df.withColumn(c, ...)` over 200+ columns, Catalyst builds a deeply nested `Project` tree causing exponential planning time or `StackOverflowError` on the Driver!
**Senior Fix:** Build all column expressions into one list and pass them in a **single** `.select(*exprs)` or `.withColumns(expr_map)` call.

## `orderBy()` vs `sortWithinPartitions()`
- `df.orderBy("col")` triggers a **global range-partitioned shuffle** across all executors (expensive Stage boundary!).
- `df.sortWithinPartitions("col")` sorts **inside each existing partition** with zero shuffle—ideal right before writing Parquet/Iceberg/Delta files to improve min/max stats pruning!
""",
        "interview_questions": [
            {"question": "Why does calling `.withColumn()` 300 times in a loop slow down or crash Spark before any task even starts?", "answer": "Each `.withColumn()` wraps the previous LogicalPlan in another `Project` node; Catalyst's rule optimizer traverses nested schemas recursively, causing quadratic/exponential planning overhead on the Driver. Passing all columns to a single `.select()` or `.withColumns()` produces one flat `Project`.", "scenario": "Renaming and trimming 400 raw CSV columns took 18 minutes in Catalyst planning until rewritten as a single `.select([F.trim(F.col(c)).alias(c) for c in df.columns])` (dropped to 0.2s)."},
        ],
    },
    {
        "day": 33,
        "phase": 7,
        "title": "Day 33 – PySpark Advanced Aggregations, Cube/Rollup & Window Analytics",
        "estimated_minutes": 95,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
spark = SparkSession.builder.appName("Day33_Windows").getOrCreate()
orders = spark.table("demo.practice.orders")
w = Window.partitionBy("o_custkey").orderBy(F.col("o_orderdate").asc(), F.col("o_orderkey").asc())
w_running = w.rowsBetween(Window.unboundedPreceding, Window.currentRow)
res = (
    orders
    .withColumn("prev_price", F.lag("o_totalprice").over(w))
    .withColumn("running_spend", F.round(F.sum("o_totalprice").over(w_running), 2))
    .withColumn("spend_rank", F.dense_rank().over(Window.partitionBy("o_custkey").orderBy(F.desc("o_totalprice"))))
)
res.select("o_custkey", "o_orderkey", "o_orderdate", "o_totalprice", "prev_price", "running_spend", "spend_rank").show(15)
spark.stop()""",
        "goals": [
            "Compute `GROUP BY`, `ROLLUP`, `CUBE`, and `GROUPING SETS` for BI summary cubes",
            "Write complex `Window` specifications (`ROWS BETWEEN` vs `RANGE BETWEEN`)",
            "Avoid OOM caused by Window without `PARTITION BY` (forces ALL data into 1 partition!)",
        ],
        "lesson_md": """# Day 33 – Advanced Aggregations & Window Functions

## 1. Dangerous Production Trap: Unpartitioned Windows
`Window.orderBy("ts")` (with **no `.partitionBy()`**) forces Spark to collapse **every row in the entire table onto a single partition on one executor**!
- Always partition by an entity key when possible, OR stage in pre-aggregated buckets.

## 2. `ROWS BETWEEN` vs `RANGE BETWEEN`
- `ROWS BETWEEN`: physical row offsets (e.g., `rowsBetween(-6, 0)` = last 7 rows).
- `RANGE BETWEEN`: logical value offsets on the `ORDER BY` column (e.g., `rangeBetween(-86400, 0)` on Unix epoch seconds = true 24-hour rolling window even with sparse events).
""",
        "interview_questions": [
            {"question": "What happens physically in Spark if you run `row_number().over(Window.orderBy('created_at'))` on a 1 TB table?", "answer": "Because there is no `.partitionBy()`, Spark inserts an `Exchange SinglePartition`, sending the entire 1 TB dataset to a single executor task, triggering massive disk spill or OOM. Fix with two-stage local partitioning (`spark_partition_id()` counts + prefix offsets) or `zipWithIndex` where order isn't global.", "scenario": "Surrogate key generation (`monotonically_increasing_id` vs `row_number()`) at petabyte scale."},
        ],
    },
    {
        "day": 34,
        "phase": 7,
        "title": "Day 34 – Semi-Structured Data: Nested JSON, Arrays, Explode & Schema Evolution",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, DoubleType
spark = SparkSession.builder.appName("Day34_NestedJSON").getOrCreate()
schema = StructType([
    StructField("order_id", StringType()),
    StructField("items", ArrayType(StructType([StructField("sku", StringType()), StructField("price", DoubleType())])))
])
raw = spark.createDataFrame([('{"order_id":"ORD-1","items":[{"sku":"A1","price":49.5},{"sku":"B2","price":19.0}]}',)], ["payload"])
parsed = raw.select(F.from_json("payload", schema).alias("j")).select("j.order_id", F.explode_outer("j.items").alias("item")).select("order_id", "item.sku", "item.price")
parsed.show()
spark.stop()""",
        "goals": [
            "Flatten nested `StructType` and `ArrayType` with `explode` vs `explode_outer` (preserving NULL/empty arrays!)",
            "Parse streaming/Kafka JSON strings safely with `from_json`, `schema_of_json`, and `_corrupt_record` quarantine",
            "Use higher-order array SQL functions (`transform`, `filter`, `aggregate`) without exploding!",
        ],
        "lesson_md": """# Day 34 – Complex Types, Explode Pitfalls & Higher-Order Functions

## 1. `explode()` Silently Drops NULLs & Empty Arrays!
- `F.explode(arr)` **filters out** any parent row whose array is `NULL` or `[]`!
- Use **`F.explode_outer(arr)`** whenever parent records must be preserved (like orders with 0 line items).

## 2. Avoid Explosion Blowup With Higher-Order Functions
If you only need to filter/sum an array field per row, **don't** `explode()` and `groupBy()` back (expensive shuffle!). Use higher-order functions **inside the same partition**:
```python
F.expr("aggregate(filter(items, x -> x.price > 10), 0D, (acc, x) -> acc + x.price)")
```
""",
        "interview_questions": [
            {"question": "How do you prevent corrupt JSON payloads from crashing an enterprise ingestion job?", "answer": "Read with an explicit `StructType` + `mode='PERMISSIVE'` and `columnNameOfCorruptRecord='_corrupt_record'` (or `from_json` returning NULL on mismatch), split clean rows to Silver and quarantine corrupt payloads to a Dead-Letter table for replay.", "scenario": "Upstream mobile SDK released a broken nested schema overnight; quarantine saved the 6 AM SLA."},
        ],
    },
    {
        "day": 35,
        "phase": 7,
        "title": "Day 35 – Spark Join Strategies Deep Dive (Broadcast, Sort-Merge, Shuffle Hash)",
        "estimated_minutes": 95,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql import functions as F
spark = SparkSession.builder.appName("Day35_Joins").getOrCreate()
orders = spark.table("demo.practice.orders")
nation = spark.table("demo.practice.nation")
cust = spark.table("demo.practice.customer")
joined = orders.join(cust, orders.o_custkey == cust.c_custkey).join(F.broadcast(nation), cust.c_nationkey == nation.n_nationkey)
joined.explain()
print("Joined count:", joined.count())
spark.stop()""",
        "goals": [
            "Compare Broadcast Hash Join (BHJ), Shuffle Hash Join (SHJ), Sort-Merge Join (SMJ), and Broadcast Nested Loop",
            "Know exact thresholds (`spark.sql.autoBroadcastJoinThreshold`, default 10MB; AQE dynamic broadcast)",
            "Avoid Driver OOM from over-broadcasting a bloated dimension table",
        ],
        "lesson_md": """# Day 35 – Spark Join Mechanics & Strategy Selection

| Join Strategy | When Selected | Shuffle Fact? | Driver Impact |
|---|---|---|---|
| **BroadcastHashJoin** | One side ≤ threshold (default 10 MB) or `F.broadcast(df)` | **Zero fact shuffle** | Collects small table to Driver first! |
| **SortMergeJoin** | Both sides large, equi-join | Shuffles + sorts BOTH sides | Minimal |
| **ShuffleHashJoin** | One side 3x smaller + `preferSortMergeJoin=false` | Shuffles both, builds hash table | None |
| **BroadcastNestedLoop** | Non-equi / cross join (`a.x < b.y`) | Slowest (`O(N*M)`) | High risk |

## Senior Trap: Driver & Executor Memory With Broadcast
Remember: Spark **collects** the broadcasted table to the Driver first (`Serialized + Deserialized`), then ships it to every Executor. Never blindly force `F.broadcast()` on a 2 GB table with 2 GB Driver memory!
""",
        "interview_questions": [
            {"question": "Why does `F.broadcast(dim)` sometimes work for 50 MB Parquet on disk yet OOM the Driver/Executor in memory?", "answer": "Parquet is heavily compressed and columnar (~5–10x smaller on disk than deserialized Java/Python hash maps in JVM RAM). A 50 MB Parquet dimension can expand to 500 MB–1 GB as an in-memory `HashedRelation` broadcast object!", "scenario": "Broadasting a string-heavy dimension failed `Could not execute broadcast in 300 secs` until projected down to only needed columns before `broadcast()`."},
        ],
    },
    {
        "day": 36,
        "phase": 7,
        "title": "Day 36 – Taming Data Skew, AQE, Key Salting & Small Files Problem",
        "estimated_minutes": 95,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql import functions as F
spark = SparkSession.builder.appName("Day36_SkewAQE").config("spark.sql.adaptive.enabled", "true").config("spark.sql.adaptive.skewJoin.enabled", "true").getOrCreate()
li = spark.table("demo.practice.lineitem")
print("Current partitions:", li.rdd.getNumPartitions())
# Inspect partition balance quickly
li.groupBy("l_shipmode").count().orderBy(F.desc("count")).show()
spark.stop()""",
        "goals": [
            "Spot skew: 199/200 tasks finish in 3 seconds while 1 straggler runs 90 minutes",
            "Apply Adaptive Query Execution (AQE: `coalescePartitions`, `skewJoin`, dynamic BHJ switching)",
            "Implement deterministic Key Salting (both `groupBy` 2-stage salt and join `explode` salt) when AQE isn't enough",
            "Eliminate the Small Files Problem (`repartition` before write, `maxRecordsPerFile`, Iceberg/Delta `OPTIMIZE`)",
        ],
        "lesson_md": """# Day 36 – Skew Handling, Salting, AQE & Small Files

## 1. Two-Stage Salting for Skewed Joins & Aggregations
When 80% of rows share one hot key (e.g., `customer_id = NULL` or `'UNKNOWN'` or default guest account):
1. **Filter & isolate NULLs** first if they don't need joining!
2. **2-Stage GroupBy Salt:** Add `salt = floor(rand() * 16)`, `groupBy(key, salt)` → partial agg → `groupBy(key)` final agg.
3. **Join Salt:** Add random `0..N-1` on the **large skewed table**, and **`explode(array(0..N-1))`** on the **dimension table**, then join on `(key, salt)`.

## 2. `repartition()` vs `coalesce()`
- `repartition(N)` / `repartition("date")`: full shuffle, balances partitions evenly, increases OR decreases count.
- `coalesce(N)`: **no shuffle**, merges partitions within nodes—can cause **severe skew** if upstream data is skewed AND breaks parallelism of earlier stages in the same Stage!
""",
        "interview_questions": [
            {"question": "Why does adding `.coalesce(4)` right after reading 500 partitions actually slow down the upstream transformation?", "answer": "Because `.coalesce()` avoids a shuffle, Spark merges it into the same Stage, reducing upstream map/filter parallelism down to just 4 tasks! Either enable AQE `coalescePartitions` after shuffles or call `.coalesce()` carefully after a narrow boundary.", "scenario": "Classic Spark performance tuning trap in 6-year interviews."},
        ],
    },
    {
        "day": 37,
        "phase": 7,
        "title": "Day 37 – Spark Memory Internals & OOM Troubleshooting (Driver & Executor)",
        "estimated_minutes": 90,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day37_Memory").getOrCreate()
for k in sorted(spark.sparkContext.getConf().getAll()):
    if "memory" in k[0] or "adaptive" in k[0] or "shuffle" in k[0]:
        print(f"{k[0]} = {k[1]}")
spark.stop()""",
        "goals": [
            "Break down container RAM: Reserved (300 MB) + User Memory + Unified Execution/Storage (`spark.memory.fraction=0.6`) + Off-Heap `memoryOverhead` (max(384MB, 10%))",
            "Diagnose Exit Code 137 (`OOMKilled` by YARN/Kubernetes cgroup) vs Java `GC overhead limit exceeded`",
            "Calculate Executor Cores vs Memory ratio (4–5 cores per executor sweet spot for HDFS/S3 I/O + GC)",
        ],
        "lesson_md": """# Day 37 – Memory Layout & OOM Root-Cause Framework

```text
Container Limit (e.g. Kubernetes Pod / YARN Container = 8 GB)
 ├── spark.executor.memoryOverhead (~10% or higher for PySpark/Arrow/Netty/Direct buffers)
 └── JVM Heap (spark.executor.memory, e.g. 6.5 GB)
       ├── Reserved Memory (300 MB)
       ├── User Memory ((1 - spark.memory.fraction) = 40% -> UDF objects, metadata)
       └── Unified Memory Pool (spark.memory.fraction = 60%)
             ├── Execution Memory (shuffles, joins, sorts, aggs — can evict Storage!)
             └── Storage Memory (cached/persisted partitions via .cache())
```

## 6-Year Rule for Container `OOMKilled` (Exit 137)
Java doesn't print a Java heap OOM when Kubernetes kills the container! Common causes:
1. PySpark Python worker subprocesses (`spark.executor.pyspark.memory`) + Arrow buffers live **outside JVM heap inside `memoryOverhead`**.
2. Too many cores per executor (`>6`) multiplying concurrent task buffers inside one container.
3. Caching unserialized huge tables (`MEMORY_ONLY` vs `MEMORY_AND_DISK_SER` or not `.unpersist()`ing).
""",
        "interview_questions": [
            {"question": "Why does a Kubernetes Spark executor get `OOMKilled (Exit 137)` even when `-Xmx` JVM heap isn't full?", "answer": "Because off-heap memory (Netty shuffle buffers, `memoryOverhead`, PySpark Python worker processes, Pandas/Arrow native C++ buffers) counts toward the container cgroup limit outside `-Xmx`. Fix by sizing `spark.executor.memoryOverhead` higher, lowering executor cores per pod, or switching Pandas/PySpark workers to native Spark SQL.", "scenario": "Production K8s Spark migration issue very common for senior DEs."},
        ],
    },
    {
        "day": 38,
        "phase": 7,
        "title": "Day 38 – Built-In SQL Functions vs Python UDFs vs Pandas (Arrow) Vectorized UDFs",
        "estimated_minutes": 80,
        "practice_type": "pyspark",
        "practice_snippet": """import time
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
spark = SparkSession.builder.appName("Day38_UDFs").getOrCreate()
df = spark.range(0, 200000)
t0 = time.time()
native = df.select(F.when(F.col("id") % 2 == 0, F.col("id") * 2).otherwise(F.col("id") + 1).alias("v")).agg(F.sum("v")).collect()
print("Native Catalyst SQL:", native[0][0], "elapsed:", round(time.time()-t0, 3), "s")
spark.stop()""",
        "goals": [
            "Understand row-by-row pickle serialization penalty of standard Python `@udf`",
            "Accelerate custom ML/Python logic 10x–50x using Apache Arrow `@pandas_udf` vectorized batches",
            "Prefer built-in Spark SQL functions + Higher-Order Functions (`transform`/`filter`) 99% of the time",
        ],
        "lesson_md": """# Day 38 – Why Python UDFs Destroy Throughput (& How Pandas UDFs Fix It)

## Standard `@udf` Bottleneck
```text
Executor JVM Row -> Pickle serialize -> Pipe to Python Worker Process -> Run fn(row) -> Pickle back -> Deserialize in JVM
```
Repeats **per single row** AND disables Catalyst predicate pushdown / Whole-Stage Codegen!

## Priority Order for Transformation Logic
1. **Native Spark SQL expressions** (`F.*`, regex, higher-order array functions) — fastest, runs in JVM off-heap Tungsten.
2. **Scala UDF registered in Spark** — avoids Python worker fork if pure JVM needed.
3. **Vectorized `@pandas_udf` (Apache Arrow)** — transfers columnar zero-copy Arrow batches directly between JVM and NumPy/Pandas (10x–50x faster than `@udf` for unavoidable ML/SciPy inference!).
""",
        "interview_questions": [
            {"question": "When IS a `@pandas_udf` justified over native Spark SQL?", "answer": "When executing specialized Python libraries unavailable natively in Spark SQL—such as scikit-learn model scoring, custom cryptographic/geospatial/NLP tokenization—where Apache Arrow zeroes out per-row pickle overhead by sending vectorized Pandas Series chunks.", "scenario": "Batch fraud scoring 50M transactions dropped from 4 hours (Python UDF) to 11 minutes (`pandas_udf`)."},
        ],
    },
    {
        "day": 39,
        "phase": 7,
        "title": "Day 39 – Spark Structured Streaming: Watermarks, Triggers, State & Exactly-Once",
        "estimated_minutes": 95,
        "practice_type": "pyspark",
        "practice_snippet": """import time
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day39_StreamingIntro").getOrCreate()
rate_df = spark.readStream.format("rate").option("rowsPerSecond", 20).load()
print("Is streaming:", rate_df.isStreaming)
q = rate_df.writeStream.format("memory").queryName("rate_check").trigger(processingTime="1 second").start()
time.sleep(3)
q.stop()
spark.sql("SELECT COUNT(*) AS ingested_rows FROM rate_check").show()
spark.stop()""",
        "goals": [
            "Micro-batch vs Continuous Processing vs `trigger(availableNow=True)` cost-saving batch-streaming",
            "Event Time (`withWatermark`) vs Processing Time & State Store cleanup (RocksDB vs HDFS-backed)",
            "End-to-End Exactly-Once Semantics (Replayable Source + Idempotent Sink + Write-Ahead Checkpoint)",
        ],
        "lesson_md": """# Day 39 – Production Spark Structured Streaming

## 1. Cost-Effective Incremental Batch: `trigger(availableNow=True)`
- Runs Structured Streaming incremental offset tracking + checkpointing, consumes **all** available Kafka/ADLS files in scaled batches, then **shuts down compute cleanly**! Saves 70%–90% over a 24/7 idle streaming cluster when minute-level latency suffices.

## 2. Watermarks & State Store OOM Prevention
Stateful aggregations (`groupBy(window(event_ts, "5 minutes"))`, stream-stream joins, `dropDuplicatesWithinWatermark`) keep state in memory. Without `.withWatermark("event_ts", "10 minutes")`, Spark state grows forever until Executors OOM! Enable **RocksDBStateStoreProvider** in production for millions of active keys.
""",
        "interview_questions": [
            {"question": "How do you achieve end-to-end Exactly-Once delivery in Spark Structured Streaming?", "answer": "Three requirements: (1) Replayable offset-addressable source (Kafka / ADLS Auto Loader), (2) Durable checkpoint location saving read offsets & state (`checkpointLocation`), and (3) Transactional/Idempotent sink (Delta/Iceberg ACID commit log or `foreachBatch` deterministic MERGE/upsert keyed on micro-batch ID + primary key).", "scenario": "Handling executor retry during micro-batch #412 without duplicating payments in Gold."},
        ],
    },
    {
        "day": 40,
        "phase": 7,
        "title": "Day 40 – Lakehouse Storage Tuning in PySpark (Delta/Iceberg MERGE, Z-Order, CDF & Vacuum)",
        "estimated_minutes": 90,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day40_IcebergMeta").getOrCreate()
spark.sql("SHOW TBLPROPERTIES demo.practice.orders").show(truncate=False)
spark.sql("DESCRIBE EXTENDED demo.practice.orders").show(30, truncate=False)
spark.stop()""",
        "goals": [
            "Inspect snapshot/file metadata tables (`$files`, `$snapshots`, Delta `_delta_log`)",
            "Compare Partitioning vs Z-Ordering vs Liquid Clustering (eliminating partition over-sharding!)",
            "Build Change Data Feed (CDF) incremental downstream pipelines (`readChangeFeed`) + safe `VACUUM` retention",
        ],
        "lesson_md": """# Day 40 – Lakehouse File Layout, Z-Order, Liquid Clustering & Time Travel

## 1. Compaction & Data Skipping
- Thousands of tiny 200 KB Parquet files kill Spark listing/footer reads.
- Target **128 MB–512 MB** file sizes via **`OPTIMIZE` / Iceberg `rewrite_data_files`** and **`ZORDER BY (high_cardinality_filter_col)`** (co-locating multi-dimensional filter columns via space-filling curves) or modern **Liquid Clustering** (`CLUSTER BY`) which avoids rewriting old partitions when filter patterns change!

## 2. `VACUUM` Danger
Default Delta `VACUUM` retention is 7 days (168 hours). Never run `VACUUM RETAIN 0 HOURS` while concurrent readers/streaming jobs are active—deleting referenced Parquet snapshots breaks running queries immediately!
""",
        "interview_questions": [
            {"question": "Why does Liquid Clustering beat Hive partitioning + Z-Order for fast-growing tables?", "answer": "Hive partitioning locks physical folder layout permanently (causing either too many tiny partitions or massive monolithic ones) and Z-Order rewrites whole partitions from scratch. Liquid Clustering uses incremental Hilbert-curve clustering that adapts as filter columns evolve without rigid directory hierarchies.", "scenario": "Customer refactored a 10 TB events table after cardinality changed from `region` to `tenant_id`."},
        ],
    },
    {
        "day": 41,
        "phase": 7,
        "title": "Day 41 – Production PySpark Testing (`pytest`/`chispa`), CI/CD & Plan Profiling",
        "estimated_minutes": 80,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day41_Testing").master("local[2]").getOrCreate()
actual = spark.createDataFrame([(1, "A"), (2, "B")], ["id", "tag"]).orderBy("id").collect()
expected = [(1, "A"), (2, "B")]
assert [(r["id"], r["tag"]) for r in actual] == expected, "Transform mismatch!"
print("Unit test assertion PASSED:", len(actual), "rows verified.")
spark.stop()""",
        "goals": [
            "Write isolated fast PySpark unit tests (`pytest` fixture `SparkSession` + `chispa.assert_df_equality`)",
            "Separate pure transformation logic (`def transform(df) -> DataFrame`) from S3/JDBC I/O for testability",
            "Read Spark UI metrics: Shuffle Read/Write, Spill (Memory vs Disk), Task Deserialization & GC Time",
        ],
        "lesson_md": """# Day 41 – Testing, CI/CD & Reading Spark UI Like a Staff Engineer

## Testable PySpark Module Design
Never bury S3 paths inside monolithic transformation scripts!
1. Keep pure functions: `def enrich_orders(orders_df: DataFrame, cust_df: DataFrame) -> DataFrame`.
2. Reuse one session-scoped `local[2]` `SparkSession` with `spark.sql.shuffle.partitions=2` so 50 unit tests finish in <15 seconds inside GitHub Actions / Azure DevOps CI.
3. Validate **schema nullability, edge cases (NULLs, duplicates, late arrivals), and idempotency** (`transform(transform(x))` or double-MERGE).
""",
        "interview_questions": [
            {"question": "You open the Spark UI on a failing stage and see 'Spill (Disk): 120 GB' and 'GC Time: 35% of task time'. What do those two signals prove?", "answer": "Tasks do not fit in Execution Memory (caused by skewed keys, massive array explosions, or too few shuffle partitions relative to data size), forcing Spark to serialize/spill to local disk and thrash JVM GC. Fix by increasing `shuffle.partitions`, salting/filtering skew, or projecting fewer columns before joins.", "scenario": "Classic live Spark UI screenshot debugging interview round."},
        ],
    },
    {
        "day": 42,
        "phase": 7,
        "title": "Day 42 – Senior PySpark Optimization Lab: Turning a 2-Hour Job into 6 Minutes",
        "estimated_minutes": 100,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql import functions as F
spark = SparkSession.builder.appName("Day42_OptimizationLab").getOrCreate()
# Optimized pipeline: prune early -> filter early -> broadcast small dims -> single agg
li = spark.table("demo.practice.lineitem").select("l_orderkey", "l_partkey", "l_extendedprice", "l_discount").filter("l_shipdate >= '1995-01-01'")
part = spark.table("demo.practice.part").select("p_partkey", "p_brand").filter("p_brand = 'Brand#13'")
res = li.join(F.broadcast(part), li.l_partkey == part.p_partkey).groupBy("p_brand").agg(F.round(F.sum(F.col("l_extendedprice") * (1 - F.col("l_discount"))), 2).alias("net_rev"))
res.show()
spark.stop()""",
        "goals": [
            "Execute a systematic 8-step Spark optimization checklist during interviews",
            "Eliminate anti-patterns: `.count()` inside logging loops, uncached multi-branch recomputation, wide `SELECT *`, skew + small files",
            "Quantify business impact (vCPU-hours saved, SLA met, memory reduction)",
        ],
        "lesson_md": """# Day 42 – 8-Step Senior Spark Performance Tuning Checklist

1. **Eliminate Accidental Actions:** Remove debug `.count()` / `.show()` left inside prod loops (triggers redundant DAG evaluations!).
2. **Prune & Filter Before Joins:** Project only needed columns and filter earliest (`Predicate Pushdown` to Parquet/Iceberg/Delta).
3. **Fix Join Plans:** Enable AQE (`autoBroadcastJoinThreshold`), broadcast small dimensions safely, remove cross joins.
4. **Kill Python UDFs:** Rewrite row-wise Python UDFs into native `F.*` SQL expressions or Arrow `@pandas_udf`.
5. **Tame Skew:** Isolate `NULL`s, enable AQE `skewJoin`, salt hot keys.
6. **Balance Partitions:** Target ~128–256 MB per partition (`shuffle.partitions` + AQE `coalescePartitions`).
7. **Eliminate Small Files:** Compact writes (`maxRecordsPerFile`, Delta/Iceberg `OPTIMIZE`).
8. **Cache Deliberately:** `.persist(MEMORY_AND_DISK)` ONLY when a filtered/expensive DataFrame is branched >=2 times, and `.unpersist()` immediately after!
""",
        "interview_questions": [
            {"question": "Walk me through how you reduced a real Spark job runtime by >80% (6-year experience favorite).", "answer": "Use a crisp metric-backed walkthrough: (1) Identified from Spark UI that Stage 4 had 199/200 tasks finishing in 10s while 1 task skewed for 85m on `NULL` customer IDs + 3 Python UDFs + 50,000 tiny output files; (2) Split/filtered NULLs, replaced UDFs with native expressions, enabled AQE + BHJ, and compacted outputs to 256 MB Parquet; (3) Cut runtime from 110m to 7m and saved 70% compute cost.", "scenario": "Expect follow-up deep dives on Shuffle Read/Write, AQE, and executor sizing."},
        ],
    },
]

