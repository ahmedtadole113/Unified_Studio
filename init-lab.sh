#!/bin/bash
set -e

echo "=================================================================="
echo "  UNIFIED ENGINEERING STUDIO (Data Engineering + SRE + AIOps)"
echo "  Single Unified Profile · Separated DE Stack & SRE Stack"
echo "=================================================================="
echo ""

if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker is not running. Please start OrbStack or Docker Desktop."
    exit 1
fi
echo "Docker daemon is running."

if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

if [ -d "data" ] && [ "$(ls -A data)" ]; then
    echo "TPC-H datasets found in data/."
else
    echo "Generating TPC-H datasets..."
    python3 notebooks/generate_data.py --sf 0.05 --output ./data
fi

STACK="${1:-all}"

case "$STACK" in
  all)
    echo "Building and starting FULL Unified Stack (Core + DE Stack + SRE Stack)..."
    docker compose up -d --build
    ;;
  core)
    echo "Starting Core Control Plane Stack..."
    docker compose up -d --build portal-backend portal-frontend postgres-dw prometheus
    ;;
  de|data-engineering)
    echo "Starting Core + Data Engineering Stack (de_net)..."
    docker compose up -d --build portal-backend portal-frontend postgres-dw prometheus minio mc spark-processing rest airflow-webserver airflow-scheduler pgadmin redpanda redpanda-console rabbitmq
    ;;
  sre)
    echo "Starting Core + SRE & Observability Stack (sre_net)..."
    docker compose up -d --build portal-backend portal-frontend postgres-dw prometheus grafana loki promtail tempo alertmanager data-generator practice-lab
    ;;
  *)
    echo "Usage: ./init-lab.sh [all|core|de|sre]"
    exit 1
    ;;
esac

echo ""
echo "=================================================================="
echo "Unified Engineering Studio is active!"
echo "Studio Console:   http://localhost:5173"
echo "Control Plane API: http://localhost:8000/docs"
echo "Prometheus:       http://localhost:9090"
echo "=================================================================="
