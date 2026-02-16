from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Position(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt_m: float | None = Field(default=None, ge=-500, le=20000)


class Attitude(BaseModel):
    yaw_deg: float | None = None


class Velocity(BaseModel):
    groundspeed_mps: float | None = None


class State(BaseModel):
    armed: bool | None = None
    mode: str | None = None


class Battery(BaseModel):
    voltage_v: float | None = None
    remaining_pct: int | None = Field(default=None, ge=0, le=100)


class Link(BaseModel):
    rssi_dbm: int | None = None


class TelemetryIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = Field(default=1)
    drone_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Z0-9-_]{3,64}$")
    ts: datetime
    position: Position
    attitude: Attitude | None = None
    velocity: Velocity | None = None
    state: State | None = None
    battery: Battery | None = None
    link: Link | None = None

    @field_validator("ts")
    @classmethod
    def enforce_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class StoredTelemetry(BaseModel):
    drone_id: str
    last_seen_ts: datetime
    source_ip: str
    telemetry: dict[str, Any]


class LatestTelemetryResponse(BaseModel):
    server_time: datetime
    count: int
    drones: list[StoredTelemetry]
