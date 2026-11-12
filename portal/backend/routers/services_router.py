"""Shared Service Registry & Health Check Routers (`/api/v1/services`, `/api/v1/health`, & legacy `/api/services`)."""

import time
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from core import audit, security
from core.config import settings
from services import docker_mgr, registry

router = APIRouter(tags=["Service Registry & Health"])


@router.get("/api/v1/health/live")
def health_live():
    """Unauthenticated liveness probe for container healthchecks & Prometheus."""
    return {"status": "ok", "service": "portal-backend", "version": settings.APP_VERSION, "ts": int(time.time())}


@router.get("/api/v1/health/ready")
def health_ready(user: Dict[str, str] = Depends(security.get_current_user)):
    items = registry.refresh_registry(include_stats=False)
    return {
        "status": "ready",
        "docker_available": docker_mgr.is_docker_available(),
        "services_healthy": sum(1 for i in items if i["status"] == "healthy"),
        "services_total": len(items),
    }


@router.get("/api/v1/services")
def list_registered_services(refresh: bool = True, user: Dict[str, str] = Depends(security.get_current_user)):
    items = registry.refresh_registry(include_stats=True) if refresh else registry.get_cached_registry()
    return {"total": len(items), "services": items}


@router.get("/api/v1/services/{service_id}")
def get_registered_service(service_id: str, user: Dict[str, str] = Depends(security.get_current_user)):
    svc = registry.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found in registry")
    return svc


@router.post("/api/v1/services/{service_id}/start")
def start_registered_service(service_id: str, admin: Dict[str, str] = Depends(security.require_admin)):
    svc = registry.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    try:
        res = docker_mgr.compose_services_action(svc["compose_services"], "up")
        audit.record_audit(admin, "service.start", service_id, f"Started {svc['compose_services']}")
        return {"status": "success", "service_id": service_id, **res}
    except Exception as exc:
        # Fallback to direct container start if compose dir unavailable
        try:
            res = docker_mgr.container_action(svc["container_name"], "start")
            audit.record_audit(admin, "service.start", service_id, f"Started container {svc['container_name']}")
            return {"status": "success", "service_id": service_id, **res}
        except Exception as exc2:
            audit.record_audit(admin, "service.start", service_id, str(exc2), status="error")
            raise HTTPException(status_code=500, detail=f"Failed to start {service_id}: {exc}") from exc2


@router.post("/api/v1/services/{service_id}/stop")
def stop_registered_service(service_id: str, admin: Dict[str, str] = Depends(security.require_admin)):
    svc = registry.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    if svc["service_id"] in ("portal-backend", "portal-frontend"):
        raise HTTPException(status_code=400, detail="Cannot stop core portal control plane via UI")
    try:
        res = docker_mgr.compose_services_action(svc["compose_services"], "stop")
        audit.record_audit(admin, "service.stop", service_id, f"Stopped {svc['compose_services']}")
        return {"status": "success", "service_id": service_id, **res}
    except Exception as exc:
        try:
            res = docker_mgr.container_action(svc["container_name"], "stop")
            audit.record_audit(admin, "service.stop", service_id, f"Stopped container {svc['container_name']}")
            return {"status": "success", "service_id": service_id, **res}
        except Exception as exc2:
            audit.record_audit(admin, "service.stop", service_id, str(exc2), status="error")
            raise HTTPException(status_code=500, detail=f"Failed to stop {service_id}: {exc}") from exc2


@router.post("/api/v1/services/{service_id}/restart")
def restart_registered_service(service_id: str, admin: Dict[str, str] = Depends(security.require_admin)):
    svc = registry.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    if svc["service_id"] in ("portal-backend", "portal-frontend"):
        raise HTTPException(status_code=400, detail="Cannot restart core control plane via UI")
    res = docker_mgr.container_action(svc["container_name"], "restart")
    audit.record_audit(admin, "service.restart", service_id, f"Restarted {svc['container_name']}")
    return {"status": "success", "service_id": service_id, **res}


# Backward-compatible DE portal endpoints (now protected by Auth/RBAC)
@router.get("/api/services")
def legacy_list_services(user: Dict[str, str] = Depends(security.get_current_user)):
    return registry.get_legacy_services_map()


@router.post("/api/services/{service_name}/start")
def legacy_start_service(service_name: str, admin: Dict[str, str] = Depends(security.require_admin)):
    return start_registered_service(service_name.lower(), admin)


@router.post("/api/services/{service_name}/stop")
def legacy_stop_service(service_name: str, admin: Dict[str, str] = Depends(security.require_admin)):
    return stop_registered_service(service_name.lower(), admin)

