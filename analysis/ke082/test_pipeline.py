"""Self-check with SYNTHETIC data (not real flights): exercises analyze + dashboard end to end.

    python3 test_pipeline.py [out_dir]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import analyze
import build_dashboard
from geo import AIRPORTS, great_circle_points, headwind_component_kt


def synthetic_track(north_bias_deg: float, dest: str = "RKSI", t0: int = 1_793_384_040) -> list[dict]:
    o, d = AIRPORTS["KJFK"], AIRPORTS[dest]
    pts = great_circle_points(o["lat"], o["lon"], d["lat"], d["lon"], n=180)
    out = []
    for i, (lat, lon) in enumerate(pts):
        f = i / 180
        bulge = north_bias_deg * 4 * f * (1 - f)  # push the middle of the route north
        alt = 0 if f < 0.02 or f > 0.98 else 37_000
        out.append({"ts": t0 + i * 300, "lat": lat + bulge, "lon": lon, "alt_ft": alt, "gs_kt": 470 if alt else 180, "track_deg": 300})
    return out


def synthetic_winds(track: list[dict], speed_kt: float) -> list[dict]:
    return [{"ts": p["ts"], "model_time": p["ts"], "level_hPa": 250, "wind_speed_kt": speed_kt, "wind_dir_deg": 270.0} for p in track]


def main() -> int:
    assert round(headwind_component_kt(100, 270, 270)) == 100  # flying west into a west wind
    assert round(headwind_component_kt(100, 270, 90)) == -100  # tailwind
    assert round(headwind_component_kt(100, 0, 270)) == 0  # pure crosswind
    flights = []
    for i, (date, bias, wind, dest) in enumerate(
        [("2026-10-26", 2, 60, "RKSI"), ("2026-10-27", 5, 90, "RKSI"), ("2026-10-28", 8, 120, "RJAA"), ("2026-10-29", 0, 40, "RKSI")]
    ):
        tr = synthetic_track(bias, dest)
        meta = {"date": date, "origin": "KJFK", "destination_sched": "RKSI", "destination_real": dest, "registration": "SYNTH", "aircraft": "TEST",
                "dep_sched_utc": tr[0]["ts"] - 600, "dep_real_utc": tr[0]["ts"], "arr_real_utc": tr[-1]["ts"], "status_text": "synthetic", "source": "synthetic test", "verified": False}
        flights.append(analyze.analyze_flight(meta, tr, synthetic_winds(tr, wind)))
    assert flights[2]["diverted_to_narita"] and not flights[0]["diverted_to_narita"]
    assert flights[1]["max_lat"] > flights[0]["max_lat"] > flights[3]["max_lat"] and flights[2]["detour_pct"] > 0  # JFK-NRT great circle peaks ~70N, lower than JFK-ICN (~78N)
    assert flights[2]["headwind_mean_kt"] > flights[1]["headwind_mean_kt"] > flights[0]["headwind_mean_kt"] > 0
    assert all(f["has_winds"] and f["wind_samples"] for f in flights)
    summary = {"generated_utc": "synthetic", "flight": "KE82", "window": {"start": "2026-10-26", "end": "2026-10-29"}, "summary": analyze.summarize(flights), "errors": [], "flights": flights}
    assert summary["summary"]["northernmost"]["date"] == "2026-10-27"
    out_dir = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "summary_synthetic.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print(build_dashboard.build(summary, os.path.join(out_dir, "dashboard_synthetic.html")))
    for f in flights:
        print(f["date"], f["destination_real"], "max_lat", f["max_lat"], "hw_mean", f["headwind_mean_kt"], "hw_max", f["headwind_max_kt"], "detour", f["detour_pct"], "%")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
