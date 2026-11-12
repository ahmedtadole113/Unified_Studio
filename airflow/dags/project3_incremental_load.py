import os
import sys
import time
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import requests
import boto3
import psycopg2
from psycopg2.extras import execute_values

default_args = {
    'owner': 'azure_admin',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'retries': 0,
    'retry_delay': timedelta(seconds=10),
}

with DAG(
    'project3_adf_incremental_load',
    default_args=default_args,
    description='Project 3: ADF Incremental Load (API -> Airflow -> Delta Lake -> Warehouse)',
    schedule_interval='*/5 * * * *',  # Run every 5 minutes (ADF trigger equivalent)
    catchup=False,
) as dag:

    # Task 1: Check target database to determine the last transaction ID loaded (Watermark lookup)
    def lookup_watermark():
        pg_conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST', 'postgres-dw'),
            database=os.environ.get('POSTGRES_DB', 'synapse_dw'),
            user=os.environ.get('POSTGRES_USER', 'postgres'),
            password=os.environ.get('POSTGRES_PASSWORD', 'password'),
            port=int(os.environ.get('POSTGRES_PORT', 5432))
        )
        cursor = pg_conn.cursor()
        
        cursor.execute("""
        CREATE SCHEMA IF NOT EXISTS synapse_dw;
        CREATE TABLE IF NOT EXISTS synapse_dw.fact_transactions (
            transaction_id INT PRIMARY KEY,
            timestamp TIMESTAMP,
            customer_id INT,
            amount DECIMAL(10, 2),
            merchant VARCHAR(100),
            category VARCHAR(50),
            status VARCHAR(20),
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        pg_conn.commit()
        
        cursor.execute("SELECT COALESCE(MAX(transaction_id), 0) FROM synapse_dw.fact_transactions;")
        last_id = cursor.fetchone()[0]
        
        cursor.close()
        pg_conn.close()
        print(f"Retrieved watermark transaction_id: {last_id}")
        return last_id

    watermark_lookup = PythonOperator(
        task_id='lookup_watermark',
        python_callable=lookup_watermark
    )

    # Task 2: Call FastAPI REST API to fetch incremental transactions
    def fetch_api_data(**kwargs):
        ti = kwargs['ti']
        last_id = ti.xcom_pull(task_ids='lookup_watermark')
        
        # FastAPI portal-backend URL
        backend_url = "http://portal-backend:8000/api/mock-api/transactions"
        params = {"last_id": last_id, "limit": 10}
        
        print(f"Fetching transactions since ID: {last_id} from {backend_url}...")
        try:
            response = requests.get(backend_url, params=params, timeout=10)
            response.raise_for_status()
            res_data = response.json()
            transactions = res_data.get("data", [])
            print(f"Retrieved {len(transactions)} new transaction records.")
            return transactions
        except Exception as e:
            print(f"Failed to fetch API data: {e}. Fallback to mock generation...")
            # Fallback mock generator
            start_id = last_id + 1
            fallback_txs = []
            for i in range(5):
                tx_id = start_id + i
                fallback_txs.append({
                    "transaction_id": tx_id,
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "customer_id": 1000 + i,
                    "amount": round(25.5 * (tx_id % 3) + 1.99, 2),
                    "merchant": "Fallback Merchant",
                    "category": "Shopping",
                    "status": "COMPLETED"
                })
            return fallback_txs

    fetch_incremental = PythonOperator(
        task_id='fetch_api_data',
        python_callable=fetch_api_data
    )

    # Task 3: Stage incremental records as a JSON/Delta file in ADLS (MinIO)
    def stage_in_datalake(**kwargs):
        ti = kwargs['ti']
        transactions = ti.xcom_pull(task_ids='fetch_api_data')
        
        if not transactions:
            print("No new records to stage.")
            return False
            
        s3 = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='admin',
            aws_secret_access_key='password',
            region_name='us-east-1'
        )
        
        # Ensure bucket exists
        try:
            s3.head_bucket(Bucket='silver')
        except Exception:
            s3.create_bucket(Bucket='silver')
            
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        key = f"transactions_incremental/transactions_{timestamp_str}.json"
        
        import json
        body = json.dumps(transactions)
        s3.put_object(Bucket='silver', Key=key, Body=body)
        print(f"Staged {len(transactions)} records to silver/{key}")
        return True

    stage_datalake = PythonOperator(
        task_id='stage_in_datalake',
        python_callable=stage_in_datalake
    )

    # Task 4: Run a MERGE/Upsert statement to load new records into Synapse DW (Postgres)
    def upsert_into_warehouse(**kwargs):
        ti = kwargs['ti']
        transactions = ti.xcom_pull(task_ids='fetch_api_data')
        
        if not transactions:
            print("No records to load.")
            return
            
        records = []
        for tx in transactions:
            records.append((
                tx["transaction_id"],
                tx["timestamp"],
                tx["customer_id"],
                tx["amount"],
                tx["merchant"],
                tx["category"],
                tx["status"]
            ))

        pg_conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST', 'postgres-dw'),
            database=os.environ.get('POSTGRES_DB', 'synapse_dw'),
            user=os.environ.get('POSTGRES_USER', 'postgres'),
            password=os.environ.get('POSTGRES_PASSWORD', 'password'),
            port=int(os.environ.get('POSTGRES_PORT', 5432))
        )
        cursor = pg_conn.cursor()
        
        upsert_query = """
        INSERT INTO synapse_dw.fact_transactions (transaction_id, timestamp, customer_id, amount, merchant, category, status, loaded_at)
        VALUES %s
        ON CONFLICT (transaction_id) 
        DO UPDATE SET 
            timestamp = EXCLUDED.timestamp,
            customer_id = EXCLUDED.customer_id,
            amount = EXCLUDED.amount,
            merchant = EXCLUDED.merchant,
            category = EXCLUDED.category,
            status = EXCLUDED.status,
            loaded_at = CURRENT_TIMESTAMP;
        """
        
        execute_values(cursor, upsert_query, records)
        pg_conn.commit()
        
        cursor.close()
        pg_conn.close()
        print(f"Successfully upserted {len(records)} records into Postgres Synapse fact_transactions.")

    upsert_warehouse = PythonOperator(
        task_id='upsert_into_warehouse',
        python_callable=upsert_into_warehouse
    )

    watermark_lookup >> fetch_incremental >> stage_datalake >> upsert_warehouse
