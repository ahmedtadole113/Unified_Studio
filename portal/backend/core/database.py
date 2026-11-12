"""SQLite WAL persistence layer for SLOs, Incidents, Audit Logs, Runbooks, Postmortems, Toil, and Governance."""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from core.config import settings


def _resolve_db_path() -> str:
    preferred = settings.SRE_DB_PATH
    parent = os.path.dirname(preferred) or "."
    try:
        os.makedirs(parent, exist_ok=True)
        probe = os.path.join(parent, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return preferred
    except OSError:
        os.makedirs("/tmp", exist_ok=True)
        return "/tmp/ues_sre_platform.db"


DB_PATH = _resolve_db_path()
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    """Create unified schema tables and seed baseline SLOs, runbooks, gates, and toil items."""
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS slos (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                service TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT 'sre',
                sli_type TEXT NOT NULL,
                target REAL NOT NULL,
                unit TEXT NOT NULL,
                comparison TEXT NOT NULL DEFAULT 'gte',
                window_days INTEGER NOT NULL DEFAULT 30,
                rolling_window TEXT NOT NULL DEFAULT '1h',
                owner_team TEXT NOT NULL,
                policy TEXT NOT NULL,
                sla_tier TEXT NOT NULL DEFAULT '99.9%',
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS slo_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slo_id TEXT NOT NULL,
                actual_sli REAL,
                error_budget_remaining_pct REAL,
                burn_rate REAL,
                status TEXT NOT NULL,
                recorded_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                domain TEXT NOT NULL,
                source TEXT NOT NULL,
                service_id TEXT,
                pipeline_id TEXT,
                job_id TEXT,
                k8s_namespace TEXT,
                k8s_pod TEXT,
                trace_id TEXT,
                summary TEXT NOT NULL,
                de_perspective TEXT NOT NULL DEFAULT '',
                sre_perspective TEXT NOT NULL DEFAULT '',
                evidence_json TEXT NOT NULL DEFAULT '{}',
                ai_rca TEXT NOT NULL DEFAULT '',
                remediation TEXT NOT NULL DEFAULT '',
                timeline_json TEXT NOT NULL DEFAULT '[]',
                slo_impact_pct REAL NOT NULL DEFAULT 0.0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                resolved_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS runbooks (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                domain TEXT NOT NULL,
                severity TEXT NOT NULL,
                trigger_alert TEXT NOT NULL,
                chaos_scenario TEXT,
                steps_md TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS postmortems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT,
                title TEXT NOT NULL,
                severity TEXT NOT NULL,
                slo_impact TEXT NOT NULL,
                error_budget_consumed_pct REAL NOT NULL DEFAULT 0.0,
                summary TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                contributing_factors TEXT NOT NULL,
                action_items_json TEXT NOT NULL,
                author TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'published',
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS toil_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                frequency_per_week INTEGER NOT NULL,
                minutes_per_occurrence INTEGER NOT NULL,
                automation_candidate TEXT NOT NULL,
                automated INTEGER NOT NULL DEFAULT 0,
                owner TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario TEXT NOT NULL,
                label TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                intensity REAL NOT NULL,
                status TEXT NOT NULL,
                observations TEXT NOT NULL,
                incident_id TEXT,
                started_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS readiness_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                release_tag TEXT NOT NULL,
                decision TEXT NOT NULL,
                eng_signoff TEXT NOT NULL,
                sre_signoff TEXT NOT NULL,
                security_signoff TEXT NOT NULL,
                checks_json TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ssdlc_gates (
                id TEXT PRIMARY KEY,
                stage_order INTEGER NOT NULL,
                stage_name TEXT NOT NULL,
                control_objective TEXT NOT NULL,
                owner_role TEXT NOT NULL,
                status TEXT NOT NULL,
                evidence TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cost_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                service TEXT NOT NULL,
                monthly_budget_usd REAL NOT NULL,
                current_run_rate_usd REAL NOT NULL,
                optimization_note TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS study_progress (
                day INTEGER PRIMARY KEY,
                completed INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                detail TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'success',
                created_at INTEGER NOT NULL
            );
            """
        )
        _seed_defaults(conn)


def _seed_defaults(conn: sqlite3.Connection) -> None:
    now = int(time.time())

    # Seed all 9 enterprise SLO types requested in Section 7
    default_slos = [
        ("slo-api-availability", "Control Plane API Availability", "portal-backend", "platform", "api_availability", 99.9, "%", "gte", 30, "1h", "Platform SRE", "Freeze non-reliability changes if 5m burn > 14.4x or remaining budget < 15%.", "99.95%", now),
        ("slo-app-availability", "Application Endpoint Availability", "simulated_app", "sre", "app_availability", 99.5, "%", "gte", 30, "5m", "App Reliability SRE", "Page on-call if 5xx error ratio exceeds 0.5% over 5m/1h multi-window.", "99.5%", now),
        ("slo-spark-success", "Spark Job Success Rate", "spark-processing", "data_engineering", "spark_job_success", 98.0, "%", "gte", 30, "24h", "Data Platform Eng", "Investigate executor OOMs or skew if Spark batch/streaming job success drops below 98%.", "98.0%", now),
        ("slo-airflow-success", "Airflow DAG Success Rate", "airflow-webserver", "data_engineering", "airflow_dag_success", 99.0, "%", "gte", 30, "24h", "Data Orchestration", "Trigger DE + SRE correlation incident on consecutive DAG task failures.", "99.0%", now),
        ("slo-data-freshness", "Lakehouse Gold Data Freshness", "minio", "data_engineering", "data_freshness", 1440.0, "min", "lte", 7, "24h", "Lakehouse Team", "Alert if Gold/Warehouse datasets exceed freshness SLA threshold.", "< 24h", now),
        ("slo-pipeline-latency", "Pipeline Completion Latency", "airflow-scheduler", "data_engineering", "pipeline_latency", 300.0, "sec", "lte", 30, "24h", "Data Eng + SRE", "Investigate Spark shuffle or DB lock contention if DAG duration exceeds 300s.", "< 5m", now),
        ("slo-kafka-lag", "Kafka / Redpanda Consumer Lag", "redpanda", "streaming", "kafka_consumer_lag", 500.0, "msgs", "lte", 7, "1h", "Streaming SRE", "Scale consumer partitions or inspect backpressure when lag > 500 messages.", "< 500 msgs", now),
        ("slo-db-availability", "PostgreSQL DW Availability", "postgres-dw", "data_engineering", "db_availability", 99.95, "%", "gte", 30, "1h", "Database SRE", "Immediate SEV-1 escalation on DW connection pool exhaustion or probe failure.", "99.95%", now),
        ("slo-response-time", "Service p99 Response Latency", "portal-backend", "platform", "service_response_time", 350.0, "ms", "lte", 30, "5m", "Core API SRE", "Trigger canary rollback or load-shedding if API/app p99 latency > 350ms.", "< 350ms", now),
    ]
    for slo in default_slos:
        conn.execute(
            """
            INSERT OR IGNORE INTO slos
            (id, name, service, domain, sli_type, target, unit, comparison, window_days, rolling_window, owner_team, policy, sla_tier, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            slo,
        )

    if conn.execute("SELECT COUNT(*) FROM runbooks").fetchone()[0] == 0:
        runbooks = [
            ("cpu-saturation", "CPU Saturation & Runaway Worker Mitigation", "infrastructure", "SEV-2", "HighContainerCPU", "high_cpu_usage",
             "### Triage\n1. Inspect `ues_container_cpu_percent` and `app_cpu_usage_percent` in Observability.\n2. Identify top CPU-consuming container or Spark executor.\n\n### Mitigation\n1. Throttle bursty producers or pause non-critical Spark jobs.\n2. Enforce CPU quota limits and restart runaway workers.\n\n### Follow-up\n- Review M4 8GB profile budgets."),
            ("memory-leak-oom", "Memory Pressure & OOMKill Prevention", "infrastructure", "SEV-1", "HighContainerMemory", "high_memory_usage",
             "### Triage\n1. Check Docker container memory % and K8s `OOMKilled` events.\n2. Correlate with Spark driver/executor heap settings in `spark-defaults.conf`.\n\n### Mitigation\n1. Stop idle heavy services via FinOps Profile Advisor.\n2. Restart leaking service and cap JVM/buffer limits."),
            ("db-pool-exhaustion", "PostgreSQL DW Connection Pool Exhaustion", "data_engineering", "SEV-1", "PostgresConnectionSaturation", "exhaust_postgres_connections",
             "### Triage\n1. Query `pg_stat_activity` for idle-in-transaction or blocked connections.\n2. Check Airflow DAGs (`project1`, `project3`) for unclosed cursors.\n\n### Mitigation\n1. Terminate idle zombie sessions (`pg_terminate_backend`).\n2. Enable statement timeouts and connection pooling."),
            ("airflow-spark-cascade", "Airflow DAG & Spark Executor Cascade Failure", "data_engineering", "SEV-1", "AirflowDAGFailure / SparkJobFailure", "kill_spark_executor",
             "### Triage\n1. Inspect failed Airflow task logs and Spark Master/App UI.\n2. Check Infrastructure view for container/K8s pod restarts during task window.\n\n### Mitigation\n1. Restore `airflow-scheduler` or `spark-processing` service.\n2. Re-run failed DAG task after confirming MinIO & Postgres health."),
            ("kafka-consumer-lag", "Redpanda / Kafka Consumer Lag Surge", "streaming", "SEV-2", "KafkaConsumerLagHigh", "kafka_consumer_lag",
             "### Triage\n1. Inspect consumer group offsets & lag in Streaming -> Kafka.\n2. Check downstream Spark Structured Streaming or AIOps consumer health.\n\n### Mitigation\n1. Resume stalled consumers or increase consumer parallelism.\n2. Verify Redpanda disk/memory headroom."),
            ("rabbitmq-dlq-backlog", "RabbitMQ Queue & Dead-Letter Backlog", "streaming", "SEV-2", "RabbitMQBacklog", "fill_rabbitmq_queue",
             "### Triage\n1. Inspect queue depth, consumer count, and DLQ counts in Streaming -> RabbitMQ.\n2. Check worker error logs in Loki.\n\n### Mitigation\n1. Restore downstream consumers or replay/purge poison messages in DLQ."),
            ("k8s-crashloop", "Kubernetes Pod CrashLoopBackOff & Scheduling Failure", "kubernetes", "SEV-1", "K8sPodCrashLoop", "k8s_crashloopbackoff",
             "### Triage\n1. Run `kubectl describe pod` / check K8s Events & Pod logs in Infrastructure -> Kubernetes.\n2. Inspect exit code (137 = OOMKilled, 1 = app/config error).\n\n### Mitigation\n1. Fix missing ConfigMap/Secret or raise memory limits.\n2. Delete failed chaos pod or trigger rollout restart."),
            ("http-500-burst", "HTTP 5xx Error Budget Burn Response", "availability", "SEV-1", "FastErrorBudgetBurn", "error_burst",
             "### Triage\n1. Check remaining error budget and 5m/1h burn rate in SRE -> Error Budgets.\n2. Inspect recent API errors and distributed traces.\n\n### Mitigation\n1. Enforce release freeze per Error Budget policy.\n2. Roll back recent deployment or isolate failing upstream."),
            ("tail-latency-slo", "Tail Latency (p99) & Network Degradation", "performance", "SEV-2", "LatencySLOBreach", "network_latency",
             "### Triage\n1. Inspect p50 vs p99 latency and Tempo/OTel trace waterfall.\n2. Identify slow downstream DB, MinIO, or network hop.\n\n### Mitigation\n1. Clear artificial latency/chaos injection or tune timeouts & circuit breakers."),
            ("ai-model-drift", "AI Model Drift & Train/Serve Skew", "ai_reliability", "SEV-2", "AIModelDriftDetected", "ai_drift",
             "### Triage\n1. Inspect drift & train/serve skew metrics.\n2. Compare online feature distribution vs baseline.\n\n### Mitigation\n1. Fall back to deterministic rules and re-validate SSDLC eval gates."),
        ]
        conn.executemany(
            "INSERT INTO runbooks (slug, title, domain, severity, trigger_alert, chaos_scenario, steps_md, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(s, t, d, sev, al, sc, md, now) for (s, t, d, sev, al, sc, md) in runbooks],
        )

    if conn.execute("SELECT COUNT(*) FROM postmortems").fetchone()[0] == 0:
        conn.execute(
            """
            INSERT INTO postmortems
            (title, severity, slo_impact, error_budget_consumed_pct, summary, root_cause, contributing_factors, action_items_json, author, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Spark Submitter Ivy Cache Startup Failure on Non-Root Image",
                "SEV-2",
                "Delayed streaming anomaly pipeline startup (100% pipeline delay during boot)",
                1.4,
                "Spark streaming job exited during Ivy dependency resolution when HOME pointed to a non-writable directory.",
                "Non-root container UID lacked writable HOME/.ivy2 directory.",
                json.dumps(["Missing readiness gate for Spark streaming app registration.", "Implicit reliance on container HOME for Ivy cache."]),
                json.dumps([
                    {"task": "Pin writable /tmp/.ivy2 cache and unify Spark inside profile-data-engineering", "owner": "Platform SRE", "status": "done"},
                    {"task": "Add Spark job success SLO to Unified Engineering Studio", "owner": "Data + SRE", "status": "done"},
                ]),
                "Unified SRE + DE Team",
                "published",
                now - 3600,
            ),
        )

    if conn.execute("SELECT COUNT(*) FROM toil_items").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO toil_items (title, category, frequency_per_week, minutes_per_occurrence, automation_candidate, automated, owner, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("Manual PromQL alert triage & runbook lookup", "Incident Triage", 8, 15, "Auto-enrich anomalies via FAISS playbook matcher", 1, "AIOps Agent", now),
                ("Airflow + Spark + K8s cross-domain failure correlation", "Pipeline Reliability", 6, 25, "Automated DE<->SRE Correlation Engine", 1, "Unified Control Plane", now),
                ("Pre-release readiness checklist verification", "Release Gate", 4, 20, "Automated SLO + Drift Admission Gate API", 1, "Platform SRE", now),
                ("Periodic chaos resilience & recovery drills", "Resilience Testing", 5, 20, "One-click controlled chaos runner with auto-recovery", 0, "Reliability Eng", now),
                ("Weekly container RAM budget & idle service pruning", "FinOps", 3, 30, "M4 8GB Profile Advisor & idle container detector", 0, "FinOps Eng", now),
            ],
        )

    if conn.execute("SELECT COUNT(*) FROM ssdlc_gates").fetchone()[0] == 0:
        gates = [
            ("ssdlc-1", 1, "1. Discovery & Risk Threat Model", "Co-define DE & SRE SLOs, RBAC, and secrets hygiene before build.", "Product + Security + SRE", "pass", "9 SLOs codified in SQLite; PBKDF2 + Bearer Auth active"),
            ("ssdlc-2", 2, "2. Data Quality & AI Eval Parity", "Verify Medallion data quality rules and AI feature parity (skew < 0.50).", "Data Eng + ML Eng", "pass", "TPC-H data quality checks & drift metrics active"),
            ("ssdlc-3", 3, "3. Resilience & Chaos Verification", "Run controlled infrastructure and pipeline failure simulations with recovery.", "Platform SRE", "warn", "Execute Chaos Lab scenarios to attach fresh evidence"),
            ("ssdlc-4", 4, "4. Error-Budget & Admission Gate", "Segregation-of-duties release sign-off gated on live error budgets.", "Embedded SRE + Security", "pass", "Automated admission gate evaluated against live SLIs"),
            ("ssdlc-5", 5, "5. Unified Observability & Correlation", "Correlate Airflow/Spark failures with Docker/K8s/Prometheus/Loki/Tempo telemetry.", "DE + AIOps Ops", "pass", "Service Registry + Prometheus + Loki + Tempo + Correlation Engine live"),
            ("ssdlc-6", 6, "6. Blameless Learning & FinOps Payoff", "Convert incidents into postmortems, runbooks, and M4 8GB resource efficiency.", "Eng + SRE + FinOps", "pass", "Postmortem, runbook, and FinOps trackers live"),
        ]
        conn.executemany(
            "INSERT INTO ssdlc_gates (id, stage_order, stage_name, control_objective, owner_role, status, evidence, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(g[0], g[1], g[2], g[3], g[4], g[5], g[6], now) for g in gates],
        )

    if conn.execute("SELECT COUNT(*) FROM cost_items").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO cost_items (category, service, monthly_budget_usd, current_run_rate_usd, optimization_note, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Compute (Unified Containers)", "Redpanda + Spark + Airflow + Portal", 950.0, 620.0, "Eliminated Confluent Kafka & duplicate Spark 3.5 cluster (-4.5 GB RAM).", now),
                ("Observability Stack", "Prometheus + Grafana + Loki + Tempo", 450.0, 260.0, "Profiled observability with 15s scrape & 128M-256M container caps.", now),
                ("Storage & Warehouse", "MinIO Lakehouse + PostgreSQL DW", 300.0, 185.0, "Shared PostgreSQL DW + MinIO S3 buckets without service duplication.", now),
            ],
        )


def _rows_to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]


# --- Audit Logs ---
def insert_audit_log(username: str, role: str, action: str, resource: str, detail: str, status: str = "success") -> None:
    now = int(time.time())
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO audit_logs (username, role, action, resource, detail, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (username, role, action, resource, detail[:1000], status, now),
        )


def get_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall())


# --- SLOs & History ---
def get_slos() -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM slos ORDER BY domain, id").fetchall())


def update_slo(slo_id: str, target: float, window_days: int, policy: str, rolling_window: Optional[str] = None) -> Optional[Dict[str, Any]]:
    now = int(time.time())
    with _lock, _connect() as conn:
        if rolling_window:
            cur = conn.execute(
                "UPDATE slos SET target = ?, window_days = ?, policy = ?, rolling_window = ?, updated_at = ? WHERE id = ?",
                (float(target), int(window_days), policy, rolling_window, now, slo_id),
            )
        else:
            cur = conn.execute(
                "UPDATE slos SET target = ?, window_days = ?, policy = ?, updated_at = ? WHERE id = ?",
                (float(target), int(window_days), policy, now, slo_id),
            )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM slos WHERE id = ?", (slo_id,)).fetchone()
        return dict(row) if row else None


def record_slo_snapshot(slo_id: str, actual_sli: Optional[float], remaining_pct: float, burn_rate: float, status: str) -> None:
    now = int(time.time())
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO slo_history (slo_id, actual_sli, error_budget_remaining_pct, burn_rate, status, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            (slo_id, actual_sli, remaining_pct, burn_rate, status, now),
        )
        # Keep bounded history (~2000 rows per SLO)
        conn.execute(
            "DELETE FROM slo_history WHERE id NOT IN (SELECT id FROM slo_history ORDER BY recorded_at DESC LIMIT 5000)"
        )


def get_slo_history(slo_id: Optional[str] = None, limit: int = 60) -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        if slo_id:
            rows = conn.execute(
                "SELECT * FROM slo_history WHERE slo_id = ? ORDER BY recorded_at DESC LIMIT ?",
                (slo_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM slo_history ORDER BY recorded_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return list(reversed(_rows_to_dicts(rows)))


# --- Incidents ---
def _deserialize_incident(row: Dict[str, Any]) -> Dict[str, Any]:
    row["evidence"] = json.loads(row.pop("evidence_json", "{}") or "{}")
    row["timeline"] = json.loads(row.pop("timeline_json", "[]") or "[]")
    return row


def upsert_incident(inc: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    with _lock, _connect() as conn:
        existing = conn.execute("SELECT * FROM incidents WHERE id = ?", (inc["id"],)).fetchone()
        if existing:
            ex_timeline = json.loads(existing["timeline_json"] or "[]")
            new_events = inc.get("timeline_append", [])
            merged_timeline = (ex_timeline + new_events)[-50:]
            conn.execute(
                """
                UPDATE incidents SET
                    title = ?, severity = ?, status = ?, domain = ?, source = ?,
                    service_id = ?, pipeline_id = ?, job_id = ?, k8s_namespace = ?, k8s_pod = ?, trace_id = ?,
                    summary = ?, de_perspective = ?, sre_perspective = ?, evidence_json = ?,
                    ai_rca = ?, remediation = ?, timeline_json = ?, slo_impact_pct = ?, updated_at = ?,
                    resolved_at = ?
                WHERE id = ?
                """,
                (
                    inc.get("title", existing["title"]),
                    inc.get("severity", existing["severity"]),
                    inc.get("status", existing["status"]),
                    inc.get("domain", existing["domain"]),
                    inc.get("source", existing["source"]),
                    inc.get("service_id", existing["service_id"]),
                    inc.get("pipeline_id", existing["pipeline_id"]),
                    inc.get("job_id", existing["job_id"]),
                    inc.get("k8s_namespace", existing["k8s_namespace"]),
                    inc.get("k8s_pod", existing["k8s_pod"]),
                    inc.get("trace_id", existing["trace_id"]),
                    inc.get("summary", existing["summary"]),
                    inc.get("de_perspective", existing["de_perspective"]),
                    inc.get("sre_perspective", existing["sre_perspective"]),
                    json.dumps(inc.get("evidence", json.loads(existing["evidence_json"] or "{}"))),
                    inc.get("ai_rca", existing["ai_rca"]),
                    inc.get("remediation", existing["remediation"]),
                    json.dumps(merged_timeline),
                    float(inc.get("slo_impact_pct", existing["slo_impact_pct"])),
                    now,
                    inc.get("resolved_at", existing["resolved_at"]),
                    inc["id"],
                ),
            )
        else:
            timeline = inc.get("timeline", [{"ts": now, "actor": inc.get("source", "system"), "event": "Incident opened"}])
            conn.execute(
                """
                INSERT INTO incidents
                (id, title, severity, status, domain, source, service_id, pipeline_id, job_id,
                 k8s_namespace, k8s_pod, trace_id, summary, de_perspective, sre_perspective,
                 evidence_json, ai_rca, remediation, timeline_json, slo_impact_pct, created_at, updated_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inc["id"],
                    inc["title"],
                    inc.get("severity", "SEV-2"),
                    inc.get("status", "open"),
                    inc.get("domain", "correlated"),
                    inc.get("source", "correlation_engine"),
                    inc.get("service_id"),
                    inc.get("pipeline_id"),
                    inc.get("job_id"),
                    inc.get("k8s_namespace"),
                    inc.get("k8s_pod"),
                    inc.get("trace_id"),
                    inc.get("summary", ""),
                    inc.get("de_perspective", ""),
                    inc.get("sre_perspective", ""),
                    json.dumps(inc.get("evidence", {})),
                    inc.get("ai_rca", ""),
                    inc.get("remediation", ""),
                    json.dumps(timeline),
                    float(inc.get("slo_impact_pct", 0.0)),
                    now,
                    now,
                    inc.get("resolved_at"),
                ),
            )
        row = dict(conn.execute("SELECT * FROM incidents WHERE id = ?", (inc["id"],)).fetchone())
        return _deserialize_incident(row)


def get_incidents(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        if status and status != "all":
            rows = conn.execute(
                "SELECT * FROM incidents WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM incidents ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [_deserialize_incident(dict(r)) for r in rows]


def get_incident(inc_id: str) -> Optional[Dict[str, Any]]:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        return _deserialize_incident(dict(row)) if row else None


def update_incident_status(inc_id: str, status: str, note: str = "", actor: str = "operator") -> Optional[Dict[str, Any]]:
    now = int(time.time())
    with _lock, _connect() as conn:
        existing = conn.execute("SELECT * FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        if not existing:
            return None
        timeline = json.loads(existing["timeline_json"] or "[]")
        timeline.append({"ts": now, "actor": actor, "event": f"Status -> {status}" + (f": {note}" if note else "")})
        resolved_at = now if status == "resolved" else existing["resolved_at"]
        conn.execute(
            "UPDATE incidents SET status = ?, timeline_json = ?, updated_at = ?, resolved_at = ? WHERE id = ?",
            (status, json.dumps(timeline[-50:]), now, resolved_at, inc_id),
        )
        row = dict(conn.execute("SELECT * FROM incidents WHERE id = ?", (inc_id,)).fetchone())
        return _deserialize_incident(row)


# --- Runbooks, Postmortems, Toil, Experiments, Readiness, SSDLC, Cost, Study ---
def get_runbooks() -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM runbooks ORDER BY domain, title").fetchall())


def upsert_runbook(data: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT INTO runbooks (slug, title, domain, severity, trigger_alert, chaos_scenario, steps_md, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title=excluded.title, domain=excluded.domain, severity=excluded.severity,
                trigger_alert=excluded.trigger_alert, chaos_scenario=excluded.chaos_scenario,
                steps_md=excluded.steps_md, updated_at=excluded.updated_at
            """,
            (data["slug"], data["title"], data.get("domain", "infrastructure"), data.get("severity", "SEV-2"),
             data.get("trigger_alert", "CustomAlert"), data.get("chaos_scenario") or "", data["steps_md"], now),
        )
        return dict(conn.execute("SELECT * FROM runbooks WHERE slug = ?", (data["slug"],)).fetchone())


def get_postmortems() -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        rows = _rows_to_dicts(conn.execute("SELECT * FROM postmortems ORDER BY created_at DESC").fetchall())
        for r in rows:
            r["contributing_factors"] = json.loads(r.get("contributing_factors") or "[]")
            r["action_items"] = json.loads(r.get("action_items_json") or "[]")
        return rows


def create_postmortem(data: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    with _lock, _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO postmortems
            (incident_id, title, severity, slo_impact, error_budget_consumed_pct, summary, root_cause, contributing_factors, action_items_json, author, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (data.get("incident_id"), data["title"], data.get("severity", "SEV-2"),
             data.get("slo_impact", "Minor latency impact"), float(data.get("error_budget_consumed_pct", 0.5)),
             data["summary"], data["root_cause"], json.dumps(data.get("contributing_factors", [])),
             json.dumps(data.get("action_items", [])), data.get("author", "SRE Practitioner"),
             data.get("status", "published"), now),
        )
        row = dict(conn.execute("SELECT * FROM postmortems WHERE id = ?", (cur.lastrowid,)).fetchone())
        row["contributing_factors"] = json.loads(row["contributing_factors"])
        row["action_items"] = json.loads(row["action_items_json"])
        return row


def get_toil_items() -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM toil_items ORDER BY automated ASC, (frequency_per_week * minutes_per_occurrence) DESC").fetchall())


def create_toil_item(data: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO toil_items (title, category, frequency_per_week, minutes_per_occurrence, automation_candidate, automated, owner, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (data["title"], data.get("category", "Operations"), int(data.get("frequency_per_week", 1)),
             int(data.get("minutes_per_occurrence", 15)), data.get("automation_candidate", "Script automation"),
             1 if data.get("automated") else 0, data.get("owner", "SRE"), now),
        )
        return dict(conn.execute("SELECT * FROM toil_items WHERE id = ?", (cur.lastrowid,)).fetchone())


def toggle_toil_automated(item_id: int) -> Optional[Dict[str, Any]]:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM toil_items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return None
        new_val = 0 if row["automated"] else 1
        conn.execute("UPDATE toil_items SET automated = ? WHERE id = ?", (new_val, item_id))
        return dict(conn.execute("SELECT * FROM toil_items WHERE id = ?", (item_id,)).fetchone())


def log_experiment(scenario: str, label: str, hypothesis: str, duration_seconds: int, intensity: float,
                   status: str = "running", observations: str = "", incident_id: Optional[str] = None) -> Dict[str, Any]:
    now = int(time.time())
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO experiments (scenario, label, hypothesis, duration_seconds, intensity, status, observations, incident_id, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (scenario, label, hypothesis, int(duration_seconds), float(intensity), status, observations, incident_id, now),
        )
        return dict(conn.execute("SELECT * FROM experiments WHERE id = ?", (cur.lastrowid,)).fetchone())


def get_experiments(limit: int = 25) -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM experiments ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall())


def update_experiment(exp_id: int, status: str, observations: str) -> Optional[Dict[str, Any]]:
    with _lock, _connect() as conn:
        cur = conn.execute("UPDATE experiments SET status = ?, observations = ? WHERE id = ?", (status, observations, exp_id))
        if cur.rowcount == 0:
            return None
        return dict(conn.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone())


def create_readiness_review(data: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO readiness_reviews (release_tag, decision, eng_signoff, sre_signoff, security_signoff, checks_json, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (data["release_tag"], data["decision"], data.get("eng_signoff", "pending"),
             data.get("sre_signoff", "pending"), data.get("security_signoff", "pending"),
             json.dumps(data.get("checks", [])), data.get("notes", ""), now),
        )
        row = dict(conn.execute("SELECT * FROM readiness_reviews WHERE id = ?", (cur.lastrowid,)).fetchone())
        row["checks"] = json.loads(row["checks_json"])
        return row


def get_readiness_reviews(limit: int = 15) -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        rows = _rows_to_dicts(conn.execute("SELECT * FROM readiness_reviews ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall())
        for r in rows:
            r["checks"] = json.loads(r.get("checks_json") or "[]")
        return rows


def get_ssdlc_gates() -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM ssdlc_gates ORDER BY stage_order ASC").fetchall())


def update_ssdlc_gate(gate_id: str, status: str, evidence: str) -> Optional[Dict[str, Any]]:
    now = int(time.time())
    with _lock, _connect() as conn:
        cur = conn.execute("UPDATE ssdlc_gates SET status = ?, evidence = ?, updated_at = ? WHERE id = ?", (status, evidence, now, gate_id))
        if cur.rowcount == 0:
            return None
        return dict(conn.execute("SELECT * FROM ssdlc_gates WHERE id = ?", (gate_id,)).fetchone())


def get_cost_items() -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM cost_items ORDER BY id ASC").fetchall())


def get_study_progress() -> Dict[int, Dict[str, Any]]:
    with _lock, _connect() as conn:
        rows = _rows_to_dicts(conn.execute("SELECT * FROM study_progress ORDER BY day ASC").fetchall())
        return {int(r["day"]): {"day": int(r["day"]), "completed": bool(r["completed"]), "notes": r["notes"], "updated_at": r["updated_at"]} for r in rows}


def upsert_study_progress(day: int, completed: bool, notes: str) -> Dict[str, Any]:
    now = int(time.time())
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT INTO study_progress (day, completed, notes, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(day) DO UPDATE SET
                completed=excluded.completed, notes=excluded.notes, updated_at=excluded.updated_at
            """,
            (int(day), 1 if completed else 0, notes or "", now),
        )
        row = dict(conn.execute("SELECT * FROM study_progress WHERE day = ?", (int(day),)).fetchone())
        row["completed"] = bool(row["completed"])
        return row

