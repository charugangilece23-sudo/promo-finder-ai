"""Invariant checker (Phase 8, architecture I1-I4).

Runs over the latest outputs/<run_id>/promos.json and exits non-zero on
any violation. Mirrors eval/check_invariants.py.
"""

from __future__ import annotations

import glob
import json
import os
import sys


def latest_run_dir() -> str | None:
    dirs = [d for d in glob.glob("outputs/*/") if os.path.isdir(d)]
    return sorted(dirs)[-1] if dirs else None


def check(promos_path: str) -> int:
    data = json.load(open(promos_path, encoding="utf-8"))
    promos = data.get("promos", [])
    errors = 0
    for p in promos:
        dur = p.get("total_duration_s", 0)
        if not (20.0 <= dur <= 60.0):
            print(f"DURATION FAIL {p.get('promo_id')}: {dur}")
            errors += 1
        for seg in p.get("segments", []):
            if seg.get("end_s", 0) <= seg.get("start_s", 0):
                print(f"END<=START {p.get('promo_id')}")
                errors += 1
            if seg.get("start_s", 0) < 0 or seg.get("end_s", 0) < 0:
                print(f"NEG TIME {p.get('promo_id')}")
                errors += 1
        seg_dur = sum(s.get("end_s", 0) - s.get("start_s", 0)
                      for s in p.get("segments", []))
        if abs(seg_dur - dur) > 0.01:
            print(f"DUR MISMATCH {p.get('promo_id')}: {seg_dur} vs {dur}")
            errors += 1
    tiers = {}
    for p in promos:
        tiers[p.get("tier", "?")] = tiers.get(p.get("tier", "?"), 0) + 1
    print(f"Total promos: {len(promos)}  Errors: {errors}")
    print(f"Tiers: {tiers}")
    print(f"Scores: {min(p['score'] for p in promos):.1f} - {max(p['score'] for p in promos):.1f}")
    return 1 if errors else 0


if __name__ == "__main__":
    run_dir = latest_run_dir()
    if not run_dir:
        print("No outputs run dir found")
        sys.exit(1)
    sys.exit(check(run_dir + "promos.json"))
