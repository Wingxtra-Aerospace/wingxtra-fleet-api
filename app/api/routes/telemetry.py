from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status

from app.schemas import LatestTelemetryResponse, TelemetryIn

router = APIRouter(prefix="/api/v1")


def require_api_key(request: Request, x_api_key: str = Header(default="")) -> None:
    if x_api_key != request.app.state.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.post("/telemetry", status_code=status.HTTP_200_OK, dependencies=[Depends(require_api_key)])
async def ingest_telemetry(payload: TelemetryIn, request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    received_at = datetime.now(timezone.utc)
    source_ip = request.client.host if request.client else "unknown"

    stored = {
        "drone_id": payload.drone_id,
        "last_seen_ts": received_at.isoformat(),
        "source_ip": source_ip,
        "telemetry": payload.model_dump(mode="json"),
    }

    await request.app.state.store.put_latest(payload.drone_id, stored)
    background_tasks.add_task(request.app.state.fanout_service.fanout, payload.model_dump(mode="json"))
    return {"status": "accepted"}


@router.get("/telemetry/latest", response_model=LatestTelemetryResponse)
async def get_latest(request: Request) -> LatestTelemetryResponse:
    latest = await request.app.state.store.get_all_latest()
    latest_sorted = sorted(latest, key=lambda d: d.get("drone_id", ""))
    return LatestTelemetryResponse(
        server_time=datetime.now(timezone.utc),
        count=len(latest_sorted),
        drones=latest_sorted,
    )
