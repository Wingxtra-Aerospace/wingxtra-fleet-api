from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

VALID_PAYLOAD = {
    "schema_version": 1,
    "drone_id": "WX-DRN-001",
    "ts": "2026-02-16T12:34:56.123Z",
    "position": {"lat": 5.6037, "lon": -0.1870, "alt_m": 120.3},
    "state": {"armed": True, "mode": "AUTO"},
    "battery": {"voltage_v": 22.1, "remaining_pct": 67},
}


def test_rejects_invalid_api_key() -> None:
    response = client.post("/api/v1/telemetry", json=VALID_PAYLOAD, headers={"X-API-Key": "bad"})
    assert response.status_code == 401


def test_accepts_and_returns_latest() -> None:
    ingest = client.post("/api/v1/telemetry", json=VALID_PAYLOAD, headers={"X-API-Key": "dev_secret"})
    assert ingest.status_code == 202

    latest = client.get("/api/v1/telemetry/latest")
    assert latest.status_code == 200
    body = latest.json()

    assert body["count"] >= 1
    drone = next(item for item in body["drones"] if item["drone_id"] == "WX-DRN-001")
    assert drone["telemetry"]["position"]["lat"] == VALID_PAYLOAD["position"]["lat"]


def test_validates_telemetry_payload() -> None:
    broken_payload = {
        **VALID_PAYLOAD,
        "drone_id": "bad name",
    }
    response = client.post(
        "/api/v1/telemetry",
        json=broken_payload,
        headers={"X-API-Key": "dev_secret"},
    )
    assert response.status_code == 422
