FROM apache/airflow:2.9.2-python3.11

USER root
# Install basic build tools and Java 17 for PySpark execution
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev openjdk-17-jre-headless \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

USER airflow
# Install python packages required for ADF equivalent operators & PySpark 4.2
RUN pip install --no-cache-dir \
    "pyspark>=4.2.0" \
    apache-airflow-providers-postgres==5.11.0 \
    apache-airflow-providers-http==4.10.1 \
    psycopg2-binary==2.9.9 \
    requests==2.31.0 \
    boto3==1.34.100
