"""Safe Docker engine integration (container lifecycle, stats, logs, networks, volumes)."""

import concurrent.futures
import copy
import logging
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.errors import DockerException, NotFound

from core.config import settings

logger = logging.getLogger("ues.docker")

_CONTAINERS_CACHE: Dict[Tuple[bool, bool], Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SEC = 4.0


def _invalidate_cache() -> None:
    with _CACHE_LOCK:
        _CONTAINERS_CACHE.clear()

ALLOWED_COMPOSE_PROFILES = {
    "profile-core",
    "profile-data-engineering",
    "profile-sre",
    "profile-storage",
    "profile-processing",
    "profile-orchestration",
    "profile-warehouse",
    "profile-streaming",
    "profile-monitoring",
}

ALLOWED_SERVICES = {
    "portal-backend",
    "portal-frontend",
    "minio",
    "mc",
    "spark-processing",
    "rest",
    "airflow-webserver",
    "airflow-scheduler",
    "postgres-dw",
    "pgadmin",
    "redpanda",
    "redpanda-console",
    "rabbitmq",
    "prometheus",
    "grafana",
    "loki",
    "promtail",
    "tempo",
    "alertmanager",
    "data-generator",
    "practice-lab",
}


def _get_client() -> Optional[docker.DockerClient]:
    try:
        return docker.from_env(timeout=4)
    except DockerException as exc:
        logger.debug("Docker client unavailable: %s", exc)
        return None


def is_docker_available() -> bool:
    client = _get_client()
    if not client:
        return False
    try:
        client.ping()
        return True
    except Exception:
        return False
    finally:
        client.close()


def _calc_cpu_pct(stats: Dict[str, Any]) -> float:
    try:
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        sys_delta = (
            stats["cpu_stats"].get("system_cpu_usage", 0)
            - stats["precpu_stats"].get("system_cpu_usage", 0)
        )
        online_cpus = stats["cpu_stats"].get("online_cpus") or len(
            stats["cpu_stats"]["cpu_usage"].get("percpu_usage") or [1]
        )
        if sys_delta > 0 and cpu_delta >= 0:
            return round((cpu_delta / sys_delta) * online_cpus * 100.0, 2)
    except Exception:
        pass
    return 0.0


def _calc_mem_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    try:
        mem_stats = stats.get("memory_stats", {})
        usage = float(mem_stats.get("usage", 0))
        cache = float(mem_stats.get("stats", {}).get("inactive_file", mem_stats.get("stats", {}).get("cache", 0)))
        working_set = max(0.0, usage - cache)
        limit = float(mem_stats.get("limit", 0))
        mem_mb = round(working_set / (1024 * 1024), 1)
        limit_mb = round(limit / (1024 * 1024), 1) if limit > 0 else 0.0
        pct = round((working_set / limit) * 100.0, 2) if limit > 0 else 0.0
        return {"memory_mb": mem_mb, "memory_limit_mb": limit_mb, "memory_percent": pct}
    except Exception:
        return {"memory_mb": 0.0, "memory_limit_mb": 0.0, "memory_percent": 0.0}


def _calc_net_io(stats: Dict[str, Any]) -> Dict[str, float]:
    rx_bytes = 0.0
    tx_bytes = 0.0
    try:
        for net in (stats.get("networks") or {}).values():
            rx_bytes += float(net.get("rx_bytes", 0))
            tx_bytes += float(net.get("tx_bytes", 0))
    except Exception:
        pass
    return {"rx_mb": round(rx_bytes / (1024 * 1024), 2), "tx_mb": round(tx_bytes / (1024 * 1024), 2)}


def get_container_summary(container_name: str, include_stats: bool = True) -> Dict[str, Any]:
    """Inspect a single container and optionally fetch live CPU/memory/network stats."""
    client = _get_client()
    if not client:
        return {"exists": False, "status": "docker_unavailable", "restart_count": 0}
    try:
        c = client.containers.get(container_name)
        attrs = c.attrs or {}
        state = attrs.get("State", {})
        health = (state.get("Health") or {}).get("Status", "none")
        res = {
            "exists": True,
            "id": c.short_id,
            "name": c.name,
            "image": (attrs.get("Config", {}).get("Image") or "unknown"),
            "status": (state.get("Status") or c.status or "unknown").lower(),
            "running": bool(state.get("Running", False)),
            "oom_killed": bool(state.get("OOMKilled", False)),
            "pid": state.get("Pid", 0),
            "restart_count": int(attrs.get("RestartCount", 0)),
            "health": health,
            "started_at": state.get("StartedAt", ""),
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "memory_limit_mb": 0.0,
            "memory_percent": 0.0,
            "rx_mb": 0.0,
            "tx_mb": 0.0,
        }
        if include_stats and res["running"]:
            try:
                st = c.stats(stream=False)
                res["cpu_percent"] = _calc_cpu_pct(st)
                res.update(_calc_mem_stats(st))
                res.update(_calc_net_io(st))
            except Exception as exc:
                logger.debug("Stats error for %s: %s", container_name, exc)
        return res
    except NotFound:
        return {"exists": False, "status": "not_created", "running": False, "restart_count": 0}
    except Exception as exc:
        logger.debug("Inspect error for %s: %s", container_name, exc)
        return {"exists": False, "status": "error", "running": False, "restart_count": 0, "error": str(exc)}
    finally:
        client.close()


def list_containers(all_containers: bool = True, include_stats: bool = True) -> List[Dict[str, Any]]:
    """List Docker containers with real status, restart counts, and resource usage."""
    cache_key = (bool(all_containers), bool(include_stats))
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CONTAINERS_CACHE.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL_SEC:
            return copy.deepcopy(cached[1])

    client = _get_client()
    if not client:
        return []
    out: List[Dict[str, Any]] = []
    try:
        for c in client.containers.list(all=all_containers):
            try:
                if c.name.startswith("k8s_"):
                    continue
                attrs = c.attrs or {}
                labels = attrs.get("Config", {}).get("Labels") or {}
                if not labels.get("com.docker.compose.project") and c.name not in ALLOWED_SERVICES and not c.name.startswith("ues-"):
                    continue
                state = attrs.get("State", {})
                health = (state.get("Health") or {}).get("Status", "none")
                ports = []
                for k, v in (attrs.get("NetworkSettings", {}).get("Ports") or {}).items():
                    if v:
                        ports.append(f"{v[0].get('HostPort', '')}->{k}")
                    else:
                        ports.append(k)
                item = {
                    "id": c.short_id,
                    "name": c.name,
                    "image": (attrs.get("Config", {}).get("Image") or "unknown"),
                    "stack": (attrs.get("Config", {}).get("Labels") or {}).get("com.ues.stack", "other"),
                    "status": (state.get("Status") or c.status or "unknown").lower(),
                    "running": bool(state.get("Running", False)),
                    "health": health,
                    "oom_killed": bool(state.get("OOMKilled", False)),
                    "restart_count": int(attrs.get("RestartCount", 0)),
                    "started_at": state.get("StartedAt", ""),
                    "ports": ports,
                    "networks": list((attrs.get("NetworkSettings", {}).get("Networks") or {}).keys()),
                    "cpu_percent": 0.0,
                    "memory_mb": 0.0,
                    "memory_limit_mb": 0.0,
                    "memory_percent": 0.0,
                    "rx_mb": 0.0,
                    "tx_mb": 0.0,
                }
                out.append(item)
            except Exception as inner_exc:
                logger.debug("Skipping transient container: %s", inner_exc)

        if include_stats:
            running_items = [x for x in out if x["running"]]
            def _fetch_stat(item: Dict[str, Any]) -> None:
                c2 = _get_client()
                if not c2:
                    return
                try:
                    cont = c2.containers.get(item["name"])
                    st = cont.stats(stream=False)
                    item["cpu_percent"] = _calc_cpu_pct(st)
                    item.update(_calc_mem_stats(st))
                    item.update(_calc_net_io(st))
                except Exception:
                    pass
                finally:
                    c2.close()

            if running_items:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(24, len(running_items))) as pool:
                    list(pool.map(_fetch_stat, running_items))

        result = sorted(out, key=lambda x: (not x["running"], x["name"]))
        with _CACHE_LOCK:
            _CONTAINERS_CACHE[cache_key] = (time.monotonic(), copy.deepcopy(result))
        return result
    except Exception as exc:
        logger.error("Failed to list containers: %s", exc)
        return []
    finally:
        client.close()


def list_networks() -> List[Dict[str, Any]]:
    client = _get_client()
    if not client:
        return []
    try:
        nets = []
        for n in client.networks.list():
            attrs = n.attrs or {}
            nets.append(
                {
                    "id": n.short_id,
                    "name": n.name,
                    "driver": attrs.get("Driver", "bridge"),
                    "scope": attrs.get("Scope", "local"),
                    "containers": len(attrs.get("Containers") or {}),
                }
            )
        return nets
    except Exception:
        return []
    finally:
        client.close()


def list_volumes() -> List[Dict[str, Any]]:
    client = _get_client()
    if not client:
        return []
    try:
        vols = []
        for v in client.volumes.list():
            attrs = v.attrs or {}
            vols.append(
                {
                    "name": v.name,
                    "driver": attrs.get("Driver", "local"),
                    "mountpoint": attrs.get("Mountpoint", ""),
                    "created_at": attrs.get("CreatedAt", ""),
                }
            )
        return vols
    except Exception:
        return []
    finally:
        client.close()


def get_container_logs(container_name: str, tail: int = 120) -> List[str]:
    client = _get_client()
    if not client:
        return []
    try:
        c = client.containers.get(container_name)
        raw = c.logs(tail=max(10, min(tail, 500)), timestamps=True).decode("utf-8", errors="replace")
        return [line for line in raw.splitlines() if line.strip()]
    except Exception as exc:
        return [f"Error fetching logs for {container_name}: {exc}"]
    finally:
        client.close()


def container_action(container_name: str, action: str) -> Dict[str, Any]:
    """Perform safe lifecycle action (start/stop/restart) on an allowlisted container."""
    if action not in {"start", "stop", "restart"}:
        raise ValueError(f"Unsupported action '{action}'")
    if container_name not in ALLOWED_SERVICES and not container_name.startswith("ues-"):
        raise ValueError(f"Container '{container_name}' is not in the Unified Engineering Studio allowlist")

    client = _get_client()
    if not client:
        raise RuntimeError("Docker daemon unavailable")
    try:
        c = client.containers.get(container_name)
        if action == "start":
            c.start()
        elif action == "stop":
            c.stop(timeout=10)
        elif action == "restart":
            c.restart(timeout=10)
        c.reload()
        _invalidate_cache()
        return {"container": container_name, "action": action, "status": c.status}
    except NotFound:
        raise
    finally:
        client.close()


def compose_services_action(compose_services: List[str], action: str) -> Dict[str, Any]:
    """Run allowlisted docker compose up/stop/restart for service groups."""
    if action not in {"up", "stop", "restart"}:
        raise ValueError("Unsupported compose action")
    for svc in compose_services:
        if svc not in ALLOWED_SERVICES:
            raise ValueError(f"Service '{svc}' not allowlisted")

    if action == "up":
        cmd = ["docker", "compose", "up", "-d"] + compose_services
    elif action == "stop":
        cmd = ["docker", "compose", "stop"] + compose_services
    else:
        cmd = ["docker", "compose", "restart"] + compose_services

    res = subprocess.run(cmd, cwd=settings.COMPOSE_PROJECT_DIR, capture_output=True, text=True, timeout=90)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or "docker compose failed")
    _invalidate_cache()
    return {"services": compose_services, "action": action, "stdout": res.stdout.strip()}


STACK_SERVICES = {
    "stack-core": ["portal-backend", "portal-frontend", "postgres-dw", "prometheus"],
    "profile-core": ["portal-backend", "portal-frontend", "postgres-dw", "prometheus"],
    "stack-de": ["minio", "mc", "spark-processing", "rest", "airflow-webserver", "airflow-scheduler", "pgadmin", "redpanda", "redpanda-console", "rabbitmq"],
    "profile-data-engineering": ["minio", "mc", "spark-processing", "rest", "airflow-webserver", "airflow-scheduler", "pgadmin", "redpanda", "redpanda-console", "rabbitmq"],
    "stack-sre": ["grafana", "loki", "promtail", "tempo", "alertmanager", "data-generator", "practice-lab"],
    "profile-sre": ["grafana", "loki", "promtail", "tempo", "alertmanager", "data-generator", "practice-lab"],
}


def compose_profile_action(profile: str, action: str) -> Dict[str, Any]:
    """Start or stop the Unified Stack, Data Engineering Stack, or SRE Stack."""
    if action not in {"up", "stop"}:
        raise ValueError("Action must be 'up' or 'stop'")

    if profile in ("stack-all", "unified"):
        cmd = ["docker", "compose", "up", "-d"] if action == "up" else ["docker", "compose", "stop"]
    elif profile in STACK_SERVICES:
        svcs = STACK_SERVICES[profile]
        cmd = (["docker", "compose", "up", "-d"] + svcs) if action == "up" else (["docker", "compose", "stop"] + svcs)
    elif profile in ALLOWED_COMPOSE_PROFILES:
        cmd = ["docker", "compose", "--profile", profile, "up", "-d"] if action == "up" else ["docker", "compose", "--profile", profile, "stop"]
    else:
        raise ValueError(f"Unknown stack or profile '{profile}'")

    res = subprocess.run(cmd, cwd=settings.COMPOSE_PROJECT_DIR, capture_output=True, text=True, timeout=180)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or "docker compose stack command failed")
    _invalidate_cache()
    return {"profile": profile, "action": action, "stdout": res.stdout.strip()}

