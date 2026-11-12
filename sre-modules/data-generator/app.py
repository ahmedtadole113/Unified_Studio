import json
import logging
import random
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from fluent import sender
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Route logs to Fluentd which matches tag "app.logs"
fluent_sender = sender.FluentSender('app', host='fluentd', port=24224)

# Core infrastructure metrics (kept compatible with existing dashboards & alerts)
CPU_USAGE = Gauge('app_cpu_usage_percent', 'Simulated CPU Usage')
MEM_USAGE = Gauge('app_memory_usage_mb', 'Simulated Memory Usage')
REQUEST_COUNT = Counter('app_request_count', 'Simulated Request Count')
ERROR_COUNT = Counter('app_error_count', 'Simulated Error Count')

# SRE Golden Signals (Availability & Latency SLO metrics)
HTTP_REQUESTS = Counter(
    'app_http_requests_total',
    'Simulated HTTP requests by outcome class',
    ['status_class'],
)
REQUEST_LATENCY = Histogram(
    'app_request_latency_seconds',
    'Simulated request latency in seconds',
    buckets=[0.025, 0.05, 0.1, 0.2, 0.35, 0.5, 1.0, 2.5, 5.0],
)

# AI / Agentic Production Failure Mode metrics
AI_MODEL_DRIFT = Gauge('ai_model_drift_score', 'Simulated model/feature drift score (0-1)')
AI_TRAIN_SERVE_SKEW = Gauge('ai_train_serve_skew_score', 'Simulated train/serve feature skew score (0-1)')
AI_OUTPUT_VARIANCE = Gauge('ai_output_variance_score', 'Simulated LLM/agent output variance score (0-1)')
AI_INFERENCE_LATENCY_MS = Gauge('ai_inference_latency_ms', 'Simulated AI model inference latency (ms)')
AI_TOKEN_RATE = Gauge('ai_token_usage_rate', 'Simulated token throughput per minute')
AI_GPU_COST_HOURLY = Gauge('ai_gpu_cost_usd_hourly', 'Simulated hourly GPU/inference cost in USD')
CONFIG_DRIFT_DETECTED = Gauge('app_config_drift_detected', '1 if environment config drift is active else 0')

SCENARIOS = {
    "normal": {
        "label": "Steady State (Baseline)",
        "description": "Normal traffic within SLO budgets, low drift, and nominal cost.",
    },
    "cpu_spike": {
        "label": "CPU Saturation / Runaway Process",
        "description": "Simulates runaway worker threads saturating CPU above 90%.",
    },
    "memory_leak": {
        "label": "Memory Leak / OOM Ramp",
        "description": "Simulates progressive heap growth crossing 900+ MB threshold.",
    },
    "db_timeout": {
        "label": "Database Pool Exhaustion",
        "description": "Simulates DB connection timeouts causing 5xx errors and tail latency.",
    },
    "error_burst": {
        "label": "HTTP 500 Error Budget Burn",
        "description": "Simulates high error rate burning multi-window availability error budget.",
    },
    "latency_degradation": {
        "label": "Tail Latency (p99) Degradation",
        "description": "Simulates downstream dependency slowdown pushing p99 past 350ms SLO.",
    },
    "ambient_noise": {
        "label": "Ambient Noise / Noisy Neighbor",
        "description": "Simulates intermittent jitter and bursty resource contention.",
    },
    "ai_drift": {
        "label": "AI Model Drift & Train/Serve Skew",
        "description": "Simulates distribution drift, feature skew, and output variance spike.",
    },
    "token_gpu_cost_spike": {
        "label": "AI Token & GPU Cost Anomaly",
        "description": "Simulates agent retry loops spiking token burn and hourly GPU spend.",
    },
    "config_drift": {
        "label": "Environment Configuration Drift",
        "description": "Simulates unauthorized/out-of-band runtime configuration drift.",
    },
}

_state_lock = threading.Lock()
_chaos_state = {
    "scenario": "normal",
    "intensity": 1.0,
    "expires_at": 0.0,
    "started_at": 0.0,
    "tick_step": 0,
}


def get_chaos_snapshot() -> dict:
    """Return a thread-safe snapshot of the active chaos/experiment scenario."""
    now = time.time()
    with _state_lock:
        if _chaos_state["scenario"] != "normal" and _chaos_state["expires_at"] > 0 and now >= _chaos_state["expires_at"]:
            logger.info("Chaos scenario '%s' expired; reverting to normal.", _chaos_state["scenario"])
            _chaos_state["scenario"] = "normal"
            _chaos_state["intensity"] = 1.0
            _chaos_state["expires_at"] = 0.0
            _chaos_state["tick_step"] = 0

        remaining = max(0, int(_chaos_state["expires_at"] - now)) if _chaos_state["scenario"] != "normal" else 0
        return {
            "scenario": _chaos_state["scenario"],
            "label": SCENARIOS[_chaos_state["scenario"]]["label"],
            "intensity": _chaos_state["intensity"],
            "remaining_seconds": remaining,
            "started_at": _chaos_state["started_at"],
            "available_scenarios": SCENARIOS,
        }


def set_chaos_scenario(scenario: str, duration_seconds: int = 90, intensity: float = 1.0) -> dict:
    """Activate or reset a chaos/research scenario."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'")
    now = time.time()
    clamped_duration = max(10, min(int(duration_seconds), 900))
    clamped_intensity = max(0.3, min(float(intensity), 2.0))
    with _state_lock:
        _chaos_state["scenario"] = scenario
        _chaos_state["intensity"] = clamped_intensity
        _chaos_state["started_at"] = now
        _chaos_state["expires_at"] = 0.0 if scenario == "normal" else now + clamped_duration
        _chaos_state["tick_step"] = 0
    logger.warning("Scenario switched to '%s' (duration=%ss, intensity=%.2f)", scenario, clamped_duration, clamped_intensity)
    return get_chaos_snapshot()


def _sample_tick(scenario: str, intensity: float, step: int) -> dict:
    """Generate realistic infrastructure, latency, and AI telemetry for one 2-second interval."""
    cpu = random.uniform(14.0, 38.0)
    mem = random.uniform(210.0, 390.0)
    req_batch = random.randint(35, 65)
    errors = 0
    latency_s = random.uniform(0.035, 0.14)
    drift = random.uniform(0.08, 0.24)
    skew = random.uniform(0.05, 0.18)
    variance = random.uniform(0.06, 0.22)
    inf_ms = random.uniform(45.0, 120.0)
    token_rate = random.uniform(1800.0, 4200.0)
    gpu_cost = random.uniform(2.8, 4.4)
    config_drift = 0
    status = "OK"
    is_anomaly = False
    msg = ""

    # Occasional organic micro-burst in steady state (~1.5%) while staying within 99.9% SLO baseline
    if scenario == "normal" and random.random() < 0.015:
        cpu = random.uniform(86.0, 96.0)
        mem = random.uniform(815.0, 920.0)
        errors = random.choice([0, 1])
        latency_s = random.uniform(0.28, 0.45)
        status = "ERROR" if errors > 0 else "WARN"
        is_anomaly = True
        msg = f"High resource usage detected: CPU={cpu:.2f}% MEM={mem:.2f}MB"
    elif scenario == "cpu_spike":
        cpu = min(99.8, random.uniform(86.0, 98.5) * min(1.15, 0.9 + 0.15 * intensity))
        latency_s = random.uniform(0.28, 0.75) * intensity
        errors = random.randint(1, 4)
        status = "ERROR"
        is_anomaly = True
        msg = f"High CPU usage detected on server: CPU={cpu:.2f}% runaway worker thread"
    elif scenario == "memory_leak":
        ramp = min(450.0, step * 18.0 * intensity)
        mem = min(1020.0, 620.0 + ramp + random.uniform(-10.0, 25.0))
        cpu = random.uniform(42.0, 72.0)
        latency_s = random.uniform(0.22, 0.55)
        is_anomaly = mem > 800.0
        if is_anomaly:
            status = "ERROR"
            errors = random.randint(1, 5)
            msg = f"High Memory usage detected: MEM={mem:.2f}MB approaching OOM limit"
        else:
            msg = f"Memory pressure rising: MEM={mem:.2f}MB CPU={cpu:.2f}%"
    elif scenario == "db_timeout":
        cpu = random.uniform(40.0, 68.0)
        mem = random.uniform(420.0, 620.0)
        errors = random.randint(6, 15)
        latency_s = random.uniform(1.1, 3.8) * min(1.5, intensity)
        status = "ERROR"
        is_anomaly = True
        msg = f"Database connection timeout ERROR: pool exhausted latency={latency_s*1000:.0f}ms"
    elif scenario == "error_burst":
        errors = random.randint(8, 22)
        cpu = random.uniform(55.0, 82.0)
        latency_s = random.uniform(0.35, 1.4)
        status = "ERROR"
        is_anomaly = True
        msg = f"Application throwing 500 ERROR codes: {errors}/{req_batch} failed requests"
    elif scenario == "latency_degradation":
        latency_s = random.uniform(0.65, 2.4) * min(1.6, intensity)
        inf_ms = random.uniform(280.0, 650.0)
        errors = random.choices([0, 2], weights=[0.7, 0.3], k=1)[0]
        status = "ERROR" if errors > 0 else "WARN"
        is_anomaly = True
        msg = f"Tail latency SLO degradation detected: p99={latency_s*1000:.0f}ms"
    elif scenario == "ambient_noise":
        burst = random.random() < 0.45
        cpu = random.uniform(72.0, 91.0) if burst else random.uniform(35.0, 58.0)
        mem = random.uniform(620.0, 840.0) if burst else random.uniform(380.0, 520.0)
        latency_s = random.uniform(0.28, 0.85) if burst else random.uniform(0.08, 0.22)
        errors = random.randint(1, 3) if burst else 0
        is_anomaly = burst
        status = "ERROR" if burst else "OK"
        msg = (
            f"Ambient noise contention burst: CPU={cpu:.2f}% MEM={mem:.2f}MB"
            if burst
            else f"Ambient noise baseline jitter: CPU={cpu:.2f}%"
        )
    elif scenario == "ai_drift":
        drift = min(0.98, random.uniform(0.68, 0.92) * min(1.2, 0.85 + 0.2 * intensity))
        skew = min(0.95, random.uniform(0.55, 0.84) * min(1.2, 0.85 + 0.2 * intensity))
        variance = min(0.95, random.uniform(0.52, 0.85))
        inf_ms = random.uniform(190.0, 420.0)
        latency_s = inf_ms / 1000.0
        status = "ERROR"
        is_anomaly = True
        msg = f"AI model drift and train/serve skew detected: drift={drift:.2f} skew={skew:.2f} variance={variance:.2f}"
    elif scenario == "token_gpu_cost_spike":
        token_rate = random.uniform(22000.0, 48000.0) * min(1.5, intensity)
        gpu_cost = random.uniform(14.5, 29.0) * min(1.5, intensity)
        inf_ms = random.uniform(240.0, 520.0)
        cpu = random.uniform(62.0, 84.0)
        status = "ERROR"
        is_anomaly = True
        msg = f"Token and GPU cost anomaly detected: tokens/min={token_rate:.0f} cost=${gpu_cost:.2f}/hr"
    elif scenario == "config_drift":
        config_drift = 1
        errors = random.randint(1, 4)
        status = "ERROR"
        is_anomaly = True
        msg = "Environment configuration drift detected: runtime parameters diverged from Git baseline"

    if not msg:
        msg = f"Normal operation: CPU={cpu:.2f}% latency={latency_s*1000:.0f}ms"

    return {
        "cpu": cpu,
        "mem": mem,
        "req_batch": req_batch,
        "errors": min(errors, req_batch),
        "latency_s": latency_s,
        "drift": drift,
        "skew": skew,
        "variance": variance,
        "inf_ms": inf_ms,
        "token_rate": token_rate,
        "gpu_cost": gpu_cost,
        "config_drift": config_drift,
        "status": status,
        "is_anomaly": is_anomaly,
        "msg": msg,
    }


def generate_logs_and_metrics():
    """Continuously generate Prometheus metrics and Fluentd structured logs."""
    logger.info("Starting SRE/AIOps Data Generator...")
    while True:
        try:
            snapshot = get_chaos_snapshot()
            scenario = snapshot["scenario"]
            intensity = snapshot["intensity"]
            with _state_lock:
                _chaos_state["tick_step"] += 1
                step = _chaos_state["tick_step"]

            sample = _sample_tick(scenario, intensity, step)

            # Update Prometheus gauges & counters
            CPU_USAGE.set(sample["cpu"])
            MEM_USAGE.set(sample["mem"])
            REQUEST_COUNT.inc(sample["req_batch"])
            if sample["errors"] > 0:
                ERROR_COUNT.inc(sample["errors"])

            good_reqs = max(0, sample["req_batch"] - sample["errors"])
            if good_reqs:
                HTTP_REQUESTS.labels(status_class="2xx").inc(good_reqs)
            if sample["errors"]:
                HTTP_REQUESTS.labels(status_class="5xx").inc(sample["errors"])

            # Observe latency samples into histogram for realistic quantile estimation
            for _ in range(5):
                jittered = max(0.01, sample["latency_s"] * random.uniform(0.75, 1.25))
                REQUEST_LATENCY.observe(jittered)

            AI_MODEL_DRIFT.set(sample["drift"])
            AI_TRAIN_SERVE_SKEW.set(sample["skew"])
            AI_OUTPUT_VARIANCE.set(sample["variance"])
            AI_INFERENCE_LATENCY_MS.set(sample["inf_ms"])
            AI_TOKEN_RATE.set(sample["token_rate"])
            AI_GPU_COST_HOURLY.set(sample["gpu_cost"])
            CONFIG_DRIFT_DETECTED.set(sample["config_drift"])

            if sample["is_anomaly"]:
                logger.warning("Simulating Anomaly [%s]: %s", scenario, sample["msg"])

            log_data = {
                "service": "simulated_app",
                "trace_id": uuid.uuid4().hex[:16],
                "scenario": scenario,
                "cpu_usage": round(sample["cpu"], 2),
                "mem_usage": round(sample["mem"], 2),
                "latency_ms": round(sample["latency_s"] * 1000.0, 2),
                "drift_score": round(sample["drift"], 3),
                "skew_score": round(sample["skew"], 3),
                "gpu_cost_usd": round(sample["gpu_cost"], 2),
                "status": sample["status"],
                "message": sample["msg"],
                "timestamp": int(time.time()),
                "is_anomaly": sample["is_anomaly"],
            }
            fluent_sender.emit('logs', log_data)
            time.sleep(2)
        except Exception as e:
            logger.error("Error generating data: %s", e)
            time.sleep(5)


class GeneratorHandler(BaseHTTPRequestHandler):
    """HTTP server exposing Prometheus /metrics and chaos experiment control API."""

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/metrics":
            payload = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif path == "/health":
            self._send_json(200, {"status": "ok", **get_chaos_snapshot()})
        elif path == "/api/chaos":
            self._send_json(200, get_chaos_snapshot())
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/chaos/reset":
            self._send_json(200, set_chaos_scenario("normal"))
            return
        if path == "/api/chaos":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
                snapshot = set_chaos_scenario(
                    scenario=body.get("scenario", "normal"),
                    duration_seconds=body.get("duration_seconds", 90),
                    intensity=body.get("intensity", 1.0),
                )
                self._send_json(200, snapshot)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_json(400, {"error": str(exc)})
        else:
            self._send_json(404, {"error": "Not found"})

    def log_message(self, format, *args):
        # Suppress noisy per-scrape access logs
        return


if __name__ == '__main__':
    server = ThreadingHTTPServer(("0.0.0.0", 8000), GeneratorHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Metrics & Chaos Control server started on port 8000")
    generate_logs_and_metrics()
