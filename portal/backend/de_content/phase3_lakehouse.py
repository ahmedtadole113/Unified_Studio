"""Phase 3: Lakehouse, MinIO/S3, Delta Lake 4.0 & Apache Iceberg (Days 14-18)."""

DAYS_14_TO_18 = [
    {
        "day": 14,
        "phase": 3,
        "title": "Day 14 – Object Storage (MinIO/S3) & Parquet Internals",
        "estimated_minutes": 80,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day14_Parquet").getOrCreate()
df = spark.read.option("header", "true").option("inferSchema", "true").csv("/home/iceberg/data/customer.csv")
df.write.mode("overwrite").parquet("/tmp/day14_customer_parquet")
pq = spark.read.parquet("/tmp/day14_customer_parquet")
print("Rows:", pq.count(), "Partitions:", pq.rdd.getNumPartitions())
spark.stop()""",
        "goals": [
            "Why Object Storage (MinIO / S3 / ADLS Gen2) beats HDFS",
            "Parquet Anatomy: Row Groups, Column Chunks, Pages, Footers",
            "Predicate Pushdown, Dictionary Encoding, & the Small Files Problem",
        ],
        "lesson_md": """# Day 14 – Object Storage & Parquet Internals

## 1. Parquet File Layout
A Parquet file splits rows horizontally into **Row Groups** (~128 MB default), and within each Row Group stores **Column Chunks** contiguously. The **Footer** stores `min`/`max` statistics per column per Row Group.
- **Predicate Pushdown:** If `WHERE order_date = '2026-11-12'` and a Row Group footer says `max(order_date) = '2026-10-31'`, Spark skips reading that entire Row Group!

## 2. The Small Files Problem
Streaming jobs writing every 5 seconds produce 17,280 tiny 5 KB files/day! Listing millions of S3 objects and opening thousands of file footers cripples query latency. **Fix:** Periodic compaction (`OPTIMIZE` in Delta / `rewrite_data_files` in Iceberg) targeting 128–512 MB files.
""",
        "interview_questions": [
            {"question": "What is the Small Files Problem in Data Lakes and how do you solve it?", "answer": "Too many tiny Parquet files (<10 MB) cause high S3 metadata listing overhead and slow Spark task scheduling. Solve via periodic compaction (`OPTIMIZE` in Delta, `rewrite_data_files` in Iceberg), `maxRecordsPerFile`, or Auto Optimize / Write Compaction.", "scenario": "Query taking 12 minutes across 120,000 50KB files drops to 8 seconds after compacting into 120 128MB files."},
        ],
    },
    {
        "day": 15,
        "phase": 3,
        "title": "Day 15 – Medallion Architecture (Bronze, Silver, Gold) with TPC-H",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as s_sum
spark = SparkSession.builder.appName("Day15_Medallion").getOrCreate()
cust = spark.read.option("header","true").option("inferSchema","true").csv("/home/iceberg/data/customer.csv")
orders = spark.read.option("header","true").option("inferSchema","true").csv("/home/iceberg/data/orders.csv")
gold = cust.join(orders, cust.c_custkey == orders.o_custkey).groupBy("c_mktsegment").agg(s_sum("o_totalprice").alias("revenue"))
gold.show()
spark.stop()""",
        "goals": [
            "Bronze (Raw Immutable Audit) -> Silver (Cleaned, Conformed, Deduplicated) -> Gold (Business Marts)",
            "Idempotency & Safe Reprocessing from Bronze",
            "Mapping TPC-H datasets across MinIO buckets and PostgreSQL DW",
        ],
        "lesson_md": """# Day 15 – Medallion Architecture (Bronze, Silver, Gold)

- **Bronze:** Raw append-only landing zone (`s3://bronze/`) preserving original schema + `_ingested_at` + `_source_file`. Enables full historical replay if a Silver bug is discovered!
- **Silver:** Cleansed, typed, deduplicated, conformed entity tables (`s3://silver/`) with Data Quality contracts enforced.
- **Gold:** Denormalized Star Schema or aggregated KPIs (`s3://gold/` and `synapse_dw` PostgreSQL) optimized for BI and ML.

## Homework
Open `notebooks/Medallion_Architecture_TPCH.ipynb` in JupyterLab and trace Bronze → Silver → Gold end-to-end.
""",
        "interview_questions": [
            {"question": "Why should Bronze never overwrite or drop raw fields?", "answer": "Bronze is your immutable system of record for raw ingestion. When business logic or parsing rules change in Silver/Gold, you can replay from Bronze without re-extracting from fragile upstream APIs or OLTP databases.", "scenario": "Discovering a currency conversion bug 3 months later -> Fix Silver SQL and replay from Bronze."},
        ],
    },
    {
        "day": 16,
        "phase": 3,
        "title": "Day 16 – Delta Lake 4.0 Deep Dive (ACID, MERGE, Time Travel, OPTIMIZE)",
        "estimated_minutes": 90,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day16_Delta").getOrCreate()
df = spark.createDataFrame([(1,"A",100),(2,"B",200)], ["id","name","val"])
df.write.format("delta").mode("overwrite").save("/tmp/day16_delta")
spark.createDataFrame([(2,"B",250),(3,"C",300)], ["id","name","val"]).createOrReplaceTempView("updates")
spark.sql("MERGE INTO delta.`/tmp/day16_delta` t USING updates s ON t.id = s.id WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *")
spark.read.format("delta").load("/tmp/day16_delta").orderBy("id").show()
spark.stop()""",
        "goals": [
            "How `_delta_log` JSON + Parquet checkpoints deliver ACID on S3/MinIO",
            "Optimistic Concurrency Control",
            "`MERGE INTO` Upserts, Time Travel (`VERSION AS OF`), `OPTIMIZE`, Z-Ordering / Liquid Clustering, `VACUUM`",
        ],
        "lesson_md": """# Day 16 – Delta Lake 4.0 Deep Dive

## 1. How `_delta_log` Works
Every commit writes an ordered atomic JSON file (`000000.json`, `000001.json`) listing `add` and `remove` Parquet files. Every 10 commits, Delta writes a Parquet checkpoint so readers reconstruct table state in milliseconds.

## 2. `VACUUM` vs Time Travel Trade-off
`VACUUM table RETAIN 168 HOURS` deletes old unreferenced Parquet files (saving S3 cost). Once vacuumed, you can no longer Time Travel to versions older than 7 days!

## 3. Z-Ordering vs Liquid Clustering
`OPTIMIZE table ZORDER BY (customer_id)` co-locates related values across files for multi-column filtering. **Liquid Clustering** (`CLUSTER BY`) replaces rigid Hive partitioning + Z-Order with incremental clustering without rewriting the whole table.
""",
        "interview_questions": [
            {"question": "How does Delta Lake provide ACID transactions on object storage like S3/MinIO which lacks multi-file locks?", "answer": "Through the `_delta_log` ordered transaction log using atomic put-if-absent/rename primitives and Optimistic Concurrency Control: writers record which files were read/added/removed and check for conflicts before committing the next sequential JSON log entry.", "scenario": "Two concurrent Spark jobs reading and writing the same table never expose half-written Parquet files."},
        ],
    },
    {
        "day": 17,
        "phase": 3,
        "title": "Day 17 – Apache Iceberg Internals (Catalogs, Hidden Partitioning & Evolution)",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """# Inspect Iceberg catalog configuration in Spark
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day17_Iceberg").getOrCreate()
for k, v in spark.sparkContext.getConf().getAll():
    if "iceberg" in k or "catalog.demo" in k:
        print(f"{k} = {v}")
spark.stop()""",
        "goals": [
            "Iceberg Tree: Catalog -> Metadata JSON -> Manifest List -> Manifest Files -> Data Files",
            "Hidden Partitioning (no extra `event_date` column needed!)",
            "In-place Schema Evolution & Partition Evolution without rewriting historical data",
        ],
        "lesson_md": """# Day 17 – Apache Iceberg Internals

## 1. Iceberg Metadata Tree
- **Catalog (`iceberg-rest` :8181):** Atomic pointer to the current `metadata.json`.
- **Manifest List:** One per snapshot; tracks partition min/max bounds for manifest pruning.
- **Manifest Files:** List individual Parquet/ORC data files + column-level min/max/null counts.

## 2. Killer Feature: Hidden Partitioning & Partition Evolution
In Hive/legacy Parquet, if data is partitioned by `date_str`, querying `WHERE ts >= '2026-11-01'` causes a **full table scan** unless users remember to filter on `date_str` too! Iceberg's `PARTITIONED BY (days(ts))` hides partitioning—queries on `ts` automatically prune partitions, and changing from `days(ts)` to `hours(ts)` works in-place without rewriting old files!
""",
        "interview_questions": [
            {"question": "What is Iceberg Partition Evolution and why does it matter?", "answer": "Iceberg stores partition specs inside metadata per snapshot rather than in physical directory paths alone. You can evolve a table from monthly to daily or hourly partitioning without migrating/rewriting terabytes of historical data.", "scenario": "Data volume grows 20x over 2 years -> evolve partition granularity seamlessly."},
        ],
    },
    {
        "day": 18,
        "phase": 3,
        "title": "Day 18 – Incremental Ingestion, Watermarking & CDC Patterns",
        "estimated_minutes": 80,
        "practice_type": "sql",
        "practice_snippet": """SELECT COUNT(*) AS loaded_txs, MIN(transaction_id) AS min_id, MAX(transaction_id) AS high_watermark
FROM synapse_dw.fact_transactions;""",
        "goals": [
            "Full Load vs Incremental High-Watermark vs Log-Based CDC",
            "Handling Updates & Hard Deletes (CDC Tombstones / `op = 'd'`)",
            "Idempotent `MERGE` / `ON CONFLICT DO UPDATE`",
        ],
        "lesson_md": """# Day 18 – Incremental Ingestion & CDC

## 1. High-Watermark Pattern (Seen in `project3_incremental_load.py`)
1. Query `MAX(updated_at)` or `MAX(transaction_id)` from target DW/Silver table.
2. Fetch `WHERE id > watermark`.
3. Stage to MinIO Silver, then `MERGE` into target.
*Limitation:* High-watermark polling misses **hard `DELETE`s** in source OLTP!

## 2. Log-Based CDC (Debezium -> Redpanda/Kafka -> Spark)
Reads database Write-Ahead Log (WAL / Binlog) directly with near-zero impact on OLTP queries and captures `INSERT` (`c`), `UPDATE` (`u`), AND `DELETE` (`d`) tombstones!
""",
        "interview_questions": [
            {"question": "Why does timestamp-based incremental polling miss deletes, and how do you capture deletes?", "answer": "Deleted rows vanish from the source table so `WHERE updated_at > last_run` never sees them. Solve by using soft-delete flags (`is_deleted`), audit tables, or log-based CDC (Debezium reading Postgres WAL/MySQL binlog).", "scenario": "Financial compliance requires deleted orders to disappear from Gold revenue reports."},
        ],
    },
]

