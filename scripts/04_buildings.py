#!/usr/bin/env python3
"""Phase 5: procedural building generation and export of compact per-city files.

What is real and what is generated (the "honest procedural fill" of CLAUDE.md):
  real       where the built-up footprint is at each epoch (GHS-BUILT-S, reconstructed before 1975),
             how much of each cell is built on, the present-day average building height of each
             cell (GHS-BUILT-H, 2018), and every landmark's position, height and year.
  generated  the individual generic buildings: their exact outline, orientation, the split of a
             cell into lots, the height of each building around the cell average, and the years
             in which low early buildings are replaced by taller ones.

Rules (CLAUDE.md, "Procedural building generation"):
  - Seeded RNG per city, so every rebuild is byte-identical.
  - year_built = the epoch in which the building's cell first enters the footprint, plus jitter.
  - Heights are capped by era (ERA_CAP) and calibrated to GHS-BUILT-H for the present.
  - Cells are redeveloped: a building that ends up taller than its era allowed starts low and is
    replaced later, so the core densifies vertically.
  - Landmarks are placed at their real coordinates and heights and are never generated.
  - Budget: about 50-150k building instances per city. Detail is spent where the built volume is:
    the core gets individual 100 m cells split into lots, the periphery is merged into 200/400 m blocks.

Outputs
  public/data/<slug>.bin    one 15-byte record per building instance (struct of arrays, see LAYOUT)
  public/data/<slug>.json   everything the app shows for the city (data, sources, camera path)

Usage: 04_buildings.py [slug ...]
"""
from __future__ import annotations

import heapq
import json
import math
import struct
import sys
import traceback

import numpy as np
import pyproj
from scipy import ndimage as ndi

from common import (CELL, CLIPS, DATA, END_YEAR, GHSL_BUILT_H_CITATION, GHSL_BUILT_S_CITATION, GHSL_EPOCHS,
                    GHSL_UCDB_CITATION, MOLLWEIDE, PUBLIC_DATA, load_cities, local_xy, merge_un, rng_for)

TARGET_INSTANCES = 115_000
MAX_INSTANCES = 145_000
MIN_UNIT_BUDGET = 20_000
NO_END = 32767
FLAG_LANDMARK = 1
FLAG_COVERED = 2       # stands where real building shapes exist (hidden when those are on screen)
FLAG_GROUND_ONLY = 4   # carries a ground patch but no building (the stylised fabric stands on it)

# Stylised era fabric (an artist's impression, for cities switched on in data/extras.json):
# cells built up before FABRIC_BEFORE are drawn as rows of low roofed houses until the cell is
# modernised, in a seeded year between FABRIC_MOD_FROM and FABRIC_MOD_TO.
FABRIC_BEFORE = 1900
FABRIC_MOD_FROM, FABRIC_MOD_PEAK, FABRIC_MOD_TO = 1900, 1930, 1965
FABRIC_LAYOUT = [("x", "<i2"), ("y", "<i2"), ("y0", "<i2"), ("y1", "<i2"), ("len", "u1"), ("wid", "u1"),
                 ("rot", "u1"), ("h", "u1"), ("kind", "u1")]
FABRIC_XY_UNIT, FABRIC_LW_UNIT, FABRIC_H_UNIT = 1.0, 0.25, 0.1

# Upper bound on the height of a generic (non-landmark) building by year, in metres.
# "Almost nothing over 30 m before 1900 unless the building is a landmark."
ERA_CAP = [(-10000, 10.0), (1700, 10.0), (1800, 12.0), (1880, 20.0), (1900, 30.0), (1930, 60.0), (1960, 110.0),
           (1980, 200.0), (2000, 450.0), (2100, 450.0)]
_CAP_Y = np.array([y for y, _ in ERA_CAP], float)
_CAP_H = np.array([h for _, h in ERA_CAP], float)

# Schematic landmark massing: nested boxes (width fraction, height fraction). Height, position and
# year are real; the outline is a stand-in so a tower reads as a tower and a temple as a temple.
LANDMARK_SHAPES = {
    "skyscraper": ([(1.0, 0.72), (0.72, 0.92), (0.3, 1.0)], lambda h: min(max(h / 6.5, 22), 75)),
    "tower": ([(1.0, 0.12), (0.42, 0.55), (0.16, 1.0)], lambda h: min(max(h / 5.0, 14), 95)),
    "temple": ([(1.0, 0.45), (0.5, 0.75), (0.2, 1.0)], lambda h: min(max(h * 1.1, 24), 110)),
    "mosque": ([(1.0, 0.4), (0.55, 0.7), (0.12, 1.0)], lambda h: min(max(h * 1.1, 28), 120)),
    "church": ([(1.0, 0.45), (0.45, 0.75), (0.16, 1.0)], lambda h: min(max(h * 0.9, 24), 110)),
    "palace": ([(1.0, 0.6), (0.5, 1.0)], lambda h: min(max(h * 4.0, 60), 300)),
    "fort": ([(1.0, 0.5), (0.45, 1.0)], lambda h: min(max(h * 4.0, 60), 300)),
    "gate": ([(1.0, 0.7), (0.6, 1.0)], lambda h: min(max(h * 0.8, 12), 60)),
    "monument": ([(1.0, 0.25), (0.45, 0.8), (0.2, 1.0)], lambda h: min(max(h * 0.4, 10), 60)),
    "bridge": ([(1.0, 1.0)], lambda h: min(max(h * 0.25, 12), 40)),
    "stadium": ([(1.0, 0.8), (0.9, 1.0)], lambda h: min(max(h * 4.0, 120), 280)),
    "other": ([(1.0, 0.7), (0.6, 1.0)], lambda h: min(max(h * 0.9, 20), 120)),
}

LAYOUT = [("x", "<i2"), ("y", "<i2"), ("y0", "<i2"), ("y1", "<i2"), ("h", "<u2"), ("w", "u1"), ("d", "u1"),
          ("rot", "u1"), ("flags", "u1"), ("g", "u1")]
WD_UNIT = 2.0  # metres per unit of w/d
GROUND_UNIT = 2.0  # metres per unit of g, the side of the ground patch a building stands on (0 = none)


def era_cap(year):
    return np.interp(year, _CAP_Y, _CAP_H)


def first_year_allowing(height: float) -> float:
    """Earliest year whose era cap reaches `height`."""
    if height <= _CAP_H[0]:
        return -10000.0
    return float(np.interp(min(height, _CAP_H[-1]), _CAP_H[1:], _CAP_Y[1:]))


# ----------------------------------------------------------------------------- level of detail

def choose_units(rr, cc, vol_w, s25, budget):
    """Split the built cells into units (400 m blocks, 200 m blocks, 100 m cells, quarter-cell lots).

    Greedy: repeatedly split the unit holding the most (proximity-weighted) built volume until the
    budget is spent, so every unit ends up representing a similar amount of city.
    Returns a list of (level, member cell indices, lot index or -1).
    """
    n = len(rr)
    order4 = np.lexsort((cc // 4, rr // 4))
    key4 = (rr[order4] // 4).astype(np.int64) * 100_000 + cc[order4] // 4
    bounds = np.flatnonzero(np.diff(key4)) + 1
    groups4 = np.split(order4, bounds)
    heap, count = [], 0
    for g in groups4:
        heapq.heappush(heap, (-float(vol_w[g].sum()), count, 4, g))
        count += 1
    units, n_units = [], len(heap)
    while heap:
        negp, _, level, g = heapq.heappop(heap)
        if n_units >= budget or level == 0:
            units.append((level, g, -1))
            continue
        if level == 1:
            i = int(g[0])
            if s25[i] >= 2400 and n_units + 3 <= budget:  # enough built surface for four separate lots
                for lot in range(4):
                    units.append((0, g, lot))
                n_units += 3
            else:
                units.append((1, g, -1))
            continue
        half = level // 2
        keys = (rr[g] // half).astype(np.int64) * 100_000 + cc[g] // half
        uniq, inv = np.unique(keys, return_inverse=True)
        if len(uniq) == 1 and half >= 1:
            heapq.heappush(heap, (negp, count, half, g))
            count += 1
            continue
        if n_units + len(uniq) - 1 > budget:
            units.append((level, g, -1))
            continue
        for k in range(len(uniq)):
            sub = g[inv == k]
            heapq.heappush(heap, (-float(vol_w[sub].sum()), count, half, sub))
            count += 1
        n_units += len(uniq) - 1
    return units


# ----------------------------------------------------------------------------- generation

def cell_fill_year(frac, entry, s_ep, rng):
    """Year at which a cell's built surface first reaches `frac` of its 2025 value.

    Before 1975 the surface is assumed to grow linearly from the cell's entry year to its 1975
    value; from 1975 on it follows the GHSL epochs, with the year drawn uniformly inside the
    five-year step in which the threshold is crossed.
    """
    s25 = max(s_ep[-1], 1.0)
    target = frac * s25
    if entry < 1975 and s_ep[0] >= target:
        return entry + (1975 - entry) * (target / max(s_ep[0], 1.0))
    k = int(np.searchsorted(s_ep, target, side="left"))
    k = min(max(k, 1), len(GHSL_EPOCHS) - 1)
    return GHSL_EPOCHS[k] - 5 * rng.random()


def height_generations(y0, hf, rng):
    """[(year, height), ...]: a building's successive rebuilds, ending at its present height hf."""
    cap0 = float(era_cap(y0))
    if hf <= cap0 * 1.1:
        return [(y0, hf)]
    gens = [(y0, max(3.0, min(hf, cap0 * (0.5 + 0.5 * rng.random()))))]
    while gens[-1][1] < hf * 0.9 and len(gens) < 3:
        t, hcur = gens[-1]
        goal = hf if len(gens) == 2 else min(hf, hcur * 1.8)
        lo = max(t + 15.0, first_year_allowing(goal))
        hi = 2023.0
        if lo >= hi:
            break
        y = lo + (hi - lo) * rng.random()
        h = hf if (len(gens) == 2 or float(era_cap(y)) >= hf) else min(hf, float(era_cap(y)) * (0.65 + 0.35 * rng.random()))
        if h <= hcur * 1.05:
            h = hf
            y = max(y, min(first_year_allowing(hf), 2023.0))
        gens.append((y, h))
    if gens[-1][1] < hf * 0.9:  # the present is calibrated to GHS-BUILT-H, so the last rebuild reaches hf
        y = max(gens[-1][0] + 5.0, min(first_year_allowing(hf), 2023.0))
        if y > gens[-1][0] and y <= 2024:
            gens.append((y, hf))
        else:
            gens[-1] = (gens[-1][0], hf)
    return gens


def landmark_instances(lm, x, y, rng):
    kind = lm.get("kind", "other")
    tiers, base_fn = LANDMARK_SHAPES.get(kind, LANDMARK_SHAPES["other"])
    h = float(lm["height_m"])
    base = base_fn(h)
    y1 = lm.get("demolished_year", NO_END)
    rot = rng.random() * 90.0 if kind in ("skyscraper", "tower") else 0.0
    out = []
    for wf, hf in tiers:
        side = max(base * wf, 4.0)
        depth = side * (0.35 if kind == "bridge" else 1.0)
        out.append((x, y, lm["year"], y1, h * hf, side, depth, rot, FLAG_LANDMARK, 0.0))
    return out, base


def generate(slug, city, cmeta, meta, clip, recon, unit_budget, extras=None):
    extras = extras or {}
    rng = rng_for(slug, "buildings")
    S = clip["S"].astype(np.float32)
    H = clip["H"].astype(np.float32)
    entry_grid, inside = recon["entry"], recon["inside"]
    sel = inside & np.isfinite(entry_grid)
    rr, cc = np.nonzero(sel)
    n = len(rr)
    s_ep = np.maximum.accumulate(S[:, rr, cc], axis=0)  # [epoch, cell]
    s25 = np.maximum(s_ep[-1], 1.0)
    entry = entry_grid[rr, cc].astype(np.float64)

    # Present-day height per cell from GHS-BUILT-H (ANBH, 2018). Cells with no height (built after
    # 2018, or missed) take the smoothed height of their neighbourhood, else the city median.
    valid = (H > 2.0) & sel
    med = float(np.median(H[valid])) if valid.any() else 6.0
    num = ndi.gaussian_filter(np.where(valid, H, 0.0), 4)
    den = ndi.gaussian_filter(valid.astype(np.float32), 4)
    smooth = np.where(den > 0.05, num / np.maximum(den, 1e-6), med)
    h_cell = np.where(valid, H, smooth)[rr, cc].astype(np.float64)
    h_cell = np.clip(h_cell, 3.0, None)

    # Local metric coordinates of every cell centre.
    lon0, lat0 = cmeta["center"]["lon"], cmeta["center"]["lat"]
    to_wgs = pyproj.Transformer.from_crs(MOLLWEIDE, "EPSG:4326", always_xy=True)
    mx = meta["x0"] + (cc + 0.5) * CELL
    my = meta["y_top"] - (rr + 0.5) * CELL
    lon, lat = to_wgs.transform(mx, my)
    x, y = local_xy(lon, lat, lon0, lat0)

    hc = city["historic_core"]
    hx, hy = local_xy(hc["lon"], hc["lat"], lon0, lat0)
    d_core_km = np.hypot(x - hx, y - hy) / 1000.0
    vol_w = s25 * h_cell * (1.0 + 3.0 * np.exp(-d_core_km / 6.0))

    # Street-grid orientation: a smooth random field, so neighbouring buildings line up.
    ang = ndi.gaussian_filter(rng.standard_normal(sel.shape).astype(np.float32), 14)
    ang = (ang / (ang.std() + 1e-9)) * 35.0
    theta_cell = ang[rr, cc].astype(np.float64)

    # Optional layers (data/extras.json)
    covered = None
    cover_path = CLIPS / f"{slug}_realcover.npz"
    if extras.get("real_shapes") and cover_path.exists():
        covered = np.load(cover_path)["cover"][rr, cc]
    fabric_cell = mod_year = None
    if extras.get("era_fabric"):
        frng = rng_for(slug, "fabric")
        fabric_cell = entry < FABRIC_BEFORE
        mod_year = frng.triangular(FABRIC_MOD_FROM, FABRIC_MOD_PEAK, FABRIC_MOD_TO, size=n)

    units = choose_units(rr, cc, vol_w, s25, unit_budget)
    recs = []  # (x, y, y0, y1, h, w, d, rot, flags, ground side)
    start = city["start_year"]
    lot_dx = np.array([-25.0, 25.0, -25.0, 25.0])
    lot_dy = np.array([-25.0, -25.0, 25.0, 25.0])
    lot_cache = {}
    for level, g, lot in units:
        if level == 0:
            i = int(g[0])
            if i not in lot_cache:
                w_area = rng.dirichlet(np.full(4, 3.0))
                w_h = np.exp(rng.normal(0, 0.45, 4))
                if h_cell[i] >= 25:
                    w_h[rng.integers(4)] *= 1.6 + rng.random()  # one tower among lower neighbours
                w_h *= 1.0 / float((w_area * w_h).sum())          # keep the cell's mean height
                fracs = (np.argsort(rng.random(4)) + 0.15 + 0.5 * rng.random(4)) / 4.0
                lot_cache[i] = (w_area, w_h, fracs)
            w_area, w_h, fracs = lot_cache[i]
            th = theta_cell[i] + rng.normal(0, 3.0)
            ct, st = math.cos(math.radians(th)), math.sin(math.radians(th))
            bx = x[i] + lot_dx[lot] * ct - lot_dy[lot] * st
            by = y[i] + lot_dx[lot] * st + lot_dy[lot] * ct
            area = min(max(s25[i] * w_area[lot], 90.0), 0.8 * 2500.0)
            hf = float(np.clip(h_cell[i] * w_h[lot], 3.0, 420.0))
            y0 = cell_fill_year(float(fracs[lot]), entry[i], s_ep[:, i], rng)
            ground = 50.0
        else:
            w8 = s25[g]
            tot = float(w8.sum())
            bx, by = float(x[g].mean()), float(y[g].mean())
            area = min(max(tot, 90.0), 0.82 * len(g) * CELL * CELL)
            hf = float(np.clip((h_cell[g] * w8).sum() / tot * math.exp(rng.normal(0, 0.2)), 3.0, 420.0))
            th = float(theta_cell[g[0]]) + rng.normal(0, 3.0)
            ground = math.sqrt(len(g)) * CELL  # the built-up cells this unit stands for
            if len(g) == 1:
                e = float(entry[g[0]])
            else:  # block: built-surface-weighted median entry year of its cells
                o = np.argsort(entry[g])
                cw = np.cumsum(w8[o])
                e = float(entry[g][o][np.searchsorted(cw, 0.5 * tot)])
            if e >= 1975:
                y0 = e - 5.0 * rng.random()
            else:
                y0 = e + rng.normal(0, max(0.5, min(0.03 * (1975 - e), 8.0)))
        y0 = float(min(max(y0, start), 2025))
        q = 0.55 + 0.45 * rng.random()
        wdt = math.sqrt(area / q)
        dpt = area / wdt
        ground_th = th
        if rng.random() < 0.3:
            wdt, dpt = dpt, wdt
        i0 = int(g[0])
        flag = FLAG_COVERED if covered is not None and covered[g].mean() >= 0.5 else 0
        if fabric_cell is not None and (fabric_cell[i0] or y0 < FABRIC_BEFORE):
            # The stylised fabric stands here until the cell is modernised: the ground patch starts at
            # the entry year, the generated boxes only at the modernisation year.
            recs.append((bx, by, y0, y0 + 1, 0.3, 2.0, 2.0, ground_th, FLAG_GROUND_ONLY, ground))
            ground = 0.0
            y0 = max(y0, float(mod_year[i0]))
        gens = height_generations(y0, hf, rng)
        for k, (gy, gh) in enumerate(gens):
            g_end = gens[k + 1][0] if k + 1 < len(gens) else NO_END
            # only the first generation carries the ground patch, which then stays for good
            recs.append((bx, by, gy, g_end, gh, wdt, dpt, ground_th, flag, ground if k == 0 else 0.0))

    arr = np.array(recs, dtype=np.float64) if recs else np.zeros((0, 10))

    # Landmarks: real position, height and year. Generic buildings on the same spot give way.
    lm_out = []
    lm_recs = []
    lrng = rng_for(slug, "landmarks")
    for lm in city["landmarks"]:
        lx, ly = local_xy(lm["lon"], lm["lat"], lon0, lat0)
        inst, base = landmark_instances(lm, float(lx), float(ly), lrng)
        if not extras.get("models"):      # with models on, scripts/09_landmark_models.py draws the landmark
            lm_recs.extend(inst)
        lm_out.append({**lm, "x": round(float(lx), 1), "y": round(float(ly), 1)})
        if len(arr):
            near = np.hypot(arr[:, 0] - lx, arr[:, 1] - ly) < (base * 0.6 + 0.5 * np.maximum(arr[:, 5], arr[:, 6]))
            y_lm = lm["year"]
            y_gone = lm.get("demolished_year", NO_END)
            before = near & (arr[:, 2] < y_lm)
            arr[before, 3] = np.minimum(arr[before, 3], y_lm)           # earlier buildings are cleared
            during = near & (arr[:, 2] >= y_lm) & (arr[:, 2] < y_gone)
            arr = arr[~during]
    if lm_recs:
        arr = np.vstack([arr, np.array(lm_recs, dtype=np.float64)])
    fabric = None
    if fabric_cell is not None:
        fabric = generate_fabric(slug, x, y, entry, mod_year, fabric_cell, theta_cell, s_ep[0], start)
    return arr, lm_out, {"cells": int(n), "units": len(units),
                         "median_height_m": round(med, 1), "lot_cells": len(lot_cache)}, fabric


def generate_fabric(slug, x, y, entry, mod_year, fabric_cell, theta_cell, s75, start):
    """Rows of low roofed houses for cells built up before FABRIC_BEFORE. Entirely generated.

    Per 100 m cell: five rows of three lots along the local street orientation, each holding one
    long roof (a row house), now and then a larger hall or a small white storehouse, with lanes
    between the rows. How many lots are filled follows how densely the cell was built in 1975. Each house appears between the cell's
    entry year and a few decades later and stands until the cell's modernisation year.
    Returns rows of (x, y, y0, y1, length, width, rotation_deg, eave_height, kind).
    """
    rng = rng_for(slug, "fabric-houses")
    out = []
    dens = np.clip(s75 / 6000.0, 0.0, 1.0)
    for i in np.flatnonzero(fabric_cell):
        th = float(theta_cell[i])
        ct, st = math.cos(math.radians(th)), math.sin(math.radians(th))
        fill = 0.55 + 0.42 * float(dens[i])
        span = max(2.0, min(70.0, 0.5 * (FABRIC_BEFORE - entry[i])))
        for r in range(5):
            for c in range(3):
                if rng.random() > fill:
                    continue
                u = (c - 1) * 33.0 + rng.normal(0, 1.5)
                v = (r - 2) * 19.5 + rng.normal(0, 1.0)
                roll = rng.random()
                if roll < 0.035:     # hall: temple, shrine or residence
                    kind, length, width, eave = 1, 22 + 9 * rng.random(), 14 + 4 * rng.random(), 6.0 + 3.0 * rng.random()
                elif roll < 0.10:    # storehouse
                    kind, length, width, eave = 2, 9 + 4 * rng.random(), 7 + 2 * rng.random(), 5.0 + 1.5 * rng.random()
                else:                # row house
                    kind, length, width = 0, 24 + 7 * rng.random(), 10.5 + 3.5 * rng.random()
                    eave = 3.2 + 1.2 * rng.random() if rng.random() < 0.7 else 5.4 + 1.2 * rng.random()
                rot = th + rng.normal(0, 1.5)
                y0 = max(float(start), entry[i] + span * rng.random() ** 2)
                y1 = float(mod_year[i]) + rng.normal(0, 4.0)
                if y1 <= y0 + 2:
                    continue
                out.append((x[i] + u * ct - v * st, y[i] + u * st + v * ct, y0, y1, length, width, rot, eave, kind))
    return np.array(out, dtype=np.float64) if out else np.zeros((0, 9))


def write_fabric(path, fab):
    order = np.argsort(fab[:, 2], kind="stable")
    fab = fab[order]
    cols = {
        "x": np.round(fab[:, 0] / FABRIC_XY_UNIT).astype("<i2"), "y": np.round(fab[:, 1] / FABRIC_XY_UNIT).astype("<i2"),
        "y0": np.clip(np.floor(fab[:, 2]), -32000, 2026).astype("<i2"),
        "y1": np.clip(np.floor(fab[:, 3]), -32000, NO_END).astype("<i2"),
        "len": np.clip(np.round(fab[:, 4] / FABRIC_LW_UNIT), 1, 255).astype("u1"),
        "wid": np.clip(np.round(fab[:, 5] / FABRIC_LW_UNIT), 1, 255).astype("u1"),
        "rot": (np.round((fab[:, 6] % 180.0) / 180.0 * 256.0) % 256).astype("u1"),
        "h": np.clip(np.round(fab[:, 7] / FABRIC_H_UNIT), 1, 255).astype("u1"),
        "kind": fab[:, 8].astype("u1"),
    }
    with open(path, "wb") as fh:
        fh.write(b"CLF1")
        fh.write(struct.pack("<I", len(fab)))
        for name, _ in FABRIC_LAYOUT:
            fh.write(cols[name].tobytes())
    return path.stat().st_size


CAMERA_MAX_R = 14_000.0   # the auto camera never pulls back further than this (metres)
CAMERA_CORE_R = 5_000.0   # ... and pushes in to about this by 2026, to watch the skyline rise
FABRIC_CAMERA_ZOOM = 0.55    # with stylised fabric, frame this fraction of the early city's radius
CAMERA_CORE_R_REAL = 2_400.0  # closer where real building shapes exist, so they can be read


def camera_path(arr, city, hx, hy, core_r=CAMERA_CORE_R, fabric=None):
    """Per-year view target for the auto camera: centre and radius of what is worth looking at.

    Up to 1975 it follows the spreading footprint (centroid, and the radius holding 65 % of the
    built area, capped at CAMERA_MAX_R). From 1975 the footprint grows slowly and the story is
    vertical, so the camera eases in on the tallest part of the city.
    """
    start = city["start_year"]
    years = sorted({start, *[y for y in (-2000, -1000, -500, 1, 500, 1000, 1200, 1400, 1500, 1600, 1700, 1750,
                                          1800, 1850, 1875, 1900, 1920, 1940, 1950, 1960, 1970)
                             if start < y], *GHSL_EPOCHS, END_YEAR})
    generic = arr[(arr[:, 8].astype(int) & (FLAG_LANDMARK | FLAG_GROUND_ONLY)) == 0]
    if fabric is not None and len(fabric):
        # the stylised houses are what stands in the early city: count them as buildings (x, y, y0, y1, w, d)
        houses = np.zeros((len(fabric), generic.shape[1]))
        houses[:, [0, 1, 2, 3]] = fabric[:, [0, 1, 2, 3]]
        houses[:, 5], houses[:, 6] = fabric[:, 4], fabric[:, 5]
        generic = np.vstack([generic, houses])
    # where the tall buildings are today: volume-weighted centroid of the tallest 1 % (plus landmarks)
    now = arr[arr[:, 3] > END_YEAR]
    tx, ty = hx, hy
    if len(now) > 50:
        cut = np.quantile(now[:, 4], 0.99)
        tall = now[now[:, 4] >= cut]
        wgt = tall[:, 4] * tall[:, 5] * tall[:, 6]
        tx, ty = float(np.average(tall[:, 0], weights=wgt)), float(np.average(tall[:, 1], weights=wgt))
        d = np.hypot(tall[:, 0] - tx, tall[:, 1] - ty)
        near = tall[d <= max(np.quantile(d, 0.6), 1500.0)]   # drop far-flung outliers, then recentre
        wn = near[:, 4] * near[:, 5] * near[:, 6]
        tx, ty = float(np.average(near[:, 0], weights=wn)), float(np.average(near[:, 1], weights=wn))
    out = []
    for yr in years:
        alive = (generic[:, 2] <= yr) & (generic[:, 3] > yr)
        if alive.sum() < 3:
            out.append({"year": yr, "x": round(hx), "y": round(hy), "r": 700})
            continue
        a = generic[alive]
        wgt = a[:, 5] * a[:, 6]
        cx, cy = float(np.average(a[:, 0], weights=wgt)), float(np.average(a[:, 1], weights=wgt))
        dist = np.hypot(a[:, 0] - cx, a[:, 1] - cy)
        o = np.argsort(dist)
        cw = np.cumsum(wgt[o])
        r = float(dist[o][np.searchsorted(cw, 0.65 * cw[-1])])
        if fabric is not None and yr < FABRIC_BEFORE:
            r *= FABRIC_CAMERA_ZOOM   # stay close enough to read the roofs; the city spreads past the frame
        r = min(max(r, 700.0), CAMERA_MAX_R)
        # keep the historic core in frame while the city is still small
        off = math.hypot(cx - hx, cy - hy)
        if off > 0.35 * r:
            k = 0.35 * r / off
            cx, cy = hx + (cx - hx) * k, hy + (cy - hy) * k
        if yr > 1975:
            f = min(1.0, (yr - 1975) / 45.0)
            f = f * f * (3 - 2 * f)
            cx, cy = cx + (tx - cx) * f, cy + (ty - cy) * f
            r = math.exp(math.log(r) * (1 - f) + math.log(min(r, core_r)) * f)
        out.append({"year": yr, "x": round(cx), "y": round(cy), "r": round(r)})
    return out


def write_bin(path, arr):
    n = len(arr)
    order = np.lexsort((arr[:, 0], arr[:, 2]))  # by year built: lets the app upload once and filter on the GPU
    arr = arr[order]
    extent = float(np.abs(arr[:, :2]).max()) if n else 1.0
    xy_scale = max(0.5, math.ceil(extent / 32000.0 * 2) / 2)
    cols = {
        "x": np.round(arr[:, 0] / xy_scale).astype("<i2"),
        "y": np.round(arr[:, 1] / xy_scale).astype("<i2"),
        "y0": np.clip(np.floor(arr[:, 2]), -32000, 2026).astype("<i2"),
        "y1": np.clip(np.floor(arr[:, 3]), -32000, NO_END).astype("<i2"),
        "h": np.clip(np.round(arr[:, 4] * 10), 20, 65535).astype("<u2"),
        "w": np.clip(np.round(arr[:, 5] / WD_UNIT), 1, 255).astype("u1"),
        "d": np.clip(np.round(arr[:, 6] / WD_UNIT), 1, 255).astype("u1"),
        "rot": (np.round((arr[:, 7] % 180.0) / 180.0 * 256.0) % 256).astype("u1"),
        "flags": arr[:, 8].astype("u1"),
        "g": np.clip(np.round(arr[:, 9] / GROUND_UNIT), 0, 255).astype("u1"),
    }
    with open(path, "wb") as fh:
        fh.write(b"CLB1")
        fh.write(struct.pack("<I", n))
        for name, _ in LAYOUT:
            fh.write(cols[name].tobytes())
    return xy_scale, path.stat().st_size


def process(slug, cmeta, un):
    cpath = DATA / "cities" / f"{slug}.json"
    if not cpath.exists():
        return {"slug": slug, "status": "skipped", "reason": "no research file"}
    city = json.loads(cpath.read_text())
    city["population"] = merge_un(city, un)
    meta = json.loads((CLIPS / f"{slug}.json").read_text())
    clip = np.load(CLIPS / f"{slug}.npz")
    recon = np.load(CLIPS / f"{slug}_recon.npz")
    summary = json.loads((DATA / "footprints" / slug / "summary.json").read_text())

    extras_path = DATA / "extras.json"
    extras = json.loads(extras_path.read_text()).get(slug, {}) if extras_path.exists() else {}
    budget = 90_000
    for _ in range(5):
        arr, lms, stats, fabric = generate(slug, city, cmeta, meta, clip, recon, budget, extras)
        if len(arr) <= MAX_INSTANCES or budget <= MIN_UNIT_BUDGET:
            break
        budget = max(MIN_UNIT_BUDGET, int(budget * TARGET_INSTANCES / len(arr)))
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    xy_scale, nbytes = write_bin(PUBLIC_DATA / f"{slug}.bin", arr)
    extras_out = {}
    if fabric is not None and len(fabric):
        fbytes = write_fabric(PUBLIC_DATA / f"{slug}-fabric.bin", fabric)
        extras_out["fabric"] = {
            "file": f"{slug}-fabric.bin", "count": int(len(fabric)), "bytes": fbytes,
            "layout": [name for name, _ in FABRIC_LAYOUT], "xy_unit": FABRIC_XY_UNIT, "lw_unit": FABRIC_LW_UNIT,
            "h_unit": FABRIC_H_UNIT, "before": FABRIC_BEFORE,
            "note": "Artist's impression. Generated rows of low roofed houses for cells the reconstruction puts "
                    f"inside the city before {FABRIC_BEFORE}; not a record of real buildings.",
        }
    if extras.get("real_shapes") and (PUBLIC_DATA / f"{slug}-real.json").exists():
        extras_out["real"] = {"index": f"{slug}-real.json", "dir": f"{slug}-real"}
    if extras.get("models"):
        extras_out["models"] = {"file": f"{slug}-models.json"}

    lon0, lat0 = cmeta["center"]["lon"], cmeta["center"]["lat"]
    hx, hy = local_xy(city["historic_core"]["lon"], city["historic_core"]["lat"], lon0, lat0)
    generic = arr[(arr[:, 8].astype(int) & (FLAG_LANDMARK | FLAG_GROUND_ONLY)) == 0]
    pre1950 = [p for p in city["population"] if p["year"] < 1950]
    reasons = list(summary.get("download_failures", []))
    if len(pre1950) < 3:
        reasons.append(f"only {len(pre1950)} sourced population points before 1950")
    if len(city["landmarks"]) < 3:
        reasons.append(f"only {len(city['landmarks'])} landmarks with a sourced height")
    if "wup2018" in un["cities"][slug] and not un["cities"][slug]["wup2018"]:
        reasons.append("not listed in UN WUP 2018, so there is no UN series for 1950-1970")
    status = "partial" if (reasons or summary.get("status") == "partial" or city.get("status") == "partial") else "ok"
    if city.get("status_reason"):
        reasons.append(city["status_reason"])
    out = {
        "slug": slug, "name": city["name"], "country": city["country"], "rank": cmeta["rank"],
        "un_name": cmeta["un_name"], "population_2025": cmeta["population_2025"],
        "status": status, "status_reasons": reasons,
        "start_year": city["start_year"], "start_label": city["start_label"],
        "start_source": city["start_source"], "start_confidence": city["start_confidence"],
        "end_year": END_YEAR,
        "center": cmeta["center"], "historic_core": city["historic_core"],
        "population": city["population"], "milestones": city["milestones"], "landmarks": lms,
        "notes": city["notes"],
        "footprint": {
            "epochs": summary["epochs"], "urban_centre": summary["urban_centre"],
            "shared_urban_centre_split": summary.get("shared_urban_centre_split"),
            "reconstruction": summary["reconstruction"], "threshold_m2_per_cell": summary["threshold_m2_per_cell"],
            "sources": {"built_surface": GHSL_BUILT_S_CITATION, "building_height": GHSL_BUILT_H_CITATION,
                        "extent": GHSL_UCDB_CITATION},
        },
        "buildings": {
            "file": f"{slug}.bin", "count": int(len(arr)), "bytes": nbytes, "xy_scale": xy_scale,
            "wd_unit": WD_UNIT, "ground_unit": GROUND_UNIT, "layout": [name for name, _ in LAYOUT],
            "generic": int(len(generic)), "landmark_parts": int((arr[:, 8].astype(int) & FLAG_LANDMARK).sum()),
            "max_generic_height_m": round(float(generic[:, 4].max()), 1) if len(generic) else 0,
            **stats,
        },
        "extras": extras_out,
        "camera": camera_path(arr, city, float(hx), float(hy),
                              CAMERA_CORE_R_REAL if "real" in extras_out else CAMERA_CORE_R,
                              fabric if "fabric" in extras_out else None),
    }
    (PUBLIC_DATA / f"{slug}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"slug": slug, "status": status, "instances": int(len(arr)), "units": stats["units"],
            "cells": stats["cells"], "lot_cells": stats["lot_cells"], "kb": round(nbytes / 1024),
            "xy_scale": xy_scale, "budget": budget, "max_h": out["buildings"]["max_generic_height_m"]}


def main():
    cities = load_cities()
    by_slug = {c["slug"]: c for c in cities}
    un = json.loads((DATA / "un_population.json").read_text())
    slugs = sys.argv[1:] or [c["slug"] for c in cities]
    failed = 0
    for slug in slugs:
        try:
            print(json.dumps(process(slug, by_slug[slug], un)), flush=True)
        except Exception as exc:  # noqa: BLE001 - one city must not stall the other 49
            failed += 1
            traceback.print_exc()
            print(json.dumps({"slug": slug, "status": "failed", "error": str(exc)}), flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
