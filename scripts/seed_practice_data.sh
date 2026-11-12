#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${ROOT_DIR}/data"

echo "==> Creating synapse_dw practice schema and loading 8 TPC-H tables into postgres-dw..."
docker exec -i postgres-dw psql -v ON_ERROR_STOP=1 -U postgres -d synapse_dw <<'SQL'
CREATE SCHEMA IF NOT EXISTS synapse_dw;

CREATE TABLE IF NOT EXISTS synapse_dw.region (
    r_regionkey INT PRIMARY KEY,
    r_name      VARCHAR(25) NOT NULL,
    r_comment   VARCHAR(152)
);

CREATE TABLE IF NOT EXISTS synapse_dw.nation (
    n_nationkey INT PRIMARY KEY,
    n_name      VARCHAR(25) NOT NULL,
    n_regionkey INT NOT NULL,
    n_comment   VARCHAR(152)
);

CREATE TABLE IF NOT EXISTS synapse_dw.customer (
    c_custkey    INT PRIMARY KEY,
    c_name       VARCHAR(25) NOT NULL,
    c_address    VARCHAR(40) NOT NULL,
    c_nationkey  INT NOT NULL,
    c_phone      VARCHAR(15) NOT NULL,
    c_acctbal    DECIMAL(15,2) NOT NULL,
    c_mktsegment VARCHAR(10) NOT NULL,
    c_comment    VARCHAR(117) NOT NULL
);

CREATE TABLE IF NOT EXISTS synapse_dw.supplier (
    s_suppkey   INT PRIMARY KEY,
    s_name      VARCHAR(25) NOT NULL,
    s_address   VARCHAR(40) NOT NULL,
    s_nationkey INT NOT NULL,
    s_phone     VARCHAR(15) NOT NULL,
    s_acctbal   DECIMAL(15,2) NOT NULL,
    s_comment   VARCHAR(101) NOT NULL
);

CREATE TABLE IF NOT EXISTS synapse_dw.part (
    p_partkey     INT PRIMARY KEY,
    p_name        VARCHAR(55) NOT NULL,
    p_mfgr        VARCHAR(25) NOT NULL,
    p_brand       VARCHAR(10) NOT NULL,
    p_type        VARCHAR(25) NOT NULL,
    p_size        INT NOT NULL,
    p_container   VARCHAR(10) NOT NULL,
    p_retailprice DECIMAL(15,2) NOT NULL,
    p_comment     VARCHAR(23) NOT NULL
);

CREATE TABLE IF NOT EXISTS synapse_dw.partsupp (
    ps_partkey    INT NOT NULL,
    ps_suppkey    INT NOT NULL,
    ps_availqty   INT NOT NULL,
    ps_supplycost DECIMAL(15,2) NOT NULL,
    ps_comment    VARCHAR(199) NOT NULL,
    PRIMARY KEY (ps_partkey, ps_suppkey)
);

CREATE TABLE IF NOT EXISTS synapse_dw.orders (
    o_orderkey      BIGINT PRIMARY KEY,
    o_custkey       INT NOT NULL,
    o_orderstatus   CHAR(1) NOT NULL,
    o_totalprice    DECIMAL(15,2) NOT NULL,
    o_orderdate     DATE NOT NULL,
    o_orderpriority VARCHAR(15) NOT NULL,
    o_clerk         VARCHAR(15) NOT NULL,
    o_shippriority  INT NOT NULL,
    o_comment       VARCHAR(79) NOT NULL
);

CREATE TABLE IF NOT EXISTS synapse_dw.lineitem (
    l_orderkey      BIGINT NOT NULL,
    l_partkey       INT NOT NULL,
    l_suppkey       INT NOT NULL,
    l_linenumber    INT NOT NULL,
    l_quantity      DECIMAL(15,2) NOT NULL,
    l_extendedprice DECIMAL(15,2) NOT NULL,
    l_discount      DECIMAL(15,2) NOT NULL,
    l_tax           DECIMAL(15,2) NOT NULL,
    l_returnflag    CHAR(1) NOT NULL,
    l_linestatus    CHAR(1) NOT NULL,
    l_shipdate      DATE NOT NULL,
    l_commitdate    DATE NOT NULL,
    l_receiptdate   DATE NOT NULL,
    l_shipinstruct  VARCHAR(25) NOT NULL,
    l_shipmode      VARCHAR(10) NOT NULL,
    l_comment       VARCHAR(44) NOT NULL,
    PRIMARY KEY (l_orderkey, l_linenumber)
);
SQL

for tbl in region nation customer supplier part partsupp orders lineitem; do
  COUNT="$(docker exec postgres-dw psql -U postgres -d synapse_dw -tAc "SELECT COUNT(*) FROM synapse_dw.${tbl};" | tr -d '[:space:]')"
  if [ "${COUNT}" = "0" ]; then
    echo "  -> Loading synapse_dw.${tbl} from ${tbl}.csv..."
    docker exec -i postgres-dw psql -v ON_ERROR_STOP=1 -U postgres -d synapse_dw -c "\copy synapse_dw.${tbl} FROM STDIN WITH (FORMAT csv, HEADER true)" < "${DATA_DIR}/${tbl}.csv"
  else
    echo "  -> synapse_dw.${tbl} already has ${COUNT} rows."
  fi
done

echo "==> Populating synapse_dw.fact_customer_revenue from customer + orders..."
docker exec -i postgres-dw psql -v ON_ERROR_STOP=1 -U postgres -d synapse_dw <<'SQL'
INSERT INTO synapse_dw.fact_customer_revenue (customer_id, customer_name, market_segment, lifetime_value, last_updated_at)
SELECT
    c.c_custkey,
    c.c_name,
    c.c_mktsegment,
    COALESCE(ROUND(SUM(o.o_totalprice), 2), 0.00) AS lifetime_value,
    CURRENT_TIMESTAMP
FROM synapse_dw.customer c
LEFT JOIN synapse_dw.orders o ON o.o_custkey = c.c_custkey
GROUP BY c.c_custkey, c.c_name, c.c_mktsegment
ORDER BY lifetime_value DESC
LIMIT 500
ON CONFLICT (customer_id) DO UPDATE SET
    customer_name = EXCLUDED.customer_name,
    market_segment = EXCLUDED.market_segment,
    lifetime_value = EXCLUDED.lifetime_value,
    last_updated_at = CURRENT_TIMESTAMP;
SQL

echo "==> Uploading 8 TPC-H CSVs to MinIO (bronze/tpch/) via portal-backend..."
docker exec -i portal-backend python3 - <<'PY'
import os, boto3

s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id=os.environ.get("MINIO_ROOT_USER", "admin"),
    aws_secret_access_key=os.environ.get("MINIO_ROOT_PASSWORD", "ues_minio_secret"),
    region_name="us-east-1",
)
for bucket in ("bronze", "silver", "gold", "warehouse"):
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)

data_dir = "/home/iceberg/data"
tables = ["region", "nation", "customer", "supplier", "part", "partsupp", "orders", "lineitem"]
for t in tables:
    s3.upload_file(f"{data_dir}/{t}.csv", "bronze", f"tpch/{t}.csv")
print("Uploaded 8 TPC-H CSVs to MinIO s3://bronze/tpch/")
PY

echo "==> Seeding identical 8 practice tables into PySpark Iceberg (demo.practice.*)..."
docker exec -i spark-processing python3 - <<'PY'
from pyspark.sql import SparkSession

data_dir = "/home/iceberg/data"
tables = ["region", "nation", "customer", "supplier", "part", "partsupp", "orders", "lineitem"]
spark = SparkSession.builder.appName("UES_Seed_Practice_Iceberg").getOrCreate()
spark.sql("CREATE NAMESPACE IF NOT EXISTS demo.practice")
existing = {r["tableName"] for r in spark.sql("SHOW TABLES IN demo.practice").collect()}
for t in tables:
    if t not in existing:
        df = spark.read.option("header", "true").option("inferSchema", "true").csv(f"{data_dir}/{t}.csv")
        df.writeTo(f"demo.practice.{t}").using("iceberg").createOrReplace()
        print(f"Created demo.practice.{t} ({df.count()} rows)")
    else:
        print(f"demo.practice.{t} already exists")
spark.stop()
PY
echo "==> Done! Identical practice data ready in Postgres DW (synapse_dw.*) and PySpark/Iceberg (demo.practice.*)."
