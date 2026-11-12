"""Phase 6 (Days 30-33): Jenkins, CI/CD Security Scanning, GitOps & Admission Rollbacks."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_30_TO_33: List[Dict] = [
    make_day(
        day=30,
        phase=6,
        title="CI/CD Architecture: Jenkins Controller/Agents & Pipeline Stages",
        subtitle="Controller vs Ephemeral Build Agents, GitHub Actions, Declarative vs Scripted & Gates",
        goal="Architect scalable, isolated CI/CD pipelines that never overload controllers",
        objective=(
            "Separate the CI control plane (Jenkins Controller / GitHub Actions orchestrator) from ephemeral execution runners (Docker/K8s agents), "
            "and wire lint -> test -> security scan -> image build -> readiness check stages cleanly."
        ),
        concepts=[
            "**Jenkins Controller** handles web UI, RBAC, credentials store, and job scheduling; **never** run builds on the controller (`numExecutors: 0`) — offload to ephemeral Docker/Kubernetes Pod agents.",
            "Modern CI stages: `Checkout -> Lint/Unit Test -> SAST/SCA -> Build Container -> Trivy Image Scan -> Push Digest -> Trigger CD`.",
            "**Declarative Pipeline** (`pipeline { agent any stages { ... } }`) provides schema validation, stage restart, and clear `post { always/failure }` blocks; **Scripted** (`node { ... }`) uses raw Groovy for complex dynamic logic.",
        ],
        deep_sections=[
            sec(
                "1. Anatomy of a Production CI/CD Stage Gate",
                "Each stage acts as a fast fail-early filter so broken code or vulnerable images never reach staging or production.",
                table={
                    "headers": ["Stage", "Tooling Example", "Fail Condition"],
                    "rows": [
                        ["1. Static Lint & Unit", "ruff/pytest, golangci-lint, yamllint", "Syntax bug or broken unit invariant"],
                        ["2. SAST & Secrets", "SonarQube, Gitleaks", "SQLi, hard-coded API keys"],
                        ["3. Build & Trivy Scan", "Docker BuildKit + Trivy", "CRITICAL/HIGH fixable CVEs"],
                        ["4. CD & Admission", "ArgoCD + A³P Readiness Gate", "Error Budget HOLD / Drift / Failing smoke check"],
                    ],
                },
            ),
        ],
        architecture="Git Push -> CI Controller -> Ephemeral Pod/Docker Agent -> Lint/Test/Scan -> Push Immutable Digest -> CD",
        commands=[
            {"cmd": "cat /lab/cicd-demo/Jenkinsfile", "explain": "Inspect declarative Jenkinsfile integrating security & K8s readiness stages", "cwd": "/lab/cicd-demo"},
            {"cmd": "python3 -c \"import yaml; y=yaml.safe_load(open('/lab/linux/config.yaml')); print('YAML valid:', y)\"", "explain": "Run fast CI YAML syntax validation step locally", "cwd": "/lab"},
        ],
        production_use_case="Feeds directly into the A³P SSDLC Quality Gates and Admission Gate release workflow.",
        scenarios=[
            scenario(
                "Jenkins UI Freezes Cluster-Wide Every Afternoon When 15 Microservices Build",
                "At 4 PM PR rush, Jenkins Web UI times out with `504` and all pipelines queue indefinitely.",
                "Inspect Jenkins System Info / Master CPU & Executor settings (`Executors on built-in node` > 0)",
                "Heavy `mvn`/`docker build` steps ran directly on the Jenkins Controller node (`master`), saturating CPU/RAM and exhausting controller disk.",
                "Set built-in controller executors to `0`, provision ephemeral Kubernetes/Docker build agents, and isolate workspaces.",
            ),
        ],
        troubleshooting=["YAML pipeline syntax errors caught locally before push save 10-minute CI debug cycles."],
        interview_qa=[
            qa("Declarative vs Scripted Jenkins Pipeline?", "Declarative enforces a structured `pipeline { agent stages post }` DSL with built-in validation, clear UI rendering, and Restart-from-Stage. Scripted runs imperative Groovy inside `node {}` blocks for rare dynamic control flow.", "basic"),
            qa("Why must build jobs never run directly on the Jenkins Controller node?", "A runaway compile/OOM kills the entire CI control plane, and build code running on the controller can potentially access `JENKINS_HOME/secrets` and credentials.", "senior"),
        ],
        assignment_items=[
            "Read /lab/cicd-demo/Jenkinsfile and explain each stage",
            "Run Python YAML validation against /lab/linux/config.yaml",
            "Explain ephemeral K8s build agents vs controller executors",
        ],
        revision=["Zero executors on Jenkins Controller", "Declarative > Scripted for maintainability", "Fail fast: Lint -> Test -> Scan -> Push"],
        interview_sim=[
            sim("How do you speed up a 14-minute CI Docker build pipeline without lowering test rigor?", ["Cache dependency layers (BuildKit cache mounts / wheels)", "Parallelize unit/lint/SAST stages", "Use multi-stage builds & .dockerignore"]),
            sim("Why should CI push `myapp:git-sha` (plus immutable digest) rather than overwriting `:latest`?", ["Guarantees deterministic rollbacks, auditability to exact Git commit, and avoids node imagePullPolicy cache bugs"]),
            sim("Explain what `post { always { cleanWs() } failure { ... } }` achieves in a Jenkinsfile.", ["Reclaims agent disk space cleanly regardless of outcome and sends failure alerts"]),
            sim("Compare Jenkins ephemeral Kubernetes Pod agents vs persistent EC2 static build slaves.", ["Ephemeral pods eliminate snowflake drift, scale to zero when idle, and isolate every build cleanly"]),
            sim("How does CI integrate with an SRE Error Budget policy?", ["Pre-deploy stage queries Prometheus/A³P Admission Gate API; HOLD blocks non-hotfix feature deploys automatically"]),
        ],
    ),

    make_day(
        day=31,
        phase=6,
        title="Credentials, OIDC, Shared Libraries & Webhooks",
        subtitle="Short-Lived OIDC vs Static Keys, Secret Masking, Shared Libraries & Webhook Triggers",
        goal="Eliminate long-lived CI secrets and standardize pipeline templates across teams",
        objective=(
            "Replace fragile copy-pasted Jenkinsfiles and static AWS/API keys with Jenkins Shared Libraries (`vars/`), "
            "short-lived OIDC federation, and push-based Webhooks instead of wasteful `pollSCM`."
        ),
        concepts=[
            "Use `withCredentials` / GitHub Secrets or **OIDC short-lived STS tokens** (zero static AWS keys stored in CI!). Never print secrets or interpolate them inside unquoted `sh \"...\"` strings.",
            "**Shared Libraries** (`@Library('sre-shared') _`) centralize security scans, build steps, and SRE Admission calls for 100+ repos.",
            "**Webhooks** push events immediately when a PR/tag happens (<1s latency, zero wasted polling); `pollSCM('* * * * *')` hammers Git servers needlessly.",
        ],
        deep_sections=[
            sec(
                "1. Secret Injection Safety in Shell Steps (`sh`)",
                "A classic Groovy/Jenkins security bug is putting `${SECRET}` inside double-quoted `sh \"curl -H $SECRET\"`, which leaks the secret in command expansion or `ps aux`.",
                example="// SAFE: Pass secret via environment variable + single-quoted shell!\nwithCredentials([string(credentialsId: 'api-key', variable: 'API_KEY')]) {\n    sh 'curl -s -H \"x-api-key: $API_KEY\" https://internal/check'\n}",
            ),
        ],
        architecture="GitHub Webhook -> CI Shared Library -> OIDC Temporary Token + Masked Env -> Build -> Smoke Gate (/api/health)",
        commands=[
            {"cmd": "grep -nE 'environment|stage|echo|sh' /lab/cicd-demo/Jenkinsfile", "explain": "Inspect declarative pipeline environment and stage blocks", "cwd": "/lab/cicd-demo"},
            {"cmd": "curl -sS http://ai_agent:8000/api/health && echo '' && curl -sS http://data_generator:8000/health && echo ''", "explain": "Simulate CI post-deploy smoke test gate against A³P services", "cwd": "/lab"},
        ],
        production_use_case="Wiring automated smoke-test and Admission Gate verification hooks directly into delivery pipelines.",
        scenarios=[
            scenario(
                "Jenkins Build Log Prints Plaintext Database Password During Deployment",
                "Security audit flags plaintext secrets visible in CI console logs.",
                "grep -rn 'withCredentials' Jenkinsfile",
                "Groovy double-quoted string `sh \"export DB_PASS=${env.PASS}\"` interpolated the secret BEFORE Jenkins' log masker registered it or split it.",
                "Bind via `environment { PASS = credentials('...') }` and reference `$PASS` strictly inside **single-quoted** `sh '...'`, or migrate to OIDC + External Secrets.",
            ),
        ],
        troubleshooting=["Webhook fails silently -> inspect GitHub webhook Delivery tab (HTTP 403 CSRF crumb, 502 firewall, or TLS self-signed cert error)."],
        interview_qa=[
            qa("Webhook vs `pollSCM`?", "Webhooks are event-driven pushes from GitHub/GitLab to CI on commit/PR (instant feedback, near-zero overhead). `pollSCM` queries Git repeatedly on a cron schedule, wasting CPU/API rate limits.", "basic"),
            qa("How does OIDC eliminate static cloud credentials in GitHub Actions / Jenkins?", "The CI runner signs a short-lived JWT identity token claiming repo/branch/environment; AWS IAM/GCP Workload Identity verifies the OIDC issuer and exchanges it for a 15-minute temporary STS role with zero stored static keys.", "senior"),
        ],
        assignment_items=[
            "Inspect Jenkinsfile blocks and run live smoke-check curls against A³P",
            "Explain single-quoted vs double-quoted sh string secret leak prevention",
            "Explain OIDC federation and Shared Libraries ROI",
        ],
        revision=["Webhooks > pollSCM", "OIDC > static IAM keys", "Single-quote sh '$VAR' to avoid Groovy interpolation leaks", "Shared Libraries DRY pipelines"],
        interview_sim=[
            sim("Why does Groovy double-quoting `sh \"echo $TOKEN\"` trigger a Jenkins security warning and risk masking bypass?", ["Groovy expands variable before passing string to bash, leaking in process args/mask misses"]),
            sim("You maintain 80 microservice repos and need every single one to adopt Trivy + A³P Admission Gate checks. How do you avoid editing 80 Jenkinsfiles per rule change?", ["Centralize pipeline template in a versioned Jenkins Shared Library / reusable GitHub Actions workflow"]),
            sim("Explain how GitHub Actions OIDC restricts `prod-deploy-role` so feature branches cannot assume production AWS permissions.", ["IAM trust policy checks `sub` claim: `repo:org/app:ref:refs/heads/main` or `environment:production`"]),
            sim("A GitHub Webhook shows HTTP 403 `No valid crumb` from Jenkins. Why?", ["Webhook hitting manual job URL instead of dedicated webhook endpoint (`/github-webhook/`) which bypasses CSRF safely with HMAC secret"]),
            sim("Why should CI pipelines query `/api/readiness/signoff` or health probes after deploy BEFORE shifting 100% traffic?", ["Automated canary/smoke validation catches bad configs before full blast radius"]),
        ],
    ),

    make_day(
        day=32,
        phase=6,
        title="DevSecOps Scanning: SAST, SCA, Trivy & K8s Admission",
        subtitle="SonarQube SAST, Dependency SCA, Container CVE Scanning & Policy Enforcement",
        goal="Shift security left inside CI/CD without creating noisy false-positive alert fatigue",
        objective=(
            "Distinguish SAST (source code), SCA (third-party dependencies/SBOM), DAST (running endpoints), and Container CVE scanning (Trivy), "
            "and enforce practical policy gates in CI and Kubernetes Admission Controllers."
        ),
        concepts=[
            "**SAST** (SonarQube/Semgrep) analyzes static source code patterns (`eval()`, SQLi). **SCA** (Dependabot/OWASP) checks `requirements.txt`/`package-lock.json` against CVE databases. **Container Scan** (Trivy/Grype) scans OS + app image layers.",
            "To avoid alert fatigue blocking every deploy on unfixable LOW CVEs, fail CI cleanly on **`HIGH,CRITICAL` with `--ignore-unfixed`** while logging MEDIUM/LOW to security tracking.",
            "**Admission Controllers** (OPA Gatekeeper / Kyverno) reject non-compliant pods at K8s API deploy time (running as root, `:latest` tag, missing resource limits).",
        ],
        deep_sections=[
            sec(
                "1. SSDLC Security Scanning Matrix",
                "Each scanner covers a blind spot missed by the others — SAST doesn't catch vulnerable `openssl` in Debian base images; Trivy image scan catches OS + Python packages together.",
                example="# Practical CI Trivy Gate (fails ONLY on actionable HIGH/CRITICAL CVEs):\ntrivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 myapp:$GIT_SHA",
                sre_example="Matches the **AI & Agentic SSDLC Quality Gates** inside A³P's AI Ops tab enforcing control objectives with Security & Risk.",
            ),
        ],
        architecture="Source (SAST/Secrets) -> Libraries (SCA/SBOM) -> Image (Trivy) -> Admission Policy (Kyverno/OPA) -> Runtime",
        commands=[
            {"cmd": "docker inspect aiops_platform-ai_agent:latest --format 'Arch={{.Architecture}} Size={{.Size}} User={{.Config.User}}'", "explain": "Audit built A³P image architecture, size, and runtime user", "cwd": "/lab"},
            {"cmd": "grep -nE 'FROM|USER' /lab/docker-demo/Dockerfile", "explain": "Verify pinned base image and non-root USER security posture", "cwd": "/lab/docker-demo"},
        ],
        production_use_case="Translating Security & Risk compliance controls directly into automated CI/CD gates and A³P SSDLC evidence.",
        scenarios=[
            scenario(
                "Critical OpenSSL/Log4j CVE Announced — Management Asks Which Running Containers Are Affected in 5 Minutes",
                "Zero-day CVE drops across all base OS libraries; 120 microservices run in production.",
                "Generate/query SBOM (CycloneDX/SPDX) from CI artifact registry + Trivy scan against running digests",
                "Without archived SBOMs (Software Bill of Materials) and pinned image digests in CI, teams spend hours manually SSHing/execing into pods.",
                "Generate an SBOM (`syft` / `trivy image --format cyclonedx`) on every CI build and store it alongside the container digest for instant CVE impact queries.",
            ),
        ],
        troubleshooting=["Blocking PRs on `LOW` or unpatched OS CVEs causes teams to bypass CI gates -> gate strictly on fixable `CRITICAL`/`HIGH`."],
        interview_qa=[
            qa("How do you prevent vulnerable or root-running images from entering production Kubernetes?", "Gate CI builds with `trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`, generate SBOMs, pin base/app digests, and enforce a Kubernetes Validating Admission Policy (Kyverno/OPA) rejecting `runAsNonRoot: false` or `:latest` tags.", "senior"),
            qa("Explain SAST vs SCA vs DAST.", "SAST scans your own static source code; SCA scans open-source third-party dependencies (`requirements.txt`, `npm`); DAST tests a live running app from the outside (fuzzing HTTP endpoints).", "basic"),
        ],
        assignment_items=[
            "Audit A³P image metadata via docker inspect and Dockerfile USER/FROM",
            "Explain SAST vs SCA vs Trivy vs Admission Controller roles",
            "Explain why --ignore-unfixed prevents false CI stalls while tracking SBOMs",
        ],
        revision=["SAST (code) + SCA (deps) + Trivy (layers) + Admission (runtime)", "Gate on fixable HIGH/CRITICAL", "Keep SBOM per release digest"],
        interview_sim=[
            sim("A security team demands failing every CI build if ANY CVE exists in Debian base images. Why will this halt delivery, and what counter-proposal balances risk and velocity?", ["Many base OS CVEs have status 'will_not_fix'/negligible risk; use distroless/slim + gate on fixable CRITICAL/HIGH + SLA remediation"]),
            sim("How does a Kubernetes Validating Admission Policy (`Kyverno`/`OPA`) complement CI security scans?", ["Blocks manual `kubectl apply` or third-party Helm charts that bypassed your CI scanner"]),
            sim("What is an SBOM and why is it valuable during a zero-day like Log4Shell?", ["Machine-readable inventory (CycloneDX/SPDX) of every package & library version in an image for instant search"]),
            sim("Why should containers set `readOnlyRootFilesystem: true` and `allowPrivilegeEscalation: false`?", ["Prevents attackers from writing malware payloads or modifying binaries inside running pods"]),
            sim("How do you ensure an image deployed to prod wasn't swapped after passing Trivy in CI?", ["Sign image digest with Sigstore Cosign in CI and verify signature in Kubernetes Admission Controller"]),
        ],
    ),

    make_day(
        day=33,
        phase=6,
        title="GitOps CD (ArgoCD / Flux) & Automated Rollbacks",
        subtitle="Pull-Based Reconciliation, Sync vs Health, Out-of-Band Drift Healing & Canary Gates",
        goal="Eliminate cluster admin credentials in CI and auto-heal configuration drift via GitOps",
        objective=(
            "Contrast Push CD (`kubectl apply` from Jenkins) vs Pull GitOps (`ArgoCD`/`Flux` inside cluster), "
            "understand `OutOfSync` vs `Degraded` states, and connect canary/automated rollbacks to Error Budgets."
        ),
        concepts=[
            "**Push CD** forces CI runners to hold cluster-admin kubeconfigs and misses manual `kubectl edit` drift later. **Pull GitOps** runs ArgoCD/Flux *inside* the cluster pulling signed manifests from Git.",
            "ArgoCD tracks two orthogonal states: **Sync Status** (`Synced` vs `OutOfSync` compared to Git) and **Health Status** (`Healthy`, `Progressing`, `Degraded`).",
            "Automated **Self-Heal** (`selfHeal: true`) reverts manual `kubectl edit` hotfixes automatically so Git remains the single source of truth.",
        ],
        deep_sections=[
            sec(
                "1. Push CI/CD vs Pull GitOps Reconciliation",
                "Keeping CI (build/test/scan image -> commit digest bump to GitOps config repo) separate from CD (ArgoCD syncing cluster to match GitOps repo) narrows security blast radius dramatically.",
                example="# ArgoCD Application syncPolicy:\nsyncPolicy:\n  automated:\n    prune: true       # Delete resources removed from Git\n    selfHeal: true    # Revert manual kubectl edit drift immediately!",
                sre_example="Simulate this directly in A³P: trigger `config_drift` in Chaos Lab and watch our **Admission Gate** immediately fail `Environment Integrity` until reconciled!",
            ),
        ],
        architecture="CI (Image Digest Bump) -> GitOps Repo <--pull-- ArgoCD/Flux Controller --reconcile--> K8s Cluster",
        commands=[
            {"cmd": "curl -sS -X POST http://ai_agent:8000/api/ask -H 'Content-Type: application/json' -d '{\"text\":\"config drift diverged from Git\"}' | jq .", "explain": "Query A³P FAISS Knowledge Base for GitOps configuration drift playbook", "cwd": "/lab"},
            {"cmd": "curl -sS http://ai_agent:8000/api/dashboard/overview | jq '.live.readiness'", "explain": "Inspect live Admission Gate checks including Environment Integrity", "cwd": "/lab"},
        ],
        production_use_case="Protecting production clusters against unauthorized hotfixes (`kubectl edit`) and enforcing Error Budget deployment freezes.",
        scenarios=[
            scenario(
                "Someone Ran `kubectl scale --replicas=1` Directly During Testing — Next Deploy Reverted or Drifted",
                "Production runs at wrong replica count after an ad-hoc manual `kubectl edit` that was never committed to Git.",
                "argocd app diff myapp ; inspect A³P Admission Gate Environment Integrity",
                "Manual cluster edits create **configuration drift** between reality and Git.",
                "Enable ArgoCD `selfHeal: true` + `OutOfSync` Prometheus alerts (`argocd_app_info{sync_status='OutOfSync'}`), and enforce read-only human RBAC in prod so changes go strictly through Git PRs.",
            ),
        ],
        troubleshooting=["ArgoCD permanently `OutOfSync` despite syncing -> cluster mutating webhook or HPA changing `spec.replicas` (add `ignoreDifferences` cleanly for HPA `replicas`)."],
        interview_qa=[
            qa("Why is Pull GitOps (ArgoCD/Flux) preferred over running `kubectl apply` inside Jenkins?", "1) Cluster admin credentials never leave the cluster to external CI runners. 2) ArgoCD continuously detects and heals live configuration drift (`selfHeal`), whereas `kubectl apply` only runs during a deploy. 3) Rollbacks are deterministic `git revert` commits.", "senior"),
            qa("How does an HPA conflict with ArgoCD `selfHeal`, and how do you fix it?", "If Git specifies `replicas: 2` and HPA scales to `5`, ArgoCD sees `OutOfSync` and scales back to `2`! Fix by omitting `spec.replicas` from the Deployment YAML when HPA is active (or configuring `ignoreDifferences` for `/spec/replicas`).", "senior"),
        ],
        assignment_items=[
            "Query A³P FAISS KB for config drift remediation and inspect Admission Gate status",
            "Explain Sync Status vs Health Status in ArgoCD",
            "Explain how Argo Rollouts performs progressive canary rollback on Prometheus metric breach",
        ],
        revision=["Pull GitOps keeps kubeconfig inside cluster", "SyncStatus != HealthStatus", "Omit spec.replicas when using HPA + ArgoCD"],
        interview_sim=[
            sim("Your ArgoCD Application shows `Synced` AND `Degraded` simultaneously. What does that mean?", ["Live manifests match Git exactly (`Synced`), yet Pods are crashing / failing Readiness probes (`Degraded`)"]),
            sim("How does Argo Rollouts automate progressive canary delivery using Prometheus SLOs?", ["Shifts 5% -> 25% -> 50% -> 100% traffic while running AnalysisTemplates against Prometheus 5xx/p99 queries; auto-aborts on breach"]),
            sim("Why did enabling `prune: true` accidentally delete a manual DB Secret during cleanup?", ["Resource wasn't tracked in GitOps repo; ArgoCD prune deletes orphaned managed resources removed from Git"]),
            sim("How do you separate the Application Source repo from the GitOps Deployment Manifest repo?", ["Prevent infinite CI rebuild loops when updating image tags; cleanest audit trail per environment"]),
            sim("Explain `Sync Waves` (`argocd.argoproj.io/sync-wave`) when deploying CRDs or DB migrations before app Pods.", ["Orders manifest application (-1 Namespace/CRD -> 0 DB Migration Job -> 1 Deployment)"]),
        ],
    ),
]

