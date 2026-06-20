"""
Rothermel-inspired fire-spread prediction model.

Implements a simplified Rothermel (1972) wind-driven elliptical spread model:
- Wind factor phi_w uses the Rothermel Table 1 power-law coefficients.
- Spread rate R scales with fire class (flame vs smoke) and phi_w.
- Perimeter is projected as a wind-biased ellipse with length-to-breadth
  ratio derived from wind speed, rotated to align the major axis downwind.
- Risk score integrates confidence, wind intensity, and humidity.

Replace `project_spread` with a cellular-automaton or ML-based model once
fuel-load, slope, and vegetation rasters are available. The function
signature is the stable contract; internals can be swapped freely.
"""

import math
from typing import Optional

from shared.models import FireDetectionEvent, GeoPoint, TelemetryEvent

# Rothermel Table 1 simplified wind coefficients
_PHI_C = 0.42
_PHI_B = 0.84
_PHI_MAX = 3.0

# Base spread rates (m/min) by fire class
_R0: dict[str, float] = {"flame": 8.0, "smoke": 3.0}
_HORIZON_MIN = 60


def _wind_factor(wind_speed_kmh: float) -> float:
    """Rothermel phi_w — dimensionless wind multiplier."""
    return min(_PHI_C * (wind_speed_kmh ** _PHI_B), _PHI_MAX)


def _ellipse_radius_km(
    angle_rad: float,
    wind_dir_rad: float,
    semi_major_km: float,
    semi_minor_km: float,
) -> float:
    """
    Radius of a wind-aligned ellipse at `angle_rad` (geographic bearing
    measured from north, clockwise). The ellipse major axis points downwind.
    """
    # Rotate so that angle is relative to the wind (downwind = 0)
    theta = angle_rad - wind_dir_rad
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    # Standard ellipse radius formula
    denom = math.hypot(semi_major_km * sin_t, semi_minor_km * cos_t)
    if denom == 0:
        return semi_minor_km
    return (semi_major_km * semi_minor_km) / denom


def project_spread(
    detection: FireDetectionEvent, wind: Optional[TelemetryEvent]
) -> tuple[list[GeoPoint], float]:
    """Returns (projected_perimeter_points, risk_score).

    Projects a 60-minute fire perimeter using a Rothermel-inspired
    wind-driven ellipse. Returns 12 GeoPoints (every 30°) and a risk
    score in (0, 0.99].
    """
    wind_speed = wind.wind_speed_kmh if wind and wind.wind_speed_kmh is not None else 10.0
    wind_dir_deg = wind.wind_direction_deg if wind and wind.wind_direction_deg is not None else 0.0
    humidity = wind.humidity_pct if wind and wind.humidity_pct is not None else None
    smoke_ppm = wind.smoke_density_ppm if wind and wind.smoke_density_ppm is not None else None

    # Base spread rate — dry-condition proxy from smoke density
    r0 = _R0.get(detection.fire_class, 3.0)
    if smoke_ppm is not None and smoke_ppm > 20:
        r0 *= 1.2

    phi_w = _wind_factor(wind_speed)
    spread_rate_m_per_min = r0 * (1.0 + phi_w)

    # 60-minute head-fire travel distance (km)
    head_dist_km = spread_rate_m_per_min * _HORIZON_MIN / 1000.0

    # Ellipse axes: major = head distance, minor determined by LB ratio
    lb = min(1.0 + 0.125 * wind_speed, 4.0)
    semi_major_km = head_dist_km
    semi_minor_km = head_dist_km / lb if lb > 0 else head_dist_km

    # Guard: always produce a visible perimeter even at very low spread
    semi_major_km = max(semi_major_km, 0.05)
    semi_minor_km = max(semi_minor_km, 0.03)

    wind_dir_rad = math.radians(wind_dir_deg)
    lat_rad = math.radians(detection.location.lat)
    lon_scale = math.cos(lat_rad) or 1e-9

    points: list[GeoPoint] = []
    for angle_deg in range(0, 360, 30):
        angle_rad = math.radians(angle_deg)
        r_km = _ellipse_radius_km(angle_rad, wind_dir_rad, semi_major_km, semi_minor_km)

        d_lat = (r_km / 111.0) * math.cos(angle_rad)
        d_lon = (r_km / (111.0 * lon_scale)) * math.sin(angle_rad)

        points.append(
            GeoPoint(
                lat=detection.location.lat + d_lat,
                lon=detection.location.lon + d_lon,
            )
        )

    # Risk score: confidence × (base + wind contribution + dryness penalty)
    humidity_penalty = ((1.0 - humidity / 100.0) * 0.2) if humidity is not None else 0.0
    risk_score = min(0.99, detection.confidence * (0.4 + phi_w / 8.0 + humidity_penalty))

    return points, round(risk_score, 2)
