from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx

from app.config import Settings
from app.models.partner import PartnerTarget

logger = logging.getLogger(__name__)

SendCallable = Callable[[PartnerTarget, dict, float], Awaitable[None]]
SleepCallable = Callable[[float], Awaitable[None]]


class FanoutService:
    def __init__(
        self,
        settings: Settings,
        sender: SendCallable | None = None,
        sleeper: SleepCallable | None = None,
    ) -> None:
        self.settings = settings
        self._sender = sender or self._send_http
        self._sleeper = sleeper or asyncio.sleep
        self.last_errors: dict[str, str] = {}

    @property
    def targets(self) -> list[PartnerTarget]:
        return self.settings.fanout_targets

    async def fanout(self, payload: dict) -> None:
        if not self.settings.fanout_enabled or not self.targets:
            return
        await asyncio.gather(*(self._send_with_retries(target, payload) for target in self.targets))

    async def _send_with_retries(self, target: PartnerTarget, payload: dict) -> None:
        for attempt in range(self.settings.fanout_max_retries + 1):
            try:
                await self._sender(target, payload, self.settings.fanout_timeout_seconds)
                logger.info("fanout success target=%s attempt=%s", target.name, attempt + 1)
                self.last_errors.pop(target.name, None)
                return
            except Exception as exc:  # noqa: BLE001
                now = datetime.now(timezone.utc).isoformat()
                self.last_errors[target.name] = now
                logger.warning(
                    "fanout failed target=%s attempt=%s error=%s",
                    target.name,
                    attempt + 1,
                    exc,
                )
                if attempt >= self.settings.fanout_max_retries:
                    return
                delay = self.settings.fanout_retry_backoff_seconds * (2**attempt)
                await self._sleeper(delay)

    async def _send_http(self, target: PartnerTarget, payload: dict, timeout_s: float) -> None:
        headers = {"Content-Type": "application/json"}
        if target.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {target.api_key}"
        else:
            headers[target.header_name or "X-API-Key"] = target.api_key

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(str(target.url), json=payload, headers=headers)
            response.raise_for_status()

    def get_targets_redacted(self) -> list[dict[str, str | None]]:
        return [target.redacted() for target in self.targets]

    def health(self) -> dict:
        return {
            "status": "ok",
            "fanout_enabled": self.settings.fanout_enabled,
            "targets": [target.name for target in self.targets],
            "last_errors": self.last_errors,
        }
