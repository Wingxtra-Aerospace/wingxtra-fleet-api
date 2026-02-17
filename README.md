# Wingxtra Fleet API
**Repository:** wingxtra-fleet-api  
**Owner:** Wingxtra Aerospace  
**Role:** Central cloud backend for real-time drone fleet tracking

---

## 1. What this system is (plain language)

This repository contains the **central fleet backend** for Wingxtra drones.

Each drone runs **DroneEngage** on a Raspberry Pi companion computer.
A separate DroneEngage **telemetry plugin** (see `wingxtra-de-telemetry-plugin`) sends telemetry directly to this API.

This backend:
- Receives telemetry from **many drones**
- Stores the **latest state per drone**
- Exposes endpoints for dashboards and future integrations
- Hosts a simple fleet dashboard (map + table)

**Important design rule:**  
➡️ Drones push telemetry directly to this backend.  
➡️ No laptop, Mission Planner, or bridge process is involved.

---

## 2. System architecture (authoritative)

[ Drone (PX4 / ArduPilot) ]
|
| MAVLink
v
[ DroneEngage Core ]
|
| DataBus (UDP 60000)
v
[ wingxtra-de-telemetry-plugin ]
|
| HTTPS POST (2–5 Hz)
v
[ wingxtra-fleet-api ]
|
+--> Redis (latest per drone)
+--> Optional DB (history)
+--> Dashboard (map)


This repo implements **only the backend + dashboard**.
It must never depend on DroneEngage internals.

---

## 3. Non-negotiable requirements

### 3.1 Telemetry ingestion
- Endpoint: `POST /api/v1/telemetry`
- Authentication: `X-API-Key` header
- Accepts telemetry from **multiple drones concurrently**
- Must be resilient to:
  - duplicate packets
  - dropped packets
  - partial payloads
- Must be fast (latest position is more important than history)

### 3.2 Telemetry retrieval
- Endpoint: `GET /api/v1/telemetry/latest`
- Returns **latest telemetry per drone_id**
- Must be fast enough for map refresh every 1–3 seconds

### 3.3 Health checks
- Endpoint: `GET /healthz`
- Returns `{"status":"ok"}` for uptime probes (Render/health monitors)

### 3.4 Dashboard

- Implemented at `GET /` (served from `app/static/index.html`)

### 3.5 Partner fan-out
- Telemetry ingestion fans out to configured partner endpoints after local storage.
- Fan-out is asynchronous and must not block ingestion responses.
- Admin endpoints:
  - `GET /api/v1/fanout/targets`
  - `GET /api/v1/fanout/health`

- Simple, reliable map UI
- Shows:
  - all drones
  - last known position
  - last_seen time
  - mode, battery, armed
- No authentication for MVP (API key only on ingest)

---

## 4. Canonical telemetry schema (v1 – DO NOT CHANGE)

This schema is the **contract** between:
- `wingxtra-de-telemetry-plugin`
- `wingxtra-fleet-api`

{
  "schema_version": 1,
  "drone_id": "WX-DRN-001",
  "ts": "2026-02-16T12:34:56.123Z",

  "position": {
    "lat": 5.6037,
    "lon": -0.1870,
    "alt_m": 120.3
  },

  "attitude": {
    "yaw_deg": 45.0
  },

  "velocity": {
    "groundspeed_mps": 12.4
  },

  "state": {
    "armed": true,
    "mode": "AUTO"
  },

  "battery": {
    "voltage_v": 22.1,
    "remaining_pct": 67
  },

  "link": {
    "rssi_dbm": -62
  }
}
Validation rules
drone_id: required, [A-Z0-9-_]{3,64}

lat: −90 to +90

lon: −180 to +180

alt_m: −500 to 20000

remaining_pct: 0–100

Missing optional sections are allowed

## 5. Storage model (MVP)
Redis (required)
Key: latest:{drone_id}

Value: full telemetry payload + metadata

Metadata added by server:

{
  "last_seen_ts": "2026-02-16T12:35:01.221Z",
  "source_ip": "41.x.x.x"
}
Optional DB (Phase 2)
Time-series telemetry history (downsampled)

Drone registry table (name, type, notes)

## 6. API specification
POST /api/v1/telemetry
Headers:

Content-Type: application/json
X-API-Key: <API_KEY>
Responses:

202 Accepted → success

400 Bad Request → invalid payload

401 Unauthorized → missing/invalid key

429 Too Many Requests → rate limited

GET /api/v1/telemetry/latest
Returns:

{
  "server_time": "2026-02-16T12:35:10Z",
  "count": 2,
  "drones": [
    {
      "drone_id": "WX-DRN-001",
      "last_seen_ts": "2026-02-16T12:35:09Z",
      "telemetry": { "...payload..." }
    }
  ]
}
## 7. Technology choices (recommended)
Preferred stack (do not improvise):

FastAPI (Python)

Redis (latest state)

Optional Postgres (history)

Docker for deployment

Codex should not switch stacks unless explicitly instructed.

## 8. Local development
Environment variables
Required:

API_KEY=dev_secret
REDIS_URL=redis://localhost:6379/0
Optional:

RATE_LIMIT_RPS=10
LOG_LEVEL=INFO
ALLOWED_ORIGINS=http://localhost:3000
FANOUT_ENABLED=false
FANOUT_TARGETS_JSON=[]
FANOUT_TIMEOUT_SECONDS=2
FANOUT_MAX_RETRIES=5
FANOUT_RETRY_BACKOFF_SECONDS=2
Run locally

With Docker Compose (api + redis):
```bash
docker compose up --build
```
- `docker-compose.yml` provides local `api` + `redis` services.


Without Docker:
```bash
uvicorn app.main:app --reload --port 8000
```
## 9. Dashboard requirements (explicit)
Uses Leaflet or Mapbox

Polls /api/v1/telemetry/latest every 1–3s

Marks drones as OFFLINE if last_seen > 30s

Clicking a drone shows detail panel

Mobile friendly

This is not a FleetShare clone.
Correctness > styling.

## 10. Acceptance tests (must pass)
Start backend

POST telemetry for:

WX-DRN-001

WX-DRN-002

Call GET /api/v1/telemetry/latest

Both drones appear

Map renders both markers

## 11. What NOT to do
❌ Do not require a laptop bridge

❌ Do not store only history without latest cache

❌ Do not hardcode secrets

❌ Do not depend on DroneEngage repos

## 12. Phase roadmap (locked)
Phase 1 (MVP)
Ingest + latest

Redis cache

Simple dashboard

Phase 2
History

WebSocket/SSE

Drone registry

Phase 3
Geofences

Alerts

Playback

Operator accounts


---

## 14. Real-world readiness notes

Yes—this architecture is suitable for real-world use when deployed with proper operations controls.

This repository now includes an MVP FastAPI receiver implementation with:
- `POST /api/v1/telemetry` (API-key protected)
- `GET /api/v1/telemetry/latest` (latest state per drone)
- Canonical payload validation for `drone_id`, coordinates, and battery constraints
- Redis-backed latest-state storage (with in-memory fallback for local dev/testing)

To run it in production safely, add:
- TLS termination (Nginx/Cloud load balancer)
- per-drone API keys or signed tokens
- ingress rate limiting + WAF
- Redis persistence/replication and monitoring
- structured logging/metrics/alerts


## 13. Implemented endpoints in this repo
- `GET /healthz` → `{"status":"ok"}`
- `GET /` → minimal Leaflet dashboard (map + table) polling `GET /api/v1/telemetry/latest` every 2 seconds
- `POST /api/v1/telemetry` → ingest with `X-API-Key`
- `GET /api/v1/telemetry/latest` → latest state per drone
