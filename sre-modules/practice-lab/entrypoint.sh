#!/usr/bin/env bash
set -euo pipefail

setup_kubeconfig() {
  mkdir -p /root/.kube
  if [ -f /kube-host/config ]; then
    python3 - <<'PY'
import re, pathlib
raw = pathlib.Path('/kube-host/config').read_text(encoding='utf-8')
raw = raw.replace('https://127.0.0.1:26443', 'https://host.docker.internal:26443')
raw = raw.replace('https://localhost:26443', 'https://host.docker.internal:26443')
if 'tls-server-name:' not in raw:
    raw = re.sub(
        r'^([ \t]*)server:\s*https://host\.docker\.internal:26443',
        r'\1server: https://host.docker.internal:26443\n\1tls-server-name: kubernetes',
        raw,
        flags=re.MULTILINE,
    )
pathlib.Path('/root/.kube/config').write_text(raw, encoding='utf-8')
PY
    chmod 600 /root/.kube/config || true
    kubectl create namespace sre-practice >/dev/null 2>&1 || true
  fi
}

seed_workspace() {
  mkdir -p /lab/linux/Projects /lab/linux/Logs /lab/linux/Scripts /lab/backups
  mkdir -p /lab/git-remote /lab/docker-demo /lab/k8s-demo /lab/helm-demo /lab/terraform-lab /lab/ansible-lab /lab/cicd-demo /lab/nginx-demo

  # Linux & Scripting sample files
  cat > /lab/linux/file1.txt <<'EOF'
alpha 100 ok
beta 200 warn
gamma 300 error
alpha 100 ok
EOF
  cp /lab/linux/file1.txt /lab/linux/oldname.txt
  printf "10\n2\n45\n8\n" > /lab/linux/numbers.txt
  printf "id,name,cpu\n1,api-1,34\n2,worker-1,88\n3,db-1,62\n" > /lab/linux/data.csv
  printf "node1 10.0.1.10\nnode2 10.0.1.11\n" > /lab/linux/file2.txt
  printf "PORT=8080\nAPP_ENV=practice\nLOG_LEVEL=INFO\n" > /lab/linux/.env
  printf "[DEFAULT]\nSomeSetting = enabled\n" > /lab/linux/config.ini
  printf "name: sre-lab\nversion: 1.0\n" > /lab/linux/config.yaml
  cat > /lab/linux/Logs/app.log <<'EOF'
2026-11-11T10:00:01Z INFO service=api status=200 latency_ms=42 msg="healthy"
2026-11-11T10:00:05Z WARN service=db status=200 latency_ms=280 msg="slow query"
2026-11-11T10:00:12Z ERROR service=api status=500 latency_ms=1420 msg="database connection timeout"
2026-11-11T10:00:18Z INFO service=worker status=200 latency_ms=55 msg="batch processed"
2026-11-11T10:00:25Z ERROR service=ai_agent status=503 latency_ms=910 msg="model drift alert"
EOF
  cat > /lab/linux/Scripts/health_check.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
for target in "http://data_generator:8000/health" "http://prometheus:9090/-/ready" "http://ai_agent:8000/api/health"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$target" || echo "000")
  echo "$target -> HTTP $code"
done
EOF
  chmod +x /lab/linux/Scripts/health_check.sh

  # Practice Git repo + local bare remote
  if [ ! -d /lab/git-remote/demo.git ]; then
    git init --bare /lab/git-remote/demo.git >/dev/null 2>&1
  fi
  if [ ! -d /lab/git-demo/.git ]; then
    mkdir -p /lab/git-demo
    cd /lab/git-demo
    git init -b main >/dev/null 2>&1
    git config user.name "SRE Practitioner"
    git config user.email "sre@orbstack.local"
    printf "# SRE Git Practice Repo\nservice: aiops-demo\n" > README.md
    printf "replicas=2\n" > config.env
    git add . && git commit -m "chore: initial baseline" >/dev/null 2>&1
    git remote add origin /lab/git-remote/demo.git
    git push -u origin main >/dev/null 2>&1 || true
    git checkout -b feature/slo-alert >/dev/null 2>&1
    printf "slo_target=99.9\n" >> config.env
    git add config.env && git commit -m "feat: add SLO target config" >/dev/null 2>&1
    git checkout main >/dev/null 2>&1
  fi

  # Docker sample lab
  cat > /lab/docker-demo/app.py <<'EOF'
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hello from SRE Docker Practice App\n")
if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 5000), H).serve_forever()
EOF
  cat > /lab/docker-demo/Dockerfile <<'EOF'
FROM python:3.9-slim
WORKDIR /app
COPY app.py .
RUN useradd -m appuser
USER appuser
EXPOSE 5000
CMD ["python3", "app.py"]
EOF

  # Kubernetes practice manifests (scoped to sre-practice namespace)
  cat > /lab/k8s-demo/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sre-nginx-demo
  namespace: sre-practice
  labels:
    app: sre-nginx-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sre-nginx-demo
  template:
    metadata:
      labels:
        app: sre-nginx-demo
    spec:
      containers:
        - name: nginx
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 2
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: sre-nginx-svc
  namespace: sre-practice
spec:
  selector:
    app: sre-nginx-demo
  ports:
    - port: 80
      targetPort: 80
EOF
  cat > /lab/k8s-demo/configmap-secret.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: sre-demo-config
  namespace: sre-practice
data:
  APP_ENV: "practice"
  SLO_TARGET: "99.9"
---
apiVersion: v1
kind: Secret
metadata:
  name: sre-demo-secret
  namespace: sre-practice
type: Opaque
stringData:
  API_TOKEN: "demo-practice-token"
EOF
  cat > /lab/k8s-demo/crashloop-broken.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: crashloop-lab
  namespace: sre-practice
spec:
  containers:
    - name: broken
      image: busybox:1.36
      command: ["sh", "-c", "echo 'missing config /etc/app/prod.conf' >&2; exit 1"]
  restartPolicy: Always
EOF

  # Helm practice chart
  if [ ! -f /lab/helm-demo/Chart.yaml ]; then
    helm create /lab/helm-demo >/dev/null 2>&1 || true
  fi

  # Terraform local practice lab (pre-seeded provider cache from /opt/tf-seed)
  if [ ! -f /lab/terraform-lab/main.tf ]; then
    cp -r /opt/tf-seed/.terraform* /lab/terraform-lab/ 2>/dev/null || true
    cat > /lab/terraform-lab/variables.tf <<'EOF'
variable "environment" {
  type    = string
  default = "orbstack-sre-lab"
}
variable "slo_target" {
  type    = string
  default = "99.9"
}
EOF
    cat > /lab/terraform-lab/main.tf <<'EOF'
terraform {
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

resource "local_file" "service_manifest" {
  filename = "${path.module}/generated_service.json"
  content = jsonencode({
    service     = "aiops-practice"
    environment = var.environment
    slo_target  = var.slo_target
  })
}

resource "null_resource" "readiness_hook" {
  triggers = {
    manifest_id = local_file.service_manifest.id
  }
}
EOF
    cat > /lab/terraform-lab/outputs.tf <<'EOF'
output "manifest_path" {
  value = local_file.service_manifest.filename
}
EOF
  fi

  # Ansible local practice lab
  cat > /lab/ansible-lab/inventory.ini <<'EOF'
[local_lab]
localhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3
EOF
  cat > /lab/ansible-lab/vars.yml <<'EOF'
service_name: sre-practice-web
slo_target: "99.9"
EOF
  cat > /lab/ansible-lab/playbook.yml <<'EOF'
- name: SRE Practice Local Playbook
  hosts: local_lab
  vars_files:
    - vars.yml
  tasks:
    - name: Ensure practice artifact directory exists
      file:
        path: /lab/ansible-lab/output
        state: directory
    - name: Render service readiness note
      copy:
        dest: /lab/ansible-lab/output/status.txt
        content: "Managed by Ansible: {{ service_name }} | SLO={{ slo_target }}\n"
    - name: Print confirmation
      debug:
        msg: "Configured {{ service_name }} at SLO {{ slo_target }}"
EOF

  # CI/CD & Proxy sample configs
  cat > /lab/cicd-demo/Jenkinsfile <<'EOF'
pipeline {
  agent any
  environment { APP_ENV = 'production' }
  stages {
    stage('Checkout') { steps { sh 'git status' } }
    stage('Test')     { steps { sh 'python3 -m unittest --help >/dev/null' } }
    stage('Security') { steps { echo 'Run Trivy & OWASP Dependency-Check gates' } }
    stage('Deploy')   { steps { echo 'kubectl apply -f /lab/k8s-demo/deployment.yaml' } }
  }
}
EOF
  cat > /lab/nginx-demo/nginx.conf <<'EOF'
events {}
http {
  upstream aiops_backend {
    server ai_agent:8000;
  }
  server {
    listen 8088;
    location / {
      proxy_pass http://aiops_backend;
      proxy_set_header Host $host;
    }
  }
}
EOF
}

setup_kubeconfig
seed_workspace
if [ "${1:-}" = "--seed-only" ]; then
  exit 0
fi
exec python3 /opt/lab_server.py
