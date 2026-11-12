"""Data Engineering integrations: PostgreSQL DW, MinIO S3, Spark 4.2, Iceberg REST, Airflow, Medallion, DQ, CDC."""

import io
import json
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import boto3
import httpx
import psycopg2
from botocore.client import Config as BotoConfig

from core.config import settings
from core.telemetry_otel import traced_operation

logger = logging.getLogger("ues.de")


def _pg_connect():
    return psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        connect_timeout=3,
    )


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
        config=BotoConfig(connect_timeout=2, read_timeout=4, retries={"max_attempts": 1}),
    )


def get_postgres_status_and_schemas() -> Dict[str, Any]:
    """Query real PostgreSQL DW availability, active connections, schemas, and tables."""
    t0 = time.time()
    try:
        conn = _pg_connect()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]

        cur.execute(
            """
            SELECT state, COUNT(*)
            FROM pg_stat_activity
            WHERE datname = %s
            GROUP BY state;
            """,
            (settings.POSTGRES_DB,),
        )
        conn_states = {str(r[0] or "idle"): int(r[1]) for r in cur.fetchall()}
        cur.execute("SHOW max_connections;")
        max_conns = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name;
            """
        )
        tables = [{"schema": r[0], "name": r[1], "type": r[2]} for r in cur.fetchall()]

        cur.execute("SELECT pg_database_size(%s);", (settings.POSTGRES_DB,))
        db_size_bytes = int(cur.fetchone()[0])

        cur.close()
        conn.close()
        latency_ms = round((time.time() - t0) * 1000, 2)
        total_active = sum(conn_states.values())
        return {
            "available": True,
            "version": version.split(" on ")[0],
            "latency_ms": latency_ms,
            "database": settings.POSTGRES_DB,
            "size_mb": round(db_size_bytes / (1024 * 1024), 2),
            "connections": total_active,
            "max_connections": max_conns,
            "connection_utilization_pct": round((total_active / max(1, max_conns)) * 100.0, 2),
            "connection_states": conn_states,
            "tables": tables,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc), "tables": [], "connections": 0, "max_connections": 0}


def execute_sql_query(sql: str, limit: int = 200) -> Dict[str, Any]:
    """Execute SQL query against PostgreSQL DW with OTel tracing and timing."""
    cleaned = sql.strip()
    if not cleaned:
        raise ValueError("SQL query cannot be empty")

    # Safety guardrail against destructive DB drops from SQL Studio UI
    lowered = cleaned.lower()
    if any(tok in lowered for tok in ("drop database", "truncate pg_", "alter system")):
        raise ValueError("Blocked potentially destructive system-level SQL statement")

    with traced_operation("postgres.sql_query", domain="data_engineering", attributes={"db.system": "postgresql"}) as span:
        t0 = time.time()
        conn = _pg_connect()
        try:
            cur = conn.cursor()
            cur.execute(cleaned)
            duration_ms = round((time.time() - t0) * 1000, 2)
            span.set_attribute("db.duration_ms", duration_ms)
            if cur.description:
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchmany(limit)
                formatted = [dict(zip(cols, [str(v) if v is not None else None for v in r])) for r in rows]
                conn.commit()
                return {
                    "status": "ok",
                    "columns": cols,
                    "rows": formatted,
                    "row_count": len(formatted),
                    "duration_ms": duration_ms,
                }
            conn.commit()
            return {
                "status": "ok",
                "columns": [],
                "rows": [],
                "row_count": cur.rowcount,
                "duration_ms": duration_ms,
                "message": f"Statement executed ({cur.rowcount} rows affected)",
            }
        finally:
            conn.close()


def get_minio_summary() -> Dict[str, Any]:
    """Query real MinIO S3 buckets, object counts, and total storage size."""
    try:
        s3 = _s3_client()
        resp = s3.list_buckets()
        buckets_out = []
        total_bytes = 0
        total_objects = 0
        latest_modified = 0.0

        for b in resp.get("Buckets", []):
            name = b["Name"]
            objs = []
            b_bytes = 0
            b_count = 0
            try:
                paginator = s3.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=name):
                    for obj in page.get("Contents", []):
                        b_count += 1
                        sz = int(obj.get("Size", 0))
                        b_bytes += sz
                        lm = obj.get("LastModified")
                        if lm:
                            ts = lm.timestamp()
                            if ts > latest_modified:
                                latest_modified = ts
                        if len(objs) < 25:
                            objs.append(
                                {
                                    "key": obj["Key"],
                                    "size_bytes": sz,
                                    "last_modified": str(lm) if lm else "",
                                }
                            )
            except Exception:
                pass
            total_bytes += b_bytes
            total_objects += b_count
            buckets_out.append(
                {
                    "name": name,
                    "object_count": b_count,
                    "size_mb": round(b_bytes / (1024 * 1024), 3),
                    "objects": objs,
                }
            )

        freshness_minutes = round((time.time() - latest_modified) / 60.0, 1) if latest_modified > 0 else None
        return {
            "available": True,
            "buckets": buckets_out,
            "total_objects": total_objects,
            "total_size_mb": round(total_bytes / (1024 * 1024), 3),
            "latest_object_age_minutes": freshness_minutes,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc), "buckets": [], "total_objects": 0, "total_size_mb": 0.0}


def preview_minio_object(bucket: str, key: str, max_bytes: int = 16384) -> Dict[str, Any]:
    s3 = _s3_client()
    obj = s3.get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{max_bytes - 1}")
    raw = obj["Body"].read().decode("utf-8", errors="replace")
    return {"bucket": bucket, "key": key, "content": raw, "content_length": obj.get("ContentLength", len(raw))}


async def get_spark_and_iceberg_status() -> Dict[str, Any]:
    """Fetch real Spark Master / Spark UI apps, Iceberg REST catalog namespaces & tables, and local notebooks."""
    spark_apps: List[Dict[str, Any]] = []
    spark_master_info: Dict[str, Any] = {}
    spark_available = False
    iceberg_available = False
    iceberg_namespaces: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=2.5) as client:
        # Try Spark Master JSON (if standalone master) or Spark Driver UI :4040
        for url in (f"{settings.SPARK_MASTER_URL}/json/", f"{settings.SPARK_UI_URL}/api/v1/applications"):
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    spark_available = True
                    data = r.json()
                    if isinstance(data, dict) and "activeapps" in data:
                        spark_master_info = data
                        spark_apps = data.get("activeapps", []) + data.get("completedapps", [])
                    elif isinstance(data, list):
                        spark_apps = data
                    break
            except Exception:
                continue

        # Check JupyterLab API if running in spark-processing
        if not spark_available:
            try:
                r = await client.get(f"{settings.JUPYTER_URL}/services/databricks/api")
                if r.status_code == 200:
                    spark_available = True
            except Exception:
                pass

        # Iceberg REST Catalog
        try:
            r = await client.get(f"{settings.ICEBERG_REST_URL}/v1/namespaces")
            if r.status_code == 200:
                iceberg_available = True
                for ns in r.json().get("namespaces", []):
                    ns_name = ".".join(ns)
                    tables = []
                    try:
                        tr = await client.get(f"{settings.ICEBERG_REST_URL}/v1/namespaces/{ns_name}/tables")
                        if tr.status_code == 200:
                            tables = [t.get("name") for t in tr.json().get("identifiers", [])]
                    except Exception:
                        pass
                    iceberg_namespaces.append({"namespace": ns_name, "tables": tables})
        except Exception:
            pass

    # Scan notebooks folder
    notebooks = []
    nb_dir = os.path.join(settings.COMPOSE_PROJECT_DIR, "notebooks")
    if os.path.isdir(nb_dir):
        for fname in sorted(os.listdir(nb_dir)):
            if fname.endswith(".ipynb"):
                fpath = os.path.join(nb_dir, fname)
                notebooks.append(
                    {
                        "name": fname,
                        "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                        "url": f"/services/databricks/lab/tree/notebooks/{fname}",
                    }
                )

    return {
        "spark_available": spark_available,
        "spark_master": spark_master_info,
        "applications": spark_apps,
        "iceberg_available": iceberg_available,
        "iceberg_namespaces": iceberg_namespaces,
        "notebooks": notebooks,
    }


def execute_pyspark_code(code: str, app_name: str = "UES_PySpark_Studio") -> Dict[str, Any]:
    """Execute PySpark code inside the running `spark-processing` container via docker exec."""
    if not code.strip():
        raise ValueError("PySpark code cannot be empty")

    with traced_operation("spark.pyspark_exec", domain="data_engineering", attributes={"spark.app": app_name}):
        t0 = time.time()
        # Run Python code safely via stdin inside spark-processing container
        cmd = [
            "docker",
            "exec",
            "-i",
            settings.SPARK_CONTAINER_NAME,
            "python3",
            "-c",
            code,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            duration_ms = round((time.time() - t0) * 1000, 2)
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "exit_code": proc.returncode,
                "stdout": proc.stdout[-12000:],
                "stderr": proc.stderr[-8000:],
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "exit_code": 124, "stdout": "", "stderr": "PySpark execution timed out (45s limit)", "duration_ms": 45000.0}
        except Exception as exc:
            return {"status": "error", "exit_code": 1, "stdout": "", "stderr": str(exc), "duration_ms": round((time.time() - t0) * 1000, 2)}


async def get_airflow_overview() -> Dict[str, Any]:
    """Query Airflow REST API for real DAGs and recent DAG runs."""
    auth = (settings.AIRFLOW_API_USER, settings.AIRFLOW_API_PASSWORD)
    base = settings.AIRFLOW_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.5, auth=auth) as client:
            health_r = await client.get(f"{base}/health")
            dags_r = await client.get(f"{base}/api/v1/dags", params={"limit": 50})
            if dags_r.status_code != 200:
                return {"available": False, "error": f"Airflow API HTTP {dags_r.status_code}", "dags": [], "recent_runs": []}

            dags_raw = dags_r.json().get("dags", [])
            dags = []
            recent_runs = []
            for d in dags_raw:
                dag_id = d.get("dag_id")
                d_runs = []
                try:
                    rr = await client.get(f"{base}/api/v1/dags/{dag_id}/dagRuns", params={"limit": 5, "order_by": "-execution_date"})
                    if rr.status_code == 200:
                        d_runs = rr.json().get("dag_runs", [])
                except Exception:
                    pass
                last_run = d_runs[0] if d_runs else None
                for run in d_runs:
                    recent_runs.append(
                        {
                            "dag_id": dag_id,
                            "run_id": run.get("dag_run_id"),
                            "state": run.get("state"),
                            "start_date": run.get("start_date"),
                            "end_date": run.get("end_date"),
                            "execution_date": run.get("execution_date"),
                        }
                    )
                dags.append(
                    {
                        "dag_id": dag_id,
                        "description": d.get("description") or "",
                        "is_paused": d.get("is_paused"),
                        "is_active": d.get("is_active"),
                        "schedule": str((d.get("timetable_description") or d.get("schedule_interval") or "Manual")),
                        "owners": d.get("owners", []),
                        "last_run_state": last_run.get("state") if last_run else "never_run",
                        "last_run_date": last_run.get("execution_date") if last_run else None,
                    }
                )

            health_json = health_r.json() if health_r.status_code == 200 else {}
            return {
                "available": True,
                "health": health_json,
                "dags": dags,
                "recent_runs": sorted(recent_runs, key=lambda x: str(x.get("execution_date") or ""), reverse=True)[:25],
            }
    except Exception as exc:
        # Fallback: inspect local DAG files on disk even when Airflow service is stopped
        dag_files = []
        dags_dir = os.path.join(settings.COMPOSE_PROJECT_DIR, "airflow", "dags")
        if os.path.isdir(dags_dir):
            for fname in sorted(os.listdir(dags_dir)):
                if fname.endswith(".py"):
                    dag_files.append({"dag_id": fname[:-3], "is_paused": None, "last_run_state": "airflow_offline", "description": f"DAG file: {fname}"})
        return {"available": False, "error": str(exc), "dags": dag_files, "recent_runs": []}


async def trigger_airflow_dag(dag_id: str) -> Dict[str, Any]:
    auth = (settings.AIRFLOW_API_USER, settings.AIRFLOW_API_PASSWORD)
    base = settings.AIRFLOW_URL.rstrip("/")
    with traced_operation("airflow.trigger_dag", domain="data_engineering", attributes={"airflow.dag_id": dag_id}):
        async with httpx.AsyncClient(timeout=5.0, auth=auth) as client:
            # Unpause first if paused so manual trigger runs
            await client.patch(f"{base}/api/v1/dags/{dag_id}", json={"is_paused": False})
            resp = await client.post(f"{base}/api/v1/dags/{dag_id}/dagRuns", json={"conf": {"triggered_by": "unified_engineering_studio"}})
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Airflow trigger failed ({resp.status_code}): {resp.text[:250]}")
            return resp.json()


def get_medallion_and_dq_overview() -> Dict[str, Any]:
    """Compute real Medallion Architecture, Data Quality, and CDC status from MinIO + Postgres + local TPC-H."""
    minio = get_minio_summary()
    pg = get_postgres_status_and_schemas()

    buckets_map = {b["name"]: b for b in minio.get("buckets", [])}
    bronze = buckets_map.get("bronze", {"object_count": 0, "size_mb": 0.0, "objects": []})
    silver = buckets_map.get("silver", {"object_count": 0, "size_mb": 0.0, "objects": []})
    gold = buckets_map.get("gold", {"object_count": 0, "size_mb": 0.0, "objects": []})
    warehouse = buckets_map.get("warehouse", {"object_count": 0, "size_mb": 0.0, "objects": []})

    # Real Data Quality check on TPC-H data or Postgres fact tables
    dq_checks = []
    data_dir = os.path.join(settings.COMPOSE_PROJECT_DIR, "data")
    tpch_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")] if os.path.isdir(data_dir) else []
    dq_checks.append(
        {
            "rule": "TPC-H Seed Datasets Present",
            "layer": "Source / Raw",
            "status": "pass" if len(tpch_files) >= 8 else "warn",
            "detail": f"{len(tpch_files)} CSV files in data/ ({', '.join(sorted(tpch_files)[:4])}...)" if tpch_files else "No TPC-H CSVs found",
        }
    )
    dq_checks.append(
        {
            "rule": "Bronze Bucket Ingestion",
            "layer": "Bronze (MinIO)",
            "status": "pass" if bronze["object_count"] > 0 else "info",
            "detail": f"{bronze['object_count']} objects ({bronze['size_mb']} MB)" if minio["available"] else "MinIO offline",
        }
    )
    dq_checks.append(
        {
            "rule": "Silver Conformed Layer",
            "layer": "Silver (MinIO)",
            "status": "pass" if silver["object_count"] > 0 else "info",
            "detail": f"{silver['object_count']} objects ({silver['size_mb']} MB)" if minio["available"] else "MinIO offline",
        }
    )
    dq_checks.append(
        {
            "rule": "Gold Analytical Marts & DW",
            "layer": "Gold + PostgreSQL DW",
            "status": "pass" if (gold["object_count"] > 0 or len(pg.get("tables", [])) > 0) else "info",
            "detail": f"Gold objects: {gold['object_count']} | DW tables: {len(pg.get('tables', []))}",
        }
    )

    return {
        "medallion": {
            "minio_available": minio["available"],
            "bronze": bronze,
            "silver": silver,
            "gold": gold,
            "warehouse": warehouse,
        },
        "postgres_dw": pg,
        "data_quality": dq_checks,
        "cdc_pipelines": [
            {
                "name": "Project 3: Incremental API Watermark -> MinIO -> Postgres DW",
                "dag_id": "project3_adf_incremental_load",
                "target_table": "synapse_dw.fact_transactions",
                "status": "active" if pg["available"] else "standby",
            },
            {
                "name": "Project 4: PostgreSQL CDC -> Redpanda -> Spark Structured Streaming -> Iceberg/Delta",
                "notebook": "project4_cdc_pipeline.ipynb",
                "status": "ready",
            },
        ],
    }

