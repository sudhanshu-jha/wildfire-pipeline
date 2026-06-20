from datetime import datetime, timezone

from services.detection.model_stub import run_fire_detection
from services.prediction.spread_model_stub import project_spread
from shared.models import DroneFrame, FireDetectionEvent, GeoPoint, TelemetryEvent


def make_frame(drone_id="drone-01") -> DroneFrame:
    return DroneFrame(
        drone_id=drone_id,
        location=GeoPoint(lat=30.0, lon=-5.0),
        altitude_m=120.0,
        timestamp=datetime(2026, 6, 19, 12, 0, 0, tzinfo=timezone.utc),
        frame_url="s3://bucket/frame.jpg",
    )


def test_detection_stub_returns_valid_class():
    frame = make_frame()
    fire_class, confidence, bbox = run_fire_detection(frame)
    assert fire_class in ("none", "smoke", "flame")
    if fire_class == "none":
        assert confidence == 0.0
        assert bbox is None
    else:
        assert 0.0 < confidence <= 1.0
        assert bbox is not None and len(bbox) == 4


def test_detection_stub_is_deterministic_for_same_input():
    frame = make_frame()
    result_a = run_fire_detection(frame)
    result_b = run_fire_detection(frame)
    assert result_a == result_b


def test_spread_model_returns_perimeter_and_risk():
    detection = FireDetectionEvent(
        detection_id="d1",
        drone_id="drone-01",
        location=GeoPoint(lat=30.0, lon=-5.0),
        confidence=0.9,
        fire_class="flame",
    )
    wind = TelemetryEvent(
        source_id="drone-01",
        source_type="drone",
        location=GeoPoint(lat=30.0, lon=-5.0),
        wind_speed_kmh=20.0,
        wind_direction_deg=90.0,
    )
    perimeter, risk = project_spread(detection, wind)

    assert len(perimeter) == 12  # 360 / 30 degree steps
    assert 0.0 < risk <= 0.99
    # Every projected point should be reasonably close to the origin for
    # these inputs (sanity bound, not a precise geometry check).
    for point in perimeter:
        assert abs(point.lat - detection.location.lat) < 0.05
        assert abs(point.lon - detection.location.lon) < 0.05


def test_spread_model_handles_missing_wind():
    detection = FireDetectionEvent(
        detection_id="d2",
        drone_id="drone-02",
        location=GeoPoint(lat=10.0, lon=10.0),
        confidence=0.6,
        fire_class="smoke",
    )
    perimeter, risk = project_spread(detection, wind=None)
    assert len(perimeter) == 12
    assert 0.0 < risk <= 0.99
