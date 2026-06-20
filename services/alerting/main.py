"""
Alerting service.

Consumes `fire.predictions`, maps risk_score to a severity tier, and
publishes/exposes alerts via:
  - GET  /alerts        last-50 polling endpoint (backwards compat)
  - WS   /ws/alerts     WebSocket push — every new alert is broadcast to all
                        connected clients immediately, no polling needed

Persistence: if DATABASE_URL is set, alerts are also written to Postgres.
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from shared.config import settings
from shared import db
from shared.messaging import create_bus
from shared.models import AlertEvent, AlertSeverity, FirePredictionEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alerting")

bus = create_bus()
active_alerts: list[AlertEvent] = []
_ws_clients: set[WebSocket] = set()


def severity_for(risk_score: float) -> AlertSeverity:
    if risk_score >= 0.85:
        return AlertSeverity.EVACUATE
    if risk_score >= 0.65:
        return AlertSeverity.WARNING
    if risk_score >= 0.4:
        return AlertSeverity.WATCH
    return AlertSeverity.INFO


async def _broadcast(alert: AlertEvent) -> None:
    """Send alert JSON to all connected WebSocket clients."""
    if not _ws_clients:
        return
    payload = alert.model_dump_json()
    dead: set[WebSocket] = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


async def handle_prediction(raw: bytes) -> None:
    prediction = FirePredictionEvent.model_validate_json(raw)
    severity = severity_for(prediction.risk_score)

    alert = AlertEvent(
        alert_id=str(uuid.uuid4()),
        based_on_prediction_id=prediction.prediction_id,
        location=prediction.origin,
        severity=severity,
        message=(
            f"Fire risk {severity.value} (score={prediction.risk_score}) near "
            f"{prediction.origin.lat:.4f},{prediction.origin.lon:.4f} - "
            f"{prediction.horizon_minutes}min horizon"
        ),
    )
    active_alerts.append(alert)
    await bus.publish("fire.alerts", alert)
    await db.store_alert(alert)
    await _broadcast(alert)
    logger.info(alert.message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bus.connect()
    await bus.ensure_stream("PREDICTIONS", ["fire.predictions"])
    await bus.ensure_stream("ALERTS", ["fire.alerts"])
    await db.connect(settings.database_url)
    task = asyncio.create_task(
        bus.consume_loop("fire.predictions", "alerting-svc", handle_prediction)
    )
    yield
    task.cancel()
    await bus.close()
    await db.close()


app = FastAPI(title="Wildfire Alerting Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/alerts")
async def list_alerts():
    """Last 50 alerts (polling). Prefer the WebSocket endpoint for real-time push."""
    return active_alerts[-50:]


@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """
    WebSocket feed — connect once, receive every new alert as JSON the instant
    it is generated.  Replays the last 50 alerts on connect so the client
    starts with full context.
    """
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        # Replay history so client is immediately up to date
        for alert in active_alerts[-50:]:
            await websocket.send_text(alert.model_dump_json())
        # Keep alive — the server pushes; client just holds the connection
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)
