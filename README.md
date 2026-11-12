# Unified Engineering Studio — Data Engineering + SRE + AIOps Platform

An integrated, enterprise-style **Unified Engineering Studio** consolidating **Data Engineering** (`Riyaz_DE_platform`) and **SRE / AIOps** (`ahmed_aiops`) into a single React + FastAPI control plane, shared service registry, unified authentication/RBAC, centralized observability, and Apple Silicon M4 (8 GB RAM) resource-profiled Docker Compose + Kubernetes architecture.

---

## Architecture Principle

```
One React + Vite Frontend (:5173)
  -> One Authentication & PBKDF2 / Bearer JWT RBAC Layer
  -> One Modular FastAPI Control Plane (:8000 /api/v1/*)
  -> One Shared Service Registry (DISCOVER -> REGISTER -> HEALTH CHECK -> MONITOR -> ALERT -> RECOVER)
  -> Shared Infrastructure (No duplicated Postgres, Kafka/Redpanda, Spark, or Grafana)
  -> Data Engineering + SRE + Kubernetes + FinOps + AIOps Workloads
  -> Centralized Observability (Prometheus + Grafana + Loki + Tempo + OpenTelemetry + Alertmanager)
```

---

## 3 Execution Profiles (Apple Silicon M4 8 GB RAM Constraint)

| Profile | Command | Services Included | Memory Limit Sum |
| :--- | :--- | :--- | :--- |
| **Profile 1: Core** (default) | `docker compose up -d` | `portal-frontend`, `portal-backend`, `postgres-dw`, `prometheus` | ~1,152 MB |
| **Profile 2: Data Engineering** | `docker compose --profile profile-data-engineering up -d` | `minio`, `mc`, `spark-processing`, `rest` (Iceberg), `airflow-webserver`, `airflow-scheduler`, `pgadmin`, `redpanda`, `redpanda-console`, `rabbitmq` + Core | ~4,160 MB |
| **Profile 3: SRE & Kubernetes** | `docker compose --profile profile-sre up -d` | `grafana`, `loki`, `promtail`, `tempo`, `alertmanager`, `data-generator`, `practice-lab` (+ Host OrbStack/k3d/kind K8s) + Core | ~2,016 MB |

Backward-compatible granular DE profiles (`profile-storage`, `profile-processing`, `profile-orchestration`, `profile-warehouse`, `profile-streaming`, `profile-monitoring`) are also preserved.

---

## Quick Start

1. **Configure environment:**
   ```bash
   cp .env.example .env
   # Review and change UES_AUTH_SECRET, GRAFANA_ADMIN_PASSWORD, POSTGRES_PASSWORD, etc.
   ```

2. **Bootstrap Core Profile (Profile 1):**
   ```bash
   ./init-lab.sh core
   ```

3. **Optionally start Data Engineering (Profile 2) or SRE/Observability (Profile 3):**
   ```bash
   ./init-lab.sh data-engineering
   # or
   ./init-lab.sh sre
   ```

4. **Access the Studio:**
   - **Unified Engineering Studio UI:** `http://localhost:5173`
   - **Control Plane OpenAPI Docs:** `http://localhost:8000/docs`
   - **Prometheus:** `http://localhost:9090`
   - **Grafana (Profile 3, auth required):** `http://localhost:3010/services/monitoring/`

---

## Troubleshooting

- **Docker daemon not running:** Start OrbStack or Docker Desktop before running `./init-lab.sh`.
- **Kubernetes shows `disabled` or `unreachable`:** Enable Kubernetes in OrbStack (`orbctl start k8s`) or start a `k3d`/`kind` cluster; Docker Compose workflows continue normally without Kubernetes.
- **High memory usage on 8 GB MacBook:** Stop unused profiles via `docker compose --profile profile-data-engineering stop` or use the Profile Manager in **Overview** / **FinOps**.
- **Grafana login:** Anonymous admin access is disabled by design. Sign in using `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` from `.env`.
