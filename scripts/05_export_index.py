#!/usr/bin/env python3
"""Write public/data/cities.json: the slim city index the app's picker loads first.

Each city's status comes from its exported file: "ok", "partial" (flagged gaps, still playable),
or "missing" (no exported data; the picker shows it greyed out).
"""
from __future__ import annotations

import json

from common import DATA, PUBLIC_DATA


def main():
    src = json.loads((DATA / "cities.json").read_text())
    out = []
    for c in src["cities"]:
        meta_path = PUBLIC_DATA / f"{c['slug']}.json"
        status, start = "missing", None
        if meta_path.exists() and (PUBLIC_DATA / f"{c['slug']}.bin").exists():
            meta = json.loads(meta_path.read_text())
            status, start = meta["status"], meta["start_year"]
        out.append({
            "slug": c["slug"], "name": c["name"], "country": c["country"], "rank": c["rank"],
            "population_2025": c["population_2025"], "start_year": start, "status": status,
            "center": c["center"], "un_name": c["un_name"],
        })
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DATA / "cities.json").write_text(json.dumps(
        {"ranking_source": src["ranking_source"], "cities": out}, ensure_ascii=False, separators=(",", ":")) + "\n")
    counts = {s: sum(1 for c in out if c["status"] == s) for s in ("ok", "partial", "missing")}
    print(f"index written: {counts}")


if __name__ == "__main__":
    main()
