from __future__ import annotations

import json
import os
from functools import lru_cache

from pydantic import ValidationError

from app.models.partner import PartnerTarget


class Settings:
    def __init__(self) -> None:
        self.api_key = os.getenv("API_KEY", "dev_secret")
        self.redis_url = os.getenv("REDIS_URL", "")

        self.fanout_enabled = os.getenv("FANOUT_ENABLED", "false").lower() == "true"
        self.fanout_timeout_seconds = float(os.getenv("FANOUT_TIMEOUT_SECONDS", "2"))
        self.fanout_max_retries = int(os.getenv("FANOUT_MAX_RETRIES", "5"))
        self.fanout_retry_backoff_seconds = float(os.getenv("FANOUT_RETRY_BACKOFF_SECONDS", "2"))
        self.fanout_targets = self._load_targets(os.getenv("FANOUT_TARGETS_JSON", "[]"))

    @staticmethod
    def _load_targets(raw: str) -> list[PartnerTarget]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("FANOUT_TARGETS_JSON must be valid JSON") from exc

        if not isinstance(parsed, list):
            raise ValueError("FANOUT_TARGETS_JSON must be a JSON list")

        targets: list[PartnerTarget] = []
        for item in parsed:
            try:
                targets.append(PartnerTarget.model_validate(item))
            except ValidationError as exc:
                raise ValueError(f"Invalid fanout target config: {item}") from exc
        return targets


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
