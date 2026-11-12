"""Phase 10 (Days 42-45): Production Incident Scenarios, AI Failure Modes & 4-Year SRE Readiness."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_42_TO_45: List[Dict] = [
    make_day(
        day=42,
        phase=10,
        title="Production Scenarios I: CPU 100%, Memory Leak, Disk Full & Timeouts",
        subtitle="Full Incident Lifecycle: Detect (Prom/Spark) -> Triage -> Mitigate -> Verify -> Blameless Postmortem",
        goal="Execute end-to-end production incident command cleanly under time pressure",
        objective=(
            "Synthesize Linux, Networking, Prometheus, and Splunk into a calm, repeatable **Incident Command** loop: "
            "detect via Golden Signals, isolate root cause objectively, execute Runbook mitigation, verify recovery, and publish a blameless postmortem."
        ),
        concepts=[
            "**Incident Command Lifecycle**: Detect (Alert/Burn) -> Acknowledge & Assess Blast Radius -> Mitigate User Impact FIRST (rollback/failover/rate-limit/reset) -> Verify Metrics+Logs Green -> Blameless Postmortem (systemic fixes, NEVER blame humans).",
            "Do NOT start deep code refactoring during an active SEV-1 — restore user SLO first, preserve forensic evidence (`ps`/`logs`/`trace_id`), then fix permanently post-incident.",
        ],
        deep_sections=[
            sec(
                "1. Top 4 Infrastructure Production Scenarios (Quick Triage Matrix)",
                "Practice walking through each of these 4 classic scenarios cleanly in interviews AND live inside A³P Chaos Lab:",
                table={
                    "headers": ["Incident", "Telemetry Signal", "Immediate Mitigation", "Systemic Fix"],
                    "rows": [
                        ["CPU 100%", "Prom CPU > 90%, Load >> nproc, p99 spike", "Scale replicas / shed non-critical load / rollback hot loop", "Profile flamegraph, fix O(n²) loop or regex"],
                        ["Memory Leak", "Sawtooth RSS climbing -> Exit 137 OOMKills", "Grab heap dump BEFORE graceful pod recycle", "Fix unbounded cache/session map + heap cap"],
                        ["Disk Full", "df 100% / Kafka stalled / lsof +L1", "Truncate active big log (`: >`), expand LV, prune images", "Add logrotate + disk alerts at 75%/85%"],
                        ["504 DB Timeout", "Fast TCP connect, slow TTFB, pool exhausted", "Circuit-break slow query, increase/tune pool or failover", "Add DB index, statement_timeout, read replica"],
                    ],
                },
            ),
        ],
        architecture="Chaos/Incident -> Prometheus Alert + Spark/FAISS Match -> SPL/Traces Triage -> Runbook Mitigation -> Gemini Postmortem",
        commands=[
            {"cmd": "curl -s -X POST http://ai_agent:8000/api/chaos -H 'Content-Type: application/json' -d '{\"scenario\":\"db_timeout\",\"duration_seconds\":45,\"intensity\":1.0}' | jq .", "explain": "Inject live DB Timeout & 504 latency outage into A³P", "cwd": "/lab"},
            {"cmd": "sleep 6 && curl -s 'http://ai_agent:8000/api/recommendations?limit=3' | jq .", "explain": "Inspect live Spark Streaming + FAISS AI Agent triage recommendation", "cwd": "/lab"},
            {"cmd": "curl -s -X POST http://ai_agent:8000/api/chaos/reset | jq .", "explain": "Mitigate incident back to steady baseline and verify recovery", "cwd": "/lab"},
        ],
        production_use_case="Drilling full Detect -> Mitigate -> Verify -> Gemini Postmortem cycles live on Aariz Advance AI platform (A³P).",
        scenarios=[
            scenario(
                "Checkout 504 Timeout Spike After Harmless-Looking Minor Feature Deploy",
                "Availability drops from 99.95% to 94.2%; Admission Gate flips to `HOLD`; SPL shows `database connection timeout` on `/checkout`.",
                "Check deploy timeline -> compare p99 + DB pool saturation + trace waterfall -> rollback OR kill blocking DB lock",
                "New feature ran an unindexed `SELECT` inside an open DB transaction, exhausting the 20-connection pool and blocking healthy endpoints!",
                "Mitigate immediately (`git revert` / rollout undo / kill blocking query), verify 5xx rate returns to 0, then add statement timeouts, connection-pool isolation (bulkheads), and query-plan CI checks.",
            ),
        ],
        troubleshooting=["Declaring 'resolved' right after restarting a pod without waiting for error rate & p99 charts to flatten -> wait 2–3 scrape cycles before closing incident."],
        interview_qa=[
            qa("Walk me through debugging a sudden production 504/timeout spike.", "1) Check error budget burn & blast radius (all users vs 1 endpoint). 2) Inspect Golden Signals (latency, traffic, errors, saturation) + recent deployments/feature flags. 3) Correlate trace waterfall & SPL logs (`trace_id`) to isolate app vs downstream DB/DNS. 4) Mitigate user impact first (rollback/rollback flag/shed load), verify metrics recover, then author a blameless postmortem.", "senior"),
        ],
        assignment_items=[
            "Inject db_timeout in Chaos Lab, verify Spark/FAISS + Prometheus alerts, and reset",
            "Draft & publish a blameless postmortem via Postmortems -> Draft with Gemini",
            "Walk through all 4 matrix incidents (CPU, Memory Leak, Disk Full, Timeout) aloud",
        ],
        revision=["Mitigate user impact BEFORE deep debugging", "Preserve forensic evidence before restart", "Verify metrics green before closing"],
        interview_sim=[
            sim("At 2:10 PM, p99 latency spikes 10x and error rate hits 8% right after a normal deploy 8 minutes ago. Walk through your exact decision at 2:12 PM: debug forward or rollback?", ["Mitigate first -> rollback immediately (unless rollback is destructive like schema drop), verify recovery, then debug safely in staging"]),
            sim("How do you run a genuinely **blameless** postmortem when an engineer pushed the broken config?", ["Assume good intent; ask 'how did our CI/Admission Gate/peer review/guardrails allow one human typo to break prod?' -> fix the system"]),
            sim("Give 3 systemic action items (NOT 'be more careful') after a Disk-Full outage caused by unrotated logs.", ["1) Automated logrotate/retention policy, 2) Terraform/Helm disk alerts at 75%/85%, 3) CI Admission check verifying log bounds"]),
            sim("A service has a slow memory leak climbing 50 MB/hr toward OOMKill. How do you capture root-cause evidence before recycling pods?", ["Drain traffic (delete endpoints/cordon), trigger heap/memory profile (pprof/jmap/tracemalloc), THEN delete pod cleanly"]),
            sim("What is a 'cascading retry storm' during a DB timeout incident and how do you stop it?", ["Clients retrying failed requests multiply DB load 3x–10x; fix with exponential backoff + jitter + circuit breakers"]),
        ],
    ),

    make_day(
        day=43,
        phase=10,
        title="Production Scenarios II: K8s, DNS, TLS, Git & Terraform Failures",
        subtitle="CrashLoopBackOff, ImagePullBackOff, Node NotReady, CoreDNS, SSL Expiry & IaC Drift",
        goal="Solve complex cross-layer platform outages spanning Kubernetes, TLS/DNS, Git, and Terraform",
        objective=(
            "Rehearse multi-domain platform outages cleanly: K8s node/pod failures, DNS outages, expired TLS certificates, "
            "broken Git merges, and out-of-band Terraform infrastructure drift."
        ),
        concepts=[
            "Platform incidents rarely stay inside one tool: e.g., an expired TLS cert triggers `502` on Nginx Ingress, retries trigger HPA pod scale-up, exhausting subnet IPs (`Pending` pods!).",
            "Always isolate layer by layer: DNS (`dig`) -> L4 TCP (`nc`) -> TLS (`openssl`) -> K8s (`describe`/`events`/`logs --previous`) -> IaC (`terraform plan`).",
        ],
        deep_sections=[
            sec(
                "1. Platform Failure Fast-Lookup Reference",
                "Keep these 5 root-cause patterns sharp for senior SRE technical rounds:",
                table={
                    "headers": ["Failure", "First Command", "Exact Culprit"],
                    "rows": [
                        ["K8s `CrashLoopBackOff`", "`kubectl describe pod` + `logs --previous`", "Exit 1 config error / 137 OOMKill / bad probe"],
                        ["K8s `Node NotReady`", "`kubectl describe node` + `journalctl -u kubelet`", "DiskPressure / MemoryPressure / containerd down"],
                        ["DNS Outage in K8s", "`kubectl get pods,ep -n kube-system -l k8s-app=kube-dns`", "CoreDNS crashed or NetworkPolicy blocked UDP/TCP 53"],
                        ["TLS Outage", "`openssl s_client -connect host:443 ... x509 -dates`", "Expired cert, wrong SAN, or missing intermediate CA"],
                        ["Terraform State Lock / Drift", "`terraform plan -detailed-exitcode`", "Manual console edit (`exit 2`) or hung CI lock"],
                    ],
                },
            ),
        ],
        architecture="K8s Debug (Events/--previous) | DNS/TLS Probe (dig/openssl) | Git Revert | Terraform Plan/Reconcile",
        commands=[
            {"cmd": "kubectl apply -f /lab/k8s-demo/crashloop-broken.yaml && sleep 3 && kubectl get events -n sre-practice --sort-by=.lastTimestamp | tail -n 6", "explain": "Trigger and inspect Kubernetes pod crash events", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl delete pod crashloop-lab -n sre-practice --ignore-not-found && dig +short prometheus kafka", "explain": "Clean up broken pod and verify internal service DNS resolution", "cwd": "/lab/k8s-demo"},
            {"cmd": "cd /lab/terraform-lab && terraform plan -no-color", "explain": "Confirm zero infrastructure drift in /lab/terraform-lab", "cwd": "/lab/terraform-lab"},
        ],
        production_use_case="Combines K8s, DNS, TLS, Git, and Terraform checks into real incident drills on OrbStack.",
        scenarios=[
            scenario(
                "Kubernetes Node Flips to `NotReady` and Pods Start Evicting Across AZ-1",
                "Prometheus alerts `KubeNodeNotReady` while `kube_pod_status_phase{phase='Pending'}` climbs.",
                "kubectl describe node <node> ; check Conditions (MemoryPressure, DiskPressure, PIDPressure, Ready) ; journalctl -u kubelet",
                "Node's `/var/lib/docker` or `/var/log/pods` filled 92% of root disk, triggering `DiskPressure` and blocking kubelet health lease renewals.",
                "Cordon & safely drain (`kubectl drain --ignore-daemonsets --delete-emptydir-data`), prune dead images/logs or expand volume, verify `Ready`, and uncordon.",
            ),
        ],
        troubleshooting=["Never run `kubectl delete pod --force --grace-period=0` on a StatefulSet pod unless you verified the underlying node is genuinely dead (risk of split-brain volume corruption!)."],
        interview_qa=[
            qa("How do you diagnose a Kubernetes `Node NotReady` or cluster-wide DNS failure?", "For `Node NotReady`: `kubectl describe node` (check `MemoryPressure`/`DiskPressure`/`PIDPressure`), then on the node check `systemctl status kubelet containerd` and `journalctl -u kubelet`. For DNS failure: verify CoreDNS pods & `kube-dns` Endpoints (`kubectl get ep kube-dns -n kube-system`), test `dig @10.96.0.10`, and check NetworkPolicy rules for UDP/TCP 53.", "senior"),
        ],
        assignment_items=[
            "Run crashloop event capture, cleanup, DNS check, and terraform plan verify",
            "Walk through Node NotReady DiskPressure triage & safe cordon/drain",
            "Explain why force-deleting StatefulSet pods without node verification causes split-brain",
        ],
        revision=["Node NotReady -> describe node Conditions + kubelet logs", "DNS fail -> CoreDNS pods + kube-dns endpoints + port 53", "Never force-delete StatefulSet pod lightly"],
        interview_sim=[
            sim("New pods fail with `ImagePullBackOff: toomanyrequests: You have reached your pull rate limit` from Docker Hub during a node replacement storm. How do you mitigate & prevent?", ["Immediate: mirror/pull from private ECR/GAR cache; Long-term: pull-through registry mirror & avoid public Docker Hub in prod"]),
            sim("A cluster upgrade stalls because `kubectl drain node-3` hangs on `cannot evict pod as it would violate the pod's disruption budget`. What do you check?", ["Check PDB (`kubectl get pdb -A`): minAvailable equals total replicas (e.g. replicas=1 with minAvailable=1)!"]),
            sim("After renewing an Ingress TLS secret, `curl` still serves the expired certificate. Why?", ["Ingress controller cached old cert, secret key typo (`tls.crt`/`tls.key`), or wrong namespace / DNS still pointing to old LB"]),
            sim("How do you recover if a `kube-system` CoreDNS ConfigMap edit broke DNS cluster-wide?", ["kubectl edit/apply saved Git manifest of `coredns` ConfigMap in `kube-system` + `kubectl rollout restart deploy/coredns -n kube-system`"]),
            sim("Compare `kubectl drain` vs `kubectl cordon`.", ["cordon only marks node Unschedulable for NEW pods; drain cordons AND gracefully evicts existing pods respecting PDBs"]),
        ],
    ),

    make_day(
        day=44,
        phase=10,
        title="Production Scenarios III: AI/Agentic Failure Modes & Admission Gate",
        subtitle="Model Drift, Train/Serve Feature Skew, Output Variance, Token/GPU Cost Anomalies & SSDLC",
        goal="Operate AI & Agentic workloads with SLOs, drift detection, FinOps caps, and release gating",
        objective=(
            "Go beyond traditional HTTP 200 uptime: catch silent AI quality degradation (data drift, train/serve skew, hallucination/output variance) "
            "and runaway token/GPU spend anomalies, and gate production releases on objective AI/SSDLC reliability checks."
        ),
        concepts=[
            "**Silent AI Failure**: An LLM or ML service can return **HTTP 200 OK in 180ms** while emitting garbage because input feature distributions drifted (`drift > 0.65`) or online feature transforms diverge from offline training (`train/serve skew > 0.50`)!",
            "**Token & GPU FinOps**: An unthrottled agentic loop or prompt-injection spike can burn `$10k/hr` in GPU/token costs even with moderate QPS — emit `ai_token_usage_rate` and `ai_gpu_cost_usd_hourly` alerts + per-tenant token budgets.",
            "**AI & Agentic SSDLC**: Enforce automated evaluation benchmarks, prompt/guardrail regression tests, Shadow/Canary fallback, and Segregation-of-Duties sign-off in A³P's **Admission Gate**.",
        ],
        deep_sections=[
            sec(
                "1. AI-Specific Production Failure Modes vs Traditional Microservices",
                "Senior SRE roles operating AI/agentic systems specifically test these 4 failure modes:",
                table={
                    "headers": ["AI Failure Mode", "A³P Live Metric / Alert", "Mitigation Pattern"],
                    "rows": [
                        ["Data / Model Drift", "`ai_model_drift_score > 0.65` (`AIModelDriftDetected`)", "Switch traffic to validated shadow/fallback model & trigger retraining check"],
                        ["Train / Serve Skew", "`ai_train_serve_skew_score > 0.50` (`AITrainServeSkewHigh`)", "Enforce unified feature store (`Feast`/shared transform library) in CI"],
                        ["Output / Latency Variance", "`ai_output_variance_score` & `inf_ms`", "Pin decoding temp, schema validation (`responseMimeType`), semantic fallback"],
                        ["Token / GPU Cost Anomaly", "`ai_gpu_cost_usd_hourly > 12` (`AIGPUCostAnomaly`)", "Cap `maxOutputTokens`, enforce agent max-step loop circuit breakers & caching"],
                    ],
                },
            ),
        ],
        architecture="AI Metrics (Drift/Skew/Variance/GPU$) -> Spark + Prom Alerts -> Admission Gate (HOLD) -> Gemini Triage & Shadow Fallback",
        commands=[
            {"cmd": "curl -s -X POST http://ai_agent:8000/api/chaos -H 'Content-Type: application/json' -d '{\"scenario\":\"ai_drift\",\"duration_seconds\":30,\"intensity\":1.0}' | jq .", "explain": "Inject live AI Model Drift & Train/Serve Skew into A³P", "cwd": "/lab"},
            {"cmd": "sleep 5 && curl -s http://ai_agent:8000/api/dashboard/overview | jq '.live.readiness | {gate_status, passed_count, total_checks}'", "explain": "Verify Admission Gate flips automatically off ADMIT when AI drift breaches SLO", "cwd": "/lab"},
            {"cmd": "curl -s -X POST http://ai_agent:8000/api/chaos/reset | jq .", "explain": "Reset AI Drift scenario and restore healthy Admission Gate posture", "cwd": "/lab"},
        ],
        production_use_case="Core differentiator of Aariz Advance AI platform (A³P): unifying traditional infra SRE with real-time AI/Agentic observability, Gemini triage, and FinOps.",
        scenarios=[
            scenario(
                "LLM Agent Loop Enters Infinite Tool-Retry Spiral Overnight — `$4,200` Token Spike with All HTTP 200s!",
                "Prometheus `AIGPUCostAnomaly` fires (`ai_gpu_cost_usd_hourly` spikes > $12/hr) even though HTTP `5xx` rate is `0%`.",
                "Inspect `aiops_gemini_tokens_total`, `/api/dashboard/overview` AI KPIs, and trace spans of tool-calling loops",
                "An agent failed JSON schema parsing on a tool output and retried `max_iterations=unlimited` with full conversation context every second.",
                "Cap `max_iterations` and per-request token budgets (`maxOutputTokens`), enforce structured schema (`responseMimeType: application/json`), add semantic caching, and alert on token burn-rate alongside latency.",
            ),
        ],
        troubleshooting=["Ignoring `ai_model_drift_score` until customers report bad answers leaves hours/days of silent quality degradation."],
        interview_qa=[
            qa("How do you define SLOs for an AI/LLM service beyond HTTP 200 and uptime?", "Measure: 1) End-to-end TTFT & p99 inference latency, 2) Schema/format validity & guardrail pass rate, 3) Feature drift & train/serve skew scores, 4) Model fallback rate, and 5) Cost/token budget per successful task.", "senior"),
            qa("Explain Train/Serve Skew with a concrete engineering example.", "During offline training, Python `pandas` replaces missing income with the dataset mean and normalizes timestamps in UTC; in live serving, a Go/C++ API replaces missing fields with `0` or local timezone! Model inputs match schema (`HTTP 200`) yet predictions degrade badly.", "senior"),
        ],
        assignment_items=[
            "Run ai_drift and token_gpu_cost_spike scenarios and observe Prometheus + Admission Gate",
            "Ask Google Gemini SRE Copilot in AI Ops tab to diagnose live drift & SSDLC gates",
            "Explain 4 AI production failure modes and how A³P monitors each",
        ],
        revision=["HTTP 200 != AI correctness", "Monitor Drift, Skew, Variance, GPU/Token $/hr", "Bound agent loops + enforce JSON schemas"],
        interview_sim=[
            sim("A newly deployed recommendation model passes all unit tests and returns HTTP 200 in 45ms, yet business conversion drops 18%. How could an SRE detect this in <15 minutes?", ["Track feature distribution drift (PSI/KL divergence), null-feature rate, prediction distribution skew, and shadow A/B comparison alerts"]),
            sim("What guardrails prevent an autonomous AI agent from running infinite tool-call loops or leaking system secrets?", ["Hard iteration/step budget, per-user token rate limit, sandboxed least-privilege tool auth, output PII/secret redaction, and human approval for destructive tools"]),
            sim("Why did our earlier Gemini `mode=postmortem` JSON call truncate mid-string before adding `responseMimeType: application/json` and raising `maxOutputTokens`?", ["Reasoning/thinking tokens count against total output token budget on Gemini 2.5 models!"]),
            sim("How do you implement graceful degradation when an external LLM provider returns HTTP 429/503?", ["Circuit breaker -> local deterministic/FAISS playbook fallback (like A³P does!) + prompt compaction + multi-region/provider fallback"]),
            sim("How does AI & Agentic SSDLC extend traditional CI/CD security gates?", ["Adds dataset lineage, eval/hallucination benchmark regression gates, prompt-injection tests, and model card sign-off before Admission"]),
        ],
    ),

    make_day(
        day=45,
        phase=10,
        title="4-Year SRE Staff Readiness: Error Budgets, Toil, FinOps & Executive Briefs",
        subtitle="SLOs > Raw Uptime, Error Budget Policies, Toil ROI, Segregation of Duties & Evidence Narratives",
        goal="Communicate reliability, performance, and cost trade-offs like an embedded Principal/Staff SRE",
        objective=(
            "Bring all 45 days together into cohesive SRE leadership habits: justify velocity holds using objective Error Budgets, "
            "prioritize automation by Toil ROI, partner cleanly across Eng/Security/FinOps, and defend architecture trade-offs with live data."
        ),
        concepts=[
            "**SLOs > 100% Uptime**: 100% reliability is practically impossible and leaves zero budget for deployments or chaos experiments. An **Error Budget** (`100% - SLO`) turns reliability vs feature velocity from an emotional argument into shared math!",
            "**Error Budget Policy**: When budget remains (`>0%`), Product Engineering ships freely; when budget exhausts (`HOLD`), Engineering shifts capacity exclusively to reliability fixes/postmortem items until budget recovers.",
            "**Toil Elimination ROI**: Quantify toil (`frequency/wk * minutes/run * human error risk`), automate the highest-ROI repetitive tasks via self-service/CI gates, and keep SRE engineering time > 50% project/automation work.",
            "**Segregation of Duties**: Embedded SREs partner closely with Product, Platform, Security & Risk — co-defining SLOs and **owning the production Admission Decision** objectively.",
        ],
        deep_sections=[
            sec(
                "1. Leading with Evidence: How a 4-Year SRE Answers Executive Trade-Off Questions",
                "Weak answer: *'We shouldn't deploy today because the system feels unstable.'* Strong SRE answer: *'Our 5m Availability SLI dipped to 99.1%, burning 82% of our 30-day Error Budget at 4.8x burn rate with 2 unmitigated SEV-2 AI drift items. Per our co-signed Error Budget Policy, Admission Gate is HOLD until we restore pool limits and verify zero drift in Chaos Lab.'*",
                sre_example="Generate this exact evidence brief live right now using A³P's **Stakeholder Narrative Builder** (`/api/narrative`) or Gemini **`narrative`** mode!",
            ),
        ],
        architecture="SLOs & Error Budgets + Toil ROI + Chaos Evidence + FinOps Ledger -> Stakeholder Reliability Narrative & Admission Decision",
        commands=[
            {"cmd": "curl -s http://ai_agent:8000/api/narrative | jq -r '.narrative_md'", "explain": "Generate live evidence-backed SRE Stakeholder Narrative from A³P telemetry", "cwd": "/lab"},
            {"cmd": "curl -s http://ai_agent:8000/api/dashboard/overview | jq '{slos: .live.slos, gate: .live.readiness.gate_status, toil_auto_pct: .toil.automation_pct, costs: .costs}'", "explain": "Inspect synthesized SLOs, Admission Gate, Toil ROI %, and FinOps summary", "cwd": "/lab"},
        ],
        production_use_case="Rehearsing final 4-year SRE panel rounds, executive readiness reviews, and daily autonomous SRE workflows on A³P.",
        scenarios=[
            scenario(
                "VP of Engineering Demands Deploying a Major Feature Despite 0% Remaining Error Budget",
                "A high-profile launch misses readiness checks (`gate=HOLD`, 0% error budget left after two SEV-1s this month), and Product pushes to override the gate.",
                "Generate live evidence brief (`GET /api/narrative`), present exact burn math, open SEV-1 postmortem action items, and risk exposure",
                "Without an agreed-upon **Error Budget Policy** and Segregation-of-Duties gate, SRE becomes either a rubber stamp or an arbitrary blocker.",
                "Hold the Segregation-of-Duties line calmly using co-defined objective data: propose concrete unblock criteria (e.g., fix top 2 postmortem safeguards + pass 90s chaos load verification in staging, OR documented executive risk acceptance exception if business-critical).",
            ),
        ],
        troubleshooting=["Saying 'we must achieve 100% uptime' in an SRE interview -> signals tool-operator thinking rather than reliability economics."],
        interview_qa=[
            qa("Why are SLOs and Error Budgets superior to targeting 100% uptime?", "100% uptime leaves zero room for releases, hardware failures, or chaos testing, and costs exponentially more for imperceptible user gain. An SLO (e.g. 99.9%) creates an Error Budget (`0.1%`) that aligns engineering velocity and operational safety using objective release policies.", "senior"),
            qa("How do you measure and prioritize SRE toil elimination?", "Track repetitive, manual, interrupt-driven tasks with zero enduring value (`frequency/week x duration` + blast radius). Prioritize automating the top weekly time sinks with high human-error risk (e.g. certificate checks, readiness verification, log triage) into CI gates or self-service tooling.", "senior"),
            qa("What makes an effective SRE vs a traditional ops 'ticket/tool operator'?", "An embedded SRE uses software engineering and systems rigor: codifies dashboards/alerts in Git, runs hypothesis-driven chaos & capacity tests before impact, owns admission gates via SLO math, eliminates toil systematically, and drives blameless learning back into product architecture.", "senior"),
        ],
        assignment_items=[
            "Generate a live Stakeholder Narrative via /api/narrative and Gemini Draft Exec Brief",
            "Log and toggle a Toil automation item in Toil, Capacity & Cost",
            "Complete an Admission Gate Segregation-of-Duties sign-off review",
            "Run Gemini Mock Interview Mode across Phases 1-10 to test readiness",
        ],
        revision=["100% uptime is wrong target", "Error Budgets align Dev velocity & SRE stability", "Quantify Toil ROI (freq x duration)", "Lead every discussion with objective evidence"],
        interview_sim=[
            sim("A product manager says '99.9% SLO means we can afford 43 minutes of downtime every month, so let's schedule maintenance'. How do you explain Error Budgets accurately?", ["Budget covers unplanned outages, deploys, AND maintenance combined; once spent, feature releases freeze until recovered"]),
            sim("How do you justify spending 3 engineering sprints automating a manual release checklist that only takes 2 hours/week?", ["Evaluate total org toil across N teams, human error outage cost (`SEV-1` cost >> 3 sprints), and deployment velocity blocked while waiting on manual SRE signoff"]),
            sim("Describe a situation where you pushed back on launching a system into production. What evidence convinced stakeholders?", ["Present objective Admission Gate failure (missing failover test, unvalidated backup restore, burning budget, or missing runbook/alerting) + concrete unblock path"]),
            sim("How do you balance Cloud/AI FinOps cost reduction without breaking reliability SLOs?", ["Rightsize idle capacity & cache repetitive LLM calls while keeping multi-AZ redundancy & headroom on critical tiers — measure cost per unit SLO"]),
            sim("Give a 60-second summary of how Aariz Advance AI platform (A³P) mirrors real production SRE operations.", ["Covers log ingestion (Fluentd->Kafka), stream anomaly detection (PySpark->FAISS), Prometheus/Grafana SLOs, Chaos Lab, Admission Gate, Toil/FinOps, OrbStack K8s/IaC sandbox, and Gemini SRE Copilot"]),
        ],
    ),
]

