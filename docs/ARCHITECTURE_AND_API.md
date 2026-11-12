# Unified Engineering Studio — Architecture, API & Operations Guide

## 1. Repository Consolidation Summary

| Capability | Primary (`Riyaz_DE_platform`) | Secondary (`ahmed_aiops`) | Unified Studio Resolution |
| :--- | :--- | :--- | :--- |
| Frontend UI | React + Vite (`portal/frontend`) | Static HTML/JS (`ai_agent/static`) | Single React + Vite Apple Pro UI with 8 domains (`Overview`, `Data Engineering`, `Streaming`, `Infrastructure`, `Observability`, `SRE Ops`, `FinOps`, `AIOps`) |
| Backend Control Plane | FastAPI (`portal/backend/main.py`) | FastAPI (`ai_agent/agent.py`) | Modular FastAPI routers (`/api/v1/*`) + legacy compatibility endpoints |
| Auth & RBAC | Plaintext `users.json` + header check | None (localhost-bound) | PBKDF2-HMAC-SHA256 password hashing + HMAC-SHA256 Bearer JWT + RBAC + Audit Log |
| Kafka / Streaming | Redpanda + Console (256M) | Confluent Kafka (1G) | Consolidated on Redpanda (`redpanda:9092`) |
| Apache Spark | Spark 4.2 + Delta 4.0 + Iceberg + Jupyter | Spark 3.5 master/worker/submitter (3.5G) | Consolidated on `spark-processing` (Spark 4.2 + Delta 4.0 + Iceberg) |
| Observability | Grafana (anon admin) | Prometheus + Grafana + Fluentd | Prometheus + Grafana (auth-enforced, 9 provisioned dashboards) + Loki + Promtail + Tempo + OpenTelemetry + Alertmanager |
| SLO / Chaos / AIOps | Gemini AI Copilot | SQLite SLOs, Chaos, FAISS KB, SPL, 45-Day Roadmap | Unified 9-SLO engine, DE↔SRE Correlation Engine, 10 confirmed Chaos Scenarios, FAISS + Gemini RCA |

## 2. Modular Backend API Endpoints

- `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `GET/POST/DELETE /api/v1/auth/users`
- `GET /api/v1/platform/overview`, `GET/POST /api/v1/platform/profiles`, `GET /api/v1/platform/audit`, `GET/POST /api/v1/platform/readiness`, `GET /api/v1/platform/events/stream`
- `GET /api/v1/health/live`, `GET /api/v1/health/ready`
- `GET /api/v1/services`, `GET /api/v1/services/{id}`, `POST /api/v1/services/{id}/start|stop|restart`
- `GET /api/v1/infrastructure/summary`, `GET /api/v1/docker/containers`, `GET /api/v1/docker/containers/{name}/logs`, `POST /api/v1/docker/containers/{name}/{action}`
- `GET /api/v1/kubernetes/overview`, `GET /api/v1/kubernetes/workloads`, `GET /api/v1/kubernetes/pods/{ns}/{pod}/logs`, `POST /api/v1/kubernetes/scale`
- `GET /api/v1/data-engineering/overview`, `POST /api/v1/data-engineering/sql/execute`, `GET /api/v1/data-engineering/datalake/buckets`, `GET /api/v1/data-engineering/datalake/preview`
- `GET /api/v1/spark/status`, `POST /api/v1/spark/execute`
- `GET /api/v1/airflow/dags`, `POST /api/v1/airflow/dags/{dag_id}/trigger`
- `GET /api/v1/streaming/overview`, `POST /api/v1/streaming/kafka/topics|produce`, `POST /api/v1/streaming/rabbitmq/publish`, `DELETE /api/v1/streaming/rabbitmq/queues/{q}/purge`
- `GET /api/v1/metrics/overview`, `GET /api/v1/metrics/promql`
- `GET /api/v1/logs/search`, `GET /api/v1/logs/spl`
- `GET /api/v1/traces`, `GET /api/v1/traces/{trace_id}`
- `GET/PUT /api/v1/slo`, `GET /api/v1/error-budget`
- `GET /api/v1/incidents`, `POST /api/v1/incidents/correlate`, `PUT /api/v1/incidents/{id}/status`, `POST /api/v1/incidents/webhook/alertmanager`
- `GET /api/v1/incidents/chaos/scenarios`, `POST /api/v1/incidents/chaos/execute`, `POST /api/v1/incidents/chaos/recover`
- `GET/POST /api/v1/incidents/runbooks/*`, `/postmortems/*`, `/toil/*`
- `GET /api/v1/finops/overview`
- `GET /api/v1/aiops/overview`, `POST /api/v1/aiops/playbooks/search`, `POST /api/v1/aiops/copilot`, `GET/PUT /api/v1/aiops/roadmap`, `GET /api/v1/aiops/cheatsheet`

## 3. 9 Measured SLOs & Multi-Window Burn Rates

1. `slo-api-availability` — Control Plane API Availability (`ues_http_requests_total`)
2. `slo-app-availability` — Application Endpoint Availability (`app_http_requests_total`)
3. `slo-spark-success` — Spark Job Success Rate (Spark Master/UI REST API)
4. `slo-airflow-success` — Airflow DAG Success Rate (Airflow REST API)
5. `slo-data-freshness` — Lakehouse Gold Data Freshness (MinIO S3 object timestamps)
6. `slo-pipeline-latency` — Pipeline Completion Latency (Airflow DAG run durations)
7. `slo-kafka-lag` — Redpanda / Kafka Consumer Lag (Kafka Admin offset delta)
8. `slo-db-availability` — PostgreSQL DW Availability (Live connection & `pg_stat_activity` saturation)
9. `slo-response-time` — Service p99 Response Latency (`ues_http_request_duration_seconds_bucket`)

