"""Run the whole KE082 pipeline: FR24 flights + tracks -> winds -> metrics -> dashboard.

    python3 run_all.py [--days 7] [--end YYYY-MM-DD] [--offline]

Falls back gracefully: if Flightradar24 / Open-Meteo are unreachable it keeps whatever is
cached in data/ (JSON tracks, CSV exports, winds) plus the hand-entered data/flights_known.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import analyze
import build_dashboard
import fr24
import winds as windmod

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
NY = ZoneInfo("America/New_York")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def dep_date_local(meta: dict) -> str | None:
    ts = meta.get("dep_real_utc") or meta.get("dep_sched_utc")
    return None if ts is None else datetime.fromtimestamp(ts, NY).strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--end", default=None, help="last JFK departure date (local), default = yesterday")
    ap.add_argument("--offline", action="store_true", help="do not call FR24 / Open-Meteo")
    ap.add_argument("--flight", default="KE82")
    args = ap.parse_args()

    end = date.fromisoformat(args.end) if args.end else datetime.now(NY).date() - timedelta(days=1)
    dates = [(end - timedelta(days=i)).isoformat() for i in range(args.days - 1, -1, -1)]
    log(f"window: {dates[0]} .. {dates[-1]}")

    with open(os.path.join(DATA, "flights_known.json")) as fh:
        known = json.load(fh)
    metas = {f["date"]: f for f in known["flights"] if f["date"] in dates}
    for d in dates:
        metas.setdefault(d, {"date": d, "origin": "KJFK", "destination_sched": "RKSI", "source": "none", "verified": False})

    tracks = fr24.local_json_tracks()
    tracks.update(fr24.local_csv_tracks())
    errors = []

    if not args.offline:
        try:
            for f in fr24.fetch_flight_list(args.flight, limit=100):
                d = dep_date_local(f)
                if d not in metas:
                    continue
                f.update({"date": d, "source": "flightradar24", "verified": True})
                metas[d] = {**metas[d], **{k: v for k, v in f.items() if v is not None}}
                if d not in tracks and f.get("fr24_id"):
                    try:
                        pts = fr24.fetch_trail(f["fr24_id"])
                        if pts:
                            tracks[d] = pts
                            fr24.save_track(d, f["fr24_id"], pts)
                            log(f"{d}: {len(pts)} track points")
                        time.sleep(1.0)
                    except Exception as e:  # noqa: BLE001
                        errors.append(f"{d} trail: {e}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"flightradar24 list: {e}")
            log(f"FR24 unavailable: {e}")

    results = []
    for d in dates:
        track = tracks.get(d) or []
        w = windmod.load_winds(d)
        if track and w is None and not args.offline:
            try:
                w = windmod.fetch_winds_for_points(windmod.sample_track(track))
                windmod.save_winds(d, w)
                log(f"{d}: {len(w)} wind samples")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{d} winds: {e}")
                w = None
        results.append(analyze.analyze_flight(metas[d], track, w))

    summary = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "flight": args.flight,
        "window": {"start": dates[0], "end": dates[-1]},
        "schedule": known.get("schedule"),
        "summary": analyze.summarize(results),
        "errors": errors,
        "flights": results,
    }
    with open(os.path.join(DATA, "summary.json"), "w") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    out = build_dashboard.build(summary, os.path.join(HERE, "dashboard.html"))
    log(f"wrote {out}")
    if errors:
        log("errors:\n  " + "\n  ".join(errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
