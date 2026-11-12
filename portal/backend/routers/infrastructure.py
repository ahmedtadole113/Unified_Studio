"""Infrastructure Management Router (`/api/v1/infrastructure`, `/api/v1/docker`, `/api/v1/kubernetes`)."""

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import audit, security
from services import docker_mgr, k8s_mgr

router = APIRouter(tags=["Infrastructure Management"])


class ScaleRequest(BaseModel):
    namespace: str
    deployment: str
    replicas: int


@router.get("/api/v1/infrastructure/summary")
def infrastructure_summary(user: Dict[str, str] = Depends(security.get_current_user)):
    containers = docker_mgr.list_containers(all_containers=True, include_stats=True)
    networks = docker_mgr.list_networks()
    volumes = docker_mgr.list_volumes()
    k8s = k8s_mgr.get_cluster_overview()
    return {
        "docker": {
            "available": docker_mgr.is_docker_available(),
            "running": sum(1 for c in containers if c["running"]),
            "total": len(containers),
            "containers": containers,
            "networks": networks,
            "volumes": volumes,
        },
        "kubernetes": k8s,
    }


@router.get("/api/v1/docker/containers")
def docker_containers(user: Dict[str, str] = Depends(security.get_current_user)):
    return {
        "available": docker_mgr.is_docker_available(),
        "containers": docker_mgr.list_containers(all_containers=True, include_stats=True),
        "networks": docker_mgr.list_networks(),
        "volumes": docker_mgr.list_volumes(),
    }


@router.get("/api/v1/docker/containers/{name}/logs")
def docker_container_logs(name: str, tail: int = 120, user: Dict[str, str] = Depends(security.get_current_user)):
    return {"container": name, "lines": docker_mgr.get_container_logs(name, tail=tail)}


@router.post("/api/v1/docker/containers/{name}/{action}")
def docker_container_lifecycle(name: str, action: str, admin: Dict[str, str] = Depends(security.require_admin)):
    if name in ("portal-backend", "portal-frontend") and action == "stop":
        raise HTTPException(status_code=400, detail="Cannot stop core control plane container")
    try:
        res = docker_mgr.container_action(name, action)
        audit.record_audit(admin, f"docker.{action}", name, f"Container {action} -> {res['status']}")
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/kubernetes/overview")
def k8s_overview(user: Dict[str, str] = Depends(security.get_current_user)):
    return k8s_mgr.get_cluster_overview()


@router.get("/api/v1/kubernetes/workloads")
def k8s_workloads(namespace: Optional[str] = "all", user: Dict[str, str] = Depends(security.get_current_user)):
    return k8s_mgr.get_workloads(namespace=namespace)


@router.get("/api/v1/kubernetes/pods/{namespace}/{pod}/logs")
def k8s_pod_logs(namespace: str, pod: str, tail: int = 100, user: Dict[str, str] = Depends(security.get_current_user)):
    return {"namespace": namespace, "pod": pod, "lines": k8s_mgr.get_pod_logs(namespace, pod, tail=tail)}


@router.post("/api/v1/kubernetes/scale")
def k8s_scale(req: ScaleRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = k8s_mgr.scale_deployment(req.namespace, req.deployment, req.replicas)
        audit.record_audit(admin, "k8s.scale", f"{req.namespace}/{req.deployment}", f"replicas={req.replicas}")
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

