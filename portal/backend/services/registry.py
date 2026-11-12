"""Shared Service Registry — Single Source of Truth for Discovery, Health, Lifecycle & Metrics."""

import concurrent.futures
import logging
import socket
import threading
import time
from typing import Any, Dict, List, Optional

import httpx
from prometheus_client import Gauge

from core.config import settings
from services import docker_mgr

logger = logging.getLogger("ues.registry")

# Prometheus Metrics exported for all registered services
UES_SERVICE_UP = Gauge("ues_service_up", "1 if service is healthy else 0", ["service_id", "category", "profile"])
UES_CONTAINER_CPU = Gauge("ues_container_cpu_percent", "Container CPU usage percent", ["service_id", "container_name"])
UES_CONTAINER_MEM_MB = Gauge("ues_container_memory_mb", "Container working memory MB", ["service_id", "container_name"])
UES_CONTAINER_MEM_PCT = Gauge("ues_container_memory_percent", "Container memory percent of limit", ["service_id", "container_name"])
UES_CONTAINER_RESTARTS = Gauge("ues_container_restarts_total", "Container restart count", ["service_id", "container_name"])


# Canonical Registry Catalog (19 unified components across 3 hardware profiles)
SERVICE_CATALOG: List[Dict[str, Any]] = [
    {
        "service_id": "portal-backend",
        "service_name": "Unified Control Plane (FastAPI)",
        "category": "platform",
        "container_name": "portal-backend",
        "compose_services": ["portal-backend"],
        "profile": "profile-core",
        "internal_endpoint": "http://portal-backend:8000",
        "external_endpoint": "http://localhost:8000",
        "health_check_endpoint": "http://127.0.0.1:8000/api/v1/health/live",
        "tcp_host": "127.0.0.1",
        "tcp_port": 8000,
        "dependencies": ["postgres-dw"],
        "owner": "Platform Engineering",
        "criticality": "critical",
        "associated_slo": "slo-api-availability",
        "monitoring_config": {"scrape_target": "portal-backend:8000/metrics", "interval": "10s"},
        "ui_url": "http://localhost:8000/docs",
        "legacy_key": None,
    },
    {
        "service_id": "portal-frontend",
        "service_name": "Unified Engineering Studio UI",
        "category": "platform",
        "container_name": "portal-frontend",
        "compose_services": ["portal-frontend"],
        "profile": "profile-core",
        "internal_endpoint": "http://portal-frontend:5173",
        "external_endpoint": "http://localhost:5173",
        "health_check_endpoint": "http://portal-frontend:5173/",
        "tcp_host": "portal-frontend",
        "tcp_port": 5173,
        "dependencies": ["portal-backend"],
        "owner": "Platform Engineering",
        "criticality": "critical",
        "associated_slo": "slo-api-availability",
        "monitoring_config": {"probe": "http_get"},
        "ui_url": "http://localhost:5173",
        "legacy_key": None,
    },
    {
        "service_id": "postgres-dw",
        "service_name": "PostgreSQL 16 Data Warehouse",
        "category": "warehouse",
        "container_name": "postgres-dw",
        "compose_services": ["postgres-dw"],
        "profile": "profile-core",
        "internal_endpoint": "postgres-dw:5432",
        "external_endpoint": "localhost:5432",
        "health_check_endpoint": "tcp://postgres-dw:5432",
        "tcp_host": "postgres-dw",
        "tcp_port": 5432,
        "dependencies": [],
        "owner": "Data Warehouse + DB SRE",
        "criticality": "critical",
        "associated_slo": "slo-db-availability",
        "monitoring_config": {"probe": "pg_isready_and_sql"},
        "ui_url": "http://localhost:5173/services/synapse/",
        "legacy_key": "synapse",
    },
    {
        "service_id": "pgadmin",
        "service_name": "pgAdmin 4 (Synapse SQL UI)",
        "category": "warehouse",
        "container_name": "pgadmin",
        "compose_services": ["pgadmin"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "http://pgadmin:80",
        "external_endpoint": "http://localhost:5050",
        "health_check_endpoint": "http://pgadmin:80/services/synapse/misc/ping",
        "tcp_host": "pgadmin",
        "tcp_port": 80,
        "dependencies": ["postgres-dw"],
        "owner": "Data Engineering",
        "criticality": "medium",
        "associated_slo": "slo-db-availability",
        "monitoring_config": {"probe": "http_get"},
        "ui_url": "http://localhost:5173/services/synapse/",
        "legacy_key": None,
    },
    {
        "service_id": "minio",
        "service_name": "MinIO S3 Data Lake (ADLS Gen2)",
        "category": "storage",
        "container_name": "minio",
        "compose_services": ["minio", "mc"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "http://minio:9000",
        "external_endpoint": "http://localhost:9001",
        "health_check_endpoint": "http://minio:9000/minio/health/live",
        "tcp_host": "minio",
        "tcp_port": 9000,
        "dependencies": [],
        "owner": "Data Lakehouse Team",
        "criticality": "critical",
        "associated_slo": "slo-data-freshness",
        "monitoring_config": {"probe": "minio_health_live"},
        "ui_url": "http://localhost:5173/services/datalake/",
        "legacy_key": "datalake",
    },
    {
        "service_id": "spark-processing",
        "service_name": "Apache Spark 4.2 + Delta + JupyterLab",
        "category": "compute",
        "container_name": "spark-processing",
        "compose_services": ["spark-processing", "rest"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "http://spark-processing:8888",
        "external_endpoint": "http://localhost:8888",
        "health_check_endpoint": "http://spark-processing:8888/services/databricks/api",
        "tcp_host": "spark-processing",
        "tcp_port": 8888,
        "dependencies": ["minio", "iceberg-rest"],
        "owner": "Data Platform Eng",
        "criticality": "high",
        "associated_slo": "slo-spark-success",
        "monitoring_config": {"spark_ui": "http://spark-processing:4040/api/v1/applications"},
        "ui_url": "http://localhost:5173/services/databricks/",
        "legacy_key": "databricks",
    },
    {
        "service_id": "iceberg-rest",
        "service_name": "Apache Iceberg REST Catalog",
        "category": "compute",
        "container_name": "iceberg-rest",
        "compose_services": ["rest"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "http://rest:8181",
        "external_endpoint": "http://localhost:8181",
        "health_check_endpoint": "http://rest:8181/v1/config",
        "tcp_host": "rest",
        "tcp_port": 8181,
        "dependencies": ["minio"],
        "owner": "Data Lakehouse Team",
        "criticality": "high",
        "associated_slo": "slo-data-freshness",
        "monitoring_config": {"probe": "iceberg_v1_config"},
        "ui_url": "http://localhost:8181/v1/config",
        "legacy_key": None,
    },
    {
        "service_id": "airflow-webserver",
        "service_name": "Apache Airflow 2.9 Webserver",
        "category": "orchestration",
        "container_name": "airflow-webserver",
        "compose_services": ["airflow-webserver", "airflow-scheduler"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "http://airflow-webserver:8080/services/airflow",
        "external_endpoint": "http://localhost:8085",
        "health_check_endpoint": "http://airflow-webserver:8080/services/airflow/health",
        "tcp_host": "airflow-webserver",
        "tcp_port": 8080,
        "dependencies": ["postgres-dw", "minio"],
        "owner": "Data Orchestration",
        "criticality": "high",
        "associated_slo": "slo-airflow-success",
        "monitoring_config": {"probe": "airflow_health"},
        "ui_url": "http://localhost:5173/services/airflow/",
        "legacy_key": "airflow",
    },
    {
        "service_id": "airflow-scheduler",
        "service_name": "Apache Airflow Scheduler",
        "category": "orchestration",
        "container_name": "airflow-scheduler",
        "compose_services": ["airflow-scheduler"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "airflow-scheduler",
        "external_endpoint": "http://localhost:8085",
        "health_check_endpoint": "http://airflow-webserver:8080/services/airflow/health",
        "tcp_host": "airflow-webserver",
        "tcp_port": 8080,
        "dependencies": ["airflow-webserver", "postgres-dw"],
        "owner": "Data Orchestration",
        "criticality": "high",
        "associated_slo": "slo-pipeline-latency",
        "monitoring_config": {"probe": "docker_and_scheduler_heartbeat"},
        "ui_url": "http://localhost:5173/services/airflow/",
        "legacy_key": None,
    },
    {
        "service_id": "redpanda",
        "service_name": "Redpanda Kafka-Compatible Broker",
        "category": "streaming",
        "container_name": "redpanda",
        "compose_services": ["redpanda", "redpanda-console"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "redpanda:9092",
        "external_endpoint": "localhost:9092",
        "health_check_endpoint": "http://redpanda:9644/v1/status/ready",
        "tcp_host": "redpanda",
        "tcp_port": 9092,
        "dependencies": [],
        "owner": "Streaming Platform",
        "criticality": "high",
        "associated_slo": "slo-kafka-lag",
        "monitoring_config": {"scrape_target": "redpanda:9644/public_metrics"},
        "ui_url": "http://localhost:5173/services/eventhub/",
        "legacy_key": "eventhub",
    },
    {
        "service_id": "redpanda-console",
        "service_name": "Redpanda Console (Event Hub UI)",
        "category": "streaming",
        "container_name": "redpanda-console",
        "compose_services": ["redpanda-console"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "http://redpanda-console:8080",
        "external_endpoint": "http://localhost:8081",
        "health_check_endpoint": "http://redpanda-console:8080/services/eventhub/",
        "tcp_host": "redpanda-console",
        "tcp_port": 8080,
        "dependencies": ["redpanda"],
        "owner": "Streaming Platform",
        "criticality": "medium",
        "associated_slo": "slo-kafka-lag",
        "monitoring_config": {"probe": "http_get"},
        "ui_url": "http://localhost:5173/services/eventhub/",
        "legacy_key": None,
    },
    {
        "service_id": "rabbitmq",
        "service_name": "RabbitMQ AMQP Broker (Service Bus)",
        "category": "messaging",
        "container_name": "rabbitmq",
        "compose_services": ["rabbitmq"],
        "profile": "profile-data-engineering",
        "internal_endpoint": "amqp://rabbitmq:5672",
        "external_endpoint": "http://localhost:15672",
        "health_check_endpoint": "http://rabbitmq:15692/metrics",
        "tcp_host": "rabbitmq",
        "tcp_port": 5672,
        "dependencies": [],
        "owner": "Messaging SRE",
        "criticality": "high",
        "associated_slo": "slo-response-time",
        "monitoring_config": {"scrape_target": "rabbitmq:15692/metrics"},
        "ui_url": "http://localhost:5173/services/servicebus/",
        "legacy_key": "servicebus",
    },
    {
        "service_id": "prometheus",
        "service_name": "Prometheus Time-Series Engine",
        "category": "observability",
        "container_name": "prometheus",
        "compose_services": ["prometheus"],
        "profile": "profile-core",
        "internal_endpoint": "http://prometheus:9090",
        "external_endpoint": "http://localhost:9090",
        "health_check_endpoint": "http://prometheus:9090/-/ready",
        "tcp_host": "prometheus",
        "tcp_port": 9090,
        "dependencies": [],
        "owner": "Observability SRE",
        "criticality": "critical",
        "associated_slo": "slo-api-availability",
        "monitoring_config": {"scrape_target": "prometheus:9090/metrics"},
        "ui_url": "http://localhost:9090",
        "legacy_key": None,
    },
    {
        "service_id": "grafana",
        "service_name": "Grafana Unified Dashboards",
        "category": "observability",
        "container_name": "grafana",
        "compose_services": ["grafana"],
        "profile": "profile-sre",
        "internal_endpoint": "http://grafana:3000",
        "external_endpoint": "http://localhost:3010",
        "health_check_endpoint": "http://grafana:3000/services/monitoring/api/health",
        "tcp_host": "grafana",
        "tcp_port": 3000,
        "dependencies": ["prometheus"],
        "owner": "Observability SRE",
        "criticality": "high",
        "associated_slo": "slo-api-availability",
        "monitoring_config": {"probe": "grafana_api_health"},
        "ui_url": "http://localhost:5173/services/monitoring/",
        "legacy_key": "monitoring",
    },
    {
        "service_id": "loki",
        "service_name": "Grafana Loki Centralized Logging",
        "category": "observability",
        "container_name": "loki",
        "compose_services": ["loki"],
        "profile": "profile-sre",
        "internal_endpoint": "http://loki:3100",
        "external_endpoint": "http://localhost:3100",
        "health_check_endpoint": "http://loki:3100/ready",
        "tcp_host": "loki",
        "tcp_port": 3100,
        "dependencies": [],
        "owner": "Observability SRE",
        "criticality": "medium",
        "associated_slo": "slo-response-time",
        "monitoring_config": {"scrape_target": "loki:3100/metrics"},
        "ui_url": "http://localhost:3100/ready",
        "legacy_key": None,
    },
    {
        "service_id": "tempo",
        "service_name": "Grafana Tempo Distributed Tracing",
        "category": "observability",
        "container_name": "tempo",
        "compose_services": ["tempo"],
        "profile": "profile-sre",
        "internal_endpoint": "http://tempo:3200",
        "external_endpoint": "http://localhost:3200",
        "health_check_endpoint": "http://tempo:3200/ready",
        "tcp_host": "tempo",
        "tcp_port": 3200,
        "dependencies": [],
        "owner": "Observability SRE",
        "criticality": "medium",
        "associated_slo": "slo-response-time",
        "monitoring_config": {"otlp_http": "tempo:4318"},
        "ui_url": "http://localhost:3200/ready",
        "legacy_key": None,
    },
    {
        "service_id": "alertmanager",
        "service_name": "Prometheus Alertmanager",
        "category": "observability",
        "container_name": "alertmanager",
        "compose_services": ["alertmanager"],
        "profile": "profile-sre",
        "internal_endpoint": "http://alertmanager:9093",
        "external_endpoint": "http://localhost:9093",
        "health_check_endpoint": "http://alertmanager:9093/-/ready",
        "tcp_host": "alertmanager",
        "tcp_port": 9093,
        "dependencies": ["prometheus"],
        "owner": "Observability SRE",
        "criticality": "high",
        "associated_slo": "slo-api-availability",
        "monitoring_config": {"webhook": "/api/v1/incidents/webhook/alertmanager"},
        "ui_url": "http://localhost:9093",
        "legacy_key": None,
    },
    {
        "service_id": "data-generator",
        "service_name": "SRE Telemetry & Chaos Target",
        "category": "sre",
        "container_name": "data-generator",
        "compose_services": ["data-generator"],
        "profile": "profile-sre",
        "internal_endpoint": "http://data-generator:8000",
        "external_endpoint": "http://localhost:8001",
        "health_check_endpoint": "http://data-generator:8000/health",
        "tcp_host": "data-generator",
        "tcp_port": 8000,
        "dependencies": ["redpanda"],
        "owner": "Chaos & Reliability Eng",
        "criticality": "medium",
        "associated_slo": "slo-app-availability",
        "monitoring_config": {"scrape_target": "data-generator:8000/metrics"},
        "ui_url": "http://localhost:8001/health",
        "legacy_key": None,
    },
    {
        "service_id": "practice-lab",
        "service_name": "SRE & DevOps Command Sandbox",
        "category": "sre",
        "container_name": "practice-lab",
        "compose_services": ["practice-lab"],
        "profile": "profile-sre",
        "internal_endpoint": "http://practice-lab:8090",
        "external_endpoint": "http://localhost:8090",
        "health_check_endpoint": "http://practice-lab:8090/status",
        "tcp_host": "practice-lab",
        "tcp_port": 8090,
        "dependencies": [],
        "owner": "SRE Practice Lab",
        "criticality": "low",
        "associated_slo": "slo-api-availability",
        "monitoring_config": {"probe": "http_get"},
        "ui_url": "http://localhost:8090/status",
        "legacy_key": None,
    },
]

_REGISTRY_LOCK = threading.Lock()
_REGISTRY_STATE: Dict[str, Dict[str, Any]] = {}


def _tcp_probe(host: str, port: int, timeout: float = 0.25) -> bool:
    for candidate in (host, "127.0.0.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((candidate, port))
                return True
        except OSError:
            continue
    return False


def _http_probe(url: str, timeout: float = 0.8) -> Optional[int]:
    if not url or not url.startswith("http"):
        return None
    try:
        with httpx.Client(timeout=timeout, verify=False) as client:
            resp = client.get(url)
            return resp.status_code
    except Exception:
        return None


def _probe_single_service(spec: Dict[str, Any], containers_map: Dict[str, Dict[str, Any]], now: int) -> Dict[str, Any]:
    sid = spec["service_id"]
    cname = spec["container_name"]
    c_info = containers_map.get(cname)

    docker_running = bool(c_info and c_info.get("running"))
    docker_exists = c_info is not None
    docker_status = c_info.get("status", "not_created") if c_info else "not_created"
    restarts = int(c_info.get("restart_count", 0)) if c_info else 0
    cpu_pct = float(c_info.get("cpu_percent", 0.0)) if c_info else 0.0
    mem_mb = float(c_info.get("memory_mb", 0.0)) if c_info else 0.0
    mem_limit_mb = float(c_info.get("memory_limit_mb", 0.0)) if c_info else 0.0
    mem_pct = float(c_info.get("memory_percent", 0.0)) if c_info else 0.0

    # Probe TCP/HTTP only when container is running or absent (local mode); stopped containers are already known down
    if sid == "portal-backend":
        tcp_ok, http_code = True, 200
    elif docker_exists and not docker_running:
        tcp_ok, http_code = False, None
    else:
        tcp_ok = _tcp_probe(spec["tcp_host"], spec["tcp_port"])
        http_code = _http_probe(spec["health_check_endpoint"]) if (tcp_ok and spec["health_check_endpoint"].startswith("http")) else None

    if sid == "portal-backend":
        status = "healthy"
        lifecycle = "MONITORING"
        probe_detail = "Control plane responding"
    elif docker_running and (http_code is None or 200 <= http_code < 400) and tcp_ok:
        if restarts >= 3 or (c_info and c_info.get("oom_killed")) or mem_pct > 90.0:
            status = "degraded"
            lifecycle = "ALERTING"
            probe_detail = f"Running with pressure (restarts={restarts}, mem={mem_pct}%)"
        else:
            status = "healthy"
            lifecycle = "MONITORING"
            probe_detail = "Docker UP + probe OK" + (f" (HTTP {http_code})" if http_code else " (TCP OK)")
    elif docker_running and not tcp_ok:
        status = "degraded"
        lifecycle = "HEALTH_CHECKING"
        probe_detail = "Container running; health endpoint not yet ready"
    elif docker_running and http_code is not None and http_code >= 400:
        status = "degraded"
        lifecycle = "ALERTING"
        probe_detail = f"Container running; health probe returned HTTP {http_code}"
    elif not docker_exists and tcp_ok:
        status = "healthy"
        lifecycle = "MONITORING"
        probe_detail = "Host/local endpoint reachable"
    elif docker_exists and not docker_running:
        status = "unavailable"
        lifecycle = "ALERTING" if spec["criticality"] == "critical" else "REGISTERED"
        probe_detail = f"Container state: {docker_status}"
    else:
        status = "unavailable"
        lifecycle = "REGISTERED"
        probe_detail = "Service profile not started"

    entry = {
        **spec,
        "status": status,
        "lifecycle_state": lifecycle,
        "probe_detail": probe_detail,
        "http_status": http_code,
        "tcp_reachable": tcp_ok,
        "docker_exists": docker_exists,
        "docker_status": docker_status,
        "cpu_utilization_pct": cpu_pct,
        "memory_utilization_mb": mem_mb,
        "memory_limit_mb": mem_limit_mb,
        "memory_utilization_pct": mem_pct,
        "restart_count": restarts,
        "oom_killed": bool(c_info.get("oom_killed", False)) if c_info else False,
        "last_checked_at": now,
    }

    UES_SERVICE_UP.labels(service_id=sid, category=spec["category"], profile=spec["profile"]).set(1 if status == "healthy" else 0)
    UES_CONTAINER_CPU.labels(service_id=sid, container_name=cname).set(cpu_pct)
    UES_CONTAINER_MEM_MB.labels(service_id=sid, container_name=cname).set(mem_mb)
    UES_CONTAINER_MEM_PCT.labels(service_id=sid, container_name=cname).set(mem_pct)
    UES_CONTAINER_RESTARTS.labels(service_id=sid, container_name=cname).set(restarts)

    with _REGISTRY_LOCK:
        _REGISTRY_STATE[sid] = entry
    return entry


def refresh_registry(include_stats: bool = True) -> List[Dict[str, Any]]:
    """Run real parallel DISCOVER -> REGISTER -> HEALTH CHECK -> MONITOR lifecycle across all services."""
    containers_map = {c["name"]: c for c in docker_mgr.list_containers(all_containers=True, include_stats=include_stats)}
    now = int(time.time())
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda sp: _probe_single_service(sp, containers_map, now), SERVICE_CATALOG))
    return results


def get_cached_registry() -> List[Dict[str, Any]]:
    with _REGISTRY_LOCK:
        if _REGISTRY_STATE:
            return [ _REGISTRY_STATE[s["service_id"]] for s in SERVICE_CATALOG if s["service_id"] in _REGISTRY_STATE ]
    return refresh_registry(include_stats=True)


def get_service(service_id: str) -> Optional[Dict[str, Any]]:
    items = get_cached_registry()
    for item in items:
        if item["service_id"] == service_id or item.get("legacy_key") == service_id:
            return item
    return None


def get_legacy_services_map() -> Dict[str, Any]:
    """Maintain backward compatibility with original DE portal `/api/services` response shape."""
    items = refresh_registry(include_stats=True)
    legacy = {}
    for item in items:
        key = item.get("legacy_key")
        if not key:
            continue
        legacy[key] = {
            "name": item["service_name"],
            "container_name": item["container_name"],
            "status": "online" if item["status"] == "healthy" else ("degraded" if item["status"] == "degraded" else "offline"),
            "cpu_usage": f"{item['cpu_utilization_pct']}%",
            "memory_usage": f"{item['memory_utilization_mb']} MB",
            "memory_limit": f"{item['memory_limit_mb']} MB" if item["memory_limit_mb"] else "N/A",
            "memory_percent": f"{item['memory_utilization_pct']}%",
            "ui_url": item["ui_url"],
        }
    return legacy

