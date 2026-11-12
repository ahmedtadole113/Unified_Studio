"""Environment-driven configuration for Unified Engineering Studio Control Plane."""

import os
from functools import lru_cache


class Settings:
    """Centralized settings loaded from environment variables with safe local defaults."""

    APP_NAME: str = os.getenv("UES_APP_NAME", "Unified Engineering Studio")
    APP_VERSION: str = os.getenv("UES_APP_VERSION", "5.0.0")
    ENVIRONMENT: str = os.getenv("UES_ENV", "development")

    # Security & Auth
    AUTH_SECRET: str = os.getenv("UES_AUTH_SECRET", "ues-dev-ephemeral-secret-override-in-env")
    TOKEN_TTL_SECONDS: int = int(os.getenv("UES_TOKEN_TTL_SECONDS", "43200"))  # 12h
    USERS_DB_PATH: str = os.getenv("UES_USERS_DB_PATH", "/data/users.json")
    BOOTSTRAP_ADMIN_USER: str = os.getenv("UES_BOOTSTRAP_ADMIN_USER", "aariz")
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("UES_BOOTSTRAP_ADMIN_PASSWORD", "aariz")
    BOOTSTRAP_ADMIN_ALIAS: str = os.getenv("UES_BOOTSTRAP_ADMIN_ALIAS", "ariz")

    # SQLite State DB
    SRE_DB_PATH: str = os.getenv("SRE_DB_PATH", "/data/sre_platform.db")

    # Workspace & Compose
    COMPOSE_PROJECT_DIR: str = os.getenv("UES_COMPOSE_DIR", "/home/iceberg")
    NOTEBOOKS_DIR: str = os.getenv("UES_NOTEBOOKS_DIR", "/home/iceberg/notebooks")

    # PostgreSQL Data Warehouse
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres-dw")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "synapse_dw")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")

    # MinIO / S3 Data Lake
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_CONSOLE_URL: str = os.getenv("MINIO_CONSOLE_URL", "http://minio:9001")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ROOT_USER", "admin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_ROOT_PASSWORD", "password")

    # Spark & Iceberg
    SPARK_MASTER_URL: str = os.getenv("SPARK_MASTER_URL", "http://spark-processing:8080")
    SPARK_UI_URL: str = os.getenv("SPARK_UI_URL", "http://spark-processing:4040")
    JUPYTER_URL: str = os.getenv("JUPYTER_URL", "http://spark-processing:8888")
    ICEBERG_REST_URL: str = os.getenv("ICEBERG_REST_URL", "http://rest:8181")
    SPARK_CONTAINER_NAME: str = os.getenv("SPARK_CONTAINER_NAME", "spark-processing")

    # Airflow
    AIRFLOW_URL: str = os.getenv("AIRFLOW_URL", "http://airflow-webserver:8080/services/airflow")
    AIRFLOW_API_USER: str = os.getenv("AIRFLOW_USER", "admin")
    AIRFLOW_API_PASSWORD: str = os.getenv("AIRFLOW_PASSWORD", "admin")

    # Streaming: Redpanda / Kafka & RabbitMQ
    KAFKA_BROKER: str = os.getenv("KAFKA_BROKER", "redpanda:9092")
    REDPANDA_ADMIN_URL: str = os.getenv("REDPANDA_ADMIN_URL", "http://redpanda:9644")
    REDPANDA_CONSOLE_URL: str = os.getenv("REDPANDA_CONSOLE_URL", "http://redpanda-console:8080")
    RABBITMQ_MGMT_URL: str = os.getenv("RABBITMQ_MGMT_URL", "http://rabbitmq:15672/services/servicebus")
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
    RABBITMQ_AMQP_PORT: int = int(os.getenv("RABBITMQ_AMQP_PORT", "5672"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")

    # Observability Stack
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
    GRAFANA_URL: str = os.getenv("GRAFANA_URL", "http://grafana:3000/services/monitoring")
    GRAFANA_USER: str = os.getenv("GRAFANA_ADMIN_USER", "admin")
    GRAFANA_PASSWORD: str = os.getenv("GRAFANA_ADMIN_PASSWORD", "ues-grafana-admin")
    LOKI_URL: str = os.getenv("LOKI_URL", "http://loki:3100")
    TEMPO_URL: str = os.getenv("TEMPO_URL", "http://tempo:3200")
    OTEL_EXPORTER_ENDPOINT: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4318")
    ALERTMANAGER_URL: str = os.getenv("ALERTMANAGER_URL", "http://alertmanager:9093")

    # SRE Telemetry / Practice Lab
    DATA_GENERATOR_URL: str = os.getenv("DATA_GENERATOR_URL", "http://data-generator:8000")
    PRACTICE_LAB_URL: str = os.getenv("PRACTICE_LAB_URL", "http://practice-lab:8090")

    # Kubernetes
    KUBECONFIG_PATH: str = os.getenv("KUBECONFIG", "/root/.kube/config")
    KUBE_HOST_MOUNT: str = os.getenv("KUBE_HOST_MOUNT", "/kube-host/config")

    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Hardware / FinOps Rates (USD, transparent configurable model)
    COST_PER_VCPU_HOUR: float = float(os.getenv("UES_COST_PER_VCPU_HOUR", "0.042"))
    COST_PER_GB_RAM_HOUR: float = float(os.getenv("UES_COST_PER_GB_RAM_HOUR", "0.0055"))
    COST_PER_GB_STORAGE_MONTH: float = float(os.getenv("UES_COST_PER_GB_STORAGE_MONTH", "0.023"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

