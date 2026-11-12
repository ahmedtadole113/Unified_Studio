"""Data Engineering <-> SRE Correlation Engine (Section 8).

Correlates Airflow DAG failures, Spark job failures, Kubernetes pod restarts/CrashLoopBackOff/OOMKilled,
Docker container exits/pressure, Prometheus alerts, Loki/container error logs, and OpenTelemetry trace IDs
into unified dual-perspective incidents (Data Engineer view + SRE view).
"""

import logging
import time
from typing import Any, Dict, List

from core import database
from core.telemetry_otel import get_recent_traces, traced_operation
from services import aiops_engine, de_client, k8s_mgr, loki_client, prometheus_client, registry

logger = logging.getLogger("ues.correlation")


async def run_correlation_pass() -> Dict[str, Any]:
    """Inspect live DE & SRE signals, correlate overlapping anomalies, and create/update unified Incidents."""
    with traced_operation("correlation.run_pass", domain="correlation") as span:
        now = int(time.time())
        services = registry.refresh_registry(include_stats=True)
        airflow = await de_client.get_airflow_overview()
        spark = await de_client.get_spark_and_iceberg_status()
        k8s = k8s_mgr.get_cluster_overview()
        obs = await prometheus_client.get_observability_status()
        logs = await loki_client.query_logs(minutes=15, limit=50)
        traces = get_recent_traces(limit=20)

        unavailable_svcs = [s for s in services if s["status"] == "unavailable" and s["docker_exists"]]
        degraded_svcs = [s for s in services if s["status"] == "degraded"]
        failed_dags = [r for r in airflow.get("recent_runs", []) if r.get("state") == "failed"]
        failed_spark = [a for a in spark.get("applications", []) if str(a.get("state", "")).upper() in ("FAILED", "KILLED", "ERROR")]
        k8s_crash = k8s.get("summary", {}).get("crashloop_pods", []) if k8s.get("connected") else []
        k8s_oom = k8s.get("summary", {}).get("oom_killed_pods", []) if k8s.get("connected") else []
        firing_alerts = obs.get("alerts", [])
        error_logs = [l for l in logs.get("logs", []) if l.get("level") == "ERROR"]
        latest_trace_id = traces[0]["trace_id"] if traces else f"tr-{now}"

        created_or_updated: List[Dict[str, Any]] = []

        # 1. Correlate Pipeline Failure (Airflow/Spark) with Infrastructure Pressure / Outage
        if failed_dags or failed_spark or (unavailable_svcs and any(s["category"] in ("compute", "orchestration", "warehouse", "storage") for s in unavailable_svcs)):
            dag_id = failed_dags[0]["dag_id"] if failed_dags else None
            spark_id = failed_spark[0].get("id") if failed_spark else None
            infra_causes = [s["service_id"] for s in (unavailable_svcs + degraded_svcs)]
            inc_id = f"inc-corr-de-{dag_id or spark_id or (infra_causes[0] if infra_causes else 'pipeline')}"
            evidence_text = f"Airflow failed={len(failed_dags)} Spark failed={len(failed_spark)} Infra down={infra_causes} K8s crash={k8s_crash} alerts={[a['name'] for a in firing_alerts]}"
            kb_match = aiops_engine.kb.recommend_text(evidence_text)

            de_view = (
                f"Pipeline Impact: {len(failed_dags)} failed Airflow DAG run(s) ({dag_id or 'none'}), "
                f"{len(failed_spark)} failed Spark app(s) ({spark_id or 'none'}). "
                f"Check Gold/DW freshness and upstream MinIO/Postgres connectivity."
            )
            sre_view = (
                f"Infrastructure Evidence: Unavailable/Degraded services={infra_causes or 'none'}, "
                f"K8s CrashLoop={k8s_crash or 'none'}, OOMKilled={k8s_oom or 'none'}, "
                f"Firing Prometheus Alerts={[a['name'] for a in firing_alerts] or 'none'}, "
                f"Error logs in window={len(error_logs)}."
            )

            inc = database.upsert_incident(
                {
                    "id": inc_id,
                    "title": f"Correlated Data Pipeline & Infrastructure Incident ({dag_id or spark_id or ', '.join(infra_causes)})",
                    "severity": "SEV-1" if (unavailable_svcs or k8s_oom) else "SEV-2",
                    "status": "open",
                    "domain": "correlated",
                    "source": "correlation_engine",
                    "service_id": infra_causes[0] if infra_causes else "airflow-webserver",
                    "pipeline_id": dag_id,
                    "job_id": spark_id,
                    "k8s_namespace": k8s_crash[0].split("/")[0] if k8s_crash else None,
                    "k8s_pod": k8s_crash[0].split("/")[1] if k8s_crash else None,
                    "trace_id": latest_trace_id,
                    "summary": evidence_text,
                    "de_perspective": de_view,
                    "sre_perspective": sre_view,
                    "evidence": {
                        "failed_dags": failed_dags[:5],
                        "failed_spark_apps": failed_spark[:5],
                        "unavailable_services": [s["service_id"] for s in unavailable_svcs],
                        "k8s_crashloop": k8s_crash,
                        "k8s_oom": k8s_oom,
                        "firing_alerts": firing_alerts[:5],
                        "sample_error_logs": error_logs[:5],
                    },
                    "ai_rca": f"FAISS Playbook [{kb_match['runbook_slug']}] (confidence {kb_match['similarity']}): {kb_match['remediation']}",
                    "remediation": kb_match["remediation"],
                    "slo_impact_pct": 1.5 if unavailable_svcs else 0.5,
                    "timeline_append": [{"ts": now, "actor": "correlation_engine", "event": f"Correlated DE/SRE signals: {evidence_text[:180]}"}],
                }
            )
            created_or_updated.append(inc)
            await loki_client.push_log_to_loki("correlation-engine", "ERROR", f"[{inc_id}] {evidence_text}")

        # 2. Correlate Kubernetes Pod CrashLoop / OOMKilled
        if k8s_crash or k8s_oom:
            pod_ref = (k8s_crash + k8s_oom)[0]
            ns, pod = pod_ref.split("/", 1) if "/" in pod_ref else ("default", pod_ref)
            inc_id = f"inc-k8s-{ns}-{pod}"
            kb_match = aiops_engine.kb.recommend_text(f"Kubernetes pod CrashLoopBackOff OOMKilled {pod_ref}")
            inc = database.upsert_incident(
                {
                    "id": inc_id,
                    "title": f"Kubernetes Workload Failure: {pod_ref}",
                    "severity": "SEV-1",
                    "status": "open",
                    "domain": "kubernetes",
                    "source": "correlation_engine",
                    "service_id": "kubernetes",
                    "k8s_namespace": ns,
                    "k8s_pod": pod,
                    "trace_id": latest_trace_id,
                    "summary": f"Detected CrashLoopBackOff={k8s_crash}, OOMKilled={k8s_oom}",
                    "de_perspective": "If Spark-on-K8s or data job pod is affected, downstream batch/streaming SLAs may delay.",
                    "sre_perspective": f"Pod `{pod}` in namespace `{ns}` is restarting or OOMKilled. Inspect K8s Events & pod logs.",
                    "evidence": {"crashloop_pods": k8s_crash, "oom_killed_pods": k8s_oom},
                    "ai_rca": f"FAISS Playbook [{kb_match['runbook_slug']}]: {kb_match['remediation']}",
                    "remediation": kb_match["remediation"],
                    "slo_impact_pct": 1.0,
                    "timeline_append": [{"ts": now, "actor": "k8s_watcher", "event": f"Detected failing pod {pod_ref}"}],
                }
            )
            created_or_updated.append(inc)

        # 3. Correlate Prometheus Firing Alerts
        for alert in firing_alerts:
            aname = alert.get("name", "PrometheusAlert")
            inc_id = f"inc-prom-{aname.lower()}"
            kb_match = aiops_engine.kb.recommend_text(f"{aname} {alert.get('summary', '')}")
            inc = database.upsert_incident(
                {
                    "id": inc_id,
                    "title": f"Alert Firing: {aname}",
                    "severity": "SEV-1" if alert.get("severity") == "critical" else "SEV-2",
                    "status": "open",
                    "domain": alert.get("domain", "sre"),
                    "source": "prometheus_alert",
                    "service_id": "prometheus",
                    "trace_id": latest_trace_id,
                    "summary": alert.get("summary") or alert.get("description") or aname,
                    "de_perspective": "Check whether active Spark/Airflow/DW pipelines are impacted by resource or latency saturation.",
                    "sre_perspective": f"Prometheus alert `{aname}` firing ({alert.get('severity')}). {alert.get('description', '')}",
                    "evidence": {"alert": alert, "error_logs": error_logs[:3]},
                    "ai_rca": f"FAISS Playbook [{kb_match['runbook_slug']}]: {kb_match['remediation']}",
                    "remediation": kb_match["remediation"],
                    "slo_impact_pct": 0.8,
                    "timeline_append": [{"ts": now, "actor": "prometheus", "event": f"Alert {aname} firing"}],
                }
            )
            created_or_updated.append(inc)

        span.set_attribute("correlation.incidents_touched", len(created_or_updated))
        return {
            "timestamp": now,
            "signals": {
                "unavailable_services": [s["service_id"] for s in unavailable_svcs],
                "degraded_services": [s["service_id"] for s in degraded_svcs],
                "failed_dags": len(failed_dags),
                "failed_spark_apps": len(failed_spark),
                "k8s_crashloop": len(k8s_crash),
                "k8s_oom_killed": len(k8s_oom),
                "firing_alerts": len(firing_alerts),
                "error_logs": len(error_logs),
            },
            "correlated_incidents": created_or_updated,
        }

