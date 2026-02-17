from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routes.fanout import router as fanout_router
from app.api.routes.telemetry import router as telemetry_router
from app.config import get_settings
from app.services.fanout import FanoutService
from app.store import InMemoryTelemetryStore, RedisTelemetryStore, TelemetryStore


app = FastAPI(title="Wingxtra Fleet API", version="0.1.0")
DASHBOARD_FILE = Path(__file__).parent / "static" / "index.html"


def _build_store() -> TelemetryStore:
    settings = get_settings()
    if settings.redis_url:
        try:
            import redis.asyncio as redis  # type: ignore

            return RedisTelemetryStore(redis.from_url(settings.redis_url, decode_responses=True))
        except Exception:
            return InMemoryTelemetryStore()
    return InMemoryTelemetryStore()


settings = get_settings()
app.state.store = _build_store()
app.state.api_key = settings.api_key
app.state.fanout_service = FanoutService(settings=settings)

app.include_router(telemetry_router)
app.include_router(fanout_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_FILE)
