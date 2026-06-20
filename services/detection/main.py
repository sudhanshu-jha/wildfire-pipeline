"""
Detection service.

Consumes drone frame metadata off `drones.frames`, runs (stubbed) fire/smoke
detection, and publishes any positive hits to `fire.detections`. No HTTP
ingress from the outside world - this service only talks to NATS and to
whatever inference backend `model_stub.run_fire_detection` is eventually
replaced with.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.detection.model_stub import run_fire_detection
from shared.config import settings
from shared import db
from shared.messaging import create_bus
from shared.models import DroneFrame, FireDetectionEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("detection")

bus = create_bus()
recent_detections: list[FireDetectionEvent] = []


async def handle_frame(raw: bytes) -> None:
    frame = DroneFrame.model_validate_json(raw)
    fire_class, confidence, bbox = run_fire_detection(frame)
    if fire_class == "none":
        return

    detection = FireDetectionEvent(
        detection_id=str(uuid.uuid4()),
        drone_id=frame.drone_id,
        location=frame.location,
        confidence=confidence,
        fire_class=fire_class,
        bounding_box=bbox,
    )
    recent_detections.append(detection)
    await bus.publish("fire.detections", detection)
    await db.store_detection(detection)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bus.connect()
    await bus.ensure_stream("FRAMES", ["drones.frames"])
    await bus.ensure_stream("DETECTIONS", ["fire.detections"])
    await db.connect(settings.database_url)
    task = asyncio.create_task(bus.consume_loop("drones.frames", "detection-svc", handle_frame))
    yield
    task.cancel()
    await bus.close()
    await db.close()


app = FastAPI(title="Wildfire Detection Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/detections")
async def list_detections():
    """Last 50 detections, mainly for local debugging/demo."""
    return recent_detections[-50:]
