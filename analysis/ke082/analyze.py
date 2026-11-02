"""Per-flight metrics for KE082: how far north, headwind component, diversion, timing."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from geo import (
    AIRPORTS,
    crosswind_component_kt,
    haversine_nm,
    headwind_component_kt,
    initial_bearing,
    unwrap_lon,
)

CRUISE_MIN_FT = 25_000


def _iso(ts: int | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def analyze_flight(meta: dict, track: list[dict], winds: list[dict] | None) -> dict:
    """meta: one row from fr24.fetch_flight_list (or hand-entered). track/winds may be empty."""
    origin = AIRPORTS.get(meta.get("origin") or "KJFK")
    dest_icao = meta.get("destination_real") or meta.get("destination_sched") or "RKSI"
    dest = AIRPORTS.get(dest_icao, AIRPORTS["RKSI"])
    out = {
        "date": meta["date"],
        "registration": meta.get("registration"),
        "aircraft": meta.get("aircraft"),
        "origin": meta.get("origin") or "KJFK",
        "destination_sched": meta.get("destination_sched") or "RKSI",
        "destination_real": dest_icao,
        "diverted": dest_icao != (meta.get("destination_sched") or "RKSI"),
        "diverted_to_narita": dest_icao == "RJAA",
        "status_text": meta.get("status_text"),
        "dep_sched_utc": _iso(meta.get("dep_sched_utc")),
        "dep_real_utc": _iso(meta.get("dep_real_utc")),
        "arr_sched_utc": _iso(meta.get("arr_sched_utc")),
        "arr_real_utc": _iso(meta.get("arr_real_utc")),
        "source": meta.get("source", "flightradar24"),
        "verified": meta.get("verified", True),
        "notes": meta.get("notes"),
        "track_source": meta.get("track_source") or ("flightradar24" if track else None),
        "has_track": bool(track) and meta.get("track_source") != "great_circle_reference",
        "has_winds": bool(winds),
    }
    if meta.get("dep_real_utc") and meta.get("arr_real_utc"):
        out["block_time_min"] = round((meta["arr_real_utc"] - meta["dep_real_utc"]) / 60)
    if meta.get("dep_sched_utc") and meta.get("dep_real_utc"):
        out["dep_delay_min"] = round((meta["dep_real_utc"] - meta["dep_sched_utc"]) / 60)

    gc_nm = haversine_nm(origin["lat"], origin["lon"], dest["lat"], dest["lon"])
    out["great_circle_nm"] = round(gc_nm)
    if not track:
        return out

    # --- geometry ----------------------------------------------------------
    top = max(track, key=lambda p: p["lat"])
    out["max_lat"] = round(top["lat"], 2)
    out["max_lat_lon"] = round(top["lon"], 2)
    out["max_lat_time_utc"] = _iso(top["ts"])
    out["crossed_alaska"] = any(-170 < p["lon"] < -140 and p["lat"] > 55 for p in track)
    out["polar_min_dist_nm"] = round(min(90 - p["lat"] for p in track) * 60)
    flown = sum(haversine_nm(a["lat"], a["lon"], b["lat"], b["lon"]) for a, b in zip(track, track[1:]))
    out["distance_flown_nm"] = round(flown)
    out["detour_pct"] = round((flown / gc_nm - 1) * 100, 1)
    out["airborne_min"] = round((track[-1]["ts"] - track[0]["ts"]) / 60)
    cruise = [p for p in track if p["alt_ft"] >= CRUISE_MIN_FT]
    if cruise:
        out["cruise_alt_mean_ft"] = round(sum(p["alt_ft"] for p in cruise) / len(cruise))
        out["cruise_alt_max_ft"] = round(max(p["alt_ft"] for p in cruise))
        out["gs_mean_kt"] = round(sum(p["gs_kt"] for p in cruise) / len(cruise))
        out["gs_min_kt"] = round(min(p["gs_kt"] for p in cruise))
    # Northern-ness profile: latitude sampled on a longitude grid (for the chart)
    prof = {}
    for p in track:
        key = int(round(unwrap_lon(p["lon"]) / 5.0) * 5)
        prof.setdefault(key, []).append(p["lat"])
    out["lat_profile"] = [{"lon": k, "lat": round(sum(v) / len(v), 2)} for k, v in sorted(prof.items())]

    # --- winds ---------------------------------------------------------------
    if not winds:
        return out
    by_ts = {w["ts"]: w for w in winds if w.get("wind_speed_kt") is not None}
    samples = []
    pts = [p for p in track if p["ts"] in by_ts]
    for a, b in zip(pts, pts[1:]):
        if a["alt_ft"] < CRUISE_MIN_FT:
            continue
        course = initial_bearing(a["lat"], a["lon"], b["lat"], b["lon"])
        w = by_ts[a["ts"]]
        hw = headwind_component_kt(w["wind_speed_kt"], w["wind_dir_deg"], course)
        xw = crosswind_component_kt(w["wind_speed_kt"], w["wind_dir_deg"], course)
        samples.append(
            {
                "ts": a["ts"],
                "lat": round(a["lat"], 2),
                "lon": round(a["lon"], 2),
                "lon_unwrapped": round(unwrap_lon(a["lon"]), 2),
                "alt_ft": a["alt_ft"],
                "level_hPa": w["level_hPa"],
                "wind_speed_kt": round(w["wind_speed_kt"]),
                "wind_dir_deg": round(w["wind_dir_deg"]),
                "course_deg": round(course),
                "headwind_kt": round(hw, 1),
                "crosswind_kt": round(xw, 1),
                "gs_kt": a["gs_kt"],
                "weight_s": b["ts"] - a["ts"],
            }
        )
    if not samples:
        return out
    wsum = sum(s["weight_s"] for s in samples)
    mean_hw = sum(s["headwind_kt"] * s["weight_s"] for s in samples) / wsum
    worst = max(samples, key=lambda s: s["headwind_kt"])
    pac = [s for s in samples if 140 <= s["lon_unwrapped"] <= 230]  # 140E .. 130W
    out["headwind_mean_kt"] = round(mean_hw, 1)
    out["headwind_max_kt"] = round(worst["headwind_kt"], 1)
    out["headwind_max_at"] = {"lat": worst["lat"], "lon": worst["lon"], "time_utc": _iso(worst["ts"])}
    out["tailwind_max_kt"] = round(-min(s["headwind_kt"] for s in samples), 1)
    out["headwind_hours_over_50kt"] = round(sum(s["weight_s"] for s in samples if s["headwind_kt"] > 50) / 3600, 1)
    if pac:
        pw = sum(s["weight_s"] for s in pac)
        out["headwind_pacific_mean_kt"] = round(sum(s["headwind_kt"] * s["weight_s"] for s in pac) / pw, 1)
    out["wind_speed_max_kt"] = max(s["wind_speed_kt"] for s in samples)
    out["est_tas_mean_kt"] = round(sum((s["gs_kt"] + s["headwind_kt"]) * s["weight_s"] for s in samples) / wsum)
    out["wind_samples"] = samples
    return out


def summarize(flights: list[dict]) -> dict:
    with_track = [f for f in flights if f.get("has_track")]
    with_wind = [f for f in flights if f.get("headwind_mean_kt") is not None]
    s_ref = [f for f in flights if f.get("track_source") == "great_circle_reference"]
    s = {
        "n_flights": len(flights),
        "n_with_track": len(with_track),
        "n_with_winds": len(with_wind),
        "narita_dates": [f["date"] for f in flights if f.get("diverted_to_narita")],
        "diverted_dates": [f["date"] for f in flights if f.get("diverted")],
        "n_reference_route": len(s_ref),
    }
    if with_track:
        n = max(with_track, key=lambda f: f["max_lat"])
        s["northernmost"] = {"date": n["date"], "max_lat": n["max_lat"], "lon": n["max_lat_lon"]}
    if with_wind:
        w = max(with_wind, key=lambda f: f["headwind_mean_kt"])
        s["strongest_headwind"] = {"date": w["date"], "mean_kt": w["headwind_mean_kt"], "max_kt": w["headwind_max_kt"]}
    return s
