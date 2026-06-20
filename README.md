<div align="center">

# 🔥 Wildfire Detection Pipeline

**Event-driven wildfire detection, prediction, and alerting — from drone to dashboard in real time.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![NATS](https://img.shields.io/badge/NATS-JetStream-27AAE1?style=flat-square&logo=natsdotio&logoColor=white)](https://nats.io)
[![Postgres](https://img.shields.io/badge/Postgres-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

![Dashboard](docs/screenshot.png)

</div>

---

## Overview

Four FastAPI microservices form an end-to-end pipeline — drones POST telemetry and frame metadata to **ingestion**, a vision model classifies frames in **detection**, a Rothermel-inspired spread model projects fire perimeters in **prediction**, and **alerting** maps risk scores to severity tiers and broadcasts via WebSocket.

A React + Leaflet dashboard receives alerts in real time and polls detections / predictions every 5 seconds. Everything is persisted to Postgres. NATS JetStream is the default message bus; Kafka is a one-env-var swap.

```
                 HTTP                      NATS / Kafka subjects
  drones/sensors ──► [ingestion] ──► drones.telemetry ──┐
                                  └─► drones.frames    ──┼──► [detection] ──► fire.detections
                                                          │                          │
                                                          │                          ▼
                                                          └──────────────────► [prediction] ──► fire.predictions ──► [alerting] ──► fire.alerts
                                                             (telemetry as                                                │
                                                              wind proxy)                                                │
                                                                                                                         ▼
                                                                                                                    [dashboard]
                                                                                                               WebSocket + HTTP/nginx
```

---

## Services

| Service | Port | Consumes | Publishes | Implementation |
|---|---|---|---|---|
| `ingestion` | 8001 | HTTP `POST /telemetry`, `/frames` | `drones.telemetry`, `drones.frames` | Pure ingress |
| `detection` | 8002 | `drones.frames` | `fire.detections` | `ModelBackend` — ONNX or deterministic stub |
| `prediction` | 8003 | `fire.detections`, `drones.telemetry` | `fire.predictions` | Rothermel wind-driven ellipse |
| `alerting` | 8004 | `fire.predictions` | `fire.alerts` | Severity mapping + WebSocket broadcast |
| `dashboard` | 3000 | `/api/*` + `ws://.../ws/alerts` | — | React + Leaflet, nginx-proxied |

### Infrastructure

| Container | Purpose | Ports |
|---|---|---|
| `nats` | Message bus with JetStream persistence | 4222 · 8222 (monitor) |
| `postgres` | Event store — telemetry, detections, predictions, alerts | 5432 |
| `kafka` | Alternative transport (`--profile kafka`) | 9092 |

---

## Quick Start

```bash
make up
```

> Builds and starts 7 containers: NATS · Postgres · ingestion · detection · prediction · alerting · dashboard.

Open **http://localhost:3000** — the dashboard loads immediately.

**Simulate a drone fleet** (separate terminal):

```bash
pip install httpx
make simulate          # 3 drones · telemetry + frames every 3 s · Ctrl-C to stop
```

**Inspect raw data:**

```bash
curl localhost:8002/detections | jq
curl localhost:8003/predictions | jq
curl localhost:8004/alerts | jq
make logs              # tail all service logs
```

---

## Dashboard

| Panel | What it shows |
|---|---|
| **Health bar** | Per-service status pills + `ws` WebSocket indicator + last-updated time |
| **Stats row** | Live counts — detections, flame, smoke, predictions, alerts, emergency, warning |
| **Map** | Dark Leaflet map — orange/red dots per detection, coloured perimeter polygons per prediction; hover for details |
| **Alerts panel** | Real-time WebSocket push, colour-coded by severity (watch / warning / emergency / evacuate) |
| **Detections list** | Newest-first feed with fire class badge and confidence score |

Alerts arrive via WebSocket the instant they are generated — no polling lag. Detections and predictions refresh every 5 seconds.

---

## Architecture Highlights

### 🔌 Swappable Transport

`shared/messaging.py` defines a `MessageBus` ABC. `JetStreamBus` (NATS) and `KafkaBus` (aiokafka) both implement it. Switch with one env var:

```bash
TRANSPORT=kafka docker compose --profile kafka up
```

Service code never imports NATS or Kafka directly — it calls `create_bus()`.

### 🧠 Detection Model Abstraction

`ModelBackend` ABC in `services/detection/model_stub.py`:

- **`StubBackend`** — deterministic hash-seeded results, no GPU needed
- **`ONNXBackend`** — loads a real ONNX checkpoint (e.g. YOLOv8-fire) when `DETECTION_MODEL_PATH` is set

```bash
docker compose run \
  -e DETECTION_MODEL_PATH=/models/yolov8-fire.onnx \
  -v /path/to/models:/models \
  detection
```

Expected contract: `float32 NCHW [1, 3, 640, 640]` in → `[N, 6]` (x1 y1 x2 y2 confidence class\_id) out.

### 🔥 Rothermel Spread Model

`services/prediction/spread_model_stub.py` implements a simplified [Rothermel (1972)](https://research.fs.usda.gov/treesearch/32533) wind-driven ellipse:

- Wind factor `φ_w = 0.42 × speed^0.84` (capped at 3×)
- Spread rate by fire class (flame: 8 m/min, smoke: 3 m/min), boosted 20% when smoke density > 20 ppm
- Length-to-breadth ratio from wind speed (capped at 4:1)
- Nearest-source telemetry join for wind data — geodesically closest sensor per detection

### 💾 Postgres Persistence

`shared/db.py` — async `asyncpg` pool, schema auto-created on first connect. Every event is written after NATS publish. Silence no-op when `DATABASE_URL` is unset.

Tables: `telemetry` · `detections` · `predictions` · `alerts`

### ⚡ WebSocket Push

`GET /ws/alerts` on the alerting service replays the last 50 alerts on connect, then pushes every new alert the instant it is generated. The dashboard auto-reconnects with 3 s backoff.

---

## Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `NATS_URL` | `nats://localhost:4222` | NATS connection string |
| `TRANSPORT` | `nats` | `nats` or `kafka` |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Used when `TRANSPORT=kafka` |
| `DATABASE_URL` | *(set in docker-compose)* | Postgres DSN; empty = in-memory only |
| `DETECTION_MODEL_PATH` | *(unset)* | ONNX checkpoint path; unset = `StubBackend` |

---

## NATS Monitoring

**http://localhost:8222** — JetStream monitoring UI.

| Endpoint | Shows |
|---|---|
| `/varz` | Server stats, uptime, message counts |
| `/connz` | Active client connections |
| `/subsz` | Active subscriptions |
| `/jsz` | JetStream streams and consumer state |

---

## Testing

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. make test
```

Unit tests cover `StubBackend` (determinism, valid output) and the Rothermel spread model (perimeter shape, risk bounds, wind=None fallback). No NATS or Postgres required.

---

## What's Production-Ready vs. Still Stubbed

### ✅ Production-shaped

- Event schemas and service boundaries (`shared/models.py`)
- `MessageBus` abstraction — NATS and Kafka implementations, swappable via env var
- `ModelBackend` abstraction — plug in any ONNX model with zero service changes
- Rothermel spread model with nearest-source telemetry join
- Postgres persistence via asyncpg — schema auto-migrated, silent no-op when disabled
- WebSocket push with history replay and auto-reconnect
- Full Docker Compose topology with health checks and service dependencies

### 🚧 Replace before production

- `ONNXBackend.detect()` uses a zero tensor — wire in real image fetch from `frame.frame_url`
- Spread model uses a single 60-minute horizon — add multiple horizons and fuel-load rasters
- HTTP poll endpoints (`/detections`, `/predictions`) read in-memory lists — swap for `await db.get_recent_*()`
- No auth on ingestion endpoints

---

## Project Layout

```
wildfire-pipeline/
├── services/
│   ├── ingestion/           Pure HTTP ingress → NATS publish
│   ├── detection/           ModelBackend ABC → StubBackend / ONNXBackend
│   ├── prediction/          Rothermel spread model + nearest telemetry join
│   └── alerting/            Severity mapping + WebSocket broadcast
├── shared/
│   ├── models.py            Pydantic event schemas (shared contract)
│   ├── messaging.py         MessageBus ABC → JetStreamBus / KafkaBus
│   ├── db.py                asyncpg pool · schema init · store/query helpers
│   └── config.py            Settings (env vars / .env)
├── dashboard/
│   ├── src/
│   │   ├── hooks/usePipeline.ts     WebSocket alerts + 5s poll
│   │   └── components/
│   │       ├── FireMap.tsx          Leaflet map
│   │       ├── AlertPanel.tsx       Real-time alert feed
│   │       ├── DetectionList.tsx    Detection feed
│   │       ├── StatsBar.tsx         Live counts
│   │       └── HealthBar.tsx        Service + WS health
│   ├── nginx.conf           HTTP proxy + WebSocket upgrade
│   └── Dockerfile           node:20 build → nginx:alpine serve
├── scripts/
│   └── simulate_drone.py    3-drone fleet simulator (httpx)
├── tests/                   Unit tests — no infra required
├── docs/
│   └── screenshot.png       Dashboard screenshot
├── docker-compose.yml       Full stack; Kafka via --profile kafka
├── requirements.txt         fastapi · nats-py · asyncpg · aiokafka · …
└── Makefile                 up / down / logs / simulate / test
```

---

<div align="center">

Built with FastAPI · NATS JetStream · React · Leaflet · Postgres · Docker

</div>
