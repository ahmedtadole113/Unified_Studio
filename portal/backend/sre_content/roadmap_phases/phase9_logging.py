"""Phase 9 (Days 40-41): Splunk Enterprise Architecture & SPL Search Mastery."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_40_TO_41: List[Dict] = [
    make_day(
        day=40,
        phase=9,
        title="Splunk Architecture: Forwarders, Indexers, Search Head & Indexes",
        subtitle="UF -> Heavy Forwarder -> Indexer (Hot/Warm/Cold/Frozen) -> Search Head & A³P Pipeline",
        goal="Map Splunk Enterprise components to real streaming log pipelines and organize indexes/sourcetypes",
        objective=(
            "Understand how Splunk scales log ingestion and search horizontally (`UF -> Indexer -> Search Head`), "
            "why `index` vs `sourcetype` matter, bucket lifecycle retention, and how A³P mirrors this live (`Fluentd -> Kafka -> Spark/SPL`)."
        ),
        concepts=[
            "**Universal Forwarder (UF)** runs lightweight on hosts shipping raw streams (`TCP 9997`); **Heavy Forwarder (HF)** can parse, filter, or mask PII before indexing; **Indexer** parses timestamps/fields into compressed time-series buckets (`rawdata` + `.tsidx`); **Search Head** dispatches SPL across Indexers and merges results.",
            "**Index** = storage boundary, RBAC access scope, and retention lifecycle (`Hot -> Warm -> Cold -> Frozen`). **Sourcetype** = data schema/format parser (e.g. `nginx:access`, `app:json`, `kube:container`).",
            "In **A³P**, `Fluentd` acts as Forwarder, `Kafka` buffers streams reliably, and our built-in Splunk SPL engine indexes `index=app_logs` and `index=anomalies` live!",
        ],
        deep_sections=[
            sec(
                "1. Splunk Bucket Lifecycle & A³P Equivalent Pipeline",
                "Knowing where logs age out prevents compliance retention violations and explains why searching 90-day Cold/Frozen buckets slows down.",
                table={
                    "headers": ["Tier / Role", "Splunk Enterprise", "A³P Live Stack Equivalent"],
                    "rows": [
                        ["Collection / Shipping", "Universal Forwarder (port 9997)", "Fluentd (`fluentd.conf`, port 24224)"],
                        ["Transport / Parsing", "Heavy Forwarder + Indexer Parsing", "Apache Kafka (`raw_app_logs`) + PySpark Streaming"],
                        ["Storage Boundary (`index`)", "Hot (active R/W) -> Warm (RO) -> Cold -> Frozen (archive/delete)", "`index=app_logs` & `index=anomalies`"],
                        ["Query & Alerts", "Search Head (`SPL` engine)", "A³P Observability -> Splunk SPL Lab (`/api/spl/search`)"],
                    ],
                },
            ),
        ],
        architecture="Host/App Logs -> Forwarder (UF/Fluentd) -> Queue (Kafka) -> Indexer (Buckets) -> Search Head (SPL Engine)",
        commands=[
            {"cmd": "curl -sG 'http://ai_agent:8000/api/spl/search' --data-urlencode 'q=index=app_logs | head 5' | jq '.rows[0:3]'", "explain": "Search live streaming events in index=app_logs using SPL", "cwd": "/lab"},
            {"cmd": "curl -sG 'http://ai_agent:8000/api/spl/search' --data-urlencode 'q=index=app_logs status=ERROR | stats count by scenario' | jq .", "explain": "Run live SPL `stats count by scenario` over failing log events", "cwd": "/lab"},
        ],
        production_use_case="Running real interactive SPL searches across live Kafka events inside A³P's **Observability -> Splunk SPL Lab** tab.",
        scenarios=[
            scenario(
                "Splunk License Violation / Search Slowdown After App Switched Debug Logging On in Prod!",
                "App deploy accidentally set `LOG_LEVEL=DEBUG`, quadrupling daily GB ingested (`500 GB/day` license cap breached) and delaying indexing.",
                "Query license/volume by sourcetype: `index=_internal source=*license_usage.log | stats sum(b) by st` (or in A³P `index=app_logs | stats count by status`)",
                "Unfiltered `DEBUG` logs or noisy healthcheck `/health` 200 OK lines flooded Universal Forwarders and Indexers.",
                "Fix app log level back to `INFO`, drop noisy `/health` events on Heavy Forwarder `transforms.conf` (`nullQueue`), and add per-sourcetype ingestion anomaly alerts.",
            ),
        ],
        troubleshooting=["Logs delayed by 10+ minutes (`_indextime - _time` large) -> UF queue blocked (`tcpout` backpressure) or Indexer disk I/O saturated."],
        interview_qa=[
            qa("Explain Splunk architecture and the difference between `index` and `sourcetype`.", "Universal Forwarders collect & ship logs -> Indexers parse events/timestamps into indexed buckets (`rawdata` + `tsidx`) -> Search Heads coordinate SPL queries across Indexers. An **Index** is the physical storage/retention/RBAC boundary; **Sourcetype** identifies the log format/field-extraction schema.", "basic"),
            qa("Explain Splunk bucket lifecycle (`Hot`, `Warm`, `Cold`, `Frozen`).", "Active incoming events write to **Hot** buckets (R/W). Once full/aged, they roll to **Warm** (read-only, fast disk), then **Cold** (cheaper storage tier), and finally **Frozen** (deleted by default or archived to S3 `coldToFrozenScript` before thawing if audited later).", "senior"),
        ],
        assignment_items=[
            "Query live index=app_logs and index=anomalies via SPL in /lab or Observability tab",
            "Explain Universal Forwarder vs Heavy Forwarder vs Indexer vs Search Head",
            "Explain Hot -> Warm -> Cold -> Frozen bucket lifecycle and nullQueue cost filtering",
        ],
        revision=["UF -> Indexer -> Search Head", "Index = storage/RBAC boundary; Sourcetype = format", "Hot -> Warm -> Cold -> Frozen"],
        interview_sim=[
            sim("A compliance officer requests logs from 14 months ago when your Splunk Cold retention is 90 days. How do you handle archival and recovery cleanly?", ["Configure frozenTimePeriodInSecs + coldToFrozenDir / S3 archive; restore (`splunk rebuild` / thaw) only the needed date bucket"]),
            sim("How can you mask credit cards / API tokens BEFORE logs ever hit Splunk Indexers?", ["Configure SEDCMD or transforms.conf regex masking at Heavy Forwarder parsing queue (or Fluentd record_transformer filter)"]),
            sim("Why is searching `_time` vs `_indextime` useful during an incident?", ["Large gap (`_indextime - _time`) proves logging pipeline/UF queuing delay rather than app clock skew"]),
            sim("Compare Universal Forwarder vs HTTP Event Collector (HEC).", ["UF tails host files / inputs.conf; HEC accepts stateless JSON events over HTTPS directly from Lambdas/apps/Fluentd"]),
            sim("What causes Splunk `Skipping` or `Blocked` queues on Forwarders?", ["Indexer disk full, network firewall on port 9997, or license/indexing pipeline bottleneck"]),
        ],
    ),

    make_day(
        day=41,
        phase=9,
        title="Splunk SPL Mastery: `where`, `stats`, `top`, `timechart` & Correlation",
        subtitle="Early Pipe Optimization, Aggregation (`stats` vs `transaction`), Latency Tables & Trace Joins",
        goal="Write fast, production-grade SPL queries to isolate outages and correlate `trace_id`s",
        objective=(
            "Write efficient SPL queries that scan minimal buckets by filtering BEFORE the first pipe `|`, "
            "then summarize with `where`, `stats`, `top`, `timechart`, and `table` — and correlate failing logs with distributed traces."
        ),
        concepts=[
            "**Rule #1 of Fast SPL**: Put `index=...`, `sourcetype=...`, time bounds, and exact keyword filters **BEFORE the first pipe `|`** so Indexers use `.tsidx` bloom filters instead of decompressing every raw event!",
            "`stats` streams/aggregates in map-reduce across Indexers (fast, low RAM); avoid `transaction` or subsearch `join` over millions of events when `stats values(...) by trace_id` does it 20x faster!",
            "`timechart` buckets metrics over time slots (`span=30s` / `1m`) for graphing error bursts cleanly.",
        ],
        deep_sections=[
            sec(
                "1. Slow SPL vs Fast Optimized SPL",
                "Notice how moving filters left of `|` and picking `stats` over `transaction` transforms a 4-minute query into a 0.5-second query.",
                example="# BAD (decompresses ALL logs across all indexes before filtering!):\nindex=* | where status=500 AND scenario=\"db_timeout\" | table timestamp trace_id\n\n# GOOD (bloom-filtered on index=app_logs BEFORE pipe):\nindex=app_logs status=ERROR scenario=db_timeout | where latency_ms > 200 | stats count avg(latency_ms) max(latency_ms) by service",
                sre_example="Every SPL query here runs live in A³P **Observability -> Splunk SPL Lab** over streaming Kafka events, and clicking any `trace_id` jumps straight to the trace waterfall!",
            ),
        ],
        architecture="index=app_logs <early keyword filters> | where <expr> | stats / top / timechart | sort / table / head",
        commands=[
            {"cmd": "curl -sG 'http://ai_agent:8000/api/spl/search' --data-urlencode 'q=index=app_logs | where latency_ms > 200 | table timestamp trace_id scenario status latency_ms message | head 8' | jq .", "explain": "Filter high-latency log events and project diagnostic table columns", "cwd": "/lab"},
            {"cmd": "curl -sG 'http://ai_agent:8000/api/spl/search' --data-urlencode 'q=index=app_logs | top 5 message' | jq .", "explain": "Rank top 5 recurring log messages by count and percentage", "cwd": "/lab"},
            {"cmd": "curl -sG 'http://ai_agent:8000/api/spl/search' --data-urlencode 'q=index=app_logs | timechart avg(cpu_usage)' | jq .", "explain": "Aggregate live CPU usage time buckets using SPL timechart", "cwd": "/lab"},
        ],
        production_use_case="Isolating noisy failing traces during `db_timeout` or `error_burst` drills and creating log-based SLO alerts.",
        scenarios=[
            scenario(
                "Search Head Memory Exceeded (`Search auto-canceled`) During SEV-1 Log Investigation",
                "While investigating a checkout outage, an engineer runs `index=prod | transaction trace_id` across 2 hours and crashes/slows the Search Head.",
                "Rewrite using index-time filter + streaming `stats`: `index=prod status>=500 | stats earliest(_time) as start values(service) as hops count by trace_id`",
                "`transaction` pulls every matching raw event into Search Head RAM to group sessions, hitting memory caps cleanly avoided by `stats`.",
                "Always filter before the first `|` and replace `transaction`/`join` with `stats ... by trace_id`.",
            ),
        ],
        troubleshooting=["`search * | where ...` or leading wildcards `*timeout` bypass `.tsidx` fast word index scans -> always filter exact tokens left of `|`."],
        interview_qa=[
            qa("How do you optimize a slow Splunk SPL query?", "1) Narrow time range (`earliest`/`latest`). 2) Specify exact `index`, `sourcetype`, and positive keyword filters **before the first pipe `|`**. 3) Avoid leading wildcards (`*error`). 4) Replace `transaction`/`join` with `stats ... by key`. 5) Use Summary Indexing / Data Model acceleration (`tstats`) for dashboards.", "senior"),
            qa("Difference between `search` filtering and `where` command in SPL?", "Initial search terms before `|` are case-insensitive keyword/field matches pushed down to Indexer bloom filters. `where` runs after `|` with case-sensitive expressions, math comparisons (`latency_ms > 200`), and function evaluation.", "basic"),
        ],
        assignment_items=[
            "Run where, top, stats, and timechart SPL queries via /api/spl/search or UI",
            "Trigger db_timeout in Chaos Lab and isolate failing trace_ids with SPL",
            "Explain why stats beats transaction and why early filtering left of pipe matters",
        ],
        revision=["Filter early BEFORE first |", "stats > transaction / join", "where = post-pipe math/case-sensitive", "tstats = fastest indexed fields"],
        interview_sim=[
            sim("Explain the difference between `stats count by status`, `chart count over host by status`, and `timechart span=5m count by status`.", ["stats = flat summary rows; chart = 2D pivot matrix; timechart = _time always on X-axis for time-series graphs"]),
            sim("An SPL query `index=web *timeout*` runs 15x slower than `index=web timeout`. Why?", ["Leading wildcard * breaks Splunk's tokenized word index (.tsidx), forcing raw decompression of every bucket"]),
            sim("How would you extract an unparsed numeric latency `lat=421ms` at search time in SPL and compute p95?", ["rex field=_raw \"lat=(?<lat_ms>\\d+)ms\" | stats perc95(lat_ms)"]),
            sim("Why should scheduled Splunk alerts avoid `earliest=-24h` on `*/1 * * * *` cron?", ["Scanning 24h every minute wastes massive Search Head concurrency; scan only slightly wider than schedule (`-5m` on 5m cron)"]),
            sim("How do you correlate an error logged in Fluentd/Splunk (`trace_id`) with Prometheus latency metrics?", ["Log structured trace_id in app JSON + emit Prometheus OpenTelemetry Exemplars pointing to Tempo/Jaeger trace_id"]),
        ],
    ),
]

