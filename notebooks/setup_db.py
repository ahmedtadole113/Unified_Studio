"""
Setup script: loads all TPC-H CSV files into a local DuckDB database.
Run this once with %run ./setup_db.py before using %%sql cells.
"""
import duckdb
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "data/tpch.duckdb")
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

TABLES = [
    "customer", "lineitem", "nation", "orders",
    "part", "partsupp", "region", "supplier"
]

conn = duckdb.connect(DB_PATH)

for table in TABLES:
    csv_path = os.path.join(DATA_DIR, f"{table}.csv")
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto('{csv_path}', header=true)")
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"✅ Loaded {table}: {count:,} rows")

conn.close()
print(f"\n🎉 DuckDB database ready at: {DB_PATH}")
print("Now run: %sql duckdb:///data/tpch.duckdb")
