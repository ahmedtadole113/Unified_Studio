"""Phase 8 (Days 37-39): Prometheus TSDB, PromQL Mastery & SLO-Driven Grafana Alerting."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_37_TO_39: List[Dict] = [
    make_day(
        day=37,
        phase=8,
        title="Prometheus Architecture: Pull Scraping, Exporters & Cardinality",
        subtitle="HTTP /metrics Pull Model, Service Discovery, TSDB Chunks & Label Cardinality Traps",
        goal="Operate Prometheus scraping targets cleanly and avoid high-cardinality TSDB OOM outages",
        objective=(
            "Understand why Prometheus scrapes `/metrics` over HTTP (`10s` interval in A³P), how `up == 0` catches dead targets automatically, "
            "and why unbounded labels (`user_id`, `request_id`, `email`) blow up Prometheus memory."
        ),
        concepts=[
            "**Pull Model**: Prometheus discovers targets (static, EC2, K8s Pod/ServiceMonitor) and pulls `HTTP GET /metrics` every `scrape_interval` (`10s` in A³P). Every scrape emits synthetic metric `up{job,instance}` (`1`=healthy, `0`=down).",
            "Time-series identity = `metric_name{label1=\"val1\", label2=\"val2\"}`. Every unique label combination creates a brand-new TSDB time series in RAM!",
            "**Cardinality Bomb**: putting `user_id` (100k users) x `endpoint` (50) = **5,000,000 active series** -> Prometheus OOMKills instantly! Keep labels strictly bounded (`status_class=\"2xx|4xx|5xx\"`, `method`, `service`).",
        ],
        deep_sections=[
            sec(
                "1. Prometheus Pull Model vs Pushgateway / OTel Push",
                "Prometheus also exposes a Pushgateway for ephemeral cron jobs that vanish before a 15s scrape cycle, but long-lived services always expose `/metrics` for pull scraping.",
                example="# Live A³P metrics from data_generator:8000/metrics:\napp_cpu_usage_percent 24.18\napp_http_requests_total{method=\"GET\",status_class=\"2xx\"} 4821\nai_model_drift_score 0.14\n\n# Notice `status_class` has ONLY 3 values (2xx/4xx/5xx) — bounded low cardinality!",
            ),
        ],
        architecture="Targets (/metrics: data_generator, ai_agent, grafana) <--10s HTTP Pull-- Prometheus TSDB (RAM Head + 2h Disk Blocks)",
        commands=[
            {"cmd": "curl -s http://data_generator:8000/metrics | grep -E '^(app_|ai_)' | head -n 16", "explain": "Inspect raw Prometheus text exposition metrics from data_generator", "cwd": "/lab"},
            {"cmd": "curl -s 'http://prometheus:9090/api/v1/query?query=up' | jq '.data.result[] | {job:.metric.job, instance:.metric.instance, up:.value[1]}'", "explain": "Query live target health (`up` metric) across all 4 A³P scrape jobs", "cwd": "/lab"},
        ],
        production_use_case="Powering live 10s telemetry across all 4 targets (`prometheus`, `simulated_app`, `aiops_agent`, `grafana`) in A³P.",
        scenarios=[
            scenario(
                "Prometheus Pod Enters `OOMKilled` Loop Every 20 Minutes After New Release",
                "Right after deploying an API v2 update, `prometheus-server` restarts with Exit `137`.",
                "curl -s 'http://prometheus:9090/api/v1/status/tsdb' | jq '.data.seriesCountByMetricName[:5]'",
                "A developer added `path=request.url` (with raw UUIDs like `/orders/9a8b7c...`) or `user_id` to `http_requests_total` labels, creating millions of unique series!",
                "Inspect top series via `/api/v1/status/tsdb`, drop the high-cardinality label via `metric_relabel_configs` temporarily if urgent, and replace raw URLs with low-cardinality route templates (`/orders/{id}`).",
            ),
        ],
        troubleshooting=["Target shows `DOWN` (`up == 0`) in Prometheus `/targets` -> check service DNS name, port, `/metrics` path, or NetworkPolicy."],
        interview_qa=[
            qa("Pull vs Push monitoring — why does Prometheus default to Pull?", "Pull scraping gives centralized rate control, automatic dead-instance detection (`up == 0`), simple local debugging (`curl :8000/metrics`), and no agent push-credential sprawl. Push (Pushgateway/OTel Collector) is used for short-lived batch jobs or firewalled edge networks.", "basic"),
            qa("What is high-cardinality explosion in Prometheus and how do you find & fix it?", "Every unique label-value pair allocates an independent TSDB series in memory. Unbounded labels (`user_id`, `trace_id`, raw URL paths) exhaust RAM and OOMKill Prometheus. Diagnose via `/api/v1/status/tsdb` (`seriesCountByMetricName`), normalize routes/status classes in code, or drop labels via `metric_relabel_configs`.", "senior"),
        ],
        assignment_items=[
            "Inspect raw /metrics output on data_generator:8000 and ai_agent:8000",
            "Query Prometheus `up` API and confirm all 4 A³P targets return 1",
            "Explain how high-cardinality labels crash Prometheus TSDB",
        ],
        revision=["Pull /metrics -> up == 0 catches dead targets", "Bound label cardinality (status_class, not user_id!)", "TSDB status API finds top series"],
        interview_sim=[
            sim("A developer suggests adding `trace_id` as a label on `http_request_duration_seconds` so they can find slow traces in Prometheus. Why must you reject this in PR review?", ["Every single HTTP request gets a unique trace_id -> infinite cardinality explosion -> Prometheus OOM!", "Use OpenTelemetry Exemplars on histograms instead!"]),
            sim("How does a 60-second Python batch CronJob get scraped if Prometheus only scrapes every 30s?", ["Push metrics to Prometheus Pushgateway on exit (or expose via OTel Collector) — note Pushgateway requires manual cleanup/staleness alerts"]),
            sim("What is the difference between `relabel_configs` and `metric_relabel_configs` in `prometheus.yml`?", ["relabel_configs runs BEFORE scraping (filter targets, rewrite __address__); metric_relabel_configs runs AFTER scraping before TSDB ingestion (drop noisy metrics/labels)"]),
            sim("Where does Prometheus store recent samples vs older compressed blocks?", ["In-memory Head block (backed by WAL for crash recovery) flushed every ~2 hours into immutable compacted TSDB disk chunks"]),
            sim("How do you scale Prometheus horizontally when one server hits 10M+ active series across multiple Kubernetes clusters?", ["Sharding / federation or remote_write to Thanos / Mimir / Cortex / VictoriaMetrics for global PromQL & object-storage retention"]),
        ],
    ),

    make_day(
        day=38,
        phase=8,
        title="PromQL Mastery: Counters, Gauges, Histograms & SLO Math",
        subtitle="rate() vs irate(), increase(), sum by(), histogram_quantile() & Availability Ratio",
        goal="Write accurate PromQL for golden signals, p99 tail latency, and error budgets",
        objective=(
            "Avoid the classic PromQL mistake of averaging pre-computed quantiles or calling `rate()` on Gauges: master the 4 Prometheus metric types, "
            "counter resets, `sum(rate(_bucket[5m])) by (le)`, and A³P's live Availability & Burn Rate formulas."
        ),
        concepts=[
            "**Gauge** (`app_cpu_usage_percent`, `ai_model_drift_score`): goes up/down -> query directly or use `avg_over_time()`, `max_over_time()`. **NEVER** call `rate()` on a Gauge!",
            "**Counter** (`app_http_requests_total`, `aiops_gemini_tokens_total`): monotonically increases (resets to 0 on restart) -> ALWAYS wrap in `rate(m[5m])` (per-sec average handling resets) or `increase(m[1h])`.",
            "**Histogram** emits `_bucket{le=...}`, `_sum`, `_count`: NEVER average client-computed percentiles! Always aggregate buckets first: `histogram_quantile(0.99, sum(rate(app_request_latency_seconds_bucket[1m])) by (le))`.",
        ],
        deep_sections=[
            sec(
                "1. The 4 Golden Signal PromQL Recipes (Live in A³P)",
                "Every number in the A³P Command Center Overview & Grafana dashboard comes directly from these exact PromQL patterns:",
                table={
                    "headers": ["Golden Signal", "Exact PromQL Pattern", "Why Written This Way"],
                    "rows": [
                        ["Availability % (5m)", "`100 * (1 - (sum(rate(app_http_requests_total{status_class=\"5xx\"}[5m])) / clamp_min(sum(rate(app_http_requests_total[5m])), 0.001)))`", "`clamp_min` avoids divide-by-zero when idle"],
                        ["p99 Latency (ms)", "`1000 * histogram_quantile(0.99, sum(rate(app_request_latency_seconds_bucket[1m])) by (le))`", "Must keep `by (le)` when summing across instances!"],
                        ["5xx Error Rate /s", "`sum(rate(app_http_requests_total{status_class=\"5xx\"}[1m]))`", "`rate()` handles counter resets cleanly"],
                        ["AI Drift (Gauge)", "`ai_model_drift_score`", "Read Gauge directly (no `rate()`)"],
                    ],
                },
            ),
        ],
        architecture="Counter (_total) -> rate()[5m] | Histogram (_bucket) -> sum by (le) -> histogram_quantile(0.99) | Gauge -> Direct/over_time",
        commands=[
            {"cmd": "curl -sG 'http://prometheus:9090/api/v1/query' --data-urlencode 'query=app_cpu_usage_percent' | jq '.data.result[0].value'", "explain": "Query current CPU gauge value via PromQL API", "cwd": "/lab"},
            {"cmd": "curl -sG 'http://prometheus:9090/api/v1/query' --data-urlencode 'query=1000 * histogram_quantile(0.99, sum(rate(app_request_latency_seconds_bucket[1m])) by (le))' | jq '.data.result[0].value'", "explain": "Compute live p99 request latency (ms) via histogram_quantile", "cwd": "/lab"},
            {"cmd": "curl -sG 'http://prometheus:9090/api/v1/query' --data-urlencode 'query=sum(rate(app_http_requests_total{status_class=\"5xx\"}[5m])) / clamp_min(sum(rate(app_http_requests_total[5m])), 0.001)' | jq '.data.result[0].value'", "explain": "Calculate live 5-minute 5xx error ratio powering the SLO budget engine", "cwd": "/lab"},
        ],
        production_use_case="Driving live Availability SLIs, Error Budget burn rates, and Gemini token/latency tracking inside A³P.",
        scenarios=[
            scenario(
                "Dashboard Shows `p99 Latency = 80ms` While Customers Complain About 2-Second Slowness!",
                "Team reports `avg(app_latency_p99)` across 10 pods looks fine (`80ms`), missing severe tail latency on 2 overloaded pods.",
                "Switch client-side Summary `avg()` to server-aggregated `histogram_quantile(0.99, sum(rate(app_request_latency_seconds_bucket[5m])) by (le))`",
                "Averaging quantiles/Summaries across pods is mathematically invalid (`avg(p99)` hides a single pod stalling at 4,000ms)!",
                "Emit Prometheus **Histograms** (`_bucket`), aggregate raw bucket rates globally with `sum(...) by (le)`, and compute `histogram_quantile(0.99, ...)` at query time.",
            ),
        ],
        troubleshooting=["`rate(counter[10s])` returns empty `[ ]` when scrape interval is `10s` -> range window MUST be at least `4x scrape_interval` (e.g. `[1m]`) so >=2 samples fall inside!"],
        interview_qa=[
            qa("How do you compute fleet-wide p99 latency across 10 replicas in PromQL?", "`histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`. Summing bucket rates `by (le)` first merges distributions across all pods before calculating the 99th percentile.", "senior"),
            qa("Difference between `rate()` and `irate()`?", "`rate(x[5m])` computes average per-second rate across all samples in the 5-minute window (smooth, best for alerts and SLOs). `irate(x[5m])` only uses the last two data points (hyper-spiky, good only for zoomed graphs, dangerous for alerts).", "senior"),
        ],
        assignment_items=[
            "Run live Gauge, Histogram p99, and 5xx Availability PromQL queries via /lab",
            "Test custom PromQL expressions inside A³P Observability -> PromQL Explorer",
            "Explain why rate() range must exceed 2x-4x scrape_interval and why averaging quantiles fails",
        ],
        revision=["Counter -> rate()/increase()", "Gauge -> direct / avg_over_time()", "Histogram -> sum(rate(_bucket)) by (le) -> histogram_quantile", "rate window >= 4x scrape_interval"],
        interview_sim=[
            sim("A PromQL alert uses `rate(http_requests_total[15s])` when `scrape_interval` is `15s`, and the alert never fires! Why?", ["rate needs >=2 samples in window; 15s window often catches only 0 or 1 sample -> empty result! Use >= 4x scrape_interval ([1m] or [5m])"]),
            sim("An app restarted cleanly at 12:01, resetting its monotonic counter from 500,000 back to 0. Does `rate(m[5m])` report a negative spike?", ["No — PromQL rate() detects counter resets automatically and sums increments cleanly"]),
            sim("Why can `histogram_quantile(0.99, ...)` underestimate or flatten at `5000ms` if your highest configured bucket is `le=\"5.0\"`?", ["Any latency > highest explicit bucket falls into `le=\"+Inf\"` and linearly interpolates inaccurately; pick realistic upper buckets matching your SLOs"]),
            sim("Compare a Prometheus `Summary` vs a `Histogram`.", ["Summary calculates quantiles client-side (cannot aggregate across pods!); Histogram emits cumulative buckets aggregatable globally via `sum by (le)`"]),
            sim("Write a PromQL expression returning ONLY targets currently failing health scrapes (`up == 0`) or containers restarting > 3 times in 15m.", ["up == 0 ; increase(kube_pod_container_status_restarts_total[15m]) > 3"]),
        ],
    ),

    make_day(
        day=39,
        phase=8,
        title="SLO-Driven Alerting & Codified Grafana Dashboards",
        subtitle="Multi-Window Error Budget Burn Alerts, `for:` Hysteresis & Git-Provisioned Grafana JSON",
        goal="Replace noisy cause-based pages with actionable SLO burn alerts and zero-drift dashboards",
        objective=(
            "Eliminate 3 AM alert fatigue: inspect A³P's `prometheus/alerts.yml` and codified Grafana provisioning (`dashboards.yml` + JSON), "
            "and learn Google SRE Multi-Window Multi-Burn-Rate alerting (`1h/5m` fast burn + `6h/30m` slow burn)."
        ),
        concepts=[
            "**Symptom vs Cause**: Page humans ONLY on user-impacting symptoms threatening the SLO (`ErrorBudgetBurnFast`, `LatencySLOBreach`, `AIModelDriftDetected`) — keep cause metrics (CPU 82%, disk trends) as dashboard context or warning tickets.",
            "**`for:` Duration**: requiring a rule expression to stay true for `15s–5m` avoids false pages from transient 1-second micro-spikes.",
            "**Codified Observability**: Grafana dashboards & Prometheus alerts stored in Git (`grafana/provisioning/dashboards/*.json`) guarantee identical dashboards across dev/staging/prod with zero click-ops drift.",
        ],
        deep_sections=[
            sec(
                "1. Multi-Window Multi-Burn-Rate Alerting (Google SRE Standard)",
                "If your 30-day Error Budget is `0.1%` (99.9% SLO), burning at **14.4x** consumes 2% of your entire monthly budget in **1 hour** -> **PAGE IMMEDIATELY!** Burning at **1x** stays within monthly budget -> **NO PAGE!**",
                table={
                    "headers": ["Severity", "Burn Rate", "Long / Short Window", "Action"],
                    "rows": [
                        ["Page (Critical)", "14.4x (2% budget in 1h)", "1h AND 5m both burning", "Immediate on-call page + Admission Gate HOLD"],
                        ["Page (High)", "6x (5% budget in 6h)", "6h AND 30m both burning", "Urgent page — reset cleanly when short window clears"],
                        ["Ticket (Warning)", "1x–3x slow leak", "3d AND 6h", "File engineering tech-debt ticket, no wake-up page"],
                    ],
                },
            ),
        ],
        architecture="alerts.yml (for: 10s-15s) -> Prometheus Eval (Pending -> Firing) -> Alertmanager / A³P Gate | Grafana Git JSON",
        commands=[
            {"cmd": "curl -s http://prometheus:9090/api/v1/rules | jq '.data.groups[0].rules | map({name, state, type})'", "explain": "Inspect all 9 codified alert rules and live states (inactive/pending/firing)", "cwd": "/lab"},
            {"cmd": "curl -s -u admin:admin 'http://grafana:3000/api/search?query=Aariz' | jq .", "explain": "Verify Git-provisioned A³P Grafana dashboard via Grafana API", "cwd": "/lab"},
        ],
        production_use_case="Every alert rule (`prometheus/alerts.yml`) and Grafana panel (`aiops_sre_overview.json`) in A³P is Git-codified and reproducible.",
        scenarios=[
            scenario(
                "On-Call Engineer Receives 900 'High CPU 85%' Slack Pages During Normal Auto-Scaling Bursts",
                "Engineers start muting the `#sre-alerts` channel because CPU alerts fire constantly while p99 latency and 5xx error rates stay 100% green.",
                "Audit alert-to-incident correlation over 30 days; inspect `alerts.yml` rules",
                "Alerting directly on raw CPU utilization (a *cause*, not user impact) without `for:` hysteresis causes severe alert fatigue — hiding real outages in noise.",
                "Delete raw-CPU pages, replace with multi-window SLO Error Budget burn + p99 Latency breach alerts, and keep CPU as a non-paging Grafana diagnostic panel.",
            ),
        ],
        troubleshooting=["Grafana manual UI edits disappear on container recreate -> always export updated JSON back into `grafana/provisioning/dashboards/` and commit to Git."],
        interview_qa=[
            qa("Why alert on Error Budget burn rate instead of raw CPU %?", "Customers experience failed or slow requests, not 85% CPU. High CPU with healthy latency is efficient hardware utilization! Burn-rate alerts page ONLY when reliability errors threaten your SLO budget fast enough to need human action.", "senior"),
            qa("Why does multi-window alerting check BOTH a long window (`1h`) AND a short window (`5m`)?", "Checking `1h` alone delays detection at incident start AND keeps firing for 55 minutes *after* you already mitigated the outage! Pairing `1h AND 5m` ensures fast detection AND fast alert reset (<5m after fix).", "senior"),
        ],
        assignment_items=[
            "Query live Prometheus alert rules via /api/v1/rules",
            "Verify Grafana A³P dashboard provisioning via /api/search",
            "Explain pending vs firing state transitions and multi-window burn math",
        ],
        revision=["Page on SLO symptoms, not raw CPU", "for: hysteresis stops flapping", "1h+5m dual-window resets fast after mitigation", "Dashboards codified in Git JSON"],
        interview_sim=[
            sim("Explain the three Prometheus alert states (`inactive`, `pending`, `firing`) when `for: 5m` is set.", ["inactive=false; pending=true < 5m (not paged yet); firing=true continuously >= 5m"]),
            sim("A service has a 99.9% 30-day SLO (`0.1%` budget = 43.2 minutes). If an outage causes 100% 5xx errors (`1000x` burn rate), how fast is the entire monthly error budget gone?", ["43.2 minutes! Explains why fast-burn detection in <5 minutes is essential"]),
            sim("Why should every paging alert include `runbook_url` and `dashboard_url` annotations?", ["Zero wasted time hunting docs at 3 AM — matches how A³P links every alert directly to its Runbook"]),
            sim("How does Grafana provisioning eliminate 'click-ops drift' across staging and prod?", ["Reads YAML datasources + dashboard JSON from Git at boot; prevents unversioned edits"]),
            sim("An engineer keeps receiving repeat pages for a known maintenance window. What Alertmanager mechanism handles planned maintenance cleanly?", ["Alertmanager Silences (time-bound label matchers) or Inhibition rules (suppress child pod alerts when whole node is Down)"]),
        ],
    ),
]

