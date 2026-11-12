"""Phase 9: Azure Databricks, Unity Catalog, Microsoft Fabric & FinOps (Days 51-56)."""

DAYS_51_TO_56 = [
    {
        "day": 51,
        "phase": 9,
        "title": "Day 51 – Azure Databricks Architecture & Unity Catalog 3-Level Namespace",
        "estimated_minutes": 90,
        "practice_type": "pyspark",
        "practice_snippet": """# Practice Unity Catalog 3-level namespace pattern (catalog.schema.table) on live Iceberg REST!
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day51_3LevelNamespace").getOrCreate()
spark.sql("SHOW TABLES IN demo.practice").show(truncate=False)
spark.sql("DESCRIBE TABLE demo.practice.customer").show(truncate=False)
spark.stop()""",
        "goals": [
            "Separate Databricks Control Plane (UI, Notebooks, Workflows, Unity Metastore) vs Data/Compute Plane (VNet Injection, ADLS in customer subscription)",
            "Master Unity Catalog 3-Level Namespace (`catalog.schema.table`), Storage Credentials (Access Connector Managed Identity) & External Locations",
            "Know Managed Tables vs External Tables (`DROP TABLE` deletes files only on Managed Tables!) & Access Modes (`Shared`/`Assigned` vs Legacy)",
        ],
        "lesson_md": """# Day 51 – Azure Databricks Architecture & Unity Catalog

## 1. Control Plane vs Compute Plane (Security Interview Standard)
- Your ADLS Gen2 Parquet/Delta data **never leaves your Azure tenant**! Deploy Azure Databricks with **VNet Injection** + **No Public IP (`NPIP` / Secure Cluster Connectivity)** + **Private Link** for Regulated Finance/Healthcare environments.

## 2. Unity Catalog 3-Level Namespace (`prod_catalog.silver.orders`)
- **Storage Credential:** Points to an **Azure Databricks Access Connector** (User-Assigned Managed Identity) holding `Storage Blob Data Contributor` on ADLS Gen2.
- **External Location:** Pairs an `abfss://` URL prefix with a Storage Credential.
- **Managed vs External Tables:**
  - `Managed`: Unity Catalog governs both metadata + lifecycle (`DROP TABLE` schedules underlying Delta file deletion after retention!).
  - `External`: `DROP TABLE` drops metastore pointer only; underlying ADLS files remain untouched.
""",
        "interview_questions": [
            {"question": "Why should modern Azure Databricks teams stop mounting ADLS with `dbutils.fs.mount()` and migrate to Unity Catalog External Locations?", "answer": "DBFS root mounts use cluster-wide credentials accessible to everyone on a cluster (`No Isolation Shared`), breaking fine-grained table/column/row ACLs and column-level lineage. Unity Catalog uses Storage Credentials + External Locations scoped per user identity with full audit logs and automatic lineage.", "scenario": "Enterprise legacy Databricks workspace upgrade to Unity Catalog."},
        ],
    },
    {
        "day": 52,
        "phase": 9,
        "title": "Day 52 – Databricks Clusters, Photon Engine, DBUs & Compute Sizing",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """from pyspark.sql import SparkSession
from pyspark.sql import functions as F
spark = SparkSession.builder.appName("Day52_PhotonCompute").getOrCreate()
# Simulated compute cost awareness: vectorized built-ins over raw loops
df = spark.table("demo.practice.lineitem")
summary = df.groupBy("l_returnflag", "l_linestatus").agg(F.count("*").alias("cnt"), F.round(F.sum("l_extendedprice"), 2).alias("sum_price"))
summary.show()
spark.stop()""",
        "goals": [
            "Know All-Purpose Compute (~2.5x–3.5x DBU rate!) vs Automated Job Compute (~$0.15/DBU) vs SQL Serverless Warehouses",
            "Explain **Photon Engine**: native C++ vectorized SIMD execution replacing JVM bottlenecks on scans/joins/aggs",
            "Optimize VM Families (`E_ds_v5` Memory-Optimized vs `L_sv3` Storage-Optimized NVMe SSD cache vs `D_ds_v5` General Purpose) + Spot eviction fallback",
        ],
        "lesson_md": """# Day 52 – Compute Sizing, Photon Engine & DBU FinOps

## 1. Never Schedule Production Jobs on All-Purpose Clusters!
All-purpose interactive clusters cost roughly **2.5x–3.5x more per DBU** than Automated Job Compute. Always run scheduled Airflow/Workflows pipelines on dedicated ephemeral **Job Compute**!

## 2. When Photon Helps (and When It Doesn't)
- **Photon** accelerates Spark SQL, built-in `F.*` DataFrame transforms, Delta `MERGE`, and wide Parquet/Delta scans by **2x–8x** using vectorized C++ execution.
- **Photon does NOT accelerate** Python UDFs (`@udf` / `@pandas_udf`)—falling back across JVM↔Python borders wastes Photon DBU premiums!
- **Spot Strategy:** Put Workers on Spot (`Spot with Fallback to On-Demand`) while keeping the **Driver 100% On-Demand** so Spot evictions never kill orchestrator state.
""",
        "interview_questions": [
            {"question": "You turned on Photon and your Databricks bill doubled without reducing runtime. What happened?", "answer": "Either the job spends most of its time in Python UDFs, external JDBC network waits, small-file metadata bottlenecks, or slow API calls where Photon C++ vectorization isn't utilized, while Photon doubles DBU cost per hour.", "scenario": "Classic 6-year Azure Databricks FinOps audit case."},
        ],
    },
    {
        "day": 53,
        "phase": 9,
        "title": "Day 53 – Auto Loader (`cloudFiles`) & Delta Live Tables (DLT) Declarative Pipelines",
        "estimated_minutes": 90,
        "practice_type": "pyspark",
        "practice_snippet": """# Practice incremental schema enforcement & expectation assertions locally in PySpark
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
spark = SparkSession.builder.appName("Day53_DLTExpectations").getOrCreate()
orders = spark.table("demo.practice.orders")
valid = orders.filter((F.col("o_orderkey").isNotNull()) & (F.col("o_totalprice") > 0))
quarantine = orders.filter((F.col("o_orderkey").isNull()) | (F.col("o_totalprice") <= 0))
print("Valid orders:", valid.count(), "| Quarantined:", quarantine.count())
spark.stop()""",
        "goals": [
            "Compare Auto Loader `directoryListing` vs **File Notification Mode** (Azure Queue + Event Grid for 10M+ files/day)",
            "Handle schema evolution safely (`cloudFiles.schemaLocation`, `addNewColumns`, `rescue`, `_rescued_data`)",
            "Design Delta Live Tables (DLT / Lakeflow) with `@dlt.table`, Streaming Tables vs Materialized Views, and Expectations (`expect`, `expect_or_drop`, `expect_or_fail`)",
        ],
        "lesson_md": """# Day 53 – Auto Loader & Delta Live Tables (DLT)

## 1. Why Auto Loader Beats Raw `spark.read.json()` / `readStream`
Raw file streaming repeatedly lists **every object** in an ADLS container every trigger (`O(N)` HTTP calls, throttles ADLS at millions of files!).
- **Auto Loader (`spark.readStream.format("cloudFiles")`):** Caches discovered files incrementally in RocksDB (`checkpointLocation`), and in **File Notification Mode** automatically provisions **Azure Event Grid + Azure Queue Storage** to ingest only newly arrived blobs in `O(1)`!
- Unexpected columns go safely into `_rescued_data` instead of silently failing jobs.

## 2. DLT / Lakeflow Data Quality Expectations
- `@dlt.expect("valid_ts", "ts IS NOT NULL")` -> log metric, keep row.
- `@dlt.expect_or_drop(...)` -> filter invalid rows + route cleanly if paired with quarantine stream.
- `@dlt.expect_or_fail(...)` -> halt pipeline immediately on critical contract breach!
""",
        "interview_questions": [
            {"question": "Why does Auto Loader File Notification mode save significant ADLS cost at 50M+ historical objects?", "answer": "Directory listing walks millions of ADLS directories every trigger, incurring huge ADLS transaction costs and rate limits. File Notification subscribes once to Event Grid blob creation events queued in Azure Storage Queues (`cloudFiles.useNotifications=true`), billing only per actually arriving file.", "scenario": "IoT telemetry ingestion scaling from 10k files/day to 5M files/day."},
        ],
    },
    {
        "day": 54,
        "phase": 9,
        "title": "Day 54 – Databricks Workflows, Asset Bundles (DABs) & Azure DevOps CI/CD",
        "estimated_minutes": 80,
        "practice_type": "azure",
        "practice_snippet": """# Databricks Asset Bundles (databricks.yml) GitOps CI/CD structure for Dev -> Staging -> Prod
# targets:
#   dev:   { mode: development, workspace: { host: https://adb-dev.azuredatabricks.net } }
#   prod:  { mode: production,  run_as: { service_principal_name: "<ENTRA_SP_ID>" } }
# commands:
#   databricks bundle validate -t prod && databricks bundle deploy -t prod && databricks bundle run -t prod medallion_job""",
        "goals": [
            "Architect Databricks Asset Bundles (`databricks.yml`) vs fragile UI JSON export scripts",
            "Run Jobs in Prod under an **Entra ID Service Principal** (`run_as`), NEVER a personal developer account!",
            "Orchestrate Task Values (`dbutils.jobs.taskValues`), Repair-Run recovery, and ADF ↔ Databricks integration",
        ],
        "lesson_md": """# Day 54 – GitOps CI/CD with Databricks Asset Bundles (DABs)

## 1. Zero Personal Credentials in Production
Never deploy scheduled Workflows running as `alice@company.com`—when Alice changes teams or leaves, every production job breaks immediately! Always set `run_as.service_principal_name` via Azure DevOps OIDC / GitHub Actions Federated Credentials.

## 2. Multi-Task Workflow Orchestration
- Share **one Job Cluster across parallel/sequential tasks** inside the same Workflow to avoid paying 3–5 minutes of VM boot warmup on every single Bronze → Silver → Gold step!
- Pass lightweight JSON parameters downstream via `dbutils.jobs.taskValues.set()` / `.get()`.
""",
        "interview_questions": [
            {"question": "How do you avoid paying repeated cluster boot delays across a 6-step Databricks Workflow while still isolating Prod from Dev?", "answer": "Define a shared **Workflow Job Cluster (`job_cluster_key`)** inside the DAB `databricks.yml` so Bronze/Silver/Gold Python tasks reuse the same ephemeral job cluster and terminate together upon completion; parameterize catalog (`dev_catalog` vs `prod_catalog`) and Service Principal `run_as` per DAB target.", "scenario": "CI/CD promotion architecture across Dev/Test/Prod Azure subscriptions."},
        ],
    },
    {
        "day": 55,
        "phase": 9,
        "title": "Day 55 – Microsoft Fabric, OneLake & Direct Lake Architecture",
        "estimated_minutes": 80,
        "practice_type": "azure",
        "practice_snippet": """# Concept Check: OneLake Unified Delta Parquet Architecture
# ADLS Gen2 Container -> Fabric Shortcut (Zero Copy!) -> OneLake Delta Lake Table -> Power BI Direct Lake Mode
# Mirrors our local Unified Studio pattern: MinIO Bronze/Warehouse -> Spark/Iceberg -> Postgres/BI!""",
        "goals": [
            "Understand Microsoft Fabric SaaS Capacity (F-SKUs vs Synapse DWUs) & **OneLake** ('OneDrive for Data')",
            "Use **OneLake Shortcuts** to expose existing ADLS Gen2 / S3 / Databricks Unity Catalog Delta tables with zero data copy",
            "Explain **Power BI Direct Lake Mode** vs Import Mode vs DirectQuery (memory speed without scheduled dataset refresh!)",
        ],
        "lesson_md": """# Day 55 – Microsoft Fabric & OneLake for 6-Year Azure DEs

## 1. Why Senior Azure DEs Are Asked About Fabric Now
Microsoft consolidated ADF, Synapse Pipelines, Synapse Spark, Data Explorer, and Power BI under one capacity model (**F-SKUs**):
- **OneLake Shortcuts:** Point directly at existing ADLS Gen2 Delta tables without duplicating terabytes of storage!
- **Direct Lake Mode:** Power BI reads Delta Parquet columns directly from OneLake into VertiPaq RAM—combining **Import-mode BI speed** with **real-time Delta freshness** and zero Import refresh pipelines.
- **Fabric Warehouse vs Fabric Lakehouse:** Choose Lakehouse (Spark/Delta primary) or T-SQL Warehouse (`INSERT/UPDATE/DELETE` ACID transactions across multi-tables with cross-database querying in SQL endpoint).
""",
        "interview_questions": [
            {"question": "When would an enterprise stay on Azure Databricks + ADLS Gen2 vs migrating fully to Microsoft Fabric?", "answer": "Keep Azure Databricks for complex multi-cloud governance (AWS+Azure), mature custom Spark/ML workloads, Photon price-performance at massive scale, and Unity Catalog openness; leverage Fabric/OneLake Shortcuts cleanly for Power BI Direct Lake serving and unified SaaS capacity teams without duplicating raw lake storage.", "scenario": "CTO/Architect vendor-evaluation interview round."},
        ],
    },
    {
        "day": 56,
        "phase": 9,
        "title": "Day 56 – Azure Data FinOps, Observability (Log Analytics/KQL) & Cost Guardrails",
        "estimated_minutes": 85,
        "practice_type": "sql",
        "practice_snippet": """-- Inspect FinOps container memory allocation or warehouse table storage sizes locally
SELECT n.nspname AS schema_name, c.relname AS table_name,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'synapse_dw' AND c.relkind = 'r'
ORDER BY pg_total_relation_size(c.oid) DESC;""",
        "goals": [
            "Design Azure Cost Controls: Auto-termination (10–15 min idle), Job Compute vs Interactive, Spot Workers, Synapse Auto-Pause & Delta storage tiering",
            "Stream ADF, Databricks (`system.billing.usage` + `system.lakeflow`!), and Event Hubs diagnostics into **Azure Log Analytics**",
            "Write KQL (Kusto) alerting queries for SLA breaches, SHIR offline alerts & cluster DBU spikes",
        ],
        "lesson_md": """# Day 56 – Enterprise Azure FinOps & Log Analytics Monitoring

## Top 5 Azure Data Cost Savings a 6-Year DE Delivers
1. Switch interactive scheduled notebooks to **Job Compute** (~60% instant DBU drop).
2. Enforce **10-min auto-termination** & cluster policies capping max DBUs/team.
3. Convert 24/7 idle Structured Streaming jobs that only need 5–15 min freshness to **`trigger(availableNow=True)`** + Airflow/Workflows.
4. Set **ADLS Gen2 Lifecycle Policies** moving old Bronze raw files >30 days to **Cool** and >180 days to **Archive** (cut storage bill 70%+).
5. Enable **Databricks System Tables (`system.billing.usage`)** to tag every DBU by `cost_center`, `pipeline`, and `env`!
""",
        "interview_questions": [
            {"question": "Your company's monthly Azure Databricks + ADLS bill jumped from $18k to $45k overnight. How do you pinpoint the exact culprit in 10 minutes?", "answer": "Query Databricks `system.billing.usage` (grouped by `workspace_id`, `sku_name`, `usage_metadata.job_id`, `run_as`) joined with cluster tags, and check Azure Cost Analysis filtered by Storage `Transactions` (often caused by missing Auto Loader notifications or small-file listing storms) vs Compute All-Purpose clusters left running 24/7.", "scenario": "Real FinOps emergency response expected at 6-year seniority."},
        ],
    },
]

