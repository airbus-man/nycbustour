"""Flightradar24 access for KE082.

Two sources, tried in this order:
  1. Flightradar24's public (undocumented) JSON endpoints used by its website.
     Needs network access to api.flightradar24.com and data-live.flightradar24.com.
  2. CSV exports saved from the Flightradar24 website / app (Gold/Business feature:
     flight page -> "Download" -> CSV). Drop them into data/tracks/ named
     <YYYY-MM-DD>_<anything>.csv (date = JFK departure date, local).

Everything is returned as plain dicts so the rest of the pipeline has no FR24 coupling.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

LIST_URL = "https://api.flightradar24.com/common/v1/flight/list.json"
TRAIL_URL = "https://data-live.flightradar24.com/clickhandler/"
# Honest client identification. These endpoints are the ones the FR24 website itself calls;
# if they refuse non-browser clients, use the CSV-export path below (or the official FR24 API).
HEADERS = {
    "User-Agent": "ke082-route-analysis/1.0 (github.com/airbus-man/nycbustour; python-requests)",
    "Accept": "application/json, text/plain, */*",
}
HERE = os.path.dirname(os.path.abspath(__file__))
TRACK_DIR = os.path.join(HERE, "data", "tracks")


def fetch_flight_list(flight_number: str = "KE82", limit: int = 100) -> list[dict]:
    """Recent flights for a flight number (newest first)."""
    params = {"query": flight_number, "fetchBy": "flight", "page": 1, "limit": limit}
    r = requests.get(LIST_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()["result"]["response"]["data"] or []
    out = []
    for f in data:
        ap = f.get("airport", {})
        t = f.get("time", {})
        real_dest = (ap.get("destination") or {})
        diverted_to = ((ap.get("real") or {}).get("destination") or {}) if ap.get("real") else {}
        out.append(
            {
                "fr24_id": f.get("identification", {}).get("id"),
                "callsign": (f.get("identification", {}).get("callsign") or "KAL82"),
                "registration": (f.get("aircraft") or {}).get("registration"),
                "aircraft": ((f.get("aircraft") or {}).get("model") or {}).get("code"),
                "origin": ((ap.get("origin") or {}).get("code") or {}).get("icao"),
                "destination_sched": (real_dest.get("code") or {}).get("icao"),
                "destination_real": (diverted_to.get("code") or {}).get("icao") or (real_dest.get("code") or {}).get("icao"),
                "status_text": ((f.get("status") or {}).get("text")),
                "dep_sched_utc": (t.get("scheduled") or {}).get("departure"),
                "dep_real_utc": (t.get("real") or {}).get("departure"),
                "arr_sched_utc": (t.get("scheduled") or {}).get("arrival"),
                "arr_real_utc": (t.get("real") or {}).get("arrival"),
            }
        )
    return out


def fetch_trail(fr24_id: str) -> list[dict]:
    """Position trail for one flight id: [{ts, lat, lon, alt_ft, gs_kt, track_deg}]."""
    r = requests.get(TRAIL_URL, params={"version": "1.5", "flight": fr24_id}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    trail = r.json().get("trail") or []
    pts = [
        {"ts": p["ts"], "lat": p["lat"], "lon": p["lng"], "alt_ft": p.get("alt", 0), "gs_kt": p.get("spd", 0), "track_deg": p.get("hd", 0)}
        for p in trail
    ]
    pts.sort(key=lambda p: p["ts"])
    return pts


def load_csv_track(path: str) -> list[dict]:
    """Parse a Flightradar24 CSV export (Timestamp,UTC,Callsign,Position,Altitude,Speed,Direction)."""
    pts = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            pos = row.get("Position") or ""
            m = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", pos)
            if not m:
                continue
            ts = row.get("Timestamp")
            if ts and ts.isdigit():
                ts = int(ts)
            else:
                ts = int(datetime.strptime(row["UTC"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
            pts.append(
                {
                    "ts": ts,
                    "lat": float(m.group(1)),
                    "lon": float(m.group(2)),
                    "alt_ft": float(row.get("Altitude") or 0),
                    "gs_kt": float(row.get("Speed") or 0),
                    "track_deg": float(row.get("Direction") or 0),
                }
            )
    pts.sort(key=lambda p: p["ts"])
    return pts


def load_kml_track(path: str) -> list[dict]:
    """Parse a Flightradar24 KML export (gx:Track with <when>/<gx:coord>, or a plain LineString)."""
    import xml.etree.ElementTree as ET

    ns = {"k": "http://www.opengis.net/kml/2.2", "gx": "http://www.google.com/kml/ext/2.2"}
    root = ET.parse(path).getroot()
    pts = []
    for tr in root.iter("{http://www.google.com/kml/ext/2.2}Track"):
        whens = [w.text for w in tr.findall("k:when", ns)]
        coords = [c.text for c in tr.findall("gx:coord", ns)]
        for w, c in zip(whens, coords):
            lon, lat, alt_m = (float(x) for x in c.split()[:3])
            ts = int(datetime.strptime(w.strip()[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            pts.append({"ts": ts, "lat": lat, "lon": lon, "alt_ft": alt_m * 3.28084, "gs_kt": 0, "track_deg": 0})
    if not pts:  # LineString without times: cannot be time-matched to winds, but still gives geometry
        for ls in root.iter("{http://www.opengis.net/kml/2.2}LineString"):
            c = ls.find("k:coordinates", ns)
            for i, trip in enumerate((c.text or "").split()):
                lon, lat, alt_m = (float(x) for x in trip.split(",")[:3])
                pts.append({"ts": i, "lat": lat, "lon": lon, "alt_ft": alt_m * 3.28084, "gs_kt": 0, "track_deg": 0})
    pts.sort(key=lambda p: p["ts"])
    # fill ground speed / course from consecutive fixes so cruise filtering and charts work
    from geo import haversine_nm, initial_bearing

    for a, b in zip(pts, pts[1:]):
        dt = b["ts"] - a["ts"]
        a["track_deg"] = initial_bearing(a["lat"], a["lon"], b["lat"], b["lon"])
        a["gs_kt"] = haversine_nm(a["lat"], a["lon"], b["lat"], b["lon"]) / dt * 3600 if dt > 0 else 0
    return pts


def _date_from_name(path: str) -> str | None:
    """Accept 2026-10-30_*.ext, 20261030*.ext or FR24's own KE82_<date>... names."""
    base = os.path.basename(path)
    m = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", base)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def local_csv_tracks() -> dict[str, list[dict]]:
    """{departure_date: track} for every CSV/KML export in data/tracks."""
    out = {}
    for path in sorted(glob.glob(os.path.join(TRACK_DIR, "*.csv")) + glob.glob(os.path.join(TRACK_DIR, "*.kml"))):
        d = _date_from_name(path)
        if not d:
            print(f"skip {path}: name must contain the JFK departure date (YYYY-MM-DD)", file=sys.stderr)
            continue
        try:
            pts = load_kml_track(path) if path.lower().endswith(".kml") else load_csv_track(path)
        except Exception as e:  # noqa: BLE001
            print(f"skip {path}: {e}", file=sys.stderr)
            continue
        if pts:
            out[d] = pts
    return out


def save_track(date: str, fr24_id: str, pts: list[dict]) -> str:
    path = os.path.join(TRACK_DIR, f"{date}_{fr24_id}.json")
    with open(path, "w") as fh:
        json.dump(pts, fh)
    return path


def local_json_tracks() -> dict[str, list[dict]]:
    out = {}
    for path in sorted(glob.glob(os.path.join(TRACK_DIR, "*.json"))):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
        if m:
            with open(path) as fh:
                out[m.group(1)] = json.load(fh)
    return out


if __name__ == "__main__":
    flights = fetch_flight_list(sys.argv[1] if len(sys.argv) > 1 else "KE82")
    for f in flights:
        print(json.dumps(f))
        time.sleep(0.2)
