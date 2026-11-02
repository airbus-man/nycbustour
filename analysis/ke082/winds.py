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
    for i in range(0, len(points), 50):
        chunk = points[i : i + 50]
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
        r = requests.get(API, params=params, timeout=60)
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, dict):
            payload = [payload]
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
