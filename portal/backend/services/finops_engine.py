"""FinOps & Capacity Management Engine — Real container/K8s/storage utilization, cost model, & M4 8GB profiles."""

import time
from typing import Any, Dict, List

from core import database
from core.config import settings
from services import de_client, docker_mgr, k8s_mgr, registry


EXECUTION_PROFILES: List[Dict[str, Any]] = [
    {
        "id": "profile-core",
        "name": "Profile 1: Core Control Plane",
        "description": "Frontend, FastAPI Control Plane, PostgreSQL DW, and lightweight Prometheus.",
        "services": ["portal-frontend", "portal-backend", "postgres-dw", "prometheus"],
        "estimated_limit_mb": 896,
        "recommended_for": "Daily control plane, SQL Studio, Service Registry & Kubernetes inspection on 8 GB RAM.",
    },
    {
        "id": "profile-data-engineering",
        "name": "Profile 2: Data Engineering Studio",
        "description": "MinIO Data Lake, Spark 4.2 + Delta + Iceberg + JupyterLab, Airflow, PostgreSQL DW, Redpanda, RabbitMQ.",
        "services": ["minio", "mc", "spark-processing", "rest", "airflow-webserver", "airflow-scheduler", "postgres-dw", "pgadmin", "redpanda", "redpanda-console", "rabbitmq", "prometheus"],
        "estimated_limit_mb": 4352,
        "recommended_for": "TPC-H Medallion pipelines, PySpark 4.2, Delta MERGE, Airflow DAGs, Kafka & RabbitMQ labs.",
    },
    {
        "id": "profile-sre",
        "name": "Profile 3: SRE, Observability & Kubernetes Lab",
        "description": "Prometheus, Grafana, Loki, Tempo, Alertmanager, SRE Telemetry/Chaos Target & Practice Sandbox (+ Host K8s).",
        "services": ["prometheus", "grafana", "loki", "tempo", "alertmanager", "data-generator", "practice-lab"],
        "estimated_limit_mb": 1280,
        "recommended_for": "SLO/error-budget drills, PromQL/Loki/Tempo investigations, Chaos Engineering & Kubernetes labs.",
    },
]


def get_finops_overview() -> Dict[str, Any]:
    """Compute real measured CPU/RAM/Network/Storage usage, idle resources, cost estimation, and capacity forecast."""
    services = registry.get_cached_registry()
    containers = docker_mgr.list_containers(all_containers=True, include_stats=True)
    k8s = k8s_mgr.get_cluster_overview()
    minio = de_client.get_minio_summary()
    pg = de_client.get_postgres_status_and_schemas()

    running = [c for c in containers if c.get("running")]
    total_cpu_pct = round(sum(float(c.get("cpu_percent", 0.0)) for c in running), 2)
    total_mem_mb = round(sum(float(c.get("memory_mb", 0.0)) for c in running), 1)
    total_limit_mb = round(sum(float(c.get("memory_limit_mb", 0.0)) for c in running), 1)
    total_rx_mb = round(sum(float(c.get("rx_mb", 0.0)) for c in running), 2)
    total_tx_mb = round(sum(float(c.get("tx_mb", 0.0)) for c in running), 2)

    storage_mb = round(minio.get("total_size_mb", 0.0) + pg.get("size_mb", 0.0), 2)
    storage_gb = round(storage_mb / 1024.0, 4)

    # Service-wise cost estimation based on actual measured memory & CPU utilization
    service_costs = []
    idle_resources = []
    total_hourly_usd = 0.0

    for c in running:
        mem_gb = float(c.get("memory_mb", 0.0)) / 1024.0
        # Approximate vCPU usage from percentage (100% = 1 vCPU)
        vcpu_used = max(0.05, float(c.get("cpu_percent", 0.0)) / 100.0)
        hourly = round((vcpu_used * settings.COST_PER_VCPU_HOUR) + (mem_gb * settings.COST_PER_GB_RAM_HOUR), 5)
        monthly = round(hourly * 24 * 30, 2)
        total_hourly_usd += hourly

        service_costs.append(
            {
                "service": c["name"],
                "cpu_percent": c["cpu_percent"],
                "memory_mb": c["memory_mb"],
                "memory_limit_mb": c["memory_limit_mb"],
                "memory_percent": c["memory_percent"],
                "network_rx_mb": c["rx_mb"],
                "network_tx_mb": c["tx_mb"],
                "estimated_hourly_usd": hourly,
                "estimated_monthly_usd": monthly,
            }
        )

        # Idle resource identification: running non-core containers consuming <0.3% CPU and >100MB RAM
        if c["name"] not in ("portal-backend", "portal-frontend", "prometheus") and c["cpu_percent"] < 0.3 and c["memory_mb"] > 100.0:
            idle_resources.append(
                {
                    "container": c["name"],
                    "cpu_percent": c["cpu_percent"],
                    "memory_mb": c["memory_mb"],
                    "recommendation": f"Stop '{c['name']}' when not actively running workloads to reclaim {c['memory_mb']} MB RAM (~${monthly}/mo cloud equivalent).",
                }
            )

    storage_monthly_usd = round(storage_gb * settings.COST_PER_GB_STORAGE_MONTH, 4)
    total_monthly_usd = round(total_hourly_usd * 24 * 30 + storage_monthly_usd, 2)

    # 8 GB MacBook M4 Capacity Guardrail (target safe container working set <= 5120 MB leaving 3 GB for macOS)
    mac_budget_mb = 5120.0
    headroom_mb = round(max(0.0, mac_budget_mb - total_mem_mb), 1)
    budget_pct = round((total_mem_mb / mac_budget_mb) * 100.0, 1)

    # Active profile inference
    running_names = {c["name"] for c in running}
    profile_status = []
    for prof in EXECUTION_PROFILES:
        active_in_prof = [s for s in prof["services"] if s in running_names]
        profile_status.append(
            {
                **prof,
                "active_count": len(active_in_prof),
                "total_count": len(prof["services"]),
                "active_services": active_in_prof,
                "state": "active" if len(active_in_prof) == len(prof["services"]) else ("partial" if active_in_prof else "stopped"),
            }
        )

    # Simple capacity forecast based on current utilization
    forecast = {
        "current_ram_mb": total_mem_mb,
        "safe_ram_ceiling_mb": mac_budget_mb,
        "ram_headroom_mb": headroom_mb,
        "ram_budget_used_pct": budget_pct,
        "status": "critical" if budget_pct > 90 else ("warning" if budget_pct > 75 else "healthy"),
        "projected_30d_storage_mb": round(storage_mb * 1.25, 2),
        "recommendation": (
            "Memory exceeds 8 GB MacBook safe container ceiling; stop idle DE/SRE profiles."
            if budget_pct > 90
            else "Operating comfortably within Apple Silicon M4 8 GB RAM headroom."
        ),
    }

    return {
        "measured_at": int(time.time()),
        "hardware_target": "Apple Silicon M4 (8 GB RAM constraint)",
        "allocation": {
            "running_containers": len(running),
            "total_containers": len(containers),
            "total_cpu_percent": total_cpu_pct,
            "total_memory_mb": total_mem_mb,
            "total_memory_limit_mb": total_limit_mb,
            "network_rx_mb": total_rx_mb,
            "network_tx_mb": total_tx_mb,
            "storage_mb": storage_mb,
        },
        "kubernetes": {
            "connected": k8s.get("connected", False),
            "nodes": k8s.get("nodes", []),
            "pods_total": k8s.get("summary", {}).get("pods_total", 0),
        },
        "cost_model": {
            "rates": {
                "vcpu_hour_usd": settings.COST_PER_VCPU_HOUR,
                "gb_ram_hour_usd": settings.COST_PER_GB_RAM_HOUR,
                "gb_storage_month_usd": settings.COST_PER_GB_STORAGE_MONTH,
            },
            "estimated_hourly_usd": round(total_hourly_usd, 4),
            "estimated_monthly_usd": total_monthly_usd,
            "storage_monthly_usd": storage_monthly_usd,
            "service_breakdown": sorted(service_costs, key=lambda x: x["estimated_monthly_usd"], reverse=True),
            "budget_items": database.get_cost_items(),
        },
        "idle_resources": idle_resources,
        "profiles": profile_status,
        "forecast": forecast,
    }

