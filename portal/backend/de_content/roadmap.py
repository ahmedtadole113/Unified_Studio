"""Unified 30-Day Data Engineering Curriculum & Interview Roadmap Aggregator."""

from typing import Any, Dict, List

from de_content.phase1_sql_modeling import DAYS_1_TO_6
from de_content.phase2_python_spark import DAYS_7_TO_13
from de_content.phase3_lakehouse import DAYS_14_TO_18
from de_content.phase4_orchestration_streaming import DAYS_19_TO_23
from de_content.phase5_dw_ops_finops import DAYS_24_TO_27
from de_content.phase6_system_design_interviews import DAYS_28_TO_30

DE_PHASES: List[Dict[str, Any]] = [
    {"id": 1, "days": "1-6", "title": "Phase 1: SQL & Data Modeling Foundations", "goal": "OLTP/OLAP, Columnar, Joins, Windows, Star Schema & SCD2"},
    {"id": 2, "days": "7-13", "title": "Phase 2: Python, PySpark 4.2 & Distributed Compute", "goal": "Spark internals, AQE, Skew, OOMs, Streaming & Data Quality"},
    {"id": 3, "days": "14-18", "title": "Phase 3: Lakehouse, Delta Lake 4.0 & Apache Iceberg", "goal": "Parquet, Medallion, ACID MERGE, Iceberg & CDC"},
    {"id": 4, "days": "19-23", "title": "Phase 4: Orchestration (Airflow) & Streaming (Kafka/RabbitMQ)", "goal": "Idempotent DAGs, Partitions, Lag, DLQs & E2E CDC"},
    {"id": 5, "days": "24-27", "title": "Phase 5: Warehousing, DE Observability, FinOps & Security", "goal": "EXPLAIN ANALYZE, DE+SRE SLOs, FinOps & PII Governance"},
    {"id": 6, "days": "28-30", "title": "Phase 6: System Design & DE Interview Crack Playbook", "goal": "Lambda/Kappa Design, Migrations & Live Coding/RCA Drills"},
]

DE_ROADMAP_DAYS: List[Dict[str, Any]] = (
    DAYS_1_TO_6
    + DAYS_7_TO_13
    + DAYS_14_TO_18
    + DAYS_19_TO_23
    + DAYS_24_TO_27
    + DAYS_28_TO_30
)

