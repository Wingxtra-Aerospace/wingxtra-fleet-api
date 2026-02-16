from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse

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


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Wingxtra Fleet Dashboard</title>
  <link
    rel=\"stylesheet\"
    href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\"
    integrity=\"sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=\"
    crossorigin=\"\"
  />
  <style>
    body { font-family: Arial, sans-serif; margin: 0; color: #222; }
    h1 { font-size: 1.1rem; margin: 0; }
    .header { padding: 10px 12px; background: #0c3f7a; color: #fff; }
    .layout { display: grid; grid-template-columns: 2fr 1fr; min-height: calc(100vh - 48px); }
    #map { min-height: 420px; }
    .panel { padding: 10px; border-left: 1px solid #e5e7eb; overflow: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { border-bottom: 1px solid #e5e7eb; text-align: left; padding: 6px; }
    @media (max-width: 900px) {
      .layout { grid-template-columns: 1fr; }
      .panel { border-left: none; border-top: 1px solid #e5e7eb; }
    }
  </style>
</head>
<body>
  <div class=\"header\"><h1>Wingxtra Fleet Dashboard</h1></div>
  <div class=\"layout\">
    <div id=\"map\"></div>
    <div class=\"panel\">
      <table>
        <thead>
          <tr><th>Drone</th><th>Status</th><th>Mode</th><th>Battery</th><th>Last Seen</th></tr>
        </thead>
        <tbody id=\"rows\"></tbody>
      </table>
    </div>
  </div>

  <script
    src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"
    integrity=\"sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=\"
    crossorigin=\"\"
  ></script>
  <script>
    const map = L.map('map').setView([5.6037, -0.1870], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const markers = new Map();
    const rowsEl = document.getElementById('rows');

    function offline(lastSeenTs) {
      return (Date.now() - new Date(lastSeenTs).getTime()) > 30000;
    }

    async function refresh() {
      try {
        const res = await fetch('/api/v1/telemetry/latest', { cache: 'no-store' });
        const data = await res.json();

        rowsEl.innerHTML = '';
        for (const item of data.drones || []) {
          const t = item.telemetry || {};
          const p = t.position || {};
          if (typeof p.lat !== 'number' || typeof p.lon !== 'number') continue;

          let marker = markers.get(item.drone_id);
          if (!marker) {
            marker = L.marker([p.lat, p.lon]).addTo(map);
            markers.set(item.drone_id, marker);
          } else {
            marker.setLatLng([p.lat, p.lon]);
          }

          const state = t.state || {};
          const battery = t.battery || {};
          const isOffline = offline(item.last_seen_ts);
          const status = isOffline ? 'OFFLINE' : 'ONLINE';
          marker.bindPopup(`${item.drone_id}<br/>${status}<br/>Mode: ${state.mode || '-'}<br/>Battery: ${battery.remaining_pct ?? '-'}%`);

          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${item.drone_id}</td><td>${status}</td><td>${state.mode || '-'}</td><td>${battery.remaining_pct ?? '-'}%</td><td>${item.last_seen_ts}</td>`;
          rowsEl.appendChild(tr);
        }
      } catch (err) {
        console.error('Dashboard refresh failed', err);
      }
    }

    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
"""


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
