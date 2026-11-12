import os
import sys
import time
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.PostgresOperator import PostgresOperator
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
    'project1_adf_batch_pipeline',
    default_args=default_args,
    description='Project 1: Batch ETL Ingestion & Medallion Pipeline (ADF -> ADLS -> Databricks -> Synapse)',
    schedule_interval=None, # Triggered manually
    catchup=False,
) as dag:

    # Task 1: Upload CSV files from local directory to MinIO Bronze bucket (ADLS Gen2 simulation)
    def copy_csv_to_bronze():
        s3 = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='admin',
            aws_secret_access_key='password',
            region_name='us-east-1'
        )
        
        # Ensure 'bronze' bucket exists
        try:
            s3.head_bucket(Bucket='bronze')
        except Exception:
            s3.create_bucket(Bucket='bronze')
            print("Created 'bronze' bucket in MinIO")

        # Files to upload
        data_dir = "/home/iceberg/data"
        if not os.path.exists(data_dir):
            data_dir = "/opt/airflow/dags"  # Fallback

        files = ['customer.csv', 'orders.csv', 'nation.csv', 'region.csv', 'supplier.csv', 'part.csv', 'partsupp.csv']
        
        uploaded_count = 0
        for file in files:
            path = os.path.join(data_dir, file)
            if os.path.exists(path):
                print(f"Uploading {file} to bronze bucket...")
                s3.upload_file(path, 'bronze', file)
                uploaded_count += 1
            else:
                print(f"File {file} not found under {data_dir}. Skipping.")

        if uploaded_count == 0:
            print("No CSV files found in data folder. Creating sample customer dataset inside Bronze.")
            s3.put_object(
                Bucket='bronze',
                Key='customer.csv',
                Body="c_custkey,c_name,c_mktsegment,c_acctbal\n1,Customer_A,BUILDING,5000.50\n2,Customer_B,AUTOMOBILE,3200.10\n3,Customer_C,MACHINERY,-150.00\n"
            )
            s3.put_object(
                Bucket='bronze',
                Key='orders.csv',
                Body="o_orderkey,o_custkey,o_totalprice,o_orderdate\n100,1,150.00,2026-06-01\n101,1,200.00,2026-06-02\n102,2,3200.10,2026-06-03\n"
            )

    copy_to_bronze = PythonOperator(
        task_id='copy_csv_to_bronze',
        python_callable=copy_csv_to_bronze
    )

    # Task 2: Simulate Databricks Silver transformations
    # Cleans data, handles datatypes, maps schemas, saves to MinIO 'silver' bucket.
    def transform_bronze_to_silver():
        s3 = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='admin',
            aws_secret_access_key='password',
            region_name='us-east-1'
        )
        
        # Ensure 'silver' bucket exists
        try:
            s3.head_bucket(Bucket='silver')
        except Exception:
            s3.create_bucket(Bucket='silver')
            
        print("Reading raw customer from Bronze and applying cleaning...")
        # Simulating Spark schema mapping and formatting
        # In a real environment, this triggers a Notebook execution or spark-submit
        try:
            # Fetch from Bronze
            cust_obj = s3.get_object(Bucket='bronze', Key='customer.csv')
            cust_data = cust_obj['Body'].read().decode('utf-8').splitlines()
            
            # Apply transformation (e.g., skip header, filter, map columns)
            header = cust_data[0].split(',')
            cleaned_rows = ["customer_id,name,market_segment,account_balance"]
            
            for line in cust_data[1:]:
                if not line.strip():
                    continue
                cols = line.split(',')
                # Type cast check & clean
                cust_id = int(cols[0])
                name = cols[1].strip()
                segment = cols[2].strip()
                bal = float(cols[3]) if len(cols) > 3 else 0.0
                
                cleaned_rows.append(f"{cust_id},{name},{segment},{bal}")
                
            s3.put_object(Bucket='silver', Key='customer_silver.csv', Body="\n".join(cleaned_rows))
            print("Successfully saved customer_silver.csv to MinIO silver bucket.")
        except Exception as e:
            print(f"Error during Silver customer transformation: {e}")

        print("Reading raw orders from Bronze and applying cleaning...")
        try:
            ord_obj = s3.get_object(Bucket='bronze', Key='orders.csv')
            ord_data = ord_obj['Body'].read().decode('utf-8').splitlines()
            
            cleaned_ord_rows = ["order_id,customer_id,total_price,order_date"]
            for line in ord_data[1:]:
                if not line.strip():
                    continue
                cols = line.split(',')
                order_id = int(cols[0])
                cust_id = int(cols[1])
                price = float(cols[2])
                date = cols[3].strip()
                
                cleaned_ord_rows.append(f"{order_id},{cust_id},{price},{date}")
                
            s3.put_object(Bucket='silver', Key='orders_silver.csv', Body="\n".join(cleaned_ord_rows))
            print("Successfully saved orders_silver.csv to MinIO silver bucket.")
        except Exception as e:
            print(f"Error during Silver orders transformation: {e}")

    silver_transform = PythonOperator(
        task_id='spark_silver_transform',
        python_callable=transform_bronze_to_silver
    )

    # Task 3: Simulate Databricks Gold aggregates
    # Aggregates business data and stores in 'gold' bucket
    def aggregate_silver_to_gold():
        s3 = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='admin',
            aws_secret_access_key='password',
            region_name='us-east-1'
        )
        
        # Ensure 'gold' bucket exists
        try:
            s3.head_bucket(Bucket='gold')
        except Exception:
            s3.create_bucket(Bucket='gold')

        print("Loading Silver tables for aggregation...")
        try:
            # Read customer_silver
            cust_obj = s3.get_object(Bucket='silver', Key='customer_silver.csv')
            cust_lines = cust_obj['Body'].read().decode('utf-8').splitlines()
            customers = {}
            for line in cust_lines[1:]:
                if not line.strip():
                    continue
                c_id, name, segment, bal = line.split(',')
                customers[int(c_id)] = {"name": name, "segment": segment}

            # Read orders_silver
            ord_obj = s3.get_object(Bucket='silver', Key='orders_silver.csv')
            ord_lines = ord_obj['Body'].read().decode('utf-8').splitlines()
            
            # Aggregate total revenue per customer
            revenue_by_cust = {}
            for line in ord_lines[1:]:
                if not line.strip():
                    continue
                o_id, c_id, price, date = line.split(',')
                c_id = int(c_id)
                price = float(price)
                revenue_by_cust[c_id] = revenue_by_cust.get(c_id, 0.0) + price

            # Join & Write to Gold
            gold_rows = ["customer_id,customer_name,market_segment,lifetime_value"]
            for c_id, info in customers.items():
                ltv = revenue_by_cust.get(c_id, 0.0)
                gold_rows.append(f"{c_id},{info['name']},{info['segment']},{ltv}")

            s3.put_object(Bucket='gold', Key='gold_customer_revenue.csv', Body="\n".join(gold_rows))
            print("Successfully saved gold_customer_revenue.csv to MinIO gold bucket.")
        except Exception as e:
            print(f"Error during Gold aggregation: {e}")

    gold_aggregation = PythonOperator(
        task_id='spark_gold_aggregation',
        python_callable=aggregate_silver_to_gold
    )

    # Task 4: Load gold table into PostgreSQL Data Warehouse (Synapse equivalent)
    def load_gold_to_synapse():
        s3 = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='admin',
            aws_secret_access_key='password',
            region_name='us-east-1'
        )
        
        # Read from gold bucket
        gold_obj = s3.get_object(Bucket='gold', Key='gold_customer_revenue.csv')
        gold_lines = gold_obj['Body'].read().decode('utf-8').splitlines()
        
        # Create list of tuples for insertion
        records = []
        for line in gold_lines[1:]:
            if not line.strip():
                continue
            c_id, name, segment, ltv = line.split(',')
            records.append((int(c_id), name, segment, float(ltv)))

        # Write to PostgreSQL DW
        # Use postgres parameters from environment
        pg_conn = psycopg2.connect(
            host=os.environ.get('POSTGRES_HOST', 'postgres-dw'),
            database=os.environ.get('POSTGRES_DB', 'synapse_dw'),
            user=os.environ.get('POSTGRES_USER', 'postgres'),
            password=os.environ.get('POSTGRES_PASSWORD', 'password'),
            port=int(os.environ.get('POSTGRES_PORT', 5432))
        )
        cursor = pg_conn.cursor()
        
        # Create fact/dim tables or staging
        cursor.execute("""
        CREATE SCHEMA IF NOT EXISTS synapse_dw;
        CREATE TABLE IF NOT EXISTS synapse_dw.fact_customer_revenue (
            customer_id INT PRIMARY KEY,
            customer_name VARCHAR(100),
            market_segment VARCHAR(50),
            lifetime_value DECIMAL(18, 2),
            last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # Upsert records using MERGE equivalent
        upsert_query = """
        INSERT INTO synapse_dw.fact_customer_revenue (customer_id, customer_name, market_segment, lifetime_value, last_updated_at)
        VALUES %s
        ON CONFLICT (customer_id) 
        DO UPDATE SET 
            customer_name = EXCLUDED.customer_name,
            market_segment = EXCLUDED.market_segment,
            lifetime_value = EXCLUDED.lifetime_value,
            last_updated_at = CURRENT_TIMESTAMP;
        """
        
        execute_values(cursor, upsert_query, records)
        pg_conn.commit()
        
        cursor.close()
        pg_conn.close()
        print(f"Successfully loaded {len(records)} records into Postgres Synapse fact_customer_revenue.")

    synapse_load = PythonOperator(
        task_id='synapse_load_warehouse',
        python_callable=load_gold_to_synapse
    )

    copy_to_bronze >> silver_transform >> gold_aggregation >> synapse_load
