"""
Prediction service.

Keeps the latest telemetry reading per source in memory as a crude wind
proxy, and on every fire detection runs the (stubbed) spread model to
project a perimeter and risk score onto `fire.predictions`.

The in-memory `latest_telemetry` dict is fine for a single-instance
skeleton; a real deployment would back this with Redis or a proper
windowed stream join (e.g. keyed by geo-cell) so it scales horizontally.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.prediction.spread_model_stub import project_spread
from shared.config import settings
from shared import db
from shared.messaging import create_bus
from shared.models import FireDetectionEvent, FirePredictionEvent, TelemetryEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prediction")

bus = create_bus()
latest_telemetry: dict[str, TelemetryEvent] = {}
recent_predictions: list[FirePredictionEvent] = []


async def handle_telemetry(raw: bytes) -> None:
    event = TelemetryEvent.model_validate_json(raw)
    latest_telemetry[event.source_id] = event


async def handle_detection(raw: bytes) -> None:
    detection = FireDetectionEvent.model_validate_json(raw)

    # Nearest-source telemetry join — find the reading geographically closest
    # to the detection. Falls back to any available reading, then to None.
    wind = _nearest_telemetry(detection.location.lat, detection.location.lon)

    perimeter, risk = project_spread(detection, wind)
    prediction = FirePredictionEvent(
        prediction_id=str(uuid.uuid4()),
        based_on_detection_id=detection.detection_id,
        origin=detection.location,
        projected_perimeter=perimeter,
        horizon_minutes=60,
        risk_score=risk,
    )
    recent_predictions.append(prediction)
    await bus.publish("fire.predictions", prediction)
    await db.store_prediction(prediction)


def _nearest_telemetry(lat: float, lon: float) -> TelemetryEvent | None:
    """Return the telemetry reading whose source is geographically closest."""
    if not latest_telemetry:
        return None
    return min(
        latest_telemetry.values(),
        key=lambda t: (t.location.lat - lat) ** 2 + (t.location.lon - lon) ** 2,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bus.connect()
    await bus.ensure_stream("TELEMETRY", ["drones.telemetry"])
    await bus.ensure_stream("DETECTIONS", ["fire.detections"])
    await bus.ensure_stream("PREDICTIONS", ["fire.predictions"])
    await db.connect(settings.database_url)
    t1 = asyncio.create_task(
        bus.consume_loop("drones.telemetry", "prediction-svc-telemetry", handle_telemetry)
    )
    t2 = asyncio.create_task(
        bus.consume_loop("fire.detections", "prediction-svc-detections", handle_detection)
    )
    yield
    t1.cancel()
    t2.cancel()
    await bus.close()
    await db.close()


app = FastAPI(title="Wildfire Prediction Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/predictions")
async def list_predictions():
    """Last 50 predictions, mainly for local debugging/demo."""
    return recent_predictions[-50:]
