"""Phase 8: Azure Data Cloud Foundations & Ingestion Mastery for 6-Year Senior DEs (Days 43-50)."""

DAYS_43_TO_50 = [
    {
        "day": 43,
        "phase": 8,
        "title": "Day 43 – Azure Core Security, IAM, Managed Identities & Private Networking",
        "estimated_minutes": 85,
        "practice_type": "azure",
        "practice_snippet": """# Azure CLI: Assign Storage Blob Data Contributor to Managed Identity without storing secrets
az role assignment create \\
  --assignee-object-id <ADF_OR_DATABRICKS_MI_PRINCIPAL_ID> \\
  --assignee-principal-type ServicePrincipal \\
  --role "Storage Blob Data Contributor" \\
  --scope /subscriptions/<SUB_ID>/resourceGroups/rg-de-prod/providers/Microsoft.Storage/storageAccounts/adlsdeprod""",
        "goals": [
            "Understand Subscriptions, Resource Groups, Entra ID (AAD), Service Principals vs Managed Identities (System & User-Assigned)",
            "Differentiate Azure RBAC (management + coarse data plane) vs ADLS POSIX ACLs (folder/file fine-grained permissions)",
            "Design Zero-Public-Internet Data Platforms with VNets, Private Endpoints & Private DNS Zones",
        ],
        "lesson_md": """# Day 43 – Azure IAM, Managed Identities & Private Networking

## 1. Zero-Secret Authentication Pattern
A 6-year Azure Data Engineer **never** hardcodes Storage Account Keys or SAS tokens in production!
- Use **Managed Identities (MI)** (for ADF, Synapse, Logic Apps) or **Unity Catalog Access Connectors** (User-Assigned MI) to authenticate via Microsoft Entra ID OAuth tokens.

## 2. RBAC vs POSIX ACLs on ADLS Gen2
- **RBAC (`Storage Blob Data Reader/Contributor`):** Grants broad access across the **entire** container/storage account. Useful for service-level ingestion.
- **POSIX ACLs (`rwx` per directory/file):** Grants granular access down to `/silver/finance/` without exposing `/silver/hr_pii/`. Note: requires `Execute (x)` traversal permission on all parent folders!
""",
        "interview_questions": [
            {"question": "Why does granting a user `Read` POSIX ACL on `/gold/finance/sales.parquet` still fail if RBAC isn't assigned?", "answer": "POSIX ACL evaluation requires Execute (`--x`) permission on **every parent directory** from root (`/`, `/gold`, `/gold/finance`) in addition to Read (`r--`) on the file. If an upstream team forgets `--x` on `/gold`, Entra ID ACL checks deny access.", "scenario": "Classic Azure ADLS Gen2 production permission debugging question."},
        ],
    },
    {
        "day": 44,
        "phase": 8,
        "title": "Day 44 – ADLS Gen2 Internals: Hierarchical Namespace, Medallion Layout & Throughput",
        "estimated_minutes": 80,
        "practice_type": "azure",
        "practice_snippet": """# Inspect our local ADLS Gen2 (MinIO S3) Medallion buckets mirroring Azure abfss:// containers
import boto3, os
s3 = boto3.client("s3", endpoint_url="http://minio:9000", aws_access_key_id=os.environ.get("MINIO_ROOT_USER","admin"), aws_secret_access_key=os.environ.get("MINIO_ROOT_PASSWORD","ues_minio_secret"))
for b in s3.list_buckets()["Buckets"]:
    print("Container:", b["Name"])""",
        "goals": [
            "Understand why Hierarchical Namespace (HNS) transforms Blob Storage into true atomic-rename ADLS Gen2",
            "Use `abfss://<container>@<account>.dfs.core.windows.net/` vs legacy `wasbs://`",
            "Design Medallion containers, hot/cool/archive lifecycle policies & soft-delete protection",
        ],
        "lesson_md": """# Day 44 – Azure Data Lake Storage Gen2 (ADLS Gen2)

## Why Hierarchical Namespace (HNS) Matters for Spark & Databricks
In flat Azure Blob Storage (`wasbs://`), renaming a folder (e.g., Spark staging `_temporary` commit or Delta operations) must **copy + delete every single file one by one** (`O(N)` — catastrophically slow + non-atomic!).
Enabling **HNS (`abfss://`)** makes folder renames **`O(1)` metadata atomic operations**, unlocks POSIX ACLs, and dramatically accelerates Spark listing.
""",
        "interview_questions": [
            {"question": "Why must Hierarchical Namespace be enabled at storage account creation for enterprise Lakehouse workloads?", "answer": "Without HNS, Spark directory renames are O(N) non-atomic file copies, and POSIX directory-level ACLs do not exist. Always use `abfss://...dfs.core.windows.net` with HNS enabled.", "scenario": "Team created a standard Blob account without HNS; 10,000-file Spark commits stalled for 25 minutes per job."},
        ],
    },
    {
        "day": 45,
        "phase": 8,
        "title": "Day 45 – Azure Data Factory (ADF): Pipelines, Linked Services & Integration Runtimes",
        "estimated_minutes": 90,
        "practice_type": "sql",
        "practice_snippet": """-- Inspect watermark control metadata table pattern (used by ADF Lookup + Stored Procedure / Airflow)
SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'synapse_dw';""",
        "goals": [
            "Master ADF Core Objects: Linked Services, Datasets, Activities, Pipelines, Triggers (Schedule, Tumbling Window, Storage Event)",
            "Compare Azure IR vs Self-Hosted IR (SHIR for on-prem SQL Server/Oracle behind firewalls) vs Managed VNet IR",
            "Map ADF pipelines to Apache Airflow concepts (our local `airflow/dags/adf_features_demo.py`!)",
        ],
        "lesson_md": """# Day 45 – Azure Data Factory (ADF) Architecture & Integration Runtimes

## 1. Choosing the Right Integration Runtime (IR)
- **Azure IR:** Cloud-to-cloud movement (ADLS, Synapse, REST APIs) with elastic serverless scale.
- **Self-Hosted IR (SHIR):** Installed on Windows VM(s) inside corporate network/VPN to pull on-premises SQL Server, SAP, or network file shares securely outbound over TLS (ports 443) without opening inbound firewall ports. Scale SHIR High Availability up to 4 nodes!
- **Managed VNet IR:** Runs inside ADF-managed VNet communicating via **Managed Private Endpoints** to locked-down ADLS/Synapse/SQL DB.

## 2. Trigger Types
- **Tumbling Window Trigger:** Ideal for historical backfill & strict non-overlapping hourly slices with built-in retry & `DependsOn` self-dependency (unlike basic Schedule triggers).
- **Event-Based Trigger:** Fires immediately on Event Grid Blob Created events in ADLS Gen2 (use wildcards + suffix filters cleanly).
""",
        "interview_questions": [
            {"question": "When do you choose a Tumbling Window Trigger over a Schedule Trigger in ADF?", "answer": "Use Tumbling Window Triggers when backfilling historical time slices, preserving strict time-window boundaries (`@trigger().outputs.windowStartTime` / `windowEndTime`), enforcing max concurrency (`maxConcurrency=1`), or chaining window-to-window dependencies.", "scenario": "Preventing overlapping hourly SAP extracts during a 3-day outage recovery."},
        ],
    },
    {
        "day": 46,
        "phase": 8,
        "title": "Day 46 – Metadata-Driven ADF Frameworks & Incremental Watermark Pipelines",
        "estimated_minutes": 95,
        "practice_type": "sql",
        "practice_snippet": """-- Simulated ADF Control Table Lookup + Incremental Extract against shared practice data
SELECT MAX(o_orderdate) AS max_watermark, COUNT(*) AS total_orders FROM synapse_dw.orders;""",
        "goals": [
            "Design 1 dynamic metadata-driven pipeline to ingest 200+ tables (vs building 200 static pipelines!)",
            "Implement Watermark Tables in Azure SQL DB with high-watermark Stored Procedure updates",
            "Use `Lookup -> ForEach (isSequential/batchCount) -> Copy/Notebook -> Stored Proc` + ADF Pipeline failure alerts",
        ],
        "lesson_md": """# Day 46 – Metadata-Driven ADF Design (6-Year Senior Standard)

```text
[Azure SQL control.ingestion_config (200 tables)]
       ↓
[1. Lookup Activity (active = 1)] -> array of {schema, table, watermark_col, last_val, load_type}
       ↓
[2. ForEach Activity (batchCount = 10 parallel)]
       ├── [Lookup Max Source Watermark]
       ├── [Copy Activity (Parameterized Dataset + Dynamic SQL)] -> ADLS Bronze (Parquet partitioned by yyyy/MM/dd)
       └── [Stored Procedure Activity] -> Update control.ingestion_config watermark ONLY after Copy succeeds!
```

## Critical Senior Detail: Nested `ForEach` Limitation
ADF does **not** allow a `ForEach` inside another `ForEach` (nor nested inside `If`/`Switch` directly)!
**Workaround:** Call a **Child Pipeline** via **`Execute Pipeline Activity`** for inner loops, OR flatten metadata joins upstream inside the Lookup SQL query.
""",
        "interview_questions": [
            {"question": "How do you parallelize copying 150 SQL Server tables in ADF without building 150 pipelines or hitting memory/SHIR limits?", "answer": "Store table configs and watermarks in a control metadata table, read active rows via `Lookup` (mind the 5,000-row / 4 MB Lookup cap—chunk via SQL batch IDs if needed!), iterate via `ForEach` with a tuned `batchCount` (e.g., 8–16 instead of flooding SHIR), and parameterize Source SQL + ADLS sink paths.", "scenario": "Also watch the 4 MB Lookup output limit when table counts exceed thousands!"},
        ],
    },
    {
        "day": 47,
        "phase": 8,
        "title": "Day 47 – ADF Copy Activity Tuning vs Mapping Data Flows vs Databricks Notebooks",
        "estimated_minutes": 85,
        "practice_type": "pyspark",
        "practice_snippet": """# Compare Spark parallel partition strategy used by Databricks & ADF Copy Parallelism
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("Day47_PartitionedExtract").getOrCreate()
orders = spark.table("demo.practice.orders")
print("Distinct order years:", orders.selectExpr("year(o_orderdate) as yr").distinct().orderBy("yr").collect())
spark.stop()""",
        "goals": [
            "Tune ADF Copy Activity: Data Integration Units (DIUs 2–256), `parallelCopies`, and SQL Partitioned Reads (`Physical partitions` vs `Dynamic range`)",
            "Compare ADF Mapping Data Flows (managed Spark UI/no-code, higher DBU-equivalent cost + TTL cold start) vs Azure Databricks Notebooks",
            "Know ADF cost drivers cleanly for architecture tradeoffs",
        ],
        "lesson_md": """# Day 47 – ADF Performance & Architecture Tradeoffs

## 1. Copy Activity Tuning vs Over-Provisioning
- Increasing DIUs from 4 → 32 does **nothing** if the bottleneck is a single-threaded on-prem SQL Server query! First enable **Partitioned Read (`DynamicRange` on indexed integer/date key)** in Copy Source before cranking up DIUs.
- Keep Staging Blob disabled unless loading PolyBase/Synapse DW with non-native formats.

## 2. Mapping Data Flows vs Azure Databricks
- **Mapping Data Flows:** Visual GUI, runs on Azure-managed Spark behind the scenes, has 3–5 min cluster cold-start unless paying for Integration Runtime **TTL (Time-to-Live)**. Often **2x–3x pricier** and harder to unit-test/Git-diff than code.
- **Azure Databricks:** Full PySpark/SQL/Delta/Unity Catalog control, Photon C++ speedup, easy `pytest` CI/CD—preferred at 6-year enterprise scale!
""",
        "interview_questions": [
            {"question": "When would you still use ADF Mapping Data Flows vs Azure Databricks?", "answer": "Mapping Data Flows suit small SQL-centric BI teams wanting visual zero-code transformations over moderate volumes with strict ADF-only governance; Azure Databricks is superior for large-scale Spark tuning, complex ML/streaming, Photon speed, Unity Catalog, and proper Git/pytest engineering workflows.", "scenario": "Enterprise cost audit comparing ADF TTL Data Flows vs Databricks Job Compute."},
        ],
    },
    {
        "day": 48,
        "phase": 8,
        "title": "Day 48 – Azure Key Vault, Microsoft Purview & Enterprise Data Governance",
        "estimated_minutes": 80,
        "practice_type": "sql",
        "practice_snippet": """-- Practice Row-Level & Dynamic Masking pattern in PostgreSQL / Synapse SQL
SELECT c_custkey,
       CONCAT('***-', RIGHT(c_phone, 4)) AS masked_phone,
       c_mktsegment
FROM synapse_dw.customer
LIMIT 10;""",
        "goals": [
            "Wire Azure Key Vault-backed Secret Scopes in Databricks & Linked Services in ADF",
            "Automate ADLS Gen2 / Synapse / Databricks Lineage scanning & PII Classification in Microsoft Purview",
            "Implement Dynamic Data Masking (DDM), Row-Level Security (RLS) & Tokenization",
        ],
        "lesson_md": """# Day 48 – Governance, Key Vault & PII Protection

## 1. Two Secret Patterns in Azure
- **Azure Key Vault + Managed Identity:** Store API keys, JDBC passwords, and webhooks in Key Vault; configure Key Vault **RBAC (`Key Vault Secrets User`)**; never expose secrets in ADF pipeline outputs (`SecureInput` / `SecureOutput = true`!) or Databricks notebook logs (`dbutils.secrets.get()` auto-redacts `[REDACTED]`).
- **Unity Catalog Governance:** Centralizes table ACLs, **Row Filters (`CREATE FUNCTION`)**, **Column Masks**, and automated column-level lineage across all Databricks workspaces without needing separate Purview agents for Delta tables.
""",
        "interview_questions": [
            {"question": "If someone copies `dbutils.secrets.get('kv-scope', 'api-key')` into a string manipulation and prints `key[::-1]`, what happens in Databricks?", "answer": "Databricks only redacts the exact literal secret string (`[REDACTED]`), NOT reversed/base64-encoded transforms! Never log or write secret derivations—mark `SecureOutput` in ADF and restrict interactive cluster permissions (`No Isolation Shared` -> `Shared/Unity Catalog` clusters).", "scenario": "Security review interview question for senior data engineers."},
        ],
    },
    {
        "day": 49,
        "phase": 8,
        "title": "Day 49 – Azure Event Hubs, Capture & Real-Time Streaming Ingestion",
        "estimated_minutes": 90,
        "practice_type": "streaming",
        "practice_snippet": """# Inspect our live Redpanda (Kafka-protocol compatible with Azure Event Hubs) topics & consumer lag in Streaming tab!
# Event Hubs exposes a Kafka endpoint on port 9093 using SASL_SSL + $ConnectionString or OAuth.""",
        "goals": [
            "Understand Event Hubs Architecture: Throughput Units (TUs) vs Processing Units (PUs), Partitions, Consumer Groups & Offsets",
            "Enable Event Hubs **Capture** to ADLS Gen2 (zero-code Avro/Parquet archival directly to Bronze)",
            "Connect Spark Structured Streaming to Event Hubs via the **Kafka protocol (`kafka` format)** using Entra ID OAuth / SASL",
        ],
        "lesson_md": """# Day 49 – Azure Event Hubs Mastery

## 1. Event Hubs Concepts Mapped to Kafka
- **Event Hub** ≈ Kafka Topic | **Namespace** ≈ Kafka Cluster | **Consumer Group** ≈ Kafka Consumer Group.
- **Partition Key Rule:** Always pick a high-cardinality partition key (e.g., `device_id` or `user_id`) so ordering per entity is preserved without creating a hot single partition!
- **Throughput Units (TUs):** 1 TU = **1 MB/s or 1,000 events/s ingress**, **2 MB/s or 4,096 events/s egress**. Exceeding throws `ServerBusyException` (enable **Auto-Inflate** or Standard/Premium TUs!).

## 2. Senior Tip: Prefer the Kafka Connector Over Legacy `azure-eventhubs-spark`
Event Hubs natively speaks Apache Kafka (`org.apache.spark:spark-sql-kafka-0-10`). Using the native Kafka connector avoids unmaintained Event Hubs Spark library version lag across Spark 3.5 / 4.x upgrades!
""",
        "interview_questions": [
            {"question": "Why can you NOT decrease Event Hub partitions after creation, and how do you handle scaling past 32 partitions?", "answer": "Changing partition count breaks key-hashing continuity for stateful consumers. Choose Standard/Premium Event Hubs cleanly upfront (Premium/Dedicated support higher partition counts) and decouple downstream Spark streaming concurrency via `maxOffsetsPerTrigger`.", "scenario": "Black Friday 10x traffic surge hitting Event Hub ingestion limits."},
        ],
    },
    {
        "day": 50,
        "phase": 8,
        "title": "Day 50 – Azure Synapse Analytics: Dedicated SQL Pools vs Serverless SQL & Lakehouse",
        "estimated_minutes": 95,
        "practice_type": "sql",
        "practice_snippet": """-- Simulate DW Join & Aggregation performance check on shared customer + lineitem data
EXPLAIN ANALYZE
SELECT o.o_orderpriority, COUNT(*) AS line_cnt, ROUND(SUM(l.l_extendedprice), 2) AS gross_rev
FROM synapse_dw.orders o
JOIN synapse_dw.lineitem l ON o.o_orderkey = l.l_orderkey
GROUP BY o.o_orderpriority;""",
        "goals": [
            "Master Dedicated SQL Pool MPP Architecture (Control Node + 60 Compute Distributions)",
            "Choose Distribution Keys accurately: `HASH(join_col)` vs `ROUND_ROBIN` (staging) vs `REPLICATE` (small <2GB dims)",
            "Know Clustered Columnstore Index (CCI) min-row rules (~102,400 rows per distribution × 60 = ~60M rows!) & `COPY INTO`",
            "Compare Serverless SQL Pool (`OPENROWSET` over Parquet/Delta) vs Dedicated Pool vs Fabric/Databricks SQL",
        ],
        "lesson_md": """# Day 50 – Azure Synapse Dedicated vs Serverless SQL Pools

## 1. The Classic Synapse Dedicated Pool Skew/Shuffle Disaster (Must Know for 6-Yr Interviews!)
Dedicated SQL Pool splits data across **60 physical distributions**:
- **`HASH(col)`:** Use on huge Fact tables (>60M rows) using the most common `JOIN`/`GROUP BY` key with **high cardinality and even distribution** (never hash on `date` alone if 80% queries filter one recent month or `NULL`!).
- **`REPLICATE`:** Use ONLY for **small Dimension tables (<2 GB)** so Compute Nodes don't shuffle Data Movement Service (`DMS`) across distributions during joins. Note: first query after write incurs rebuild warm-up!
- **`ROUND_ROBIN`:** Fast landing/staging tables with zero hash skew.

## 2. CCI Small-Table Trap
Never put a small 500k-row table on `CLUSTERED COLUMNSTORE INDEX` across 60 distributions—each distribution only gets ~8k rows (stuck in uncompressed `deltastore` rowgroups instead of compressed columnstore!). Use **`HEAP`** for small staging/dims.
""",
        "interview_questions": [
            {"question": "A Synapse Dedicated SQL Pool query takes 20 minutes despite scaled DWUs. `sys.dm_pdw_request_steps` shows `ShuffleMoveOperation` on step 4. How do you fix it?", "answer": "Data Movement Service (`DMS`) is shuffling huge tables across 60 distributions because the two joined tables have mismatched distribution keys (e.g., Fact hashed on `order_id` joined to Fact2 hashed on `customer_id`, or small Dim wasn't `REPLICATE`d). Align Hash distribution on the primary join key or replicate small dimensions.", "scenario": "6-year Azure Synapse performance troubleshooting classic."},
        ],
    },
]

