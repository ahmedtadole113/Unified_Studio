import re

with open("portal/backend/main.py", "r") as f:
    content = f.read()

# Replace SERVICE_PROCESSES with COMPOSE_SERVICES and SERVICE_CONTAINERS
new_mapping = """# Map of service keys to their docker compose services
COMPOSE_SERVICES = {
    "datalake": ["minio", "mc"],
    "databricks": ["spark-processing", "rest"],
    "airflow": ["airflow-webserver", "airflow-scheduler"],
    "synapse": ["postgres-dw", "pgadmin"],
    "eventhub": ["redpanda", "redpanda-console"],
    "servicebus": ["rabbitmq"],
    "monitoring": ["grafana"]
}

# Map of service keys to their primary container names for status checks
SERVICE_CONTAINERS = {
    "datalake": "minio",
    "databricks": "spark-processing",
    "airflow": "airflow-webserver",
    "synapse": "pgadmin",
    "eventhub": "redpanda-console",
    "servicebus": "rabbitmq",
    "monitoring": "grafana"
}"""
content = re.sub(r'# Map of service keys to their supervisor process names\nSERVICE_PROCESSES = \{.*?\n\}', new_mapping, content, flags=re.DOTALL)

# Replace get_supervisor_status with get_docker_status
new_get_status = """def get_docker_status(container_name: str) -> dict:
    \"\"\"Get status of a docker container.\"\"\"
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}},{{.State.Pid}}", container_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_str, pid_str = result.stdout.strip().split(",")
            pid = int(pid_str) if pid_str != "0" else None
            return {"status": status_str.lower(), "pid": pid}
        else:
            return {"status": "stopped", "pid": None}
    except Exception as e:
        logger.error(f"Failed to get status for {container_name}: {e}")
        return {"status": "error", "pid": None}"""
content = re.sub(r'def get_supervisor_status\(process_name: str\) -> dict:.*?return \{"status": "error", "pid": None\}', new_get_status, content, flags=re.DOTALL)

# Replace get_process_stats with get_container_stats
new_get_stats = """def get_container_stats(container_name: str) -> Dict:
    \"\"\"Get CPU and memory stats for a docker container.\"\"\"
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}", container_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|")
            if len(parts) == 3:
                mem_parts = parts[1].split(" / ")
                mem_usage = mem_parts[0] if len(mem_parts) > 0 else "0 MB"
                mem_limit = mem_parts[1] if len(mem_parts) > 1 else "0 MB"
                return {
                    "cpu_usage": parts[0],
                    "memory_usage": mem_usage,
                    "memory_limit": mem_limit,
                    "memory_percent": parts[2]
                }
    except Exception as e:
        logger.error(f"Failed to get stats for {container_name}: {e}")
        pass
    return {
        "cpu_usage": "0.0%",
        "memory_usage": "0 MB",
        "memory_limit": "0 MB",
        "memory_percent": "0.0%"
    }"""
content = re.sub(r'def get_process_stats\(pid: int\) -> Dict:.*?memory_percent": 0.0\n        \}', new_get_stats, content, flags=re.DOTALL)

# Update list_services
list_services_replacement = """@app.get("/api/services")
def list_services():
    services_status = {}
    for service_key, container_name in SERVICE_CONTAINERS.items():
        try:
            sup_status = get_docker_status(container_name)
            state = sup_status["status"]
            pid = sup_status["pid"]
            
            stats = {
                "cpu_usage": "0.0%",
                "memory_usage": "0 MB",
                "memory_limit": "0 MB",
                "memory_percent": "0.0%"
            }
            if state == "running" and pid:
                stats = get_container_stats(container_name)
                
            services_status[service_key] = {
                "name": SERVICE_NAMES.get(service_key, service_key.title()),
                "container_name": container_name,
                "status": "online" if state == "running" else "offline",
                "cpu_usage": stats.get("cpu_usage", "0.0%"),
                "memory_usage": stats.get("memory_usage", "0 MB"),
                "memory_limit": stats.get("memory_limit", "0 MB"),
                "memory_percent": stats.get("memory_percent", "0.0%"),
                "ui_url": SERVICE_URLS.get(service_key),
            }
        except Exception as e:
            services_status[service_key] = {
                "name": SERVICE_NAMES.get(service_key, service_key.title()),
                "container_name": container_name,
                "status": "error",
                "cpu_usage": "0%",
                "memory_usage": "0 MB",
                "memory_limit": "0 MB",
                "memory_percent": "0%",
                "ui_url": SERVICE_URLS.get(service_key),
            }
    return services_status"""
content = re.sub(r'@app\.get\("/api/services"\)\ndef list_services\(\):.*?return services_status', list_services_replacement, content, flags=re.DOTALL)

# Update start_service
start_service_replacement = """@app.post("/api/services/{service_name}/start")
def start_service(service_name: str, x_user_role: Optional[str] = Header(None)):
    if x_user_role != "admin":
        raise HTTPException(status_code=403, detail="Admin permissions required to modify services")
        
    services_to_start = COMPOSE_SERVICES.get(service_name.lower())
    if not services_to_start:
        raise HTTPException(status_code=404, detail="Service not mapped to any process")
        
    try:
        cmd = ["docker", "compose", "up", "-d"] + services_to_start
        result = subprocess.run(
            cmd,
            cwd="/home/iceberg",
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return {"status": "success", "message": f"Service {service_name} started"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to start: {result.stderr or result.stdout}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout while starting service")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))"""
content = re.sub(r'@app\.post\("/api/services/\{service_name\}/start"\).*?raise HTTPException\(status_code=500, detail=str\(e\)\)', start_service_replacement, content, flags=re.DOTALL)

# Update stop_service
stop_service_replacement = """@app.post("/api/services/{service_name}/stop")
def stop_service(service_name: str, x_user_role: Optional[str] = Header(None)):
    if x_user_role != "admin":
        raise HTTPException(status_code=403, detail="Admin permissions required to modify services")
        
    services_to_stop = COMPOSE_SERVICES.get(service_name.lower())
    if not services_to_stop:
        raise HTTPException(status_code=404, detail="Service not mapped to any process")
        
    try:
        cmd = ["docker", "compose", "stop"] + services_to_stop
        result = subprocess.run(
            cmd,
            cwd="/home/iceberg",
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return {"status": "success", "message": f"Service {service_name} stopped"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to stop: {result.stderr or result.stdout}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout while stopping service")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))"""
content = re.sub(r'@app\.post\("/api/services/\{service_name\}/stop"\).*?raise HTTPException\(status_code=500, detail=str\(e\)\)', stop_service_replacement, content, flags=re.DOTALL)

with open("portal/backend/main.py", "w") as f:
    f.write(content)
print("done")
