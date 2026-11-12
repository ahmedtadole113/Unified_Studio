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
    'pyspark_data_quality_dag',
    default_args=default_args,
    description='Run PySpark 4.2 Data Quality Check',
    schedule_interval='@daily',
    catchup=False,
) as dag:

    run_spark_job = BashOperator(
        task_id='run_data_quality_check',
        bash_command='python /opt/airflow/dags/spark_jobs/data_quality_check.py'
    )

    run_spark_job
