"""Data Engineering Router (`/api/v1/data-engineering`, `/api/v1/spark`, `/api/v1/airflow`, `/api/mock-api/transactions`)."""

import time
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core import audit, database, security
from de_content import roadmap as de_roadmap
from services import de_client

router = APIRouter(tags=["Data Engineering"])


class SqlQueryRequest(BaseModel):
    sql: str
    limit: int = 200


class PySparkExecRequest(BaseModel):
    code: str
    app_name: str = "UES_PySpark_Studio"


class DeStudyProgressRequest(BaseModel):
    completed: bool
    notes: str = ""


@router.get("/api/v1/data-engineering/overview")
async def de_overview(user: Dict[str, str] = Depends(security.get_current_user)):
    medallion = de_client.get_medallion_and_dq_overview()
    spark = await de_client.get_spark_and_iceberg_status()
    airflow = await de_client.get_airflow_overview()
    return {
        **medallion,
        "spark": spark,
        "airflow": airflow,
    }


@router.post("/api/v1/data-engineering/sql/execute")
def run_sql_studio(req: SqlQueryRequest, user: Dict[str, str] = Depends(security.get_current_user)):
    try:
        return de_client.execute_sql_query(req.sql, limit=req.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PostgreSQL query error: {exc}") from exc


@router.get("/api/v1/data-engineering/datalake/buckets")
def list_datalake_buckets(user: Dict[str, str] = Depends(security.get_current_user)):
    return de_client.get_minio_summary()


@router.get("/api/v1/data-engineering/datalake/preview")
def preview_datalake_object(bucket: str, key: str, user: Dict[str, str] = Depends(security.get_current_user)):
    try:
        return de_client.preview_minio_object(bucket, key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Object preview failed: {exc}") from exc


@router.get("/api/v1/spark/status")
async def spark_status(user: Dict[str, str] = Depends(security.get_current_user)):
    return await de_client.get_spark_and_iceberg_status()


@router.post("/api/v1/spark/execute")
def spark_execute(req: PySparkExecRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = de_client.execute_pyspark_code(req.code, app_name=req.app_name)
        audit.record_audit(admin, "spark.execute", req.app_name, f"exit_code={res['exit_code']}")
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/v1/airflow/dags")
async def airflow_dags(user: Dict[str, str] = Depends(security.get_current_user)):
    return await de_client.get_airflow_overview()


@router.post("/api/v1/airflow/dags/{dag_id}/trigger")
async def airflow_trigger(dag_id: str, admin: Dict[str, str] = Depends(security.require_admin)):
    try:
        res = await de_client.trigger_airflow_dag(dag_id)
        audit.record_audit(admin, "airflow.trigger", dag_id, f"Triggered DAG run {res.get('dag_run_id', '')}")
        return res
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/api/v1/data-engineering/roadmap")
def get_de_roadmap(user: Dict[str, str] = Depends(security.get_current_user)):
    return {
        "phases": de_roadmap.DE_PHASES,
        "days": de_roadmap.DE_ROADMAP_DAYS,
        "progress": database.get_de_study_progress(),
    }


@router.put("/api/v1/data-engineering/roadmap/{day}/progress")
def save_de_roadmap_progress(day: int, req: DeStudyProgressRequest, user: Dict[str, str] = Depends(security.get_current_user)):
    if day < 1 or day > 30:
        raise HTTPException(status_code=400, detail="Day must be between 1 and 30")
    return database.upsert_de_study_progress(day, req.completed, req.notes)


# Preserved endpoint used by Airflow DAG `project3_incremental_load.py` (unauthenticated internal service-to-service)
@router.get("/api/mock-api/transactions")
def get_mock_transactions(
    last_id: int = Query(0, description="Retrieve transactions with ID greater than this value"),
    limit: int = Query(10, description="Number of transaction records to fetch"),
):
    current_time = int(time.time())
    transactions = []
    merchant_list = ["Apple Store", "Amazon Web Services", "Starbucks", "Target", "Costco", "Microsoft Store", "Netflix", "Whole Foods"]
    category_list = ["Technology", "Cloud Services", "Food & Beverage", "Retail", "Wholesale", "Software", "Subscription", "Groceries"]
    start_id = max(last_id + 1, 1000)
    for idx in range(limit):
        tx_id = start_id + idx
        merchant_idx = tx_id % len(merchant_list)
        amount = round((24.5 * (tx_id % 7) + 9.99) * (1.15 if tx_id % 3 == 0 else 1.0), 2)
        transactions.append({
            "transaction_id": tx_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time - (limit - idx) * 60)),
            "customer_id": 10000 + (tx_id % 123),
            "amount": amount,
            "merchant": merchant_list[merchant_idx],
            "category": category_list[merchant_idx],
            "status": "COMPLETED" if tx_id % 15 != 0 else "REFUNDED",
        })
    return {"count": len(transactions), "last_id": start_id + limit - 1 if transactions else last_id, "data": transactions}

