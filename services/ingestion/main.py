"""
Ingestion service.

The one HTTP-facing entrypoint for the field side of the system - drones and
ground/weather sensors POST here. Everything downstream (detection,
prediction, alerting) is event-driven off of NATS subjects this service
publishes to, so this is the only service that needs to be reachable by
field hardware.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.config import settings
from shared import db
from shared.messaging import create_bus
from shared.models import DroneFrame, TelemetryEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingestion")

bus = create_bus()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bus.connect()
    await bus.ensure_stream("TELEMETRY", ["drones.telemetry"])
    await bus.ensure_stream("FRAMES", ["drones.frames"])
    await db.connect(settings.database_url)
    yield
    await bus.close()
    await db.close()


app = FastAPI(title="Wildfire Ingestion Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/telemetry")
async def ingest_telemetry(event: TelemetryEvent):
    """Accepts a sensor/weather-station/drone telemetry reading."""
    await bus.publish("drones.telemetry", event)
    await db.store_telemetry(event)
    return {"accepted": True, "source_id": event.source_id}


@app.post("/frames")
async def ingest_frame(frame: DroneFrame):
    """Accepts metadata for a drone-captured frame, queued for detection."""
    await bus.publish("drones.frames", frame)
    return {"accepted": True, "drone_id": frame.drone_id}
