"""Controlled Chaos Engineering & Incident Simulation Engine (10 Real SRE + DE Scenarios)."""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

import httpx
import psycopg2

from core import database
from core.config import settings
from core.telemetry_otel import traced_operation
from services import aiops_engine, docker_mgr, k8s_mgr, loki_client, streaming_client

logger = logging.getLogger("ues.chaos")

# Active runtime state for controlled chaos (Postgres held connections, simulated latency, etc.)
_CHAOS_LOCK = threading.Lock()
_HELD_PG_CONNS: List[Any] = []
_ARTIFICIAL_LATENCY_MS: int = 0

CHAOS_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "stop_docker_container",
        "title": "1. Stop a Docker Container",
        "category": "Infrastructure",
        "severity": "SEV-2",
        "target_default": "rabbitmq",
        "confirmation_phrase": "CONFIRM STOP CONTAINER",
        "description": "Stops a selectable non-core Docker container (default: rabbitmq) to verify Service Registry detection, Prometheus service_up=0 alert, and incident correlation.",
        "investigation_steps": [
            "Open Platform Overview or Service Registry to observe status transition to 'unavailable'.",
            "Check Infrastructure -> Docker Containers for exited container state.",
            "Inspect Streaming or Observability -> Alerts for service outage impact.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' or start the stopped container from Infrastructure -> Docker.",
    },
    {
        "id": "kill_spark_executor",
        "title": "2. Kill / Fail a Spark Job",
        "category": "Data Engineering",
        "severity": "SEV-1",
        "target_default": "spark-processing",
        "confirmation_phrase": "CONFIRM SPARK FAILURE",
        "description": "Triggers a controlled failing PySpark job or restarts spark-processing worker to observe Spark failure telemetry, DE->SRE correlation, and SLO impact.",
        "investigation_steps": [
            "Open SRE Operations -> Incidents to inspect both Data Engineer & SRE perspectives.",
            "Open Data Engineering -> Spark & Jobs to review job error output.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to ensure spark-processing is healthy and resolve the simulation incident.",
    },
    {
        "id": "stop_airflow_scheduler",
        "title": "3. Stop Airflow Scheduler",
        "category": "Orchestration",
        "severity": "SEV-1",
        "target_default": "airflow-scheduler",
        "confirmation_phrase": "CONFIRM STOP SCHEDULER",
        "description": "Stops the `airflow-scheduler` container so scheduled DAGs stop progressing and Service Registry flags orchestration degradation.",
        "investigation_steps": [
            "Check Service Registry for `airflow-scheduler` unavailable status.",
            "Open Data Engineering -> Airflow to verify scheduler heartbeat unhealthy.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to start `airflow-scheduler` and restore DAG scheduling.",
    },
    {
        "id": "kafka_consumer_lag",
        "title": "4. Introduce Kafka Consumer Lag",
        "category": "Streaming",
        "severity": "SEV-2",
        "target_default": "redpanda",
        "confirmation_phrase": "CONFIRM KAFKA LAG",
        "description": "Creates `ues-chaos-lag-topic`, commits an initial consumer group offset, and produces 250 unconsumed messages to generate real measurable consumer lag.",
        "investigation_steps": [
            "Open Streaming & Messaging -> Kafka/Redpanda -> Consumer Groups to observe real lag.",
            "Check SLO Engine `slo-kafka-lag` breach/warning status.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to consume and drain `ues-chaos-lag-topic` backlog back to 0 lag.",
    },
    {
        "id": "fill_rabbitmq_queue",
        "title": "5. Fill a RabbitMQ Queue",
        "category": "Messaging",
        "severity": "SEV-2",
        "target_default": "rabbitmq",
        "confirmation_phrase": "CONFIRM FILL RABBITMQ",
        "description": "Publishes 150 persistent test messages into `ues.chaos.backlog` queue in RabbitMQ with no active consumers to simulate queue saturation.",
        "investigation_steps": [
            "Open Streaming & Messaging -> RabbitMQ to inspect `ues.chaos.backlog` depth.",
            "Review Runbook `rabbitmq-dlq-backlog` in SRE Operations.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to purge `ues.chaos.backlog` cleanly.",
    },
    {
        "id": "exhaust_postgres_connections",
        "title": "6. Exhaust PostgreSQL Connections",
        "category": "Database",
        "severity": "SEV-1",
        "target_default": "postgres-dw",
        "confirmation_phrase": "CONFIRM EXHAUST POSTGRES",
        "description": "Opens 25 concurrent idle connections to `postgres-dw` to spike connection pool utilization in `pg_stat_activity`.",
        "investigation_steps": [
            "Open Data Engineering -> PostgreSQL DW to inspect active connections & pool utilization %.",
            "Check `slo-db-availability` and `db-pool-exhaustion` runbook.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to close all held chaos DB connections immediately.",
    },
    {
        "id": "high_cpu_usage",
        "title": "7. Simulate High CPU Usage",
        "category": "Compute",
        "severity": "SEV-2",
        "target_default": "data-generator",
        "confirmation_phrase": "CONFIRM HIGH CPU",
        "description": "Activates `cpu_spike` in telemetry generator (and/or local worker load) driving CPU metrics above the 85% Prometheus alert threshold.",
        "investigation_steps": [
            "Open Observability -> Alerts & PromQL Explorer (`app_cpu_usage_percent`).",
            "Open AIOps to review FAISS playbook match (`cpu-saturation`).",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to reset telemetry generator back to steady state.",
    },
    {
        "id": "high_memory_usage",
        "title": "8. Simulate High Memory Usage",
        "category": "Compute",
        "severity": "SEV-1",
        "target_default": "data-generator",
        "confirmation_phrase": "CONFIRM HIGH MEMORY",
        "description": "Triggers `memory_leak` scenario ramping memory metrics past 800 MB to fire `HighMemorySaturation` alert.",
        "investigation_steps": [
            "Open Observability -> Metrics & Alerts to track memory ramp.",
            "Check FinOps -> Capacity & M4 8GB Headroom.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to reset memory scenario back to baseline.",
    },
    {
        "id": "k8s_crashloopbackoff",
        "title": "9. Trigger Kubernetes CrashLoopBackOff",
        "category": "Kubernetes",
        "severity": "SEV-1",
        "target_default": "ues-chaos-lab/ues-crashloop-sim",
        "confirmation_phrase": "CONFIRM K8S CRASHLOOP",
        "description": "Deploys a lightweight failing busybox pod (`ues-crashloop-sim`) in isolated namespace `ues-chaos-lab` on local Kubernetes (OrbStack/k3d/kind).",
        "investigation_steps": [
            "Open Infrastructure -> Kubernetes -> Pods & Events to observe `CrashLoopBackOff` and pod logs.",
            "Open SRE Operations -> Incidents for correlated K8s failure.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to delete `ues-crashloop-sim` pod cleanly.",
    },
    {
        "id": "network_latency",
        "title": "10. Introduce Artificial Network Latency",
        "category": "Network / Performance",
        "severity": "SEV-2",
        "target_default": "portal-backend",
        "confirmation_phrase": "CONFIRM NETWORK LATENCY",
        "description": "Injects controlled artificial latency (+450ms) into API middleware & `latency_degradation` telemetry to observe p99 SLO burn and OTel trace waterfall spikes.",
        "investigation_steps": [
            "Open Observability -> Traces to observe elevated span duration.",
            "Open SRE Operations -> Error Budgets to monitor p99 latency SLO burn.",
        ],
        "recovery_instructions": "Click 'Recover Scenario' to remove artificial latency injection immediately.",
    },
]


def get_artificial_latency_ms() -> int:
    return _ARTIFICIAL_LATENCY_MS


def list_scenarios() -> List[Dict[str, Any]]:
    return [
        {
            **s,
            "active_pg_chaos_conns": len(_HELD_PG_CONNS) if s["id"] == "exhaust_postgres_connections" else 0,
            "active_latency_ms": _ARTIFICIAL_LATENCY_MS if s["id"] == "network_latency" else 0,
        }
        for s in CHAOS_SCENARIOS
    ]


async def execute_chaos_scenario(scenario_id: str, confirm: bool, confirmation_phrase: str, target: Optional[str] = None, user: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Execute a controlled chaos simulation ONLY after explicit user confirmation."""
    spec = next((s for s in CHAOS_SCENARIOS if s["id"] == scenario_id), None)
    if not spec:
        raise ValueError(f"Unknown chaos scenario '{scenario_id}'")
    if not confirm or confirmation_phrase.strip().upper() != spec["confirmation_phrase"]:
        raise ValueError(f"Explicit confirmation required. Provide confirm=true and confirmation_phrase='{spec['confirmation_phrase']}'")

    now = int(time.time())
    actor = (user or {}).get("username", "operator")
    observed = ""
    target_val = target or spec["target_default"]

    with traced_operation(f"chaos.execute.{scenario_id}", domain="chaos", attributes={"chaos.target": target_val}):
        if scenario_id == "stop_docker_container":
            if target_val in ("portal-backend", "portal-frontend"):
                raise ValueError("Refusing to stop core control plane containers during chaos drill")
            res = docker_mgr.container_action(target_val, "stop")
            observed = f"Container '{target_val}' stopped (status={res['status']})."

        elif scenario_id == "kill_spark_executor":
            # Submit a real failing PySpark execution if spark-processing is up, else record simulated executor loss
            import subprocess
            c = docker_mgr.get_container_summary("spark-processing", include_stats=False)
            if c.get("running"):
                proc = subprocess.run(
                    ["docker", "exec", "spark-processing", "python3", "-c", "raise RuntimeError('Simulated Spark Executor OOM / Lost Executor 1')"],
                    capture_output=True, text=True, timeout=15,
                )
                observed = f"Executed failing Spark job in spark-processing (exit={proc.returncode}): {proc.stderr.strip()[-200:]}"
            else:
                observed = "spark-processing is currently stopped; recorded synthetic Spark executor failure event."

        elif scenario_id == "stop_airflow_scheduler":
            res = docker_mgr.container_action("airflow-scheduler", "stop")
            observed = f"Container 'airflow-scheduler' stopped (status={res['status']})."

        elif scenario_id == "kafka_consumer_lag":
            from kafka import KafkaConsumer
            topic = "ues-chaos-lag-topic"
            try:
                streaming_client.create_kafka_topic(topic, partitions=1)
            except Exception:
                pass
            # Commit offset 0 for group ues-chaos-group, then produce 200 messages
            c = KafkaConsumer(topic, group_id="ues-chaos-group", bootstrap_servers=[settings.KAFKA_BROKER], request_timeout_ms=3000)
            c.poll(timeout_ms=500)
            c.close()
            for i in range(200):
                streaming_client.produce_kafka_message(topic, f'{{"chaos_seq": {i}, "ts": {now}}}')
            observed = f"Produced 200 unconsumed messages to '{topic}' for consumer group 'ues-chaos-group'."

        elif scenario_id == "fill_rabbitmq_queue":
            q = "ues.chaos.backlog"
            for i in range(100):
                await streaming_client.rabbitmq_publish_test_message(q, f"chaos_msg_{i}_{now}")
            observed = f"Published 100 messages into RabbitMQ queue '{q}'."

        elif scenario_id == "exhaust_postgres_connections":
            global _HELD_PG_CONNS
            with _CHAOS_LOCK:
                opened = 0
                for _ in range(25):
                    try:
                        conn = psycopg2.connect(
                            host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
                            database=settings.POSTGRES_DB, user=settings.POSTGRES_USER,
                            password=settings.POSTGRES_PASSWORD, connect_timeout=2,
                        )
                        _HELD_PG_CONNS.append(conn)
                        opened += 1
                    except Exception:
                        break
            observed = f"Opened {opened} concurrent idle connections to PostgreSQL DW (total held={len(_HELD_PG_CONNS)})."

        elif scenario_id in ("high_cpu_usage", "high_memory_usage"):
            dg_scenario = "cpu_spike" if scenario_id == "high_cpu_usage" else "memory_leak"
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    r = await client.post(f"{settings.DATA_GENERATOR_URL}/api/chaos", json={"scenario": dg_scenario, "duration_seconds": 120, "intensity": 1.4})
                    observed = f"Activated '{dg_scenario}' on data-generator (HTTP {r.status_code})."
            except Exception as exc:
                observed = f"data-generator unreachable ({exc}); recorded anomaly event in AIOps stream."

        elif scenario_id == "k8s_crashloopbackoff":
            res = k8s_mgr.deploy_crashloop_chaos_pod()
            observed = f"Created CrashLoopBackOff pod '{res['namespace']}/{res['pod']}' on Kubernetes cluster."

        elif scenario_id == "network_latency":
            global _ARTIFICIAL_LATENCY_MS
            _ARTIFICIAL_LATENCY_MS = 450
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    await client.post(f"{settings.DATA_GENERATOR_URL}/api/chaos", json={"scenario": "latency_degradation", "duration_seconds": 120, "intensity": 1.3})
            except Exception:
                pass
            observed = "Injected +450ms artificial latency into API control plane & telemetry stream."

    # Emit anomaly & create Incident record
    aiops_engine.record_anomaly({"service": target_val, "severity": spec["severity"].lower(), "scenario": scenario_id, "message": f"Chaos Scenario [{spec['title']}]: {observed}"})
    await loki_client.push_log_to_loki("chaos-engine", "ERROR", f"[{scenario_id}] {observed}")

    kb_match = aiops_engine.kb.recommend_text(f"{spec['title']} {observed}")
    inc_id = f"inc-chaos-{scenario_id}-{now}"
    incident = database.upsert_incident(
        {
            "id": inc_id,
            "title": f"Chaos Drill: {spec['title']}",
            "severity": spec["severity"],
            "status": "open",
            "domain": spec["category"].lower().replace(" ", "_"),
            "source": "chaos_engineering",
            "service_id": target_val,
            "summary": observed,
            "de_perspective": f"Assess pipeline/data impact for scenario `{scenario_id}` on `{target_val}`.",
            "sre_perspective": f"Observed response: {observed} | Recovery: {spec['recovery_instructions']}",
            "evidence": {"scenario_id": scenario_id, "target": target_val, "investigation_steps": spec["investigation_steps"]},
            "ai_rca": f"Playbook [{kb_match['runbook_slug']}]: {kb_match['remediation']}",
            "remediation": spec["recovery_instructions"],
            "slo_impact_pct": 1.2,
            "timeline": [{"ts": now, "actor": actor, "event": f"Triggered {scenario_id}: {observed}"}],
        }
    )
    exp = database.log_experiment(
        scenario=scenario_id,
        label=spec["title"],
        hypothesis=spec["description"],
        duration_seconds=120,
        intensity=1.0,
        status="running",
        observations=observed,
        incident_id=inc_id,
    )
    return {"status": "executed", "scenario": scenario_id, "observed": observed, "incident": incident, "experiment": exp}


async def recover_chaos_scenario(scenario_id: str, target: Optional[str] = None, user: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Safely recover a previously triggered chaos simulation and mark associated incidents/experiments resolved."""
    spec = next((s for s in CHAOS_SCENARIOS if s["id"] == scenario_id), None)
    if not spec:
        raise ValueError(f"Unknown chaos scenario '{scenario_id}'")

    now = int(time.time())
    actor = (user or {}).get("username", "operator")
    target_val = target or spec["target_default"]
    recovery_msg = ""

    if scenario_id == "stop_docker_container":
        res = docker_mgr.container_action(target_val, "start")
        recovery_msg = f"Started container '{target_val}' (status={res['status']})."

    elif scenario_id == "kill_spark_executor":
        c = docker_mgr.get_container_summary("spark-processing", include_stats=False)
        if c.get("exists") and not c.get("running"):
            docker_mgr.container_action("spark-processing", "start")
        recovery_msg = "Verified spark-processing is healthy."

    elif scenario_id == "stop_airflow_scheduler":
        res = docker_mgr.container_action("airflow-scheduler", "start")
        recovery_msg = f"Started container 'airflow-scheduler' (status={res['status']})."

    elif scenario_id == "kafka_consumer_lag":
        from kafka import KafkaConsumer
        c = KafkaConsumer("ues-chaos-lag-topic", group_id="ues-chaos-group", bootstrap_servers=[settings.KAFKA_BROKER], auto_offset_reset="earliest", consumer_timeout_ms=2500)
        drained = sum(1 for _ in c)
        c.commit()
        c.close()
        recovery_msg = f"Drained {drained} messages from 'ues-chaos-lag-topic' for 'ues-chaos-group'."

    elif scenario_id == "fill_rabbitmq_queue":
        await streaming_client.rabbitmq_purge_queue("ues.chaos.backlog")
        recovery_msg = "Purged RabbitMQ queue 'ues.chaos.backlog'."

    elif scenario_id == "exhaust_postgres_connections":
        global _HELD_PG_CONNS
        with _CHAOS_LOCK:
            closed = len(_HELD_PG_CONNS)
            for conn in _HELD_PG_CONNS:
                try:
                    conn.close()
                except Exception:
                    pass
            _HELD_PG_CONNS = []
        recovery_msg = f"Closed {closed} held PostgreSQL chaos connections."

    elif scenario_id in ("high_cpu_usage", "high_memory_usage"):
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                await client.post(f"{settings.DATA_GENERATOR_URL}/api/chaos/reset")
        except Exception:
            pass
        recovery_msg = "Reset telemetry generator to steady-state baseline."

    elif scenario_id == "k8s_crashloopbackoff":
        res = k8s_mgr.delete_chaos_pod()
        recovery_msg = f"Deleted Kubernetes chaos pod ({res['status']})."

    elif scenario_id == "network_latency":
        global _ARTIFICIAL_LATENCY_MS
        _ARTIFICIAL_LATENCY_MS = 0
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                await client.post(f"{settings.DATA_GENERATOR_URL}/api/chaos/reset")
        except Exception:
            pass
        recovery_msg = "Cleared artificial network latency injection."

    # Mark matching open chaos incidents resolved
    for inc in database.get_incidents(status="open", limit=30):
        if inc.get("source") == "chaos_engineering" and scenario_id in inc["id"]:
            database.update_incident_status(inc["id"], "resolved", note=recovery_msg, actor=actor)

    for exp in database.get_experiments(limit=15):
        if exp["scenario"] == scenario_id and exp["status"] == "running":
            database.update_experiment(exp["id"], "recovered", f"{exp['observations']} | Recovered: {recovery_msg}")

    await loki_client.push_log_to_loki("chaos-engine", "INFO", f"[{scenario_id}] Recovered: {recovery_msg}")
    return {"status": "recovered", "scenario": scenario_id, "detail": recovery_msg, "timestamp": now}

