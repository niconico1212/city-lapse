#!/usr/bin/env python3
"""Landmark models that go up over their real construction period (pilot: Tokyo).

Each landmark becomes a stack of simple prisms (a footprint ring, a base height and a top height)
that appear bottom to top between the construction start and the completion year, so a tower is
seen rising rather than popping in.

What is real and what is schematic
  real        position, total height and completion year (data/cities/<slug>.json, sourced);
              construction start and the key dimensions that fix the silhouette where
              data/models/<slug>.facts.json has them (sourced); for box-like towers the real
              footprint from PLATEAU (data/models/<slug>.footprints.json).
  schematic   everything else about the shape. The builders below turn a kind ("lattice tower",
              "pagoda", "gate", ...) plus those dimensions into a recognisable low-poly massing.
              Where a dimension was not sourced, a default proportion for that kind is used and the
              model says so in `shape_source`.

Output: public/data/<slug>-models.json (read by lib/extras.ts, decodeModels).
Usage: 09_landmark_models.py [slug]
"""
from __future__ import annotations

import json
import math
import re
import sys

from common import DATA, PUBLIC_DATA, load_cities, local_xy

ROOF = [74, 78, 84]        # tile grey for traditional roofs
STONE = [150, 146, 136]    # stone bases
DEFAULT_BUILD_YEARS = {"skyscraper": 4, "tower": 3, "bridge": 6, "stadium": 3}


def ring(cx, cy, hw, hd, rot_deg=0.0):
    """Clockwise rectangle (half-width hw along the rotated x axis, half-depth hd)."""
    a = math.radians(rot_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for ox, oy in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
        x, y = ox * hw, oy * hd
        out.append([round(cx + x * ca - y * sa, 2), round(cy + x * sa + y * ca, 2)])
    return out


def ngon(cx, cy, r, sides, rot_deg=0.0):
    out = []
    for k in range(sides):
        a = math.radians(rot_deg) - 2 * math.pi * k / sides  # decreasing angle = clockwise
        out.append([round(cx + r * math.cos(a), 2), round(cy + r * math.sin(a), 2)])
    return out


def scaled(poly, cx, cy, f):
    return [[round(cx + (x - cx) * f, 2), round(cy + (y - cy) * f, 2)] for x, y in poly]


def centroid(poly):
    return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)


def clockwise(poly):
    area = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))
    return poly if area < 0 else poly[::-1]


class Model:
    def __init__(self):
        self.parts = []

    def add(self, poly, z0, z1, color=None):
        if z1 - z0 > 0.05:
            part = {"p": poly, "z0": round(z0, 2), "z1": round(z1, 2)}
            if color:
                part["c"] = color
            self.parts.append(part)

    def column(self, poly, z0, z1, step, color=None):
        """A prism cut into slices so it can go up a few floors at a time."""
        n = max(1, math.ceil((z1 - z0) / step))
        for k in range(n):
            self.add(poly, z0 + (z1 - z0) * k / n, z0 + (z1 - z0) * (k + 1) / n, color)

    def taper(self, cx, cy, z0, z1, r0, r1, sides, step, rot=0.0, color=None, curve=1.0):
        """A tapering shaft as stacked prisms; curve > 1 narrows quickly near the base (lattice towers)."""
        n = max(1, math.ceil((z1 - z0) / step))
        for k in range(n):
            t = (k + 0.5) / n
            r = r1 + (r0 - r1) * (1 - t) ** curve
            self.add(ngon(cx, cy, r, sides, rot), z0 + (z1 - z0) * k / n, z0 + (z1 - z0) * (k + 1) / n,
                     color(k) if callable(color) else color)


def dims_of(facts):
    d = (facts or {}).get("dimensions") or {}
    return d if isinstance(d, dict) else {}


def num(d, key, default=None):
    v = d.get(key)
    return float(v) if isinstance(v, (int, float)) and v > 0 else default


def note_num(d, pattern, group=1):
    """A number quoted in the free-text notes of the facts file (sourced or marked DERIVED there)."""
    m = re.search(pattern, str(d.get("notes") or ""))
    return float(m.group(group)) if m else None


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] if len(h) == 6 else None


# ----------------------------------------------------------------------------- builders

def build_lattice_tower(lm, x, y, d, colors):
    """Four-legged lattice tower (Tokyo Tower type): square plan, sharply tapering, decks, mast."""
    H = lm["height_m"]
    m = Model()
    base = num(d, "base_width_m", H * 0.26) / 2
    mast_from = num(d, "mast_from_m", H * 0.76)
    decks = [k for k in (d.get("decks") or []) if isinstance(k, dict) and isinstance(k.get("z0_m"), (int, float))]
    bands = (lambda k: colors[k // 3 % len(colors)]) if len(colors) > 1 else (colors[0] if colors else None)
    m.taper(x, y, 0, mast_from, base, max(2.5, base * 0.07), 4, H / 42, rot=45, color=bands, curve=2.3)
    m.taper(x, y, mast_from, H, max(2.0, base * 0.05), 0.8, 4, H / 30, rot=45, color=bands)
    for k in decks:
        z0, z1 = float(k["z0_m"]), float(k.get("z1_m") or k["z0_m"] + 8)
        r = (max(2.5, base * 0.07) + (base - max(2.5, base * 0.07)) * (1 - z0 / mast_from) ** 2.3) * 1.45 + 3
        m.add(ngon(x, y, r, 4, 45), z0, max(z1, z0 + 6), colors[-1] if colors else None)
    return m, "four-legged lattice shaft with decks and mast"


def build_round_tower(lm, x, y, d, colors):
    """Tall broadcasting tower with a triangular base turning circular (Skytree type)."""
    H = lm["height_m"]
    m = Model()
    base = num(d, "base_width_m", H * 0.11)
    r0 = base / math.sqrt(3)                      # circumradius of the triangular base
    mast_from = num(d, "mast_from_m", H * 0.78)
    decks = [k for k in (d.get("decks") or []) if isinstance(k, dict) and isinstance(k.get("z0_m"), (int, float))]
    first_deck = min((float(k["z0_m"]) for k in decks), default=H * 0.54)
    round_at = note_num(d, r"circle at about (\d+)") or first_deck * 0.94
    c = colors[0] if colors else None
    # triangle at the base, becoming round by about half way to the first deck
    step = H / 60
    n = math.ceil(first_deck / step)
    for k in range(n):
        t = (k + 0.5) / n
        u = min(1.0, (t * first_deck) / round_at)   # 0 at the ground, 1 where the section is a circle
        sides = 3 if u < 0.2 else 6 if u < 0.45 else 12 if u < 0.75 else 24
        r = r0 * (1 - 0.62 * t ** 0.8)
        m.add(ngon(x, y, r, sides, 90), first_deck * k / n, first_deck * (k + 1) / n, c)
    top_r = r0 * 0.38
    z = first_deck
    for k in sorted(decks, key=lambda k: k["z0_m"]):
        z0, z1 = float(k["z0_m"]), float(k.get("z1_m") or k["z0_m"] + 12)
        if z0 > z:
            m.taper(x, y, z, z0, top_r, top_r * 0.9, 24, step, color=c)
        m.add(ngon(x, y, top_r * 1.75, 24), z0, max(z1, z0 + 8), c)
        z = max(z1, z0 + 8)
        top_r *= 0.8
    m.taper(x, y, z, mast_from, top_r, top_r * 0.6, 24, step, color=c)
    m.taper(x, y, mast_from, H, max(3.2, top_r * 0.45), 1.6, 12, H / 40, color=c)
    return m, "triangular base turning circular, observation decks, mast"


def build_skyscraper(lm, x, y, d, footprints):
    H = lm["height_m"]
    m = Model()
    roof = min(num(d, "roof_height_m", H * 0.96), H)
    fp = footprints[0] if footprints else None
    w, dp = num(d, "base_width_m"), num(d, "base_depth_m")
    if w and dp:
        tower, how = ring(x, y, w / 2, dp / 2), "plan dimensions from the cited source"
    elif fp and fp["area_m2"] <= 6500:
        tower, how = clockwise(fp["polygon"]), "real footprint (PLATEAU)"
    else:
        # the real footprint includes a podium: use a tower plate in proportion to the height
        side = min(max(H / 4.2, 34.0), 72.0)
        tower, how = ring(x, y, side / 2, side / 2.4), "tower plate assumed in proportion to height (footprint includes a podium)"
        if fp:
            m.add(clockwise(fp["polygon"]), 0, min(28.0, H * 0.12))
    cx, cy = centroid(tower)
    m.column(tower, 0, roof, max(8.0, H / 28))
    if H - roof > 0.5:
        m.column(scaled(tower, cx, cy, 0.45), roof, H, max(4.0, (H - roof) / 3))
    return m, f"extruded tower; {how}"


def build_twin_top(lm, x, y, d, footprints):
    """Tower that splits into two shafts above a given height (Tokyo Metropolitan Government No. 1)."""
    H = lm["height_m"]
    m = Model()
    split = num(d, "split_height_m", H * 0.62)
    fp = footprints[0] if footprints else None
    w = num(d, "base_width_m", 108.0)
    dp = num(d, "base_depth_m", 40.0)
    if fp and fp["area_m2"] <= 9000 and not num(d, "base_width_m"):
        body = clockwise(fp["polygon"])
        xs, ys = [p[0] for p in body], [p[1] for p in body]
        w, dp = max(xs) - min(xs), max(ys) - min(ys)
        cx, cy = centroid(body)
    else:
        cx, cy = x, y
        body = ring(cx, cy, w / 2, dp / 2)
    m.column(body, 0, split, H / 26)
    along_x = w >= dp
    off = (w if along_x else dp) * 0.29
    tw = (w if along_x else dp) * 0.19
    td = (dp if along_x else w) * 0.42
    for s in (-1, 1):
        ox, oy = (cx + s * off, cy) if along_x else (cx, cy + s * off)
        shaft = ring(ox, oy, tw, td) if along_x else ring(ox, oy, td, tw)
        m.column(shaft, split, H * 0.93, H / 26)
        m.column(scaled(shaft, ox, oy, 0.62), H * 0.93, H, H / 30)
    return m, "single body splitting into twin shafts"


def tiered(m, x, y, w, dp, z, tiers, tier_h, shrink, rot=0.0, wall=None):
    """Traditional timber massing: each tier is a body with a wider, thin roof slab over it."""
    for t in range(tiers):
        f = shrink ** t
        body_h = tier_h * 0.72
        m.add(ring(x, y, w * f / 2, dp * f / 2, rot), z, z + body_h, wall)
        m.add(ring(x, y, w * f / 2 * 1.32, dp * f / 2 * 1.32, rot), z + body_h, z + tier_h * 0.86, ROOF)
        m.add(ring(x, y, w * f / 2 * 0.7, dp * f / 2 * 0.7, rot), z + tier_h * 0.86, z + tier_h, ROOF)
        z += tier_h
    return z


def build_gate(lm, x, y, d):
    H = lm["height_m"]
    m = Model()
    w = num(d, "base_width_m", H * 1.3)
    dp = num(d, "base_depth_m", w * 0.45)
    tiers = int(num(d, "tiers", 2 if H >= 16 else 1))
    tiered(m, x, y, w, dp, 0, tiers, H / tiers, 0.86)
    return m, f"{tiers}-tier gate with roofs"


def build_pagoda(lm, x, y, d):
    H = lm["height_m"]
    m = Model()
    tiers = int(num(d, "tiers", 5))
    w = num(d, "base_width_m", H * 0.24)
    body_top = H * 0.7
    z = tiered(m, x, y, w, w, 0, tiers, body_top / tiers, 0.9)
    m.taper(x, y, z, H, w * 0.05 + 0.5, 0.35, 8, (H - z) / 4, color=[196, 164, 92])  # the finial
    return m, f"{tiers}-storey pagoda with finial"


def build_keep(lm, x, y, d, wall=None):
    H = lm["height_m"]
    m = Model()
    base_h = num(d, "stone_base_height_m") or note_num(d, r"x (\d+) m high") or H * 0.24
    w = num(d, "base_width_m") or note_num(d, r"1st tier is about ([\d.]+) x ([\d.]+) m") or H * 0.8
    dp = num(d, "base_depth_m") or note_num(d, r"1st tier is about ([\d.]+) x ([\d.]+) m", 2) or w * 0.88
    bw = note_num(d, r"measures (\d+) m east-west") or w * 1.12
    bd = note_num(d, r"x (\d+) m north-south") or dp * 1.12
    tiers = int(num(d, "tiers", 5))
    m.add(ring(x, y, bw / 2 * 1.08, bd / 2 * 1.08), 0, base_h * 0.5, STONE)
    m.add(ring(x, y, bw / 2, bd / 2), base_h * 0.5, base_h, STONE)
    tiered(m, x, y, w, dp, base_h, tiers, (H - base_h) / tiers, 0.84, wall=wall or [232, 228, 216])
    return m, f"stone base with a {tiers}-tier keep"


def build_diet(lm, x, y, d):
    H = lm["height_m"]
    m = Model()
    w = num(d, "base_width_m", 206.0)
    dp = num(d, "base_depth_m", 88.0)
    wing = num(d, "wing_height_m") or num(d, "roof_height_m") or H * 0.32
    c = [206, 200, 188]
    m.add(ring(x, y, w / 2, dp / 2), 0, wing, c)
    m.add(ring(x, y, w * 0.11, dp * 0.3), wing, H * 0.62, c)
    for k, f in enumerate((0.085, 0.065, 0.045, 0.022)):
        m.add(ring(x, y, w * f, w * f), H * (0.62 + 0.095 * k), H * (0.62 + 0.095 * (k + 1)), c)
    return m, "long wings with a stepped central tower"


def build_bridge(lm, x, y, d):
    H = lm["height_m"]
    m = Model()
    bearing = d.get("bearing_deg") or note_num(d, r"Bearing: about (\d+)")
    rot = 90.0 - float(bearing) if isinstance(bearing, (int, float)) else 0.0  # compass bearing -> math angle
    span = num(d, "main_span_m") or note_num(d, r"main span (\d+)") or H * 4.5
    length = num(d, "total_length_m") or note_num(d, r"Total length ([\d.]+)") or span * 1.4
    deck = num(d, "deck_height_m") or note_num(d, r"Clearance under the girder ([\d.]+)") or H * 0.4
    width = num(d, "base_width_m", 28.0)
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    c = [236, 236, 232]
    m.add(ring(x, y, length / 2, width / 2, rot), deck, deck + 6.0, c)
    for s in (-1, 1):
        tx, ty = x + s * span / 2 * ca, y + s * span / 2 * sa
        for side in (-1, 1):
            lx, ly = tx - side * (width / 2 - 1.5) * sa, ty + side * (width / 2 - 1.5) * ca
            m.column(ring(lx, ly, 3.2, 3.2, rot), 0, H, H / 8, c)
        m.add(ring(tx, ty, 3.0, width / 2, rot), H * 0.82, H * 0.86, c)
    how = "deck and two towers" + ("" if isinstance(bearing, (int, float)) else "; bearing not sourced, drawn east-west")
    return m, how


def build_default(lm, x, y, d):
    H = lm["height_m"]
    m = Model()
    side = min(max(H * 0.9, 20.0), 120.0)
    m.add(ring(x, y, side / 2, side / 2), 0, H * 0.7)
    m.add(ring(x, y, side * 0.3, side * 0.3), H * 0.7, H)
    return m, "two-step massing"


def build(lm, x, y, facts, footprints):
    d = dims_of(facts)
    name = lm["name"].lower()
    kind = lm.get("kind", "other")
    col = (facts or {}).get("color") or {}
    desc = str(col.get("description") or "").lower()
    colors = [c for c in (hex_rgb(h) for h in (col.get("hex") or []) if isinstance(h, str)) if c]
    if colors and kind == "tower" and "white" in desc and "band" in desc:
        colors = [colors[0], [244, 244, 240]]       # documented scheme: the colour and white, in bands
    if kind == "tower":
        if str(d.get("plan_shape", "")).lower().startswith("tri") or "skytree" in name:
            return build_round_tower(lm, x, y, d, colors), colors
        return build_lattice_tower(lm, x, y, d, colors), colors
    if kind == "skyscraper":
        if "metropolitan government" in name or num(d, "split_height_m"):
            return build_twin_top(lm, x, y, d, footprints), colors
        return build_skyscraper(lm, x, y, d, footprints), colors
    if kind == "gate":
        return build_gate(lm, x, y, d), colors
    if kind == "temple" and ("pagoda" in name or num(d, "tiers")):
        return build_pagoda(lm, x, y, d), colors
    if kind == "fort":
        return build_keep(lm, x, y, d, wall=[58, 56, 54] if "black" in desc else None), colors
    if kind == "bridge":
        return build_bridge(lm, x, y, d), colors
    if "diet" in name:
        return build_diet(lm, x, y, d), colors
    return build_default(lm, x, y, d), colors


def main():
    slug = sys.argv[1] if len(sys.argv) > 1 else "tokyo"
    cmeta = next(c for c in load_cities() if c["slug"] == slug)
    city = json.loads((DATA / "cities" / f"{slug}.json").read_text())
    lon0, lat0 = cmeta["center"]["lon"], cmeta["center"]["lat"]
    fpath = DATA / "models" / f"{slug}.facts.json"
    facts = {f["name"]: f for f in json.loads(fpath.read_text())["landmarks"]} if fpath.exists() else {}
    ppath = DATA / "models" / f"{slug}.footprints.json"
    foot = {f["name"]: f["footprints"] for f in json.loads(ppath.read_text())["landmarks"]} if ppath.exists() else {}
    models = []
    for lm in city["landmarks"]:
        x, y = (float(v) for v in local_xy(lm["lon"], lm["lat"], lon0, lat0))
        f = facts.get(lm["name"])
        (model, shape), colors = build(lm, x, y, f, foot.get(lm["name"], []))
        done = lm["year"]
        start = f.get("construction_start") if f else None
        assumed = not isinstance(start, int) or start >= done or done - start > 60
        if assumed:
            start = done - DEFAULT_BUILD_YEARS.get(lm.get("kind", ""), 2)
        H = lm["height_m"]
        for part in model.parts:
            # a part appears when construction reaches its base; the top is in place by the completion year
            part["y"] = round(start + (done - start) * min(1.0, part["z0"] / H), 2)
        sourced = [k for k in dims_of(f) if k != "notes"]
        models.append({
            "name": lm["name"], "construction_start": None if assumed else start, "completed": done,
            "demolished": lm.get("demolished_year"),
            "shape": shape,
            "shape_source": ("Schematic massing. " + (f"Dimensions used ({', '.join(sourced)}): {f.get('dimensions_source', '')}. "
                                                      if sourced else "No published dimensions used; default proportions for this kind. ")
                             + ("Construction start: " + str(f.get("construction_start_source", "")) if not assumed
                                else "Construction start not sourced; the model goes up over an assumed "
                                     f"{done - start} years before completion.")),
            "color": colors[0] if colors else None,
            "parts": model.parts,
        })
    out = {
        "slug": slug,
        "note": "Landmark models are schematic: position, height and completion year are the sourced values; shapes are "
                "simple massings built from published dimensions where available.",
        "models": models,
    }
    (PUBLIC_DATA / f"{slug}-models.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    for m in models:
        print(f"{m['name'][:40]:<42}{len(m['parts']):>4} parts  start={m['construction_start']}  {m['shape']}")


if __name__ == "__main__":
    main()
