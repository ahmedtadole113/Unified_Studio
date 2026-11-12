#!/bin/bash
set -e

echo "=================================================================="
echo "  UNIFIED ENGINEERING STUDIO (Data Engineering + SRE + AIOps)"
echo "  Optimized for Apple Silicon M4 (8 GB RAM Hardware Budget)"
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

PROFILE="${1:-core}"

echo ""
echo "Building Unified Control Plane (portal-backend & portal-frontend)..."
docker compose build portal-backend portal-frontend

case "$PROFILE" in
  core)
    echo "Starting PROFILE 1: CORE (Frontend, Control Plane, PostgreSQL DW, Prometheus)..."
    docker compose up -d portal-backend portal-frontend postgres-dw prometheus
    ;;
  de|data-engineering)
    echo "Starting PROFILE 2: DATA ENGINEERING STUDIO..."
    docker compose --profile profile-data-engineering up -d
    ;;
  sre)
    echo "Starting PROFILE 3: SRE, OBSERVABILITY & KUBERNETES LAB..."
    docker compose --profile profile-sre up -d
    ;;
  all)
    echo "Starting ALL PROFILES (Ensure sufficient Docker RAM allocation)..."
    docker compose --profile profile-data-engineering --profile profile-sre up -d
    ;;
  *)
    echo "Usage: ./init-lab.sh [core|data-engineering|sre|all]"
    exit 1
    ;;
esac

echo ""
echo "=================================================================="
echo "Unified Engineering Studio is ready!"
echo "Studio Console:   http://localhost:5173"
echo "Control Plane API: http://localhost:8000/docs"
echo "Prometheus:       http://localhost:9090"
echo "=================================================================="
