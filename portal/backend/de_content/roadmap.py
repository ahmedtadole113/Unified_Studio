"""Unified 60-Day Data Engineering (SQL, PySpark Zero-to-Advance & Azure Cloud 6-Yr Senior) Curriculum & Interview Roadmap Aggregator."""

from typing import Any, Dict, List

from de_content.phase1_sql_modeling import DAYS_1_TO_6
from de_content.phase2_python_spark import DAYS_7_TO_13
from de_content.phase3_lakehouse import DAYS_14_TO_18
from de_content.phase4_orchestration_streaming import DAYS_19_TO_23
from de_content.phase5_dw_ops_finops import DAYS_24_TO_27
from de_content.phase6_system_design_interviews import DAYS_28_TO_30
from de_content.phase7_pyspark_zero_to_adv import DAYS_31_TO_42
from de_content.phase8_azure_foundations import DAYS_43_TO_50
from de_content.phase9_azure_databricks_fabric import DAYS_51_TO_56
from de_content.phase10_senior6yr_interviews import DAYS_57_TO_60

DE_PHASES: List[Dict[str, Any]] = [
    {"id": 1, "days": "1-6", "title": "Phase 1: SQL & Data Modeling Foundations", "goal": "OLTP/OLAP, Columnar, Joins, Windows, Star Schema & SCD2"},
    {"id": 2, "days": "7-13", "title": "Phase 2: Python, PySpark 4.2 & Distributed Compute", "goal": "Spark internals, AQE, Skew, OOMs, Streaming & Data Quality"},
    {"id": 3, "days": "14-18", "title": "Phase 3: Lakehouse, Delta Lake 4.0 & Apache Iceberg", "goal": "Parquet, Medallion, ACID MERGE, Iceberg & CDC"},
    {"id": 4, "days": "19-23", "title": "Phase 4: Orchestration (Airflow) & Streaming (Kafka/RabbitMQ)", "goal": "Idempotent DAGs, Partitions, Lag, DLQs & E2E CDC"},
    {"id": 5, "days": "24-27", "title": "Phase 5: Warehousing, DE Observability, FinOps & Security", "goal": "EXPLAIN ANALYZE, DE+SRE SLOs, FinOps & PII Governance"},
    {"id": 6, "days": "28-30", "title": "Phase 6: System Design & DE Interview Crack Playbook", "goal": "Lambda/Kappa Design, Migrations & Live Coding/RCA Drills"},
    {"id": 7, "days": "31-42", "title": "Phase 7: PySpark Zero-to-Advance (6-Yr Senior)", "goal": "Catalyst/Tungsten, Windows, Joins, Skew/Salting, OOMs, Arrow UDFs, Streaming & Tuning"},
    {"id": 8, "days": "43-50", "title": "Phase 8: Azure Data Cloud & Ingestion Mastery", "goal": "IAM/MI/Private Link, ADLS Gen2 HNS, Dynamic ADF/SHIR, Key Vault, Event Hubs & Synapse"},
    {"id": 9, "days": "51-56", "title": "Phase 9: Azure Databricks, Unity Catalog & Fabric", "goal": "Unity Catalog, Photon, Auto Loader, DLT, Asset Bundles CI/CD, Fabric OneLake & FinOps"},
    {"id": 10, "days": "57-60", "title": "Phase 10: 6-Yr Senior Azure Design & Mock Gauntlet", "goal": "Hybrid/Streaming Blueprints, Production Troubleshooting, DR & Senior Mock Panel"},
]

DE_ROADMAP_DAYS: List[Dict[str, Any]] = (
    DAYS_1_TO_6
    + DAYS_7_TO_13
    + DAYS_14_TO_18
    + DAYS_19_TO_23
    + DAYS_24_TO_27
    + DAYS_28_TO_30
    + DAYS_31_TO_42
    + DAYS_43_TO_50
    + DAYS_51_TO_56
    + DAYS_57_TO_60
)

