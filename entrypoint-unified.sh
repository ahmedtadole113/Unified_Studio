#!/bin/bash
set -e

echo "=========================================================="
echo "  Azure Data Engineering Practice Lab — Unified Container"
echo "=========================================================="

# ── 1. Initialize PostgreSQL ──
if [ ! -d "/data/pgdata" ]; then
    echo "📦 Initializing PostgreSQL data directory..."
    mkdir -p /data/pgdata
    chown postgres:postgres /data/pgdata
    su - postgres -c "/usr/lib/postgresql/13/bin/initdb -D /data/pgdata"
    # Allow local connections without password
    echo "host all all 0.0.0.0/0 trust" >> /data/pgdata/pg_hba.conf
    echo "local all all trust" >> /data/pgdata/pg_hba.conf
    # Start PostgreSQL temporarily to create the synapse_dw database
    su - postgres -c "/usr/lib/postgresql/13/bin/pg_ctl -D /data/pgdata start -w"
    su - postgres -c "createdb synapse_dw" || true
    su - postgres -c "/usr/lib/postgresql/13/bin/pg_ctl -D /data/pgdata stop -w"
    echo "✅ PostgreSQL initialized with synapse_dw database"
fi

# ── 2. Initialize MinIO data directories ──
mkdir -p /data/minio

# ── 3. Initialize Airflow ──
export AIRFLOW_HOME="/data/airflow"
if [ ! -d "$AIRFLOW_HOME" ]; then
    echo "📦 Initializing Airflow..."
    mkdir -p "$AIRFLOW_HOME/dags"
    # Copy DAGs into Airflow home
    cp /opt/airflow-dags/*.py "$AIRFLOW_HOME/dags/" 2>/dev/null || true

    export AIRFLOW__CORE__EXECUTOR="SequentialExecutor"
    export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="sqlite:///$AIRFLOW_HOME/airflow.db"
    export AIRFLOW__CORE__LOAD_EXAMPLES="False"
    export AIRFLOW__WEBSERVER__AUTH_ROLE_PUBLIC="Admin"

    airflow db init
    airflow users create \
        --username admin --password admin \
        --firstname Admin --lastname Admin \
        --role Admin --email admin@example.com || true
    echo "✅ Airflow initialized"
else
    # Sync DAGs on restart
    cp /opt/airflow-dags/*.py "$AIRFLOW_HOME/dags/" 2>/dev/null || true
fi

# ── 4. Initialize Grafana data ──
mkdir -p /data/grafana

# ── 5. Initialize users.json ──
if [ ! -f "/data/users.json" ]; then
    echo '{"aariz": {"password": "aariz", "role": "admin"}, "ariz": {"password": "aariz", "role": "admin"}}' > /data/users.json
    echo "✅ Default users created"
fi

# ── 6. Create MinIO buckets in background ──
(
    sleep 8
    echo "📦 Creating MinIO buckets..."
    /usr/local/bin/mc alias set myminio http://localhost:9000 admin password 2>/dev/null
    /usr/local/bin/mc mb myminio/warehouse --ignore-existing 2>/dev/null || true
    /usr/local/bin/mc mb myminio/bronze --ignore-existing 2>/dev/null || true
    /usr/local/bin/mc mb myminio/silver --ignore-existing 2>/dev/null || true
    /usr/local/bin/mc mb myminio/gold --ignore-existing 2>/dev/null || true
    echo "✅ MinIO buckets ready"
) &

# ── 7. pgAdmin server config ──
mkdir -p /data/pgadmin
if [ ! -f "/data/pgadmin/servers.json" ]; then
    cat > /data/pgadmin/servers.json << 'SRVEOF'
{
    "Servers": {
        "1": {
            "Name": "Synapse DW (Local)",
            "Group": "Servers",
            "Host": "localhost",
            "Port": 5432,
            "MaintenanceDB": "synapse_dw",
            "Username": "postgres",
            "SSLMode": "prefer"
        }
    }
}
SRVEOF
fi

echo ""
echo "🚀 Starting all services via supervisord..."
echo "   Portal: http://localhost:5173"
echo "=========================================================="

# Launch supervisord as PID 1
exec /usr/bin/supervisord -c /etc/supervisord.conf
