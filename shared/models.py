"""
Shared event/data models for the wildfire detection-prediction-alerting pipeline.

These are the contracts every service speaks. Keeping them in one place
(instead of duplicating per-service) means a schema change is a single-file
edit, even though each service is deployed independently.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lat: float
    lon: float


class TelemetryEvent(BaseModel):
    """Raw reading from a ground sensor, weather station, or drone."""

    source_id: str
    source_type: str  # "drone" | "ground_sensor" | "weather_station"
    location: GeoPoint
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    smoke_density_ppm: Optional[float] = None


class DroneFrame(BaseModel):
    """Metadata for a single image/video frame captured by a drone.

    In production, frame_url would point at object storage (S3/GCS) and the
    detection service would pull the actual image for inference. The skeleton
    only passes metadata around so the pipeline can be exercised without a
    real media pipeline.
    """

    drone_id: str
    location: GeoPoint
    altitude_m: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    frame_url: str
    has_thermal: bool = False


class FireDetectionEvent(BaseModel):
    """Output of the detection service."""

    detection_id: str
    drone_id: str
    location: GeoPoint
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float
    fire_class: str  # "smoke" | "flame"
    bounding_box: Optional[list[float]] = None  # [x1, y1, x2, y2], normalized


class FirePredictionEvent(BaseModel):
    """Output of the prediction service: a projected fire perimeter."""

    prediction_id: str
    based_on_detection_id: str
    origin: GeoPoint
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    projected_perimeter: list[GeoPoint]
    horizon_minutes: int
    risk_score: float  # 0.0 - 1.0


class AlertSeverity(str, Enum):
    INFO = "info"
    WATCH = "watch"
    WARNING = "warning"
    EVACUATE = "evacuate"


class AlertEvent(BaseModel):
    """Output of the alerting service."""

    alert_id: str
    based_on_prediction_id: str
    location: GeoPoint
    severity: AlertSeverity
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
