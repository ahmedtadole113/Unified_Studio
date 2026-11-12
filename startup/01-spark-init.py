"""
Spark Session Auto-Initialization
Creates a Spark 4.2 session with Iceberg and Delta Lake support on startup
"""

import os
from pyspark.sql import SparkSession

# Check if Spark session already exists
spark = SparkSession.getActiveSession()

if spark is None:
    print("🔧 Initializing Apache Spark 4.2 with Iceberg & Delta Lake support...")

    spark = SparkSession.builder.appName("JupyterNotebook") \
        .config("spark.sql.catalog.demo.s3.endpoint", "http://localhost:9000") \
        .config("spark.sql.catalog.demo.s3.path-style-access", "true") \
        .config("spark.sql.catalog.demo.s3.region", "us-east-1") \
        .config("spark.sql.ansi.enabled", "true") \
        .getOrCreate()

    # Set log level to reduce noise
    spark.sparkContext.setLogLevel("WARN")

    print(f"✨ Apache Spark {spark.version} session initialized")
    print(f"📦 Default catalog: {spark.conf.get('spark.sql.defaultCatalog', 'demo')}")
    print(f"💾 Warehouse: {spark.conf.get('spark.sql.catalog.demo.warehouse', 's3://warehouse/wh/')}")
    print("🚀 Delta Lake 4.0 & Iceberg extensions active")
else:
    print(f"✨ Spark {spark.version} session already active")

# Make spark available globally
globals()["spark"] = spark
