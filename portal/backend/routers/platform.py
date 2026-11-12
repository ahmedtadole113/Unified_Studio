"""Platform Overview, Profile Management, Audit Logs, Readiness Gate, & SSE Stream Router (`/api/v1/platform`)."""

import asyncio
import json
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core import audit, database, security
from core.config import settings
from services import de_client, docker_mgr, finops_engine, k8s_mgr, prometheus_client, registry, slo_engine

router = APIRouter(prefix="/api/v1/platform", tags=["Platform"])


class ProfileActionRequest(BaseModel):
    profile: str
    action: str  # up | stop


class ReadinessSignoffRequest(BaseModel):
    release_tag: str
    eng_signoff: str
    sre_signoff: str
    security_signoff: str
    notes: str = ""


@router.get("/overview")
async def platform_overview(user: Dict[str, str] = Depends(security.get_current_user)):
    """Unified Platform Overview combining Service Registry, Docker, K8s, Pipelines, Incidents, SLOs, and FinOps."""
    services, k8s, airflow, spark, slo_data, obs = await asyncio.gather(
        asyncio.to_thread(registry.refresh_registry, True),
        asyncio.to_thread(k8s_mgr.get_cluster_overview),
        de_client.get_airflow_overview(),
        de_client.get_spark_and_iceberg_status(),
        slo_engine.evaluate_all_slos(),
        prometheus_client.get_observability_status(),
    )
    healthy = sum(1 for s in services if s["status"] == "healthy")
    degraded = sum(1 for s in services if s["status"] == "degraded")
    unavailable = sum(1 for s in services if s["status"] == "unavailable")

    finops = await asyncio.to_thread(finops_engine.get_finops_overview)
    incidents = database.get_incidents(status="open", limit=20)

    overall_health = "healthy"
    if unavailable > 0 and any(s["criticality"] == "critical" and s["docker_exists"] and s["status"] == "unavailable" for s in services):
        overall_health = "degraded"
    if any(i["severity"] == "SEV-1" for i in incidents) or slo_data.get("release_freeze"):
        overall_health = "critical" if slo_data.get("release_freeze") else "degraded"

    running_pipelines = len([a for a in spark.get("applications", []) if str(a.get("state", "")).upper() == "RUNNING"]) + len(
        [r for r in airflow.get("recent_runs", []) if r.get("state") == "running"]
    )

    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "overall_health": overall_health,
        "services": {
            "total": len(services),
            "healthy": healthy,
            "degraded": degraded,
            "unavailable": unavailable,
            "items": services,
        },
        "docker": {
            "available": docker_mgr.is_docker_available(),
            "running_containers": finops["allocation"]["running_containers"],
            "total_containers": finops["allocation"]["total_containers"],
            "total_cpu_percent": finops["allocation"]["total_cpu_percent"],
            "total_memory_mb": finops["allocation"]["total_memory_mb"],
        },
        "kubernetes": k8s,
        "pipelines": {
            "running": running_pipelines,
            "airflow_available": airflow.get("available", False),
            "airflow_dags_count": len(airflow.get("dags", [])),
            "spark_available": spark.get("spark_available", False),
            "spark_apps_count": len(spark.get("applications", [])),
        },
        "incidents": {
            "open_count": len(incidents),
            "items": incidents[:10],
        },
        "slo": {
            "overall_compliance_pct": slo_data["overall_compliance_pct"],
            "release_freeze": slo_data["release_freeze"],
            "counts": slo_data["counts"],
            "items": slo_data["slos"],
        },
        "observability": {
            "prometheus_reachable": obs["prometheus_reachable"],
            "firing_alerts_count": len(obs["alerts"]),
        },
        "finops": {
            "estimated_monthly_usd": finops["cost_model"]["estimated_monthly_usd"],
            "ram_budget_used_pct": finops["forecast"]["ram_budget_used_pct"],
            "ram_headroom_mb": finops["forecast"]["ram_headroom_mb"],
            "profiles": finops["profiles"],
        },
    }


@router.get("/profiles")
def list_profiles(user: Dict[str, str] = Depends(security.get_current_user)):
    finops = finops_engine.get_finops_overview()
    return {"profiles": finops["profiles"], "hardware_target": finops["hardware_target"]}


@router.post("/profiles/action")
def execute_profile_action(req: ProfileActionRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = docker_mgr.compose_profile_action(req.profile, req.action)
        audit.record_audit(admin, f"profile.{req.action}", req.profile, f"Executed compose profile {req.action}")
        return {"status": "success", **res}
    except Exception as exc:
        audit.record_audit(admin, f"profile.{req.action}", req.profile, str(exc), status="error")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit")
def get_audit_trail(limit: int = 100, user: Dict[str, str] = Depends(security.get_current_user)):
    return {"logs": audit.list_audits(limit=limit)}


@router.get("/readiness")
async def get_readiness_gate(user: Dict[str, str] = Depends(security.get_current_user)):
    services = registry.get_cached_registry()
    slo_data = await slo_engine.evaluate_all_slos()
    obs = await prometheus_client.get_observability_status()
    k8s = k8s_mgr.get_cluster_overview()
    open_sev1 = [i for i in database.get_incidents(status="open", limit=30) if i.get("severity") == "SEV-1"]

    checks = [
        {
            "id": "core_services",
            "name": "Core Control Plane & Database Healthy",
            "detail": f"Backend & Postgres checked via live probes",
            "passed": all(s["status"] == "healthy" for s in services if s["service_id"] in ("portal-backend", "postgres-dw")),
        },
        {
            "id": "no_sev1",
            "name": "Zero Open SEV-1 Incidents",
            "detail": f"{len(open_sev1)} open SEV-1 incident(s)",
            "passed": len(open_sev1) == 0,
        },
        {
            "id": "slo_budget",
            "name": "No Critical SLO Release Freeze",
            "detail": f"Overall compliance {slo_data['overall_compliance_pct']}%",
            "passed": not slo_data["release_freeze"],
        },
        {
            "id": "prom_alerts",
            "name": "Zero Critical Firing Prometheus Alerts",
            "detail": f"{len([a for a in obs['alerts'] if a.get('severity') == 'critical'])} critical alerts",
            "passed": len([a for a in obs["alerts"] if a.get("severity") == "critical"]) == 0,
        },
        {
            "id": "k8s_health",
            "name": "Kubernetes Workloads Healthy (if enabled)",
            "detail": f"K8s status: {k8s['status']}",
            "passed": (not k8s["connected"]) or k8s["summary"].get("pods_failing", 0) == 0,
        },
    ]
    passed = sum(1 for c in checks if c["passed"])
    gate_status = "ADMIT" if passed == len(checks) else ("HOLD" if passed < 4 or len(open_sev1) > 0 else "WARN")
    return {
        "gate_status": gate_status,
        "passed_count": passed,
        "total_checks": len(checks),
        "checks": checks,
        "reviews": database.get_readiness_reviews(limit=10),
    }


@router.post("/readiness/signoff")
async def create_readiness_signoff(req: ReadinessSignoffRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    gate = await get_readiness_gate(admin)
    all_signed = all(x == "approved" for x in (req.eng_signoff, req.sre_signoff, req.security_signoff))
    any_rejected = any(x == "rejected" for x in (req.eng_signoff, req.sre_signoff, req.security_signoff))
    if any_rejected or gate["gate_status"] == "HOLD":
        decision = "BLOCKED"
    elif all_signed and gate["gate_status"] == "ADMIT":
        decision = "ADMITTED"
    else:
        decision = "CONDITIONAL"

    review = database.create_readiness_review(
        {
            "release_tag": req.release_tag,
            "decision": decision,
            "eng_signoff": req.eng_signoff,
            "sre_signoff": req.sre_signoff,
            "security_signoff": req.security_signoff,
            "checks": gate["checks"],
            "notes": req.notes,
        }
    )
    audit.record_audit(admin, "readiness.signoff", req.release_tag, f"Decision={decision}")
    return review


@router.get("/events/stream")
async def sse_event_stream(user: Dict[str, str] = Depends(security.get_current_user)):
    """Server-Sent Events stream pushing live registry & incident heartbeats to the UI."""
    async def event_generator():
        while True:
            services = registry.get_cached_registry()
            open_incidents = database.get_incidents(status="open", limit=10)
            payload = {
                "ts": int(time.time()),
                "healthy": sum(1 for s in services if s["status"] == "healthy"),
                "degraded": sum(1 for s in services if s["status"] == "degraded"),
                "unavailable": sum(1 for s in services if s["status"] == "unavailable"),
                "open_incidents": len(open_incidents),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

