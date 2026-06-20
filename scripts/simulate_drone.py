"""
Simulates a small fleet of drones sending telemetry and frame captures to
the ingestion service. Run this after `make up` (or `docker compose up`) to
exercise the full pipeline end-to-end - watch detections, predictions, and
alerts flow through the logs of the other services (or hit their /detections,
/predictions, /alerts endpoints).

Usage:
    pip install httpx
    python scripts/simulate_drone.py
"""

import asyncio
import random
import uuid
from datetime import datetime, timezone

import httpx

INGESTION_URL = "http://localhost:8001"
DRONE_IDS = ["drone-01", "drone-02", "drone-03"]
BASE_LAT, BASE_LON = 30.0668, -5.0026  # arbitrary forest region


async def send_telemetry(client: httpx.AsyncClient, drone_id: str) -> None:
    payload = {
        "source_id": drone_id,
        "source_type": "drone",
        "location": {
            "lat": BASE_LAT + random.uniform(-0.05, 0.05),
            "lon": BASE_LON + random.uniform(-0.05, 0.05),
        },
        "temperature_c": round(random.uniform(20, 40), 1),
        "humidity_pct": round(random.uniform(10, 60), 1),
        "wind_speed_kmh": round(random.uniform(5, 35), 1),
        "wind_direction_deg": round(random.uniform(0, 360), 1),
        "smoke_density_ppm": round(random.uniform(0, 50), 1),
    }
    r = await client.post(f"{INGESTION_URL}/telemetry", json=payload)
    r.raise_for_status()


async def send_frame(client: httpx.AsyncClient, drone_id: str) -> None:
    payload = {
        "drone_id": drone_id,
        "location": {
            "lat": BASE_LAT + random.uniform(-0.05, 0.05),
            "lon": BASE_LON + random.uniform(-0.05, 0.05),
        },
        "altitude_m": round(random.uniform(80, 200), 1),
        "frame_url": f"s3://wildfire-frames/{uuid.uuid4()}.jpg",
        "has_thermal": random.random() > 0.5,
    }
    r = await client.post(f"{INGESTION_URL}/frames", json=payload)
    r.raise_for_status()


async def main() -> None:
    async with httpx.AsyncClient() as client:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Starting drone simulation. Ctrl+C to stop.")
        while True:
            for drone_id in DRONE_IDS:
                await send_telemetry(client, drone_id)
                await send_frame(client, drone_id)
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
