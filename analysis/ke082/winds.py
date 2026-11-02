"""Upper-air winds along a flight track from Open-Meteo (GFS/ICON blend, pressure levels).

Open-Meteo's forecast endpoint serves the last 92 days (`past_days`) at 200/250/300 hPa,
which brackets KE082's cruise levels (FL300-FL400). Needs network access to api.open-meteo.com.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import requests

from geo import MS_TO_KT, nearest_pressure_level

API = "https://api.open-meteo.com/v1/forecast"
LEVELS = (200, 250, 300)
CHUNK = 25  # locations per request; larger requests get cut off by some proxies


def _get(params: dict, attempts: int = 4) -> list[dict]:
    """GET with exponential backoff; Open-Meteo returns a list for multi-location queries."""
    import time

    delay = 2.0
    for i in range(attempts):
        try:
            r = requests.get(API, params=params, timeout=60)
            r.raise_for_status()
            payload = r.json()
            return [payload] if isinstance(payload, dict) else payload
        except (requests.RequestException, ValueError) as e:  # noqa: PERF203
            if i == attempts - 1:
                raise RuntimeError(f"open-meteo: {type(e).__name__}: {str(e)[:120]}") from e
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")
HERE = os.path.dirname(os.path.abspath(__file__))
WIND_DIR = os.path.join(HERE, "data", "winds")


def sample_track(track: list[dict], step_s: int = 900) -> list[dict]:
    """Thin a track to one point per `step_s` seconds (Open-Meteo accepts ~100 locations per call)."""
    out, last = [], None
    for p in track:
        if last is None or p["ts"] - last >= step_s:
            out.append(p)
            last = p["ts"]
    if track and out[-1] is not p:
        out.append(track[-1])
    return out


def fetch_winds_for_points(points: list[dict], past_days: int = 14) -> list[dict]:
    """For each point return {ts, level_hPa, wind_speed_kt, wind_dir_deg} at the nearest model hour."""
    results: list[dict] = []
    for i in range(0, len(points), CHUNK):
        chunk = points[i : i + CHUNK]
        hourly = ",".join(f"wind_speed_{l}hPa,wind_direction_{l}hPa" for l in LEVELS)
        params = {
            "latitude": ",".join(f"{p['lat']:.3f}" for p in chunk),
            "longitude": ",".join(f"{p['lon']:.3f}" for p in chunk),
            "hourly": hourly,
            "wind_speed_unit": "ms",
            "past_days": past_days,
            "forecast_days": 1,
            "timeformat": "unixtime",
            "timezone": "UTC",
        }
        payload = _get(params)
        for p, loc in zip(chunk, payload):
            times = loc["hourly"]["time"]
            k = min(range(len(times)), key=lambda j: abs(times[j] - p["ts"]))
            lvl = nearest_pressure_level(p.get("alt_ft") or 35_000)
            spd = loc["hourly"][f"wind_speed_{lvl}hPa"][k]
            wd = loc["hourly"][f"wind_direction_{lvl}hPa"][k]
            results.append(
                {
                    "ts": p["ts"],
                    "model_time": times[k],
                    "level_hPa": lvl,
                    "wind_speed_kt": None if spd is None else spd * MS_TO_KT,
                    "wind_dir_deg": wd,
                    "model": loc.get("model", "open-meteo best_match"),
                }
            )
    return results


def save_winds(date: str, winds: list[dict]) -> str:
    os.makedirs(WIND_DIR, exist_ok=True)
    path = os.path.join(WIND_DIR, f"{date}.json")
    with open(path, "w") as fh:
        json.dump(winds, fh)
    return path


def load_winds(date: str) -> list[dict] | None:
    path = os.path.join(WIND_DIR, f"{date}.json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return None


if __name__ == "__main__":
    now = int(datetime.now(timezone.utc).timestamp())
    print(fetch_winds_for_points([{"ts": now - 3600, "lat": 60.0, "lon": -150.0, "alt_ft": 35000}]))


# ---------------------------------------------------------------------------
# Reference route + wind-field grid (used when no Flightradar24 track is available)
# ---------------------------------------------------------------------------
GRID_LATS = list(range(30, 81, 5))
GRID_LONS = list(range(100, 181, 10)) + list(range(-170, -59, 10))  # North Pacific: 100E .. 60W
GRID_LEVEL = 250


def reference_route(dep_ts: int, origin: dict, dest: dict, block_hours: float = 15.5, n: int = 64, alt_ft: int = 35_000) -> list[dict]:
    """Great-circle route with a plausible time stamp per point. It is a REFERENCE line, not a flown track."""
    from geo import great_circle_points, initial_bearing

    pts = great_circle_points(origin["lat"], origin["lon"], dest["lat"], dest["lon"], n=n)
    out = []
    for i, (lat, lon) in enumerate(pts):
        f = i / n
        nxt = pts[min(i + 1, n)]
        out.append({"ts": int(dep_ts + f * block_hours * 3600), "lat": lat, "lon": lon, "alt_ft": alt_ft if 0.03 < f < 0.97 else 5_000, "gs_kt": 0,
                    "track_deg": initial_bearing(lat, lon, nxt[0], nxt[1])})
    return out


def fetch_wind_grid(at_ts: int, level: int = GRID_LEVEL, past_days: int = 14) -> list[dict]:
    """250 hPa wind on a coarse North-Pacific grid at the model hour nearest `at_ts`."""
    pts = [{"lat": la, "lon": lo} for la in GRID_LATS for lo in GRID_LONS]
    out = []
    for i in range(0, len(pts), CHUNK):
        chunk = pts[i : i + CHUNK]
        params = {
            "latitude": ",".join(str(p["lat"]) for p in chunk),
            "longitude": ",".join(str(p["lon"]) for p in chunk),
            "hourly": f"wind_speed_{level}hPa,wind_direction_{level}hPa",
            "wind_speed_unit": "ms", "past_days": past_days, "forecast_days": 1, "timeformat": "unixtime", "timezone": "UTC",
        }
        payload = _get(params)
        for p, loc in zip(chunk, payload):
            times = loc["hourly"]["time"]
            k = min(range(len(times)), key=lambda j: abs(times[j] - at_ts))
            spd = loc["hourly"][f"wind_speed_{level}hPa"][k]
            out.append({"lat": p["lat"], "lon": p["lon"], "spd_kt": None if spd is None else round(spd * MS_TO_KT), "dir_deg": loc["hourly"][f"wind_direction_{level}hPa"][k], "model_time": times[k]})
    return out


def save_grid(date: str, grid: list[dict]) -> None:
    os.makedirs(WIND_DIR, exist_ok=True)
    with open(os.path.join(WIND_DIR, f"grid_{date}.json"), "w") as fh:
        json.dump(grid, fh)


def load_grid(date: str) -> list[dict] | None:
    path = os.path.join(WIND_DIR, f"grid_{date}.json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return None
