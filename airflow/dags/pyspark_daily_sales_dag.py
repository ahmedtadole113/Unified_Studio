from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'azure_admin',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'retries': 0,
    'retry_delay': timedelta(seconds=10),
}

with DAG(
    'pyspark_daily_sales_dag',
    default_args=default_args,
    description='Run PySpark 4.2 Daily Sales Aggregation',
    schedule_interval='@daily',
    catchup=False,
) as dag:

    run_spark_job = BashOperator(
        task_id='run_daily_sales_aggregation',
        bash_command='python /opt/airflow/dags/spark_jobs/daily_sales_aggregation.py'
    )

    run_spark_job
