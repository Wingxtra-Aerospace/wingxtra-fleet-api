from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class TelemetryStore(ABC):
    @abstractmethod
    async def put_latest(self, drone_id: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_all_latest(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class InMemoryTelemetryStore(TelemetryStore):
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    async def put_latest(self, drone_id: str, payload: dict[str, Any]) -> None:
        self._items[drone_id] = payload

    async def get_all_latest(self) -> list[dict[str, Any]]:
        return list(self._items.values())


class RedisTelemetryStore(TelemetryStore):
    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    async def put_latest(self, drone_id: str, payload: dict[str, Any]) -> None:
        key = f"latest:{drone_id}"
        await self.redis.set(key, json.dumps(payload, default=str))

    async def get_all_latest(self) -> list[dict[str, Any]]:
        keys = await self.redis.keys("latest:*")
        if not keys:
            return []
        values = await self.redis.mget(keys)
        output: list[dict[str, Any]] = []
        for value in values:
            if value is None:
                continue
            output.append(json.loads(value))
        return output
