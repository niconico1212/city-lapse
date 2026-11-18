#!/usr/bin/env python3
"""Phase 4, step 2: per-cell entry years and footprint polygons for every epoch.

1975-2025 (GHSL, real):
  A 100 m cell is "in the footprint" at an epoch when GHS-BUILT-S reports at least TAU m2 of
  built surface in it. Its entry year is the first such epoch.

Before 1975 (reconstructed, per CLAUDE.md "Pre-1975 footprint method"):
  Start from the 1975 GHSL footprint and contract it backward toward the historic core.
    1. Rank every 1975 cell by a least-cost distance from the historic core. Travelling through
       densely built cells is cheap (dense = old), through sparse cells dearer, and across
       unbuilt gaps (water, parks) dearest, so growth follows built corridors instead of
       jumping bays and rivers. Strong secondary density peaks far from the core act as
       satellite towns that start growing once the main front is part-way to them.
    2. For every year Y from the start year to 1975, set the target footprint area
           A(Y) = A(1975) * [P(Y) / P(1975)] / m(Y)
       where P is the city's population series and m(Y) is how much denser cities were in
       year Y than in 1975 (era-typical density, see DENSITY_* below).
    3. The footprint at year Y is the A(Y) lowest-ranked cells. The footprint never shrinks:
       population losses (wars, plagues) show in the population counter, not as demolition.
  Everything produced this way is labelled `reconstructed`.

Outputs
  raw/clips/<slug>_recon.npz           entry_year per cell (float32, NaN = never built), inside mask
  data/footprints/<slug>/<year>.geojson  simplified footprint polygon per epoch
  data/footprints/<slug>/summary.json    areas, parameters and provenance (feeds docs/DATA_LOG.md)

Usage: 03_footprints.py [slug ...]
"""
from __future__ import annotations

import json
import math
import sys
import traceback

import numpy as np
import pyproj
import rasterio
import shapely
from rasterio.features import shapes
from scipy import ndimage as ndi
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from skimage.feature import peak_local_max
from skimage.graph import MCP_Geometric

from common import (CELL, CLIPS, DATA, GHSL_BUILT_S_CITATION, GHSL_EPOCHS, MOLLWEIDE, interp_log, load_cities,
                    merge_un, rng_for)

TAU = 500  # m2 of built surface in a 100 m cell (5 %) for the cell to count as built-up

# Era-typical density. Angel, Parent, Civco & Blei (2010), "The Persistent Decline in Urban
# Densities: Global and Historical Evidence of Sprawl" (Lincoln Institute of Land Policy working
# paper WP10SA1), report that built-up area densities in a global sample of 30 cities declined at
# a mean rate of about 1.5 % a year from a peak around 1890 to 2000. We apply that rate backward
# from 1975 to 1890 and hold density constant before 1890.
DENSITY_DECLINE_PER_YEAR = 0.015
DENSITY_PEAK_YEAR = 1890
DENSITY_CAP_PER_HA = 500.0  # persons per hectare of built-up cells; ceiling for whole-city density

RECON_YEARS = [-3000, -2000, -1500, -1000, -500, -250, 1, 250, 500, 750, 1000, 1100, 1200, 1300, 1400, 1500,
               1600, 1650, 1700, 1750, 1800, 1825, 1850, 1875, 1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970]

SATELLITE_ALPHA = 0.5       # satellite towns start when the main front is this fraction of the way there
SATELLITE_MIN_KM = 6.0
SATELLITE_MAX = 10

# The UN lists Guangzhou and Shenzhen separately but GHS-UCDB R2024A has them in one urban centre.
# The shared polygon is split by weighted distance to the two city centres so that each city's
# share of the area matches the land areas the UN publishes for them (4,542 and 1,459 km2).
SHARED_UC = {
    "guangzhou": ("shenzhen", 4542 / (4542 + 1459)),
    "shenzhen": ("guangzhou", 1459 / (4542 + 1459)),
}


def density_multiplier(years: np.ndarray) -> np.ndarray:
    return np.exp(DENSITY_DECLINE_PER_YEAR * (1975 - np.maximum(years, DENSITY_PEAK_YEAR)))


def rc_of(lon, lat, meta, tr):
    x, y = tr.transform(lon, lat)
    return int((meta["y_top"] - y) // CELL), int((x - meta["x0"]) // CELL)


def split_shared_uc(slug, mask, meta, cities_by_slug, tr):
    other, share = SHARED_UC[slug]
    rows, cols = np.indices(mask.shape)
    r0, c0 = rc_of(cities_by_slug[slug]["center"]["lon"], cities_by_slug[slug]["center"]["lat"], meta, tr)
    r1, c1 = rc_of(cities_by_slug[other]["center"]["lon"], cities_by_slug[other]["center"]["lat"], meta, tr)
    d_self = np.hypot(rows - r0, cols - c0)
    d_other = np.hypot(rows - r1, cols - c1)
    lo, hi = 0.05, 20.0
    for _ in range(40):  # bisection on the distance weight k so that our share of cells = `share`
        k = math.sqrt(lo * hi)
        frac = ((d_self < k * d_other) & mask).sum() / mask.sum()
        lo, hi = (k, hi) if frac < share else (lo, k)
    return mask & (d_self < k * d_other), k


def cost_surface(S75, built75, rng):
    dens = np.clip(S75 / 6000.0, 0, 1)
    cost = np.where(built75, 1.0 + 1.5 * (1.0 - dens), 8.0).astype(np.float32)
    noise = ndi.gaussian_filter(rng.standard_normal(S75.shape).astype(np.float32), 8)
    noise /= noise.std() + 1e-9
    return cost * np.exp(0.18 * noise)


def rank_cells(S75, built75, core_rc, slug):
    """Least-cost arrival 'time' from the historic core (plus satellite seeds) for every cell."""
    rng = rng_for(slug, "cost-noise")
    cost = cost_surface(S75, built75, rng)
    T, _ = MCP_Geometric(cost).find_costs([core_rc])
    dens = ndi.gaussian_filter(np.where(built75, S75, 0).astype(np.float32), 6)
    peaks = peak_local_max(dens, min_distance=50, threshold_rel=0.45, exclude_border=False)
    sats = []
    for r, c in peaks:
        dist_km = math.hypot(r - core_rc[0], c - core_rc[1]) * CELL / 1000
        if dist_km >= SATELLITE_MIN_KM:
            sats.append((float(dens[r, c]), int(r), int(c), dist_km))
    sats.sort(reverse=True)
    sats = sats[:SATELLITE_MAX]
    for _, r, c, _ in sats:
        Tj, _ = MCP_Geometric(cost).find_costs([(r, c)])
        T = np.minimum(T, SATELLITE_ALPHA * T[r, c] + Tj)
    return T, sats


def historical_population(city, un_city):
    """(years, values) of the series used to scale the footprint, ending at 1975."""
    pts = {p["year"]: p["value"] for p in city["population"] if "series" not in p and p["year"] < 1950}
    used_un = False
    for p in un_city["wup2018"]:
        if 1950 <= p["year"] <= 1975:
            pts[p["year"]] = p["value"]
            used_un = True
    note = "researched points before 1950 + UN WUP 2018 for 1950-1975"
    if not used_un:
        w25 = {p["year"]: p["value"] for p in un_city["wup2025"]}
        pts[1975] = w25[1975]
        note = ("researched points before 1950 + the UN WUP 2025 value for 1975 (this city is not in WUP 2018); "
                "the two use very different areas, so the pre-1975 footprint is especially uncertain")
    ys = sorted(pts)
    return ys, [max(pts[y], 1) for y in ys], note


def target_area(city, un_city, A75):
    """Yearly target footprint area in cells from start_year to 1975 (monotone)."""
    start = city["start_year"]
    years = np.arange(start, 1976)
    ys, vs, note = historical_population(city, un_city)
    P = interp_log(years, ys, vs)
    P75 = vs[ys.index(1975)]
    d75 = P75 / A75  # persons per built-up cell (= per hectare) in 1975
    dens = np.minimum(d75 * density_multiplier(years), max(DENSITY_CAP_PER_HA, d75))
    A = P / dens
    first = ys[0]
    if first > start:  # no population estimate before the first sourced point: ramp up from one cell
        a_first = A[years == first][0]
        ramp = np.exp(np.interp(years, [start, first], [0.0, math.log(max(a_first, 1.0))]))
        A = np.where(years < first, ramp, A)
    A = np.maximum.accumulate(np.clip(A, 1, A75))
    A[-1] = A75
    return years, A, {"population_basis": note, "density_1975_per_ha": round(d75, 1), "first_population_year": first,
                      "population_1975_used": P75}


def polygonize(mask, meta, to_wgs, coarse):
    """Binary mask -> simplified WGS84 MultiPolygon (as a GeoJSON geometry dict) and its area in km2."""
    if not mask.any():
        return None, 0.0
    m = ndi.binary_closing(mask, structure=np.ones((3, 3), bool))
    m |= mask
    cell = CELL
    tfm = rasterio.transform.from_origin(meta["x0"], meta["y_top"], CELL, CELL)
    if coarse > 1:  # very large cities: polygonise on a coarser grid to keep files small
        h, w = (m.shape[0] // coarse) * coarse, (m.shape[1] // coarse) * coarse
        m = m[:h, :w].reshape(h // coarse, coarse, w // coarse, coarse).mean(axis=(1, 3)) >= 0.5
        cell = CELL * coarse
        tfm = rasterio.transform.from_origin(meta["x0"], meta["y_top"], cell, cell)
    polys = [shape(g) for g, v in shapes(m.astype(np.uint8), mask=m, transform=tfm, connectivity=8) if v == 1]
    if not polys:
        # a handful of cells that vanish on the coarse grid: fall back to the fine grid
        return polygonize(mask, meta, to_wgs, 1) if coarse > 1 else (None, 0.0)
    min_area = 4 * cell * cell if len(polys) > 40 else 0
    keep = [p for p in polys if p.area >= min_area] or polys
    geom = unary_union(keep).simplify(cell * 1.2, preserve_topology=True)
    geom = shapely.transform(geom, lambda xy: np.column_stack(to_wgs.transform(xy[:, 0], xy[:, 1])))
    geom = shapely.set_precision(geom, 0.00001)
    return mapping(geom), float(mask.sum()) * CELL * CELL / 1e6


def process(slug, cities_by_slug, un):
    cpath = DATA / "cities" / f"{slug}.json"
    if not cpath.exists():
        return {"slug": slug, "status": "skipped", "reason": "no research file"}
    city = json.loads(cpath.read_text())
    city["population"] = merge_un(city, un)
    meta = json.loads((CLIPS / f"{slug}.json").read_text())
    clip = np.load(CLIPS / f"{slug}.npz")
    S, mask = clip["S"].astype(np.float32), clip["mask"]
    tr = pyproj.Transformer.from_crs("EPSG:4326", MOLLWEIDE, always_xy=True)
    to_wgs = pyproj.Transformer.from_crs(MOLLWEIDE, "EPSG:4326", always_xy=True)
    split_k = None
    if slug in SHARED_UC:
        mask, split_k = split_shared_uc(slug, mask, meta, cities_by_slug, tr)

    built = (S >= TAU) & mask[None]            # [epoch, row, col]
    built = np.maximum.accumulate(built, axis=0)
    built75 = built[0]
    A75 = int(built75.sum())
    if A75 < 10:
        raise RuntimeError("urban centre has almost no built-up cells in 1975")

    # Historic core cell, snapped to the nearest 1975 built-up cell.
    hc = city["historic_core"]
    r, c = rc_of(hc["lon"], hc["lat"], meta, tr)
    r, c = min(max(r, 0), mask.shape[0] - 1), min(max(c, 0), mask.shape[1] - 1)
    snap_m = 0.0
    if not built75[r, c]:
        dist, (ir, ic) = ndi.distance_transform_edt(~built75, return_indices=True)
        snap_m = float(dist[r, c] * CELL)
        r, c = int(ir[r, c]), int(ic[r, c])
    core_rc = (r, c)

    T, sats = rank_cells(S[0], built75, core_rc, slug)
    # Optional start site: where the earliest settlement stood, if that is not the historic core
    # (for example Baekje's Wiryeseong, 12 km from the centre of Joseon Seoul). Its cells are
    # ranked first, so the timeline opens there; growth then proceeds from the historic core.
    start_site_info = None
    ss = city.get("start_site")
    if ss:
        sr, sc = rc_of(ss["lon"], ss["lat"], meta, tr)
        if 0 <= sr < mask.shape[0] and 0 <= sc < mask.shape[1]:
            dist, (ir, ic) = ndi.distance_transform_edt(~built75, return_indices=True)
            snap = float(dist[sr, sc] * CELL)
            if snap <= 3000:
                sr, sc = int(ir[sr, sc]), int(ic[sr, sc])
                rows, cols = np.ogrid[:mask.shape[0], :mask.shape[1]]
                d2 = (rows - sr) ** 2 + (cols - sc) ** 2
                near = built75 & (d2 <= 3 ** 2)
                T = T.copy()
                T[near] = -1.0 + np.sqrt(d2[near]) * 1e-3
                start_site_info = {"name": ss["name"], "lat": ss["lat"], "lon": ss["lon"], "snapped_m": round(snap),
                                   "cells": int(near.sum())}
            else:
                start_site_info = {"name": ss["name"], "unused": f"no 1975 built-up cell within 3 km ({snap:.0f} m)"}
    flat = np.flatnonzero(built75)
    order = flat[np.argsort(T.ravel()[flat], kind="stable")]
    rank = np.empty(order.size, dtype=np.int64)
    rank[:] = np.arange(order.size)

    years, A, info = target_area(city, un["cities"][slug], A75)
    # entry year of the cell with rank r = first year whose target area exceeds r
    idx = np.searchsorted(A, rank, side="right")
    entry = np.full(mask.shape, np.nan, dtype=np.float32)
    entry.ravel()[order] = years[np.minimum(idx, len(years) - 1)]
    for k, e in enumerate(GHSL_EPOCHS[1:], start=1):
        new = built[k] & ~built[k - 1]
        entry[new] = e
    np.savez_compressed(CLIPS / f"{slug}_recon.npz", entry=entry, inside=mask)

    # Footprint polygons.
    fdir = DATA / "footprints" / slug
    fdir.mkdir(parents=True, exist_ok=True)
    for old in fdir.glob("*.geojson"):
        if old.name != "extent.geojson":
            old.unlink()
    total_cells = int(built[-1].sum())
    coarse = 1 if total_cells < 120_000 else 2 if total_cells < 300_000 else 3
    start = city["start_year"]
    recon_years = sorted({start, *[y for y in RECON_YEARS if start < y < 1975]})
    epochs_out = []
    method = ("1975 GHSL footprint contracted toward the historic core by least-cost distance; area scaled by "
              "population and era-typical density (Angel et al. 2010). See docs/DATA_LOG.md.")
    for y in recon_years + GHSL_EPOCHS:
        real = y >= 1975
        m = built[GHSL_EPOCHS.index(y)] if real else (entry <= y)
        geom, area = polygonize(m, meta, to_wgs, coarse)
        conf = ("estimated" if y == 2025 else "documented") if real else "reconstructed"
        props = {
            "slug": slug, "year": y, "area_km2": round(area, 2), "confidence": conf,
            "source": GHSL_BUILT_S_CITATION if real else "Reconstruction from the GHS-BUILT-S 1975 epoch (see method)",
            "method": ("GHS-BUILT-S 100 m cells with at least 5 % built surface inside the GHS-UCDB urban centre"
                       + ("; the 2025 epoch is a GHSL projection, not an observation" if y == 2025 else "")
                       ) if real else method,
            "simplified": True,
        }
        (fdir / f"{y}.geojson").write_text(json.dumps(
            {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": props, "geometry": geom}]},
            separators=(",", ":"), ensure_ascii=False) + "\n")
        epochs_out.append({"year": y, "area_km2": round(area, 2), "confidence": conf})

    summary = {
        "slug": slug, "status": meta.get("status", "ok"),
        "urban_centre": {"id": meta["uc_id"], "name": meta["uc_name"], "area_km2": round(meta["uc_area_km2"], 1)},
        "shared_urban_centre_split": ({"with": SHARED_UC[slug][0], "distance_weight": round(split_k, 3),
                                       "target_area_share": round(SHARED_UC[slug][1], 3)} if split_k else None),
        "threshold_m2_per_cell": TAU,
        "ghsl_resolution_m": meta.get("resolution_m", 100),
        "download_failures": meta.get("download_failures", []),
        "epochs": epochs_out,
        "reconstruction": {
            "historic_core": {"name": hc["name"], "lat": hc["lat"], "lon": hc["lon"], "snapped_m": round(snap_m)},
            "satellite_seeds": [{"distance_km": round(d, 1)} for _, _, _, d in sats],
            "start_site": start_site_info,
            "density_decline_per_year": DENSITY_DECLINE_PER_YEAR, "density_peak_year": DENSITY_PEAK_YEAR,
            "density_cap_per_ha": DENSITY_CAP_PER_HA, **info,
        },
    }
    (fdir / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    a = {e["year"]: e["area_km2"] for e in epochs_out}
    return {"slug": slug, "status": summary["status"], "cells75": A75, "cells25": total_cells,
            "start": start, "area_start": a[start], "area_1900": a.get(1900), "area_1975": a[1975],
            "area_2025": a[2025], "sats": len(sats), "snap_m": round(snap_m)}


def main():
    cities = load_cities()
    by_slug = {c["slug"]: c for c in cities}
    un = json.loads((DATA / "un_population.json").read_text())
    slugs = sys.argv[1:] or [c["slug"] for c in cities]
    failed = 0
    for slug in slugs:
        try:
            res = process(slug, by_slug, un)
            print(json.dumps(res), flush=True)
        except Exception as exc:  # noqa: BLE001 - one city must not stall the other 49
            failed += 1
            traceback.print_exc()
            print(json.dumps({"slug": slug, "status": "failed", "error": str(exc)}), flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
