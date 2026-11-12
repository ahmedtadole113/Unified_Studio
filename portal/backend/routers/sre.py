"""SRE Operations Router: SLOs, Error Budgets, Incidents, Correlation, Chaos Engineering, Runbooks, Postmortems."""

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core import audit, database, security
from services import chaos_engine, correlation_engine, slo_engine

router = APIRouter(tags=["SRE Operations"])


class SloUpdateRequest(BaseModel):
    target: float
    window_days: int = 30
    policy: str
    rolling_window: Optional[str] = "1h"


class IncidentStatusRequest(BaseModel):
    status: str  # open | investigating | mitigated | resolved
    note: str = ""


class ChaosExecuteRequest(BaseModel):
    scenario_id: str
    confirm: bool = False
    confirmation_phrase: str = ""
    target: Optional[str] = None


class ChaosRecoverRequest(BaseModel):
    scenario_id: str
    target: Optional[str] = None


class RunbookRequest(BaseModel):
    slug: str
    title: str
    domain: str = "infrastructure"
    severity: str = "SEV-2"
    trigger_alert: str = "CustomAlert"
    chaos_scenario: str = ""
    steps_md: str


class PostmortemRequest(BaseModel):
    incident_id: Optional[str] = None
    title: str
    severity: str = "SEV-2"
    slo_impact: str
    error_budget_consumed_pct: float = 0.5
    summary: str
    root_cause: str
    contributing_factors: List[str] = []
    action_items: List[Dict[str, str]] = []
    author: str = "SRE + DE Team"


class ToilRequest(BaseModel):
    title: str
    category: str = "Operations"
    frequency_per_week: int = 2
    minutes_per_occurrence: int = 15
    automation_candidate: str = "Automated script"
    owner: str = "SRE"


# --- SLO & Error Budgets ---
@router.get("/api/v1/slo")
async def list_slos(window: str = "1h", calendar: bool = False, user: Dict[str, str] = Depends(security.get_current_user)):
    return await slo_engine.evaluate_all_slos(window=window, calendar_mode=calendar)


@router.put("/api/v1/slo/{slo_id}")
def update_slo_config(slo_id: str, req: SloUpdateRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    updated = database.update_slo(slo_id, req.target, req.window_days, req.policy, req.rolling_window)
    if not updated:
        raise HTTPException(status_code=404, detail="SLO not found")
    audit.record_audit(admin, "slo.update", slo_id, f"target={req.target}, window={req.rolling_window}")
    return updated


@router.get("/api/v1/error-budget")
async def get_error_budgets(window: str = "1h", calendar: bool = False, user: Dict[str, str] = Depends(security.get_current_user)):
    data = await slo_engine.evaluate_all_slos(window=window, calendar_mode=calendar)
    return {
        "evaluated_at": data["evaluated_at"],
        "window": data["window"],
        "release_freeze": data["release_freeze"],
        "budgets": [
            {
                "id": s["id"],
                "name": s["name"],
                "service": s["service"],
                "domain": s["domain"],
                "target": s["target"],
                "unit": s["unit"],
                "actual_sli": s["actual_sli"],
                "error_budget_allowance_pct": s["error_budget_allowance_pct"],
                "error_budget_consumed_pct": s["error_budget_consumed_pct"],
                "error_budget_remaining_pct": s["error_budget_remaining_pct"],
                "burn_rate_5m": s["burn_rate_5m"],
                "burn_rate_1h": s["burn_rate_1h"],
                "burn_alert": s["burn_alert"],
                "status": s["status"],
                "policy": s["policy"],
            }
            for s in data["slos"]
        ],
    }


# --- Incidents & DE <-> SRE Correlation ---
@router.get("/api/v1/incidents")
def list_incidents(status: Optional[str] = "all", limit: int = 50, user: Dict[str, str] = Depends(security.get_current_user)):
    return {"incidents": database.get_incidents(status=status, limit=limit)}


@router.post("/api/v1/incidents/correlate")
async def trigger_correlation(user: Dict[str, str] = Depends(security.get_current_user)):
    return await correlation_engine.run_correlation_pass()


@router.put("/api/v1/incidents/{inc_id}/status")
def set_incident_status(inc_id: str, req: IncidentStatusRequest, user: Dict[str, str] = Depends(security.get_current_user)):
    updated = database.update_incident_status(inc_id, req.status, note=req.note, actor=user["username"])
    if not updated:
        raise HTTPException(status_code=404, detail="Incident not found")
    audit.record_audit(user, "incident.status", inc_id, f"status={req.status}")
    return updated


@router.post("/api/v1/incidents/webhook/alertmanager")
async def alertmanager_webhook(request: Request):
    """Receive Prometheus Alertmanager webhook notifications (internal Docker network)."""
    payload = await request.json()
    now = int(time.time())
    alerts = payload.get("alerts", [])
    created = []
    for a in alerts:
        labels = a.get("labels", {})
        ann = a.get("annotations", {})
        name = labels.get("alertname", "AlertmanagerAlert")
        inc = database.upsert_incident(
            {
                "id": f"inc-am-{name.lower()}",
                "title": f"Alertmanager: {name}",
                "severity": "SEV-1" if labels.get("severity") == "critical" else "SEV-2",
                "status": "resolved" if a.get("status") == "resolved" else "open",
                "domain": labels.get("domain", "sre"),
                "source": "alertmanager",
                "summary": ann.get("summary") or ann.get("description") or name,
                "sre_perspective": ann.get("description", ""),
                "evidence": a,
                "timeline_append": [{"ts": now, "actor": "alertmanager", "event": f"Alert {name} -> {a.get('status')}"}],
            }
        )
        created.append(inc["id"])
    return {"received": len(alerts), "incidents": created}


# --- Controlled Chaos Engineering (10 Scenarios) ---
@router.get("/api/v1/incidents/chaos/scenarios")
def list_chaos_scenarios(user: Dict[str, str] = Depends(security.get_current_user)):
    return {"scenarios": chaos_engine.list_scenarios(), "experiments": database.get_experiments(limit=20)}


@router.post("/api/v1/incidents/chaos/execute")
async def run_chaos_scenario(req: ChaosExecuteRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = await chaos_engine.execute_chaos_scenario(
            req.scenario_id,
            confirm=req.confirm,
            confirmation_phrase=req.confirmation_phrase,
            target=req.target,
            user=admin,
        )
        audit.record_audit(admin, "chaos.execute", req.scenario_id, res["observed"])
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/v1/incidents/chaos/recover")
async def recover_chaos(req: ChaosRecoverRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = await chaos_engine.recover_chaos_scenario(req.scenario_id, target=req.target, user=admin)
        audit.record_audit(admin, "chaos.recover", req.scenario_id, res["detail"])
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# --- Runbooks, Postmortems, Toil ---
@router.get("/api/v1/incidents/runbooks/all")
def list_runbooks(user: Dict[str, str] = Depends(security.get_current_user)):
    return {"runbooks": database.get_runbooks()}


@router.post("/api/v1/incidents/runbooks")
def save_runbook(req: RunbookRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    res = database.upsert_runbook(req.dict())
    audit.record_audit(admin, "runbook.upsert", req.slug, req.title)
    return res


@router.get("/api/v1/incidents/postmortems/all")
def list_postmortems(user: Dict[str, str] = Depends(security.get_current_user)):
    return {"postmortems": database.get_postmortems()}


@router.post("/api/v1/incidents/postmortems")
def add_postmortem(req: PostmortemRequest, user: Dict[str, str] = Depends(security.get_current_user)):
    res = database.create_postmortem(req.dict())
    audit.record_audit(user, "postmortem.create", str(res["id"]), req.title)
    return res


@router.get("/api/v1/incidents/toil/all")
def list_toil(user: Dict[str, str] = Depends(security.get_current_user)):
    items = database.get_toil_items()
    manual = sum(t["frequency_per_week"] * t["minutes_per_occurrence"] for t in items if not t["automated"])
    total = sum(t["frequency_per_week"] * t["minutes_per_occurrence"] for t in items)
    return {
        "items": items,
        "weekly_manual_minutes": manual,
        "weekly_total_minutes": total,
        "automation_pct": round(((total - manual) / total) * 100, 1) if total else 100.0,
    }


@router.post("/api/v1/incidents/toil")
def create_toil(req: ToilRequest, user: Dict[str, str] = Depends(security.get_current_user)):
    return database.create_toil_item(req.dict())


@router.post("/api/v1/incidents/toil/{item_id}/toggle")
def toggle_toil(item_id: int, user: Dict[str, str] = Depends(security.get_current_user)):
    item = database.toggle_toil_automated(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Toil item not found")
    return item

