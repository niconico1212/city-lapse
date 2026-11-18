#!/usr/bin/env python3
"""Merge the UN population series (1950 onward) into data/cities/<slug>.json.

Research agents supply population points before 1950 only. This step appends:
  1950-1970  UN WUP 2018 urban agglomeration estimates          (confidence: estimated)
  1975-2025  UN WUP 2025 Degree-of-Urbanisation city estimates  (confidence: estimated)
  2026       linear interpolation between WUP 2025's 2025 and 2030 (confidence: reconstructed)

It is idempotent: points carrying a "series" key are removed and re-added on every run, so
researched points are never touched.

Usage: 02_merge_population.py [slug ...]
"""
from __future__ import annotations

import json
import sys

from common import DATA, load_cities, merge_un


def main():
    un = json.loads((DATA / "un_population.json").read_text())
    slugs = sys.argv[1:] or [c["slug"] for c in load_cities()]
    for slug in slugs:
        path = DATA / "cities" / f"{slug}.json"
        if not path.exists():
            print(f"[skip] {slug}: no research file yet")
            continue
        city = json.loads(path.read_text())
        pts = merge_un(city, un)
        city["population"] = pts
        path.write_text(json.dumps(city, ensure_ascii=False, indent=2) + "\n")
        n_pre = sum(1 for p in pts if p["year"] < 1950)
        print(f"[ok] {slug}: {n_pre} researched + {len(pts) - n_pre} UN points")


if __name__ == "__main__":
    main()
