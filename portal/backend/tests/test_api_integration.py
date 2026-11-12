"""Automated integration tests for Unified Engineering Studio Control Plane."""

import os
import sys
import tempfile

# Isolate test state DB & users file
_TMP = tempfile.mkdtemp(prefix="ues_test_")
os.environ["SRE_DB_PATH"] = os.path.join(_TMP, "test_sre.db")
os.environ["UES_USERS_DB_PATH"] = os.path.join(_TMP, "test_users.json")
os.environ["UES_AUTH_SECRET"] = "test-secret-key-for-pytest"
os.environ["UES_BOOTSTRAP_ADMIN_USER"] = "aariz"
os.environ["UES_BOOTSTRAP_ADMIN_PASSWORD"] = "aariz"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def _get_token(client: TestClient, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    return data["access_token"]


def test_liveness_and_metrics_public():
    with TestClient(app) as client:
        r = client.get("/api/v1/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        m = client.get("/metrics")
        assert m.status_code == 200
        assert "ues_service_up" in m.text

        tx = client.get("/api/mock-api/transactions?last_id=100&limit=3")
        assert tx.status_code == 200
        assert tx.json()["count"] == 3


def test_auth_rbac_and_audit():
    with TestClient(app) as client:
        # Unauthenticated blocked
        assert client.get("/api/v1/platform/overview").status_code == 401
        assert client.get("/api/v1/services").status_code == 401

        admin_tok = _get_token(client, "aariz", "aariz")
        admin_hdr = {"Authorization": f"Bearer {admin_tok}"}

        # Create limited user
        cu = client.post(
            "/api/v1/auth/users",
            headers=admin_hdr,
            json={"username": "viewer1", "password": "viewer_password", "role": "user"},
        )
        assert cu.status_code == 200, cu.text

        # Verify password stored hashed (not plaintext)
        users_res = client.get("/api/v1/auth/users", headers=admin_hdr)
        assert users_res.status_code == 200
        assert all(u["hashed"] is True for u in users_res.json())

        user_tok = _get_token(client, "viewer1", "viewer_password")
        user_hdr = {"Authorization": f"Bearer {user_tok}"}

        # Limited user can read overview, denied admin mutations
        assert client.get("/api/v1/services", headers=user_hdr).status_code == 200
        assert client.post("/api/v1/services/minio/stop", headers=user_hdr).status_code == 403
        assert client.post("/api/v1/auth/users", headers=user_hdr, json={"username": "x", "password": "abcd", "role": "user"}).status_code == 403

        # Audit log recorded login & user creation
        audits = client.get("/api/v1/platform/audit", headers=admin_hdr)
        assert audits.status_code == 200
        assert len(audits.json()["logs"]) >= 2


def test_core_domain_endpoints():
    with TestClient(app) as client:
        tok = _get_token(client, "aariz", "aariz")
        hdr = {"Authorization": f"Bearer {tok}"}

        # Platform Overview
        ov = client.get("/api/v1/platform/overview", headers=hdr)
        assert ov.status_code == 200
        ov_j = ov.json()
        assert ov_j["services"]["total"] == 19
        assert len(ov_j["slo"]["items"]) == 9

        # Service Registry fields
        svcs = client.get("/api/v1/services", headers=hdr).json()["services"]
        first = svcs[0]
        for field in ("service_name", "category", "service_id", "container_name", "internal_endpoint", "external_endpoint", "health_check_endpoint", "status", "lifecycle_state", "dependencies", "owner", "criticality", "associated_slo", "monitoring_config"):
            assert field in first

        # SLOs & Error Budgets
        eb = client.get("/api/v1/error-budget?window=1h", headers=hdr)
        assert eb.status_code == 200
        assert len(eb.json()["budgets"]) == 9

        # Infrastructure (Docker & K8s)
        infra = client.get("/api/v1/infrastructure/summary", headers=hdr)
        assert infra.status_code == 200
        assert "docker" in infra.json() and "kubernetes" in infra.json()

        # Data Engineering & Streaming
        assert client.get("/api/v1/data-engineering/overview", headers=hdr).status_code == 200
        assert client.get("/api/v1/streaming/overview", headers=hdr).status_code == 200

        # Observability (Metrics, Logs, SPL, Traces)
        assert client.get("/api/v1/metrics/overview", headers=hdr).status_code == 200
        assert client.get("/api/v1/logs/search", headers=hdr).status_code == 200
        spl = client.get("/api/v1/logs/spl?q=index=app_logs | head 5", headers=hdr)
        assert spl.status_code == 200
        assert client.get("/api/v1/traces", headers=hdr).status_code == 200

        # FinOps
        fin = client.get("/api/v1/finops/overview", headers=hdr)
        assert fin.status_code == 200
        assert len(fin.json()["profiles"]) == 3

        # AIOps & FAISS Playbooks & Copilot fallback
        ai = client.get("/api/v1/aiops/overview", headers=hdr)
        assert ai.status_code == 200
        assert ai.json()["playbooks_count"] >= 10
        pb = client.post("/api/v1/aiops/playbooks/search", headers=hdr, json={"text": "Kubernetes CrashLoopBackOff"})
        assert pb.status_code == 200
        assert pb.json()["best"]["slug"] == "k8s-crashloop"

        cop = client.post("/api/v1/aiops/copilot", headers=hdr, json={"service": "sre", "action": "triage", "content": "Postgres connection pool exhausted"})
        assert cop.status_code == 200
        assert "db-pool-exhaustion" in cop.json()["response"]

        # Chaos Safety Guardrail (must reject unconfirmed chaos)
        bad_chaos = client.post(
            "/api/v1/incidents/chaos/execute",
            headers=hdr,
            json={"scenario_id": "kafka_consumer_lag", "confirm": False, "confirmation_phrase": "wrong"},
        )
        assert bad_chaos.status_code == 400

        # Correlation Engine
        corr = client.post("/api/v1/incidents/correlate", headers=hdr)
        assert corr.status_code == 200
        assert "signals" in corr.json()

        # 30-Day Data Engineering Roadmap & Interview Scenarios
        de_rm = client.get("/api/v1/data-engineering/roadmap", headers=hdr)
        assert de_rm.status_code == 200
        de_rm_j = de_rm.json()
        assert len(de_rm_j["phases"]) == 6
        assert len(de_rm_j["days"]) == 30
        assert len(de_rm_j["days"][0]["interview_questions"]) >= 3

        prog = client.put(
            "/api/v1/data-engineering/roadmap/1/progress",
            headers=hdr,
            json={"completed": True, "notes": "Reviewed OLTP vs OLAP and Columnar Parquet"},
        )
        assert prog.status_code == 200
        assert prog.json()["completed"] is True

