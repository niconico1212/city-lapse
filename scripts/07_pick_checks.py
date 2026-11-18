#!/usr/bin/env python3
"""Phase 7: draw the random sample of figures the independent verifier checks.

For every city, pick about 10 data points at random (seeded per city, so the draw is
reproducible and not left to the verifier's taste): the start year, then a mix of researched
population points, landmarks and milestones. UN-series points are not sampled; they are copied
from the UN workbooks by script and are checked mechanically by this script instead.

Writes data/verification/_sample.json. Verifiers write data/verification/<slug>.json.
"""
from __future__ import annotations

import json

from common import DATA, load_cities, rng_for

N = 10


def main():
    un = json.loads((DATA / "un_population.json").read_text())
    out = {}
    un_mismatch = 0
    for c in load_cities():
        slug = c["slug"]
        path = DATA / "cities" / f"{slug}.json"
        if not path.exists():
            continue
        city = json.loads(path.read_text())
        rng = rng_for(slug, "verification-sample")
        items = [{"kind": "start", "claim": f"start_year {city['start_year']}: {city['start_label']}",
                  "source": city["start_source"]}]
        pops = [p for p in city["population"] if "series" not in p]
        lms, mss = city["landmarks"], city["milestones"]
        want = {"population": 4, "landmark": 3, "milestone": 2}
        pools = {"population": list(range(len(pops))), "landmark": list(range(len(lms))),
                 "milestone": list(range(len(mss)))}
        picked = {k: [] for k in pools}
        for k, n in want.items():
            idx = pools[k]
            take = sorted(rng.choice(len(idx), size=min(n, len(idx)), replace=False).tolist()) if idx else []
            picked[k] = [idx[i] for i in take]
        # top up from whatever is left if a category was short
        short = N - 1 - sum(len(v) for v in picked.values())
        rest = [(k, i) for k in pools for i in pools[k] if i not in picked[k]]
        if short > 0 and rest:
            for j in rng.choice(len(rest), size=min(short, len(rest)), replace=False).tolist():
                picked[rest[j][0]].append(rest[j][1])
        for i in sorted(picked["population"]):
            p = pops[i]
            items.append({"kind": "population", "year": p["year"], "claim": f"population {p['value']:,} in {p['year']} ({p['confidence']})",
                          "source": p["source"]})
        for i in sorted(picked["landmark"]):
            l = lms[i]
            items.append({"kind": "landmark", "name": l["name"],
                          "claim": f"{l['name']}: completed {l['year']}, height {l['height_m']} m, at {l['lat']}, {l['lon']} ({l['confidence']})",
                          "source": l["source"]})
        for i in sorted(picked["milestone"]):
            m = mss[i]
            items.append({"kind": "milestone", "year": m["year"], "claim": f"{m['year']}: {m['title']}. {m['detail']}",
                          "source": m["source"]})
        out[slug] = items

        # mechanical check of the UN series against data/un_population.json
        w25 = {p["year"]: p["value"] for p in un["cities"][slug]["wup2025"]}
        w18 = {p["year"]: p["value"] for p in un["cities"][slug]["wup2018"]}
        for p in city["population"]:
            if p.get("series") == "UN-WUP-2025" and p["year"] in w25 and p["value"] != w25[p["year"]]:
                un_mismatch += 1
                print(f"UN mismatch {slug} {p['year']}")
            if p.get("series") == "UN-WUP-2018" and p["value"] != w18.get(p["year"]):
                un_mismatch += 1
                print(f"UN mismatch {slug} {p['year']}")
    vdir = DATA / "verification"
    vdir.mkdir(exist_ok=True)
    (vdir / "_sample.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"sampled {sum(len(v) for v in out.values())} figures across {len(out)} cities; UN-series mismatches: {un_mismatch}")


if __name__ == "__main__":
    main()
