"""
Optional Postgres persistence layer.

Enabled by setting DATABASE_URL (e.g. postgresql://user:pass@postgres:5432/wildfire).
When DATABASE_URL is empty the module is a no-op — all `store_*` calls return
immediately, keeping in-memory-only mode fully functional.

Schema is created on first connect (CREATE TABLE IF NOT EXISTS) so no separate
migration tool is needed for the skeleton.  Replace with Alembic migrations
before production.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_pool = None  # asyncpg connection pool, or None when DB is disabled


async def connect(database_url: str) -> None:
    """Open the connection pool and ensure schema exists. Call from lifespan."""
    global _pool
    if not database_url:
        logger.info("DATABASE_URL not set — running without persistence")
        return
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        await _ensure_schema()
        logger.info("Postgres connected: %s", database_url)
    except ImportError:
        logger.warning("asyncpg not installed — persistence disabled (pip install asyncpg)")
    except Exception as exc:
        logger.warning("Postgres unavailable (%s) — running without persistence", exc)


async def close() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def _ensure_schema() -> None:
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id          BIGSERIAL PRIMARY KEY,
                source_id   TEXT NOT NULL,
                source_type TEXT NOT NULL,
                lat         DOUBLE PRECISION NOT NULL,
                lon         DOUBLE PRECISION NOT NULL,
                temperature_c      DOUBLE PRECISION,
                humidity_pct       DOUBLE PRECISION,
                wind_speed_kmh     DOUBLE PRECISION,
                wind_direction_deg DOUBLE PRECISION,
                smoke_density_ppm  DOUBLE PRECISION,
                recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                detection_id TEXT PRIMARY KEY,
                drone_id     TEXT NOT NULL,
                lat          DOUBLE PRECISION NOT NULL,
                lon          DOUBLE PRECISION NOT NULL,
                fire_class   TEXT NOT NULL,
                confidence   DOUBLE PRECISION NOT NULL,
                bounding_box JSONB,
                detected_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id        TEXT PRIMARY KEY,
                based_on_detection_id TEXT NOT NULL,
                lat                  DOUBLE PRECISION NOT NULL,
                lon                  DOUBLE PRECISION NOT NULL,
                perimeter            JSONB NOT NULL,
                horizon_minutes      INT NOT NULL,
                risk_score           DOUBLE PRECISION NOT NULL,
                predicted_at         TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id              TEXT PRIMARY KEY,
                based_on_prediction_id TEXT NOT NULL,
                lat                   DOUBLE PRECISION NOT NULL,
                lon                   DOUBLE PRECISION NOT NULL,
                severity              TEXT NOT NULL,
                message               TEXT NOT NULL,
                alerted_at            TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)


# ── store helpers (silent no-ops when pool is None) ───────────────────────────

async def store_telemetry(event) -> None:
    if not _pool:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO telemetry
                   (source_id, source_type, lat, lon, temperature_c, humidity_pct,
                    wind_speed_kmh, wind_direction_deg, smoke_density_ppm, recorded_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                event.source_id, event.source_type,
                event.location.lat, event.location.lon,
                event.temperature_c, event.humidity_pct,
                event.wind_speed_kmh, event.wind_direction_deg,
                event.smoke_density_ppm, event.timestamp,
            )
    except Exception as exc:
        logger.warning("store_telemetry failed: %s", exc)


async def store_detection(event) -> None:
    if not _pool:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO detections
                   (detection_id, drone_id, lat, lon, fire_class, confidence, bounding_box, detected_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                   ON CONFLICT (detection_id) DO NOTHING""",
                event.detection_id, event.drone_id,
                event.location.lat, event.location.lon,
                event.fire_class, event.confidence,
                json.dumps(event.bounding_box), event.timestamp,
            )
    except Exception as exc:
        logger.warning("store_detection failed: %s", exc)


async def store_prediction(event) -> None:
    if not _pool:
        return
    try:
        perimeter = json.dumps([{"lat": p.lat, "lon": p.lon} for p in event.projected_perimeter])
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO predictions
                   (prediction_id, based_on_detection_id, lat, lon,
                    perimeter, horizon_minutes, risk_score, predicted_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                   ON CONFLICT (prediction_id) DO NOTHING""",
                event.prediction_id, event.based_on_detection_id,
                event.origin.lat, event.origin.lon,
                perimeter, event.horizon_minutes,
                event.risk_score, event.timestamp,
            )
    except Exception as exc:
        logger.warning("store_prediction failed: %s", exc)


async def store_alert(event) -> None:
    if not _pool:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO alerts
                   (alert_id, based_on_prediction_id, lat, lon,
                    severity, message, alerted_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)
                   ON CONFLICT (alert_id) DO NOTHING""",
                event.alert_id, event.based_on_prediction_id,
                event.location.lat, event.location.lon,
                event.severity.value, event.message, event.timestamp,
            )
    except Exception as exc:
        logger.warning("store_alert failed: %s", exc)


async def get_recent_detections(limit: int = 50) -> Optional[list[dict]]:
    """Returns rows from DB if pool is available, else None (caller uses in-memory)."""
    if not _pool:
        return None
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM detections ORDER BY detected_at DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]


async def get_recent_predictions(limit: int = 50) -> Optional[list[dict]]:
    if not _pool:
        return None
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM predictions ORDER BY predicted_at DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]


async def get_recent_alerts(limit: int = 50) -> Optional[list[dict]]:
    if not _pool:
        return None
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM alerts ORDER BY alerted_at DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]
