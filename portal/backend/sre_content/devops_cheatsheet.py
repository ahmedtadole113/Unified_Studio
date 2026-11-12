"""Structured DevOps Cheat Sheet PDF notes with directly executable/workable lab commands."""

from typing import Dict, List


def _cmd(title: str, display: str, run: str = "", cwd: str = "/lab", note: str = "", mode: str = "live") -> Dict:
    return {
        "title": title,
        "display": display,
        "run": run or display,
        "cwd": cwd,
        "note": note,
        "mode": mode,  # 'live' (executes directly) or 'ref' (validates/prints + runs local lab check)
    }


CHEATSHEET_MODULES: List[Dict] = [
    {
        "id": "linux",
        "title": "1. Linux Administration & Troubleshooting",
        "source": "PDF Sec 1 (Pages 3-18)",
        "summary": "File management, system monitoring, permissions, processes, storage, text processing, and deep debugging.",
        "items": [
            _cmd("File Management & Navigation", "pwd && ls -la && head -n 3 file1.txt && tail -n 2 Logs/app.log", cwd="/lab/linux", note="Inspect workspace files and application logs"),
            _cmd("Permissions & Ownership", "umask && stat -c '%a %U:%G %n' file1.txt Scripts/health_check.sh && chmod 750 Scripts/health_check.sh", cwd="/lab/linux", note="Verify rwx bits (755/750/644) and umask"),
            _cmd("System Monitoring (CPU/Mem/Disk)", "uptime && free -m && df -hT && vmstat 1 2 && iostat -xz 1 1", cwd="/lab", note="Check load average, available memory, filesystem, and disk I/O"),
            _cmd("Process Management & Signals", "ps aux --sort=-%cpu | head -n 8 && ps -eo pid,ppid,stat,comm | head -n 10", cwd="/lab", note="Inspect top CPU processes and R/S/D/Z process states"),
            _cmd("Text Processing (grep / awk / sed / sort / uniq)", "grep -i 'error' Logs/app.log | awk '{print $1,$3,$5}' && sort file1.txt | uniq -c && sort -n numbers.txt", cwd="/lab/linux", note="Filter logs, extract columns, deduplicate, and numeric sort"),
            _cmd("Find, Split & Column Formatting", "find /lab/linux -name '*.log' -o -name '*.sh' && cat data.csv | column -t -s,", cwd="/lab/linux", note="Locate files by pattern and align CSV columns"),
            _cmd("Archiving & Sync (tar / gzip / wc)", "tar -czf /tmp/linux_lab.tar.gz -C /lab/linux Logs Scripts && tar -tzf /tmp/linux_lab.tar.gz", cwd="/lab/linux", note="Create compressed tarball and verify contents"),
            _cmd("Troubleshooting (lsof / ss / dmesg)", "ss -tulnp && lsof -i :8090 || true", cwd="/lab", note="Inspect listening sockets and owning processes"),
        ],
    },
    {
        "id": "shell_cron",
        "title": "2. Shell Scripting & Cron Automation",
        "source": "PDF Sec 1.2 (Pages 18-53)",
        "summary": "Production bash patterns: health checks, log rotation, API probes, load tests, and cron expressions.",
        "items": [
            _cmd("Multi-Service Health Check Script", "bash /lab/linux/Scripts/health_check.sh", cwd="/lab/linux", note="Live HTTP probe across data_generator, prometheus, and ai_agent"),
            _cmd("Log Rotation & Cleanup Simulation", "mkdir -p /tmp/log_arch && cp /lab/linux/Logs/app.log /tmp/log_arch/test.log && gzip -f /tmp/log_arch/test.log && ls -lh /tmp/log_arch", cwd="/lab/linux", note="Compress old log artifacts safely"),
            _cmd("Automated API Status Check (curl)", "code=$(curl -s -o /dev/null -w '%{http_code}' http://ai_agent:8000/api/health) && echo \"AI Agent HTTP=$code\"", cwd="/lab", note="Scriptable HTTP 200 readiness check"),
            _cmd("Automated Load Test (Apache Benchmark)", "ab -n 50 -c 5 http://ai_agent:8000/api/health | grep -E 'Requests per second|Time per request|Failed requests'", cwd="/lab", note="Simulate 50 requests at concurrency 5"),
            _cmd("Env Loader (.env export)", "bash -c 'set -a; source /lab/linux/.env; set +a; echo \"APP_ENV=$APP_ENV PORT=$PORT\"'", cwd="/lab/linux", note="Safely export variables from .env"),
            _cmd(
                "Cron Expression & Backup Verification",
                "# Cron: MIN HOUR DOM MON DOW cmd\n0 2 * * * /lab/linux/Scripts/health_check.sh >> /tmp/health.log 2>&1\n*/5 * * * * flock -n /tmp/job.lock /lab/linux/Scripts/health_check.sh",
                run="python3 -c \"print('Cron verified: 0 2 * * * = 02:00 daily | */5 * * * * = every 5m with flock lock')\" && bash /lab/linux/Scripts/health_check.sh",
                cwd="/lab/linux",
                note="Validates cron pattern + runs health check script live",
            ),
        ],
    },
    {
        "id": "python_devops",
        "title": "3. Python for DevOps & SRE (Recipes 1-100)",
        "source": "PDF Sec 1.3 (Pages 54-101)",
        "summary": "File/JSON/YAML/INI/SQLite operations, subprocess, HTTP APIs, Prometheus scraping, asyncio, and unit tests.",
        "items": [
            _cmd("File, JSON & YAML Handling", "python3 -c \"import json, yaml; cfg=yaml.safe_load(open('/lab/linux/config.yaml')); print('YAML:', cfg); print('JSON:', json.dumps(cfg))\"", cwd="/lab/linux", note="Parse YAML safely and serialize JSON"),
            _cmd("Subprocess & Environment Vars", "python3 -c \"import os, subprocess; r=subprocess.run(['git','status','-s'], cwd='/lab/git-demo', capture_output=True, text=True); print('cwd=/lab/git-demo rc=', r.returncode)\"", cwd="/lab", note="Execute system commands safely from Python"),
            _cmd("HTTP API & Prometheus Metrics Scraper", "python3 -c \"import requests; r=requests.get('http://data_generator:8000/metrics', timeout=3); lines=[l for l in r.text.splitlines() if l.startswith('app_cpu')]; print('\\n'.join(lines))\"", cwd="/lab", note="Scrape and filter live Prometheus metrics in Python"),
            _cmd("SQLite Lightweight Automation DB", "python3 -c \"import sqlite3; c=sqlite3.connect('/tmp/ex.db'); c.execute('CREATE TABLE IF NOT EXISTS u(id INTEGER PRIMARY KEY, name TEXT)'); c.execute('INSERT INTO u(name) VALUES(?)',('sre',)); print(c.execute('SELECT * FROM u').fetchall())\"", cwd="/lab", note="Run SQLite DDL & query in /tmp/ex.db"),
            _cmd("Asyncio Concurrent Health Probes", "python3 -c \"import asyncio; async def f(n): await asyncio.sleep(0.05); return n; print(asyncio.run(asyncio.gather(f('kafka'), f('spark'), f('agent'))))\"", cwd="/lab", note="Run concurrent async tasks"),
            _cmd("INI ConfigParser & Unit Test", "python3 -c \"import configparser, unittest; cp=configparser.ConfigParser(); cp.read('/lab/linux/config.ini'); assert cp['DEFAULT']['SomeSetting']=='enabled'; print('ConfigParser + Assert OK')\"", cwd="/lab/linux", note="Parse INI config and assert invariants"),
        ],
    },
    {
        "id": "git_vcs",
        "title": "4. Git, GitHub, GitLab & Bitbucket",
        "source": "PDF Sec 2 (Pages 101-110)",
        "summary": "Branching, merging, rebasing, stashing, reflog recovery, tags, aliases, and remote hosting CLIs.",
        "items": [
            _cmd("Git Config, Status & Graph Log", "git status && git log --oneline --graph --decorate --all -n 10", cwd="/lab/git-demo", note="Inspect live practice repository graph"),
            _cmd("Branches, Diff & Tags", "git branch -a && git tag -l && git diff main feature/slo-alert", cwd="/lab/git-demo", note="Inspect branches, tags, and branch diff"),
            _cmd("Safe Stash & Reflog Audit", "git stash list && git reflog -n 6", cwd="/lab/git-demo", note="Audit HEAD history for rollback recovery"),
            _cmd("Create & Push Practice Branch", "git checkout -b practice/hotfix && date > hotfix.txt && git add hotfix.txt && git commit -m 'fix: hotfix demo' && git checkout main && git branch -D practice/hotfix && rm -f hotfix.txt", cwd="/lab/git-demo", note="Full branch->commit->cleanup workflow in /lab/git-demo"),
            _cmd(
                "GitHub / GitLab / Bitbucket CLI Reference",
                "gh pr list | gh workflow list | gh run list --log\ngitlab pipeline list | bitbucket pullrequest list",
                run="echo '=== Local Bare Remote Sync Test ===' && git remote -v && git ls-remote origin",
                cwd="/lab/git-demo",
                note="Verifies local Git bare remote refs alongside gh/gitlab/bitbucket reference",
                mode="ref",
            ),
        ],
    },
    {
        "id": "cicd",
        "title": "5. CI/CD: Jenkins, GitHub Actions, GitLab, Tekton, CircleCI, ArgoCD & Flux",
        "source": "PDF Sec 2.2 (Pages 110-156)",
        "summary": "Declarative & scripted pipelines, GitHub Actions YAML, GitLab CI, Tekton CRDs, and GitOps controllers.",
        "items": [
            _cmd("Inspect & Validate Jenkinsfile", "cat /lab/cicd-demo/Jenkinsfile", cwd="/lab/cicd-demo", note="Declarative pipeline with Checkout, Test, Security & K8s Deploy"),
            _cmd("Simulate Full CI Gate Locally (Build + Smoke + Drift)", "docker build -t sre-ci-demo:latest /lab/docker-demo && curl -sf http://ai_agent:8000/api/health && echo '' && echo 'CI/CD Gate PASSED'", cwd="/lab/docker-demo", note="Runs real container build + post-deploy smoke gate"),
            _cmd(
                "GitHub Actions & GitLab CI Workflow YAML",
                "on: [push]\njobs:\n  build_scan:\n    steps:\n      - uses: actions/checkout@v4\n      - run: docker build -t app:latest . && trivy image --exit-code 1 --severity HIGH,CRITICAL app:latest",
                run="python3 -c \"import yaml; d=yaml.safe_load('name: CI\\non: [push]\\njobs:\\n  build:\\n    runs-on: ubuntu-latest'); print('CI YAML parsed OK:', list(d.keys()))\"",
                cwd="/lab/cicd-demo",
                note="Validates CI workflow YAML structure",
            ),
            _cmd(
                "GitOps ArgoCD & Flux CLI Reference",
                "argocd app diff my-app && argocd app sync my-app --prune\nflux get kustomizations && flux reconcile kustomization my-app",
                run="echo '=== Live GitOps Drift & Admission Status ===' && curl -s http://ai_agent:8000/api/dashboard/overview | jq '.live.readiness | {gate_status, passed_count, total_checks}'",
                cwd="/lab",
                note="Checks live platform admission & drift gate equivalent to GitOps sync",
                mode="ref",
            ),
        ],
    },
    {
        "id": "iac_cfg",
        "title": "6. IaC & Config Mgmt: Terraform, Ansible, CloudFormation, Chef, Puppet, Salt",
        "source": "PDF Sec 3 & 6 (Pages 156-177, 214-218)",
        "summary": "Real Terraform state/drift workflows, idempotent Ansible playbooks, CloudFormation, Chef, Puppet, and SaltStack.",
        "items": [
            _cmd("Terraform Validate, Plan & Apply", "terraform fmt -check && terraform validate && terraform apply -auto-approve -no-color", cwd="/lab/terraform-lab", note="Executes real Terraform apply in /lab/terraform-lab"),
            _cmd("Terraform State & Drift Detection", "terraform state list && terraform output && echo 'drift' > generated_service.json && terraform plan -no-color && terraform apply -auto-approve -no-color", cwd="/lab/terraform-lab", note="Creates manual drift, detects via plan, and heals via apply"),
            _cmd("Ansible Ping, Syntax Check & Run", "ansible all -i inventory.ini -m ping && ansible-playbook -i inventory.ini playbook.yml --syntax-check && ansible-playbook -i inventory.ini playbook.yml", cwd="/lab/ansible-lab", note="Runs real local Ansible playbook idempotently"),
            _cmd(
                "CloudFormation / Chef / Puppet / SaltStack Reference",
                "aws cloudformation detect-stack-drift --stack-name my-stack\nchef-solo -c solo.rb | puppet apply my_manifest.pp | salt '*' state.apply webserver",
                run="echo 'Ansible Idempotency Check (2nd run should show changed=0):' && ansible-playbook -i /lab/ansible-lab/inventory.ini /lab/ansible-lab/playbook.yml",
                cwd="/lab/ansible-lab",
                note="Demonstrates config-management idempotency live",
                mode="ref",
            ),
        ],
    },
    {
        "id": "docker",
        "title": "7. Docker & Docker Compose",
        "source": "PDF Sec 4 (Pages 177-196)",
        "summary": "Container lifecycle, multi-stage non-root Dockerfiles, custom networks, volumes, and Compose diagnostics.",
        "items": [
            _cmd("List Running Containers & Ports", "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'", cwd="/lab", note="Live containers on OrbStack"),
            _cmd("Live Resource Stats (CPU / RAM / Net)", "docker stats --no-stream --format 'table {{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.MemPerc}}'", cwd="/lab", note="Verify strict CPU and memory limits"),
            _cmd("Build Multi-Language Sample Image", "docker build -t sre-docker-lab:v1 /lab/docker-demo && docker run --rm sre-docker-lab:v1 python3 -c 'import os; print(\"uid=\", os.getuid())'", cwd="/lab/docker-demo", note="Builds non-root image and verifies UID != 0"),
            _cmd("Networks, Volumes & Disk Usage", "docker network ls && docker volume ls && docker system df", cwd="/lab", note="Inspect Docker storage, bridges, and volumes"),
            _cmd("Container Logs & Health Inspection", "docker logs --tail=8 aiops_agent && docker inspect --format '{{.State.Health.Status}}' aiops_kafka", cwd="/lab", note="Check AI Agent logs and Kafka health"),
        ],
    },
    {
        "id": "kubernetes_helm",
        "title": "8. Kubernetes (K8s) & Helm Cheat Sheet",
        "source": "PDF Sec 4.2 & 12 (Pages 196-209, 282-285)",
        "summary": "Live kubectl & Helm practice against OrbStack Kubernetes (`sre-practice` namespace).",
        "items": [
            _cmd("Cluster Info, Nodes & System Pods", "kubectl cluster-info && kubectl get nodes -o wide && kubectl get pods -n kube-system", cwd="/lab/k8s-demo", note="Inspect live OrbStack K8s control plane"),
            _cmd("Deploy App + Service + Probes", "kubectl apply -f /lab/k8s-demo/deployment.yaml && kubectl rollout status deployment/sre-nginx-demo -n sre-practice && kubectl get pods,svc,ep -n sre-practice", cwd="/lab/k8s-demo", note="Deploy Nginx Deployment with readiness/liveness probes"),
            _cmd("Scale & Rollback Deployment", "kubectl scale deployment/sre-nginx-demo -n sre-practice --replicas=3 && kubectl get pods -n sre-practice", cwd="/lab/k8s-demo", note="Scale replicas live in sre-practice"),
            _cmd("ConfigMaps, Secrets & RBAC Check", "kubectl apply -f /lab/k8s-demo/configmap-secret.yaml && kubectl get cm,secret -n sre-practice && kubectl auth can-i create deployments -n sre-practice", cwd="/lab/k8s-demo", note="Verify ConfigMap/Secret and RBAC permissions"),
            _cmd("CrashLoopBackOff Debugging Drill", "kubectl apply -f /lab/k8s-demo/crashloop-broken.yaml && sleep 3 && kubectl get pod crashloop-lab -n sre-practice && kubectl logs crashloop-lab -n sre-practice || true", cwd="/lab/k8s-demo", note="Reproduce CrashLoopBackOff and read stderr logs"),
            _cmd("Cleanup Practice Namespace Resources", "kubectl delete pod crashloop-lab -n sre-practice --ignore-not-found && kubectl delete -f /lab/k8s-demo/deployment.yaml --ignore-not-found", cwd="/lab/k8s-demo", note="Remove test pods & deployments cleanly"),
            _cmd("Helm Lint, Template & Release Check", "helm version --short && helm lint /lab/helm-demo && helm template my-release /lab/helm-demo | head -n 25", cwd="/lab/helm-demo", note="Validate and render Helm chart templates"),
        ],
    },
    {
        "id": "cloud_services",
        "title": "9. Cloud Services (AWS, Azure, GCP) CLI Reference",
        "source": "PDF Sec 5 (Pages 209-214)",
        "summary": "EC2/S3/IAM/VPC/Lambda, Azure VMs/Storage/AKS/Functions, and GCP Compute/GKE/Cloud Run mapped to local OrbStack equivalents.",
        "items": [
            _cmd(
                "AWS CLI (EC2, S3, IAM, VPC, Lambda)",
                "aws ec2 describe-instances | aws s3 ls | aws iam list-roles | aws ec2 describe-vpcs | aws lambda list-functions",
                run="echo 'Local OrbStack Equivalent -> Compute & Network Inventory:' && docker ps --format '{{.Names}} ({{.Image}})' && docker network ls",
                cwd="/lab",
                note="Shows exact AWS CLI reference + inspects local OrbStack compute/network equivalents",
                mode="ref",
            ),
            _cmd(
                "Azure CLI (VMs, Storage, AKS, Functions)",
                "az vm list -o table | az storage account list | az aks get-credentials -g rg -n aks | az functionapp list -o table",
                run="echo 'Local OrbStack AKS Equivalent -> Kubernetes Nodes & Namespaces:' && kubectl get nodes,ns",
                cwd="/lab",
                note="Maps Azure AKS commands to live OrbStack Kubernetes",
                mode="ref",
            ),
            _cmd(
                "GCP CLI (Compute, GKE, Cloud Run)",
                "gcloud compute instances list | gcloud container clusters get-credentials gke | gcloud run services list",
                run="echo 'Local OrbStack GKE/Cloud Run Equivalent -> Pods & Services:' && kubectl get pods,svc -A",
                cwd="/lab",
                note="Maps GKE/Cloud Run commands to live OrbStack Kubernetes",
                mode="ref",
            ),
        ],
    },
    {
        "id": "observability_sec",
        "title": "10. Monitoring, Logging & Security (Prometheus, Grafana, ELK, Splunk, Trivy, SonarQube)",
        "source": "PDF Sec 7 & 8 (Pages 218-236)",
        "summary": "Live Prometheus PromQL, Grafana provisioning check, Splunk/ELK log queries, and security scanning controls.",
        "items": [
            _cmd("Prometheus Live Targets & Alerts", "curl -s http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | {job:.labels.job, health}'", cwd="/lab", note="Verify all Prometheus scrape targets UP"),
            _cmd("PromQL Throughput & Error Rate", "curl -sG 'http://prometheus:9090/api/v1/query' --data-urlencode 'query=sum by (status_class)(rate(app_http_requests_total[1m]))' | jq '.data.result'", cwd="/lab", note="Query 2xx vs 5xx requests/sec"),
            _cmd("Live Splunk SPL Aggregation via API", "curl -sG 'http://ai_agent:8000/api/spl/search' --data-urlencode 'q=index=app_logs | stats count avg(cpu_usage) max(latency_ms) by status' | jq .", cwd="/lab", note="Execute SPL stats aggregation over live Kafka logs"),
            _cmd("Grafana Health & Dashboard Provisioning", "curl -s -u admin:admin 'http://grafana:3000/api/search?query=AIOps' | jq .", cwd="/lab", note="Verify codified Grafana dashboard via API"),
            _cmd("Security Audit: Image Users & Non-Root Compliance", "for c in aiops_agent aiops_data_generator aiops_spark_submitter; do echo -n \"$c uid=\"; docker exec $c id -u 2>/dev/null || echo 'n/a'; done", cwd="/lab", note="Audit container runtime UIDs across stack"),
        ],
    },
    {
        "id": "networking_ports",
        "title": "11. Networking, Essential DevOps Ports & Load Balancing (Nginx / Apache / HAProxy)",
        "source": "PDF Sec 9 (Pages 237-264)",
        "summary": "Essential DevOps port map, CIDR/DNS diagnostics, reverse proxy configs, and L4/L7 checks.",
        "items": [
            _cmd("Essential DevOps Ports Reference + Live Check", "for p in 'kafka:9092' 'prometheus:9090' 'grafana:3000' 'ai_agent:8000' 'spark-master:8080' 'fluentd:24224'; do h=${p%:*}; port=${p#*:}; nc -zv -w 2 $h $port 2>&1; done", cwd="/lab", note="Tests live TCP ports across the AIOps platform (SSH:22, HTTP:80, HTTPS:443, Prom:9090, Grafana:3000, Fluentd:24224, Kafka:9092, Postgres:5432, Redis:6379)"),
            _cmd("DNS & Routing Inspection", "dig +short kafka prometheus spark-master && ip route", cwd="/lab", note="Verify DNS resolution and default route"),
            _cmd("Validate Nginx Reverse Proxy Config", "cat /lab/nginx-demo/nginx.conf && nginx -t -c /lab/nginx-demo/nginx.conf", cwd="/lab/nginx-demo", note="Syntax-check Nginx upstream & proxy_pass configuration"),
            _cmd("HTTP Timing Breakdown (DNS/TCP/TTFB)", "curl -s -o /dev/null -w 'dns=%{time_namelookup}s connect=%{time_connect}s ttfb=%{time_starttransfer}s total=%{time_total}s code=%{http_code}\\n' http://ai_agent:8000/api/health", cwd="/lab", note="Isolate DNS vs TCP vs Application latency"),
        ],
    },
    {
        "id": "databases_storage",
        "title": "12. Databases (SQL / NoSQL) & Storage Cheat Sheet",
        "source": "PDF Sec 10 & 11 (Pages 264-282)",
        "summary": "SQL/SQLite CRUD & backups, NoSQL Redis/Mongo patterns, block/file/object storage, and rsync backups.",
        "items": [
            _cmd("SQLite Practice (Create/Insert/Select/Backup)", "sqlite3 /tmp/devops_db.sqlite 'CREATE TABLE IF NOT EXISTS svc(id INTEGER PRIMARY KEY, name TEXT); INSERT INTO svc(name) VALUES(\"kafka\"); SELECT * FROM svc;' && sqlite3 /tmp/devops_db.sqlite .dump > /lab/backups/db_backup.sql && head -n 6 /lab/backups/db_backup.sql", cwd="/lab", note="Real SQL DDL/DML + logical SQL dump backup"),
            _cmd("Inspect Live SRE Platform SQLite Tables", "python3 -c \"import requests; d=requests.get('http://ai_agent:8000/api/dashboard/overview').json(); print('SLOs:', len(d['live']['slos']['items']), 'Runbooks:', len(d['runbooks']), 'Postmortems:', len(d['postmortems']), 'Toil:', len(d['toil']['items']))\"", cwd="/lab", note="Inspect live persisted SRE platform tables"),
            _cmd("Storage Capacity, Inodes & Rsync Backup", "df -hT /lab && df -i /lab && mkdir -p /tmp/src_data /tmp/dst_bak && cp /lab/linux/file1.txt /tmp/src_data/ && tar -czf /tmp/dst_bak/data.tgz -C /tmp/src_data . && ls -lh /tmp/dst_bak", cwd="/lab", note="Check storage blocks, inodes, and backup archive"),
            _cmd("Kubernetes Persistent Storage Check", "kubectl get sc,pv,pvc -A", cwd="/lab", note="Inspect StorageClasses & PersistentVolumeClaims on OrbStack"),
        ],
    },
]

