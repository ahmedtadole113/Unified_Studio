"""Unified Engineering Studio — FastAPI Control Plane Entrypoint."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from core import database, security
from core.config import settings
from core.telemetry_otel import init_otel
from routers import (
    aiops,
    auth,
    data_engineering,
    finops,
    infrastructure,
    observability,
    platform,
    services_router,
    sre,
    streaming,
)
from services import aiops_engine, chaos_engine, correlation_engine, registry, slo_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ues.control_plane")

UES_HTTP_REQUESTS = Counter(
    "ues_http_requests_total",
    "Unified Control Plane HTTP requests",
    ["method", "path", "status_class"],
)
UES_HTTP_DURATION = Histogram(
    "ues_http_request_duration_seconds",
    "Unified Control Plane HTTP latency",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

_BG_TASK = None


async def _background_control_loop() -> None:
    """Periodic discovery, SLO sampling, and DE<->SRE correlation loop."""
    while True:
        try:
            registry.refresh_registry(include_stats=True)
            await slo_engine.evaluate_all_slos()
            await correlation_engine.run_correlation_pass()
        except Exception as exc:
            logger.debug("Background telemetry loop note: %s", exc)
        await asyncio.sleep(20)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _BG_TASK
    logger.info("Initializing Unified Engineering Studio v%s...", settings.APP_VERSION)
    database.init_db()
    security.load_users()
    init_otel()
    aiops_engine.start_kafka_consumers()
    registry.refresh_registry(include_stats=False)
    _BG_TASK = asyncio.create_task(_background_control_loop())
    try:
        yield
    finally:
        if _BG_TASK:
            _BG_TASK.cancel()


app = FastAPI(
    title=f"{settings.APP_NAME} Control Plane",
    description="Unified Data Engineering + SRE + Kubernetes + FinOps + AIOps Control Plane",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_and_chaos_middleware(request: Request, call_next):
    t0 = time.time()
    # Apply controlled chaos network latency when activated explicitly by user
    lat_ms = chaos_engine.get_artificial_latency_ms()
    if lat_ms > 0 and not request.url.path.startswith("/api/v1/incidents/chaos"):
        await asyncio.sleep(lat_ms / 1000.0)

    response = await call_next(request)
    dur = time.time() - t0
    status_cls = f"{response.status_code // 100}xx"
    UES_HTTP_REQUESTS.labels(method=request.method, path=request.url.path, status_class=status_cls).inc()
    UES_HTTP_DURATION.observe(dur)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled control-plane exception on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal control plane error", "error": str(exc)})


@app.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Register all modular routers
app.include_router(auth.router)
app.include_router(platform.router)
app.include_router(services_router.router)
app.include_router(infrastructure.router)
app.include_router(data_engineering.router)
app.include_router(streaming.router)
app.include_router(observability.router)
app.include_router(sre.router)
app.include_router(finops.router)
app.include_router(aiops.router)

FastAPIInstrumentor.instrument_app(app)
