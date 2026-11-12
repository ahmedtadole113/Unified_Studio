import os
import time
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.PostgresOperator import PostgresOperator
from airflow.models.param import Param
import requests
import boto3

# Default arguments for the DAG (represents ADF retry policies and alerts)
default_args = {
    'owner': 'azure_admin',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(seconds=10),
}

# 1. Parameterized Pipeline & Schedule Trigger Example
with DAG(
    'adf_features_demo',
    default_args=default_args,
    description='Demonstrates Azure Data Factory equivalents in Apache Airflow',
    schedule_interval='@daily', # ADF Schedule Trigger
    catchup=False,
    params={
        "batch_id": Param(default="batch_001", type="string", description="Ingestion batch ID"),
        "minio_endpoint": Param(default="http://minio:9000", type="string"),
        "target_table": Param(default="synapse_dw.dim_customer", type="string")
    }
) as dag:

    # 2. ADF Lookup Activity Equivalent: Check Watermark Table
    # In ADF, a Lookup Activity retrieves metadata or configuration. Here we query Postgres.
    # Note: We will create the target schema/database during startup.
    lookup_watermark = PostgresOperator(
        task_id='adf_lookup_activity',
        postgres_conn_id='postgres_dw_conn',
        sql="""
        CREATE TABLE IF NOT EXISTS control_watermarks (
            pipeline_name VARCHAR(100) PRIMARY KEY,
            last_load_date TIMESTAMP
        );
        INSERT INTO control_watermarks (pipeline_name, last_load_date) 
        VALUES ('customer_load', '1970-01-01 00:00:00') 
        ON CONFLICT DO NOTHING;
        SELECT last_load_date FROM control_watermarks WHERE pipeline_name = 'customer_load';
        """,
        # Airflow pushes this query result to XCom (ADF output output variable)
    )

    # 3. ADF Copy Activity Equivalent: S3/MinIO Ingestion
    # In ADF, Copy Activity moves data between data stores. Here we download from local data and upload to MinIO.
    def copy_source_to_bronze(**kwargs):
        batch_id = kwargs['params']['batch_id']
        print(f"Starting Copy Activity for batch: {batch_id}")
        
        # Connect to MinIO (ADLS Gen2 equivalent)
        s3 = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='admin',
            aws_secret_access_key='password',
            region_name='us-east-1'
        )
        
        # Ingest local datasets into bronze bucket
        local_data_dir = "/home/iceberg/data"
        if not os.path.exists(local_data_dir):
            local_data_dir = "/opt/airflow/dags" # Fallback if run inside container without mount
            
        csv_file = os.path.join(local_data_dir, "customer.csv")
        
        # Ensure bucket exists
        try:
            s3.head_bucket(Bucket='bronze')
        except Exception:
            s3.create_bucket(Bucket='bronze')
            
        if os.path.exists(csv_file):
            print(f"Uploading {csv_file} to bronze/customer.csv...")
            s3.upload_file(csv_file, 'bronze', 'customer.csv')
            print("Copy Activity Completed Successfully.")
        else:
            print("Source customer.csv not found, simulating ingestion of a sample row instead...")
            s3.put_object(
                Bucket='bronze', 
                Key='customer_sample.csv', 
                Body="c_custkey,c_name,c_mktsegment\n1,Customer_A,BUILDING\n2,Customer_B,AUTOMOBILE\n"
            )

    copy_activity = PythonOperator(
        task_id='adf_copy_activity',
        python_callable=copy_source_to_bronze,
    )

    # 4. ADF Data Flow Equivalent: Process and transform
    # ADF Data Flows compile to Spark under the hood. Here we simulate the logic by executing a processing task.
    def data_flow_transformation(**kwargs):
        # We can read watermark from lookup activity via XCom
        ti = kwargs['ti']
        watermark = ti.xcom_pull(task_ids='adf_lookup_activity')
        print(f"Watermark retrieved from lookup activity: {watermark}")
        
        print("Executing Data Flow transformations...")
        # Simulating Spark execution time
        time.sleep(2)
        print("Data cleaning, mapping, and aggregation completed.")
        
    data_flow_activity = PythonOperator(
        task_id='adf_data_flow_activity',
        python_callable=data_flow_transformation,
    )

    # 5. ADF Update Watermark (Post-Ingestion step)
    update_watermark = PostgresOperator(
        task_id='adf_update_watermark',
        postgres_conn_id='postgres_dw_conn',
        sql="""
        UPDATE control_watermarks 
        SET last_load_date = CURRENT_TIMESTAMP 
        WHERE pipeline_name = 'customer_load';
        """
    )

    # Define Dependencies
    lookup_watermark >> copy_activity >> data_flow_activity >> update_watermark
