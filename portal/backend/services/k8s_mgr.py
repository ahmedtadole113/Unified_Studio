"""Real Kubernetes cluster discovery, workload/event monitoring, and safe controls."""

import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from core.config import settings

logger = logging.getLogger("ues.k8s")

_EFFECTIVE_KUBECONFIG: Optional[str] = None


def _prepare_kubeconfig() -> Optional[str]:
    """Load kubeconfig and rewrite loopback 127.0.0.1:26443 for container-to-host OrbStack K8s access."""
    global _EFFECTIVE_KUBECONFIG
    candidates = [
        settings.KUBECONFIG_PATH,
        settings.KUBE_HOST_MOUNT,
        os.path.expanduser("~/.kube/config"),
    ]
    src = next((p for p in candidates if p and os.path.isfile(p)), None)
    if not src:
        return None

    try:
        with open(src, "r", encoding="utf-8") as f:
            raw = f.read()

        # Inside container, 127.0.0.1 / localhost refers to container loopback, not Mac host
        in_container = os.path.exists("/.dockerenv")
        if in_container and ("127.0.0.1:26443" in raw or "localhost:26443" in raw):
            rewritten = raw.replace("https://127.0.0.1:26443", "https://host.docker.internal:26443")
            rewritten = rewritten.replace("https://localhost:26443", "https://host.docker.internal:26443")
            if "tls-server-name:" not in rewritten:
                rewritten = re.sub(
                    r"^([ \t]*)server:\s*https://host\.docker\.internal:26443",
                    r"\1server: https://host.docker.internal:26443\n\1tls-server-name: kubernetes",
                    rewritten,
                    flags=re.MULTILINE,
                )
            tmp_path = os.path.join(tempfile.gettempdir(), "ues_kubeconfig")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(rewritten)
            _EFFECTIVE_KUBECONFIG = tmp_path
            return tmp_path

        _EFFECTIVE_KUBECONFIG = src
        return src
    except Exception as exc:
        logger.debug("Unable to prepare kubeconfig from %s: %s", src, exc)
        return None


def _get_apis() -> Optional[Dict[str, Any]]:
    cfg_path = _prepare_kubeconfig()
    if not cfg_path:
        return None
    try:
        api_cfg = k8s_client.Configuration()
        k8s_config.load_kube_config(config_file=cfg_path, client_configuration=api_cfg)
        api_cfg.connection_pool_maxsize = 4
        api_client = k8s_client.ApiClient(configuration=api_cfg)
        return {
            "core": k8s_client.CoreV1Api(api_client),
            "apps": k8s_client.AppsV1Api(api_client),
            "net": k8s_client.NetworkingV1Api(api_client),
            "version": k8s_client.VersionApi(api_client),
        }
    except Exception as exc:
        logger.debug("K8s client init failed: %s", exc)
        return None


def get_cluster_overview() -> Dict[str, Any]:
    """Discover real cluster status, nodes, pods, anomalies (CrashLoopBackOff/OOMKilled), and events."""
    apis = _get_apis()
    if not apis:
        return {
            "enabled": False,
            "connected": False,
            "status": "disabled",
            "reason": "No kubeconfig found or local Kubernetes cluster not configured.",
            "nodes": [],
            "namespaces": [],
            "summary": {"nodes": 0, "pods_total": 0, "pods_running": 0, "pods_failing": 0, "deployments": 0, "warnings": 0},
        }

    try:
        ver = apis["version"].get_code(_request_timeout=3)
        nodes_resp = apis["core"].list_node(_request_timeout=4)
        ns_resp = apis["core"].list_namespace(_request_timeout=4)
        pods_resp = apis["core"].list_pod_for_all_namespaces(_request_timeout=5)
        deps_resp = apis["apps"].list_deployment_for_all_namespaces(_request_timeout=4)
        sts_resp = apis["apps"].list_stateful_set_for_all_namespaces(_request_timeout=4)
        events_resp = apis["core"].list_event_for_all_namespaces(limit=60, _request_timeout=4)

        nodes = []
        for n in nodes_resp.items:
            conds = {c.type: c.status for c in (n.status.conditions or [])}
            cap = n.status.capacity or {}
            alloc = n.status.allocatable or {}
            nodes.append(
                {
                    "name": n.metadata.name,
                    "ready": conds.get("Ready") == "True",
                    "kubelet_version": n.status.node_info.kubelet_version if n.status.node_info else "",
                    "os_image": n.status.node_info.os_image if n.status.node_info else "",
                    "arch": n.status.node_info.architecture if n.status.node_info else "",
                    "cpu_capacity": cap.get("cpu", ""),
                    "memory_capacity": cap.get("memory", ""),
                    "cpu_allocatable": alloc.get("cpu", ""),
                    "memory_allocatable": alloc.get("memory", ""),
                    "pressure": [k for k in ("MemoryPressure", "DiskPressure", "PIDPressure") if conds.get(k) == "True"],
                }
            )

        crashloop_pods = []
        oom_pods = []
        total_restarts = 0
        running_pods = 0
        failing_pods = 0

        for p in pods_resp.items:
            phase = (p.status.phase or "Unknown")
            if phase == "Running":
                running_pods += 1
            for cs in (p.status.container_statuses or []):
                restarts = int(cs.restart_count or 0)
                total_restarts += restarts
                waiting_reason = cs.state.waiting.reason if (cs.state and cs.state.waiting) else None
                term_reason = cs.last_state.terminated.reason if (cs.last_state and cs.last_state.terminated) else None
                if waiting_reason == "CrashLoopBackOff":
                    crashloop_pods.append(f"{p.metadata.namespace}/{p.metadata.name}")
                    failing_pods += 1
                elif term_reason == "OOMKilled":
                    oom_pods.append(f"{p.metadata.namespace}/{p.metadata.name}")
                    failing_pods += 1
                elif phase in ("Failed", "Pending") and waiting_reason in ("ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError"):
                    failing_pods += 1

        warnings = [e for e in events_resp.items if (e.type or "") == "Warning"]
        healthy = all(n["ready"] for n in nodes) and failing_pods == 0

        return {
            "enabled": True,
            "connected": True,
            "status": "healthy" if healthy else "degraded",
            "git_version": ver.git_version,
            "platform": ver.platform,
            "nodes": nodes,
            "namespaces": [ns.metadata.name for ns in ns_resp.items],
            "summary": {
                "nodes": len(nodes),
                "nodes_ready": sum(1 for n in nodes if n["ready"]),
                "pods_total": len(pods_resp.items),
                "pods_running": running_pods,
                "pods_failing": failing_pods,
                "total_restarts": total_restarts,
                "deployments": len(deps_resp.items),
                "statefulsets": len(sts_resp.items),
                "warnings": len(warnings),
                "crashloop_pods": crashloop_pods,
                "oom_killed_pods": oom_pods,
            },
        }
    except Exception as exc:
        return {
            "enabled": True,
            "connected": False,
            "status": "unreachable",
            "reason": str(exc),
            "nodes": [],
            "namespaces": [],
            "summary": {"nodes": 0, "pods_total": 0, "pods_running": 0, "pods_failing": 0, "deployments": 0, "warnings": 0},
        }


def get_workloads(namespace: Optional[str] = None) -> Dict[str, Any]:
    """Return Pods, Deployments, StatefulSets, Services, Ingress, ConfigMaps, Secrets (keys only), and Events."""
    apis = _get_apis()
    if not apis:
        return {"connected": False, "error": "Kubernetes cluster not configured"}
    ns_filter = namespace if (namespace and namespace != "all") else None
    try:
        core = apis["core"]
        apps = apis["apps"]
        net = apis["net"]

        pods_raw = core.list_namespaced_pod(ns_filter, _request_timeout=5) if ns_filter else core.list_pod_for_all_namespaces(_request_timeout=5)
        deps_raw = apps.list_namespaced_deployment(ns_filter, _request_timeout=5) if ns_filter else apps.list_deployment_for_all_namespaces(_request_timeout=5)
        sts_raw = apps.list_namespaced_stateful_set(ns_filter, _request_timeout=5) if ns_filter else apps.list_stateful_set_for_all_namespaces(_request_timeout=5)
        svcs_raw = core.list_namespaced_service(ns_filter, _request_timeout=5) if ns_filter else core.list_service_for_all_namespaces(_request_timeout=5)
        ing_raw = net.list_namespaced_ingress(ns_filter, _request_timeout=5) if ns_filter else net.list_ingress_for_all_namespaces(_request_timeout=5)
        cm_raw = core.list_namespaced_config_map(ns_filter, _request_timeout=5) if ns_filter else core.list_config_map_for_all_namespaces(_request_timeout=5)
        sec_raw = core.list_namespaced_secret(ns_filter, _request_timeout=5) if ns_filter else core.list_secret_for_all_namespaces(_request_timeout=5)
        ev_raw = core.list_namespaced_event(ns_filter, limit=80, _request_timeout=5) if ns_filter else core.list_event_for_all_namespaces(limit=80, _request_timeout=5)

        pods = []
        for p in pods_raw.items:
            restarts = sum(int(cs.restart_count or 0) for cs in (p.status.container_statuses or []))
            reasons = []
            for cs in (p.status.container_statuses or []):
                if cs.state and cs.state.waiting and cs.state.waiting.reason:
                    reasons.append(cs.state.waiting.reason)
                if cs.last_state and cs.last_state.terminated and cs.last_state.terminated.reason:
                    reasons.append(f"last:{cs.last_state.terminated.reason}")
            req_cpu, req_mem, lim_cpu, lim_mem = [], [], [], []
            for c in (p.spec.containers or []):
                res = c.resources
                if res and res.requests:
                    if res.requests.get("cpu"): req_cpu.append(res.requests["cpu"])
                    if res.requests.get("memory"): req_mem.append(res.requests["memory"])
                if res and res.limits:
                    if res.limits.get("cpu"): lim_cpu.append(res.limits["cpu"])
                    if res.limits.get("memory"): lim_mem.append(res.limits["memory"])
            pods.append(
                {
                    "name": p.metadata.name,
                    "namespace": p.metadata.namespace,
                    "phase": p.status.phase,
                    "restarts": restarts,
                    "reasons": reasons,
                    "node": p.spec.node_name or "",
                    "pod_ip": p.status.pod_ip or "",
                    "requests": {"cpu": ",".join(req_cpu) or "-", "memory": ",".join(req_mem) or "-"},
                    "limits": {"cpu": ",".join(lim_cpu) or "-", "memory": ",".join(lim_mem) or "-"},
                    "created_at": str(p.metadata.creation_timestamp) if p.metadata.creation_timestamp else "",
                }
            )

        deployments = [
            {
                "name": d.metadata.name,
                "namespace": d.metadata.namespace,
                "desired": d.spec.replicas or 0,
                "ready": d.status.ready_replicas or 0,
                "available": d.status.available_replicas or 0,
                "updated": d.status.updated_replicas or 0,
            }
            for d in deps_raw.items
        ]

        statefulsets = [
            {
                "name": s.metadata.name,
                "namespace": s.metadata.namespace,
                "desired": s.spec.replicas or 0,
                "ready": s.status.ready_replicas or 0,
            }
            for s in sts_raw.items
        ]

        services = [
            {
                "name": s.metadata.name,
                "namespace": s.metadata.namespace,
                "type": s.spec.type,
                "cluster_ip": s.spec.cluster_ip,
                "ports": [f"{p.port}:{p.target_port}/{p.protocol}" for p in (s.spec.ports or [])],
            }
            for s in svcs_raw.items
        ]

        ingresses = [
            {
                "name": i.metadata.name,
                "namespace": i.metadata.namespace,
                "hosts": [r.host for r in (i.spec.rules or []) if r.host],
            }
            for i in ing_raw.items
        ]

        configmaps = [
            {"name": c.metadata.name, "namespace": c.metadata.namespace, "keys": list((c.data or {}).keys())}
            for c in cm_raw.items
        ]

        # Security: expose secret metadata & key names ONLY, never secret values
        secrets = [
            {"name": s.metadata.name, "namespace": s.metadata.namespace, "type": s.type, "key_count": len(s.data or {})}
            for s in sec_raw.items
        ]

        events = [
            {
                "type": e.type,
                "reason": e.reason,
                "namespace": e.metadata.namespace,
                "object": f"{e.involved_object.kind}/{e.involved_object.name}" if e.involved_object else "",
                "message": e.message,
                "count": e.count or 1,
                "last_timestamp": str(e.last_timestamp or e.event_time or ""),
            }
            for e in sorted(
                ev_raw.items,
                key=lambda x: str(x.last_timestamp or x.event_time or x.metadata.creation_timestamp or ""),
                reverse=True,
            )[:60]
        ]

        return {
            "connected": True,
            "pods": pods,
            "deployments": deployments,
            "statefulsets": statefulsets,
            "services": services,
            "ingresses": ingresses,
            "configmaps": configmaps,
            "secrets": secrets,
            "events": events,
        }
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


def get_pod_logs(namespace: str, pod_name: str, tail: int = 100) -> List[str]:
    apis = _get_apis()
    if not apis:
        return ["Kubernetes cluster unavailable"]
    try:
        raw = apis["core"].read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=tail, _request_timeout=5)
        return raw.splitlines()
    except Exception as exc:
        return [f"Error reading pod logs: {exc}"]


def scale_deployment(namespace: str, name: str, replicas: int) -> Dict[str, Any]:
    if namespace in ("kube-system", "kube-public", "kube-node-lease"):
        raise ValueError(f"Refusing to modify system namespace '{namespace}'")
    apis = _get_apis()
    if not apis:
        raise RuntimeError("Kubernetes cluster unavailable")
    body = {"spec": {"replicas": max(0, min(int(replicas), 10))}}
    apis["apps"].patch_namespaced_deployment_scale(name=name, namespace=namespace, body=body, _request_timeout=5)
    return {"namespace": namespace, "deployment": name, "replicas": body["spec"]["replicas"]}


def deploy_crashloop_chaos_pod(namespace: str = "ues-chaos-lab", pod_name: str = "ues-crashloop-sim") -> Dict[str, Any]:
    """Create a controlled CrashLoopBackOff pod inside an isolated lab namespace."""
    apis = _get_apis()
    if not apis:
        raise RuntimeError("Kubernetes cluster unavailable")
    core = apis["core"]
    try:
        core.read_namespace(name=namespace, _request_timeout=4)
    except ApiException as e:
        if e.status == 404:
            ns_obj = k8s_client.V1Namespace(metadata=k8s_client.V1ObjectMeta(name=namespace, labels={"ues-lab": "true"}))
            core.create_namespace(body=ns_obj, _request_timeout=4)
        else:
            raise

    # Delete previous if exists
    try:
        core.delete_namespaced_pod(name=pod_name, namespace=namespace, grace_period_seconds=0, _request_timeout=4)
    except ApiException:
        pass

    pod = k8s_client.V1Pod(
        metadata=k8s_client.V1ObjectMeta(name=pod_name, namespace=namespace, labels={"app": "ues-chaos-sim", "chaos": "crashloop"}),
        spec=k8s_client.V1PodSpec(
            restart_policy="Always",
            containers=[
                k8s_client.V1Container(
                    name="failing-worker",
                    image="busybox:1.36",
                    command=["sh", "-c", "echo 'FATAL: simulated missing warehouse secret /etc/ues/prod.conf' >&2; sleep 1; exit 1"],
                    resources=k8s_client.V1ResourceRequirements(
                        requests={"cpu": "10m", "memory": "16Mi"},
                        limits={"cpu": "50m", "memory": "32Mi"},
                    ),
                )
            ],
        ),
    )
    core.create_namespaced_pod(namespace=namespace, body=pod, _request_timeout=5)
    return {"namespace": namespace, "pod": pod_name, "status": "created"}


def delete_chaos_pod(namespace: str = "ues-chaos-lab", pod_name: str = "ues-crashloop-sim") -> Dict[str, Any]:
    apis = _get_apis()
    if not apis:
        raise RuntimeError("Kubernetes cluster unavailable")
    try:
        apis["core"].delete_namespaced_pod(name=pod_name, namespace=namespace, grace_period_seconds=0, _request_timeout=5)
        return {"namespace": namespace, "pod": pod_name, "status": "deleted"}
    except ApiException as e:
        if e.status == 404:
            return {"namespace": namespace, "pod": pod_name, "status": "not_found"}
        raise

