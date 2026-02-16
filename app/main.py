from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from app.schemas import LatestTelemetryResponse, TelemetryIn
from app.store import InMemoryTelemetryStore, RedisTelemetryStore, TelemetryStore


app = FastAPI(title="Wingxtra Fleet API", version="0.1.0")


def _build_store() -> TelemetryStore:
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            import redis.asyncio as redis  # type: ignore

            return RedisTelemetryStore(redis.from_url(redis_url, decode_responses=True))
        except Exception:
            return InMemoryTelemetryStore()
    return InMemoryTelemetryStore()


app.state.store = _build_store()
app.state.api_key = os.getenv("API_KEY", "dev_secret")


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != app.state.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.post("/api/v1/telemetry", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
async def ingest_telemetry(payload: TelemetryIn, request: Request) -> dict[str, str]:
    received_at = datetime.now(timezone.utc)
    source_ip = request.client.host if request.client else "unknown"

    stored = {
        "drone_id": payload.drone_id,
        "last_seen_ts": received_at.isoformat(),
        "source_ip": source_ip,
        "telemetry": payload.model_dump(mode="json"),
    }

    await app.state.store.put_latest(payload.drone_id, stored)
    return {"status": "accepted"}


@app.get("/api/v1/telemetry/latest", response_model=LatestTelemetryResponse)
async def get_latest() -> LatestTelemetryResponse:
    latest = await app.state.store.get_all_latest()
    latest_sorted = sorted(latest, key=lambda d: d.get("drone_id", ""))
    return LatestTelemetryResponse(
        server_time=datetime.now(timezone.utc),
        count=len(latest_sorted),
        drones=latest_sorted,
    )
