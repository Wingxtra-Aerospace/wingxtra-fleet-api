import asyncio

import pytest

from app.main import app
from app.models.partner import PartnerTarget
from app.services.fanout import FanoutService


class DummySettings:
    def __init__(self, enabled: bool, targets: list[PartnerTarget], timeout: float = 2, retries: int = 2, backoff: float = 0):
        self.fanout_enabled = enabled
        self.fanout_targets = targets
        self.fanout_timeout_seconds = timeout
        self.fanout_max_retries = retries
        self.fanout_retry_backoff_seconds = backoff


def test_fanout_disabled_no_requests() -> None:
    calls = 0

    async def sender(target: PartnerTarget, payload: dict, timeout_s: float) -> None:
        nonlocal calls
        calls += 1

    svc = FanoutService(DummySettings(enabled=False, targets=[]), sender=sender)
    asyncio.run(svc.fanout({"drone_id": "WX-DRN-001"}))
    assert calls == 0


def test_fanout_enabled_sends_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict, headers: dict):
            captured.append({"url": url, "json": json, "headers": headers})
            return DummyResponse()

    monkeypatch.setattr("httpx.AsyncClient", DummyClient)

    targets = [
        PartnerTarget(name="A", url="https://a.example.com/ingest", auth_type="bearer", api_key="tokA"),
        PartnerTarget(
            name="B",
            url="https://b.example.com/ingest",
            auth_type="header",
            api_key="tokB",
            header_name="X-API-Key",
        ),
    ]
    svc = FanoutService(DummySettings(enabled=True, targets=targets))
    asyncio.run(svc.fanout({"drone_id": "WX-DRN-002"}))

    assert len(captured) == 2
    auth_headers = [item["headers"] for item in captured]
    assert any(h.get("Authorization") == "Bearer tokA" for h in auth_headers)
    assert any(h.get("X-API-Key") == "tokB" for h in auth_headers)


def test_ingestion_returns_200_when_fanout_fails() -> None:
    from fastapi.testclient import TestClient

    attempts = 0

    async def fail_sender(target: PartnerTarget, payload: dict, timeout_s: float) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("partner down")

    async def no_sleep(seconds: float) -> None:
        await asyncio.sleep(0)

    target = PartnerTarget(name="FailPartner", url="https://down.example.com", auth_type="bearer", api_key="x")
    app.state.fanout_service = FanoutService(
        DummySettings(enabled=True, targets=[target], retries=2, backoff=0),
        sender=fail_sender,
        sleeper=no_sleep,
    )

    client = TestClient(app)
    payload = {
        "schema_version": 1,
        "drone_id": "WX-DRN-010",
        "ts": "2026-02-16T12:34:56.123Z",
        "position": {"lat": 5.6037, "lon": -0.1870, "alt_m": 120.3},
    }

    response = client.post("/api/v1/telemetry", json=payload, headers={"X-API-Key": "dev_secret"})
    assert response.status_code == 200

    latest = client.get("/api/v1/telemetry/latest")
    assert latest.status_code == 200
    assert any(d["drone_id"] == "WX-DRN-010" for d in latest.json()["drones"])
    assert attempts == 3
