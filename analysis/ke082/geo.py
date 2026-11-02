"""Great-circle helpers and wind/track math for the KE082 analysis."""
from __future__ import annotations

import math

EARTH_RADIUS_NM = 3440.065
MS_TO_KT = 1.943844

AIRPORTS = {
    "KJFK": {"iata": "JFK", "name": "New York JFK", "lat": 40.6413, "lon": -73.7781},
    "RKSI": {"iata": "ICN", "name": "Seoul Incheon", "lat": 37.4602, "lon": 126.4407},
    "RJAA": {"iata": "NRT", "name": "Tokyo Narita", "lat": 35.7720, "lon": 140.3929},
    "PANC": {"iata": "ANC", "name": "Anchorage", "lat": 61.1743, "lon": -149.9983},
}

# Standard-atmosphere pressure altitude (ft) of the Open-Meteo pressure levels we use.
PRESSURE_LEVELS_FT = {300: 30_000, 250: 34_000, 200: 38_600}


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(math.sqrt(a))


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """True course (deg, 0..360) from point 1 toward point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    x = math.sin(dlmb) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def great_circle_points(lat1, lon1, lat2, lon2, n: int = 100):
    """n+1 points along the great circle from 1 to 2 (for the reference line on the map)."""
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    d = 2 * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2))
    pts = []
    for i in range(n + 1):
        f = i / n
        a = math.sin((1 - f) * d) / math.sin(d)
        b = math.sin(f * d) / math.sin(d)
        x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
        y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
        z = a * math.sin(p1) + b * math.sin(p2)
        pts.append((math.degrees(math.atan2(z, math.sqrt(x * x + y * y))), math.degrees(math.atan2(y, x))))
    return pts


def nearest_pressure_level(alt_ft: float) -> int:
    return min(PRESSURE_LEVELS_FT, key=lambda p: abs(PRESSURE_LEVELS_FT[p] - alt_ft))


def wind_components_kt(speed_kt: float, direction_from_deg: float) -> tuple[float, float]:
    """(u, v) wind vector in knots, pointing in the direction the air is moving to."""
    r = math.radians(direction_from_deg)
    return -speed_kt * math.sin(r), -speed_kt * math.cos(r)


def headwind_component_kt(speed_kt: float, direction_from_deg: float, course_deg: float) -> float:
    """Headwind along the aircraft course. Positive = headwind, negative = tailwind."""
    u, v = wind_components_kt(speed_kt, direction_from_deg)
    c = math.radians(course_deg)
    along_track = u * math.sin(c) + v * math.cos(c)  # + means pushing the aircraft forward
    return -along_track


def crosswind_component_kt(speed_kt: float, direction_from_deg: float, course_deg: float) -> float:
    """Crosswind; positive = from the left of the course."""
    u, v = wind_components_kt(speed_kt, direction_from_deg)
    c = math.radians(course_deg)
    return u * math.cos(c) - v * math.sin(c)


def unwrap_lon(lon: float) -> float:
    """Map longitudes so the Pacific crossing is continuous (eastern hemisphere > 180)."""
    return lon + 360 if lon < -30 else lon
