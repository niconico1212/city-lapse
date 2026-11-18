#!/usr/bin/env python3
"""Validate data/cities/<slug>.json against the schema and accuracy rules.

Usage: validate_city.py <slug> [<slug> ...]   (no args = every city in data/cities.json)
Exit code 1 if any file has errors. Warnings do not fail.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = {"documented", "estimated", "reconstructed"}
KINDS = {"tower", "skyscraper", "temple", "mosque", "church", "palace", "fort", "gate", "monument",
         "bridge", "stadium", "other"}
END_YEAR = 2026


def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def check_point(errs, where, d, need_conf=True):
    src = d.get("source")
    if not isinstance(src, str) or len(src.strip()) < 8:
        errs.append(f"{where}: missing or empty source")
    if need_conf:
        c = d.get("confidence")
        if c not in CONF:
            errs.append(f"{where}: confidence must be one of {sorted(CONF)}, got {c!r}")
        if c == "reconstructed" and not d.get("note") and not d.get("detail"):
            errs.append(f"{where}: reconstructed values need a note giving the method")


def validate(slug, city_index, allow_post_1950=False):
    errs, warns = [], []
    path = ROOT / "data" / "cities" / f"{slug}.json"
    if not path.exists():
        return [f"{path} does not exist"], []
    try:
        d = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"], []
    meta = city_index.get(slug)
    if meta is None:
        errs.append(f"slug {slug!r} is not in data/cities.json")
        return errs, warns
    for k in ("slug", "name", "country", "start_year", "start_label", "start_source", "start_confidence",
              "historic_core", "population", "milestones", "landmarks", "footprint_epochs", "notes"):
        if k not in d:
            errs.append(f"missing key: {k}")
    if errs:
        return errs, warns
    if d["slug"] != slug:
        errs.append("slug does not match filename")
    if d["footprint_epochs"] != f"footprints/{slug}/":
        errs.append(f"footprint_epochs must be 'footprints/{slug}/'")
    sy = d["start_year"]
    if not isinstance(sy, int) or sy == 0 or sy > 1950 or sy < -6000:
        errs.append(f"start_year must be a non-zero integer year (negative = BCE), got {sy!r}")
        sy = -6000
    if d["start_confidence"] not in CONF:
        errs.append("start_confidence invalid")
    if not isinstance(d["start_source"], str) or len(d["start_source"]) < 8:
        errs.append("start_source missing")
    if not isinstance(d["notes"], str) or len(d["notes"]) < 80:
        errs.append("notes should describe gaps, caveats and methods (at least a few sentences)")
    clat, clon = meta["center"]["lat"], meta["center"]["lon"]

    hc = d["historic_core"]
    if not isinstance(hc, dict) or not all(k in hc for k in ("name", "lat", "lon", "source")):
        errs.append("historic_core needs name, lat, lon, source")
    else:
        dist = km(clat, clon, hc["lat"], hc["lon"])
        if dist > 25:
            errs.append(f"historic_core is {dist:.0f} km from the city centre; check coordinates")

    pop = d["population"]
    if not isinstance(pop, list):
        errs.append("population must be a list")
        pop = []
    last = None
    for i, p in enumerate(pop):
        w = f"population[{i}] (year {p.get('year')})"
        if not isinstance(p.get("year"), int) or p["year"] == 0:
            errs.append(f"{w}: year must be a non-zero integer")
            continue
        if not isinstance(p.get("value"), (int, float)) or p["value"] < 0:
            errs.append(f"{w}: value must be a non-negative number")
        if p["year"] < sy:
            errs.append(f"{w}: earlier than start_year {sy}")
        if p["year"] >= 1950 and not allow_post_1950:
            errs.append(f"{w}: 1950 onward comes from the UN series; remove it")
        if last is not None and p["year"] <= last:
            errs.append(f"{w}: years must be strictly increasing")
        last = p["year"]
        check_point(errs, w, p)
    pre = [p for p in pop if isinstance(p.get("year"), int) and p["year"] < 1950]
    if len(pre) < 3:
        warns.append(f"only {len(pre)} population points before 1950")

    ms = d["milestones"]
    if not isinstance(ms, list) or len(ms) < 6:
        errs.append("need at least 6 milestones")
        ms = ms if isinstance(ms, list) else []
    for i, m in enumerate(ms):
        w = f"milestones[{i}] ({m.get('title')!r})"
        if not isinstance(m.get("year"), int) or m["year"] == 0 or m["year"] > END_YEAR:
            errs.append(f"{w}: bad year {m.get('year')!r}")
        elif m["year"] < sy:
            errs.append(f"{w}: earlier than start_year")
        if not m.get("title") or len(m["title"]) > 70:
            errs.append(f"{w}: title missing or longer than 70 characters")
        if not m.get("detail"):
            errs.append(f"{w}: detail missing")
        check_point(errs, w, m)
    if ms and sorted(m.get("year", 0) for m in ms) != [m.get("year", 0) for m in ms]:
        errs.append("milestones must be in chronological order")

    lms = d["landmarks"]
    if not isinstance(lms, list) or len(lms) < 5:
        errs.append("need at least 5 landmarks")
        lms = lms if isinstance(lms, list) else []
    for i, l in enumerate(lms):
        w = f"landmarks[{i}] ({l.get('name')!r})"
        if not isinstance(l.get("year"), int) or l["year"] == 0 or l["year"] > END_YEAR:
            errs.append(f"{w}: bad year {l.get('year')!r}")
        h = l.get("height_m")
        if not isinstance(h, (int, float)) or not (1 <= h <= 1100):
            errs.append(f"{w}: height_m must be a number of metres between 1 and 1100, got {h!r}")
        if not isinstance(l.get("lat"), (int, float)) or not isinstance(l.get("lon"), (int, float)):
            errs.append(f"{w}: lat/lon missing")
        else:
            dist = km(clat, clon, l["lat"], l["lon"])
            if dist > 90:
                errs.append(f"{w}: {dist:.0f} km from the city centre; check coordinates")
            elif dist > 45:
                warns.append(f"{w}: {dist:.0f} km from the city centre")
        if l.get("kind") not in KINDS:
            errs.append(f"{w}: kind must be one of {sorted(KINDS)}")
        if "demolished_year" in l and (not isinstance(l["demolished_year"], int) or l["demolished_year"] <= l.get("year", 0)):
            errs.append(f"{w}: demolished_year must be an integer after year")
        check_point(errs, w, l)
    return errs, warns


def main():
    idx = {c["slug"]: c for c in json.loads((ROOT / "data" / "cities.json").read_text())["cities"]}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    allow_post = "--merged" in sys.argv
    slugs = args or list(idx)
    bad = 0
    for s in slugs:
        errs, warns = validate(s, idx, allow_post_1950=allow_post)
        status = "FAIL" if errs else "ok"
        print(f"[{status}] {s}" + (f"  ({len(warns)} warnings)" if warns else ""))
        for e in errs:
            print(f"    error: {e}")
        for w in warns:
            print(f"    warn:  {w}")
        bad += bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
