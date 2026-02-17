from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/fanout")


@router.get("/targets")
async def get_targets(request: Request) -> dict:
    return {
        "fanout_enabled": request.app.state.fanout_service.settings.fanout_enabled,
        "targets": request.app.state.fanout_service.get_targets_redacted(),
    }


@router.get("/health")
async def get_fanout_health(request: Request) -> dict:
    return request.app.state.fanout_service.health()
