#!/usr/bin/env python3
"""Real building shapes for the satellite era (pilot: Tokyo).

From 1975 on, where an open building dataset exists, the app can show today's real building
footprints and measured heights instead of generated boxes when the viewer is zoomed in.

Tokyo source: PLATEAU (MLIT's open 3D city model), LOD0 footprints with measured heights for the
23 special wards, as flattened to GeoParquet by Pacific Spatial Solutions ("Flateau", CC BY 4.0).

What is real and what is not
  real        each building's outline and height (as surveyed for PLATEAU, 2023 edition)
  not known   when each building was built: PLATEAU's construction-year field is empty for Tokyo.
              Years are therefore assigned, in this order:
                1. documented  a matching Wikidata item with an inception/opening date (tall buildings)
                2. estimated   the GHSL epoch in which the building's 100 m cell first became built-up,
                               if that is 1980 or later
                3. generated   the cell was already built-up in 1975: low buildings (<= 20 m) appear in
                               a 1972-1978 wave, the moment the display switches from the reconstruction
                               to real shapes; taller ones get a seeded year between 1975 and 2020,
                               skewed later the taller they are
  so          a building always wears its present-day shape, including in years when something
              else stood on the lot.

Outputs
  public/data/<slug>-real/14-<x>-<y>.bin   buildings per z14 web-mercator tile (by centroid)
  public/data/<slug>-real.json             tile index, attribution, dating statistics
  data/models/<slug>.footprints.json       real footprints under each landmark (for the model builder)
  data/models/<slug>.dated.json            buildings dated from Wikidata, with the item ids
  raw/clips/<slug>_realcover.npz           100 m cells covered by real shapes (read by 04_buildings.py)

Usage: 08_real_buildings.py   (inputs: raw/plateau/*_building_lod0.parquet, raw/wd_<slug>.json)
"""
from __future__ import annotations

import glob
import json
import math
import shutil
import struct

import numpy as np
import pyarrow.parquet as pq
import pyproj
import shapely
from scipy import ndimage as ndi
from shapely.geometry import Point

from common import CELL, CLIPS, DATA, MOLLWEIDE, PUBLIC_DATA, RAW, load_cities, local_to_lonlat, local_xy, rng_for

SLUG = "tokyo"
TILE_Z = 14
XY_UNIT = 0.25          # metres per unit of the int16 vertex coordinates (relative to the tile centre)
MIN_AREA_M2 = 25.0      # sheds and garages below this are dropped
SIMPLIFY_M = 0.6
LOW_HEIGHT_M = 20.0
SWITCH_YEAR = 1975      # first GHSL epoch: where the display switches to real shapes
SOURCE = {
    "name": "PLATEAU 3D city model, Tokyo 23 wards (2023 edition), LOD0 building footprints with measured heights",
    "publisher": "Ministry of Land, Infrastructure, Transport and Tourism (MLIT), Japan",
    "url": "https://www.mlit.go.jp/plateau/",
    "derived": "Flateau GeoParquet by Pacific Spatial Solutions, https://source.coop/pacificspatial/flateau",
    "licence": "CC BY 4.0 (Flateau); PLATEAU site policy https://www.mlit.go.jp/plateau/site-policy/",
}


def tile_of(lon, lat, z=TILE_Z):
    n = 2 ** z
    x = np.floor((np.asarray(lon) + 180.0) / 360.0 * n).astype(np.int64)
    lat_r = np.radians(np.asarray(lat))
    y = np.floor((1.0 - np.arcsinh(np.tan(lat_r)) / math.pi) / 2.0 * n).astype(np.int64)
    return x, y


def tile_center(x, y, z=TILE_Z):
    n = 2 ** z
    lon = (x + 0.5) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / n))))
    return lon, lat


def load_ward(path, lon0, lat0):
    t = pq.read_table(path, columns=["GEOM", "measured_height", "cal_height_m", "storeys_above_ground", "cal_area_m2"])
    geom = shapely.from_wkb(t["GEOM"].to_numpy(zero_copy_only=False))
    h = t["measured_height"].to_numpy(zero_copy_only=False).astype(float)
    h2 = t["cal_height_m"].to_numpy(zero_copy_only=False).astype(float)
    st = t["storeys_above_ground"].to_numpy(zero_copy_only=False).astype(float)
    area = t["cal_area_m2"].to_numpy(zero_copy_only=False).astype(float)
    h = np.where(np.isfinite(h) & (h > 1.5), h, np.where(np.isfinite(h2) & (h2 > 1.5), h2, st * 3.3))
    ok = ~shapely.is_missing(geom) & np.isfinite(area) & (area >= MIN_AREA_M2)
    geom, h = geom[ok], h[ok]
    parts, idx = shapely.get_parts(geom, return_index=True)   # multipolygons -> one building per part
    h = h[idx]
    parts = shapely.transform(parts, lambda c: np.column_stack(local_xy(c[:, 0], c[:, 1], lon0, lat0)))
    parts = shapely.simplify(parts, SIMPLIFY_M, preserve_topology=True)
    keep = ~shapely.is_empty(parts) & (shapely.area(parts) >= MIN_AREA_M2)
    return parts[keep], h[keep]


def main():
    city_meta = next(c for c in load_cities() if c["slug"] == SLUG)
    city = json.loads((DATA / "cities" / f"{SLUG}.json").read_text())
    lon0, lat0 = city_meta["center"]["lon"], city_meta["center"]["lat"]
    polys, heights = [], []
    for f in sorted(glob.glob(str(RAW / "plateau" / "*_building_lod0.parquet"))):
        p, h = load_ward(f, lon0, lat0)
        polys.append(p)
        heights.append(h)
        print(f"  {f.split('/')[-1][:24]:<26}{len(p):>8}", flush=True)
    polys = np.concatenate(polys)
    h = np.concatenate(heights)
    n0 = len(polys)

    # Present-day height fallback for the few buildings with none: the GHSL cell height.
    meta = json.loads((CLIPS / f"{SLUG}.json").read_text())
    clip = np.load(CLIPS / f"{SLUG}.npz")
    recon = np.load(CLIPS / f"{SLUG}_recon.npz")
    cen = shapely.centroid(polys)
    cx, cy = shapely.get_x(cen), shapely.get_y(cen)
    clon, clat = local_to_lonlat(cx, cy, lon0, lat0)
    to_moll = pyproj.Transformer.from_crs("EPSG:4326", MOLLWEIDE, always_xy=True)
    mx, my = to_moll.transform(clon, clat)
    rows = np.clip(((meta["y_top"] - my) // CELL).astype(int), 0, clip["H"].shape[0] - 1)
    cols = np.clip(((mx - meta["x0"]) // CELL).astype(int), 0, clip["H"].shape[1] - 1)
    cell_h = clip["H"][rows, cols]
    no_h = ~np.isfinite(h) | (h < 1.5)
    h = np.where(no_h, np.maximum(cell_h, 4.0), h)
    h = np.clip(h, 2.0, 700.0)
    entry = recon["entry"][rows, cols].astype(float)

    # --- landmarks: the model replaces the real building on its site; keep that footprint for the model
    lm_out, drop = [], np.zeros(len(polys), bool)
    tree = shapely.STRtree(polys)
    for lm in city["landmarks"]:
        if lm.get("demolished_year"):
            continue
        lx, ly = local_xy(lm["lon"], lm["lat"], lon0, lat0)
        pt = Point(float(lx), float(ly))
        cand = tree.query(pt.buffer(60.0))
        hit = [int(i) for i in cand if polys[i].distance(pt) <= 8.0
               or (lm["height_m"] >= 100 and polys[i].distance(pt) <= 40.0 and h[i] >= 0.5 * lm["height_m"])]
        for i in hit:
            drop[i] = True
        hit.sort(key=lambda i: -polys[i].area)
        lm_out.append({
            "name": lm["name"],
            "footprints": [{"polygon": [[round(float(a), 2), round(float(b), 2)] for a, b in np.asarray(polys[i].exterior.coords)[:-1]],
                            "plateau_height_m": round(float(h[i]), 1), "area_m2": round(float(polys[i].area))}
                           for i in hit[:6]],
        })
    (DATA / "models").mkdir(exist_ok=True)
    (DATA / "models" / f"{SLUG}.footprints.json").write_text(json.dumps(
        {"slug": SLUG, "source": SOURCE, "units": "metres east/north of the city centre", "landmarks": lm_out},
        ensure_ascii=False, indent=1) + "\n")

    # --- years
    rng = rng_for(SLUG, "real-buildings")
    n = len(polys)
    year = np.empty(n)
    method = np.zeros(n, np.uint8)  # 0 generated, 1 GHSL epoch, 2 documented
    late = np.isfinite(entry) & (entry >= 1976)
    year[late] = entry[late] - 5.0 * rng.random(late.sum())
    method[late] = 1
    low = ~late & (h <= LOW_HEIGHT_M)
    year[low] = SWITCH_YEAR - 3.0 + 6.0 * rng.random(low.sum())
    tall = ~late & ~low
    u = rng.random(tall.sum()) ** (1.0 / (1.0 + h[tall] / 60.0))
    year[tall] = SWITCH_YEAR + 45.0 * u

    dated = []
    wd_path = RAW / f"wd_{SLUG}.json"
    if wd_path.exists():
        items = {}
        for r in json.loads(wd_path.read_text())["results"]["bindings"]:
            qid = r["b"]["value"].rsplit("/", 1)[-1]
            ys = [int(r[k]["value"][:4]) for k in ("inc", "open") if k in r and r[k]["value"][:4].isdigit()]
            if not ys:
                continue
            lon, lat = (float(v) for v in r["coord"]["value"][6:-1].split())
            it = items.setdefault(qid, {"qid": qid, "name": r["bLabel"]["value"], "years": [], "h": 0.0, "lon": lon, "lat": lat})
            it["years"] += ys
            it["h"] = max(it["h"], float(r["h"]["value"]))
        for it in items.values():
            y = min(it["years"])
            if not (1900 <= y <= 2026) or not (60 <= it["h"] <= 400):
                continue
            px, py = local_xy(it["lon"], it["lat"], lon0, lat0)
            pt = Point(float(px), float(py))
            cand = [int(i) for i in tree.query(pt.buffer(70.0)) if not drop[i] and polys[i].distance(pt) <= 60.0
                    and 0.6 * it["h"] <= h[i] <= 1.4 * it["h"]]
            if not cand:
                continue
            i = min(cand, key=lambda k: polys[k].distance(pt))
            year[i], method[i] = y, 2
            dated.append({"name": it["name"], "wikidata": it["qid"], "year": y, "wikidata_height_m": it["h"],
                          "plateau_height_m": round(float(h[i]), 1)})
    (DATA / "models" / f"{SLUG}.dated.json").write_text(json.dumps(
        {"slug": SLUG, "source": "Wikidata (CC0): inception (P571) or official opening (P1619), matched to the PLATEAU "
                                  "footprint at the item's coordinates with a height within 40 %",
         "buildings": sorted(dated, key=lambda d: d["year"])}, ensure_ascii=False, indent=1) + "\n")

    keep = ~drop
    polys, h, year, method, cx, cy, clon, clat = (a[keep] for a in (polys, h, year, method, cx, cy, clon, clat))
    rows, cols = rows[keep], cols[keep]
    n = len(polys)

    # --- coverage mask for the generator (cells that have real shapes)
    cover = np.zeros(clip["H"].shape, bool)
    cover[rows, cols] = True
    cover = ndi.binary_closing(ndi.binary_dilation(cover, iterations=1), iterations=2)
    np.savez_compressed(CLIPS / f"{SLUG}_realcover.npz", cover=cover)

    # --- rings: open, clockwise, as flat arrays
    rings = shapely.get_exterior_ring(polys)
    nv_closed = shapely.get_num_points(rings)
    coords, ridx = shapely.get_coordinates(rings, return_index=True)
    ccw = shapely.is_ccw(rings)
    start = np.concatenate([[0], np.cumsum(nv_closed)[:-1]])
    pos = np.arange(len(coords)) - start[ridx]
    last = pos == nv_closed[ridx] - 1
    coords, ridx, pos = coords[~last], ridx[~last], pos[~last]
    nv = nv_closed - 1
    newpos = np.where(ccw[ridx], nv[ridx] - 1 - pos, pos)
    order = np.lexsort((newpos, ridx))
    coords = coords[order]
    too_many = nv > 255
    if too_many.any():
        print(f"  dropping {int(too_many.sum())} buildings with more than 255 vertices")

    tx, ty = tile_of(clon, clat)
    out_dir = PUBLIC_DATA / f"{SLUG}-real"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    vstart = np.concatenate([[0], np.cumsum(nv)[:-1]])
    key = tx * 100_000 + ty
    tiles, total_bytes = {}, 0
    for k in np.unique(key):
        sel = np.flatnonzero((key == k) & ~too_many)
        if not len(sel):
            continue
        x, y = int(k // 100_000), int(k % 100_000)
        tlon, tlat = tile_center(x, y)
        ox, oy = local_xy(tlon, tlat, lon0, lat0)
        sel = sel[np.argsort(year[sel], kind="stable")]
        vidx = np.concatenate([np.arange(vstart[i], vstart[i] + nv[i]) for i in sel])
        xy = np.round((coords[vidx] - [ox, oy]) / XY_UNIT)
        if np.abs(xy).max() > 32000:
            raise RuntimeError(f"tile {x}/{y}: vertex out of int16 range")
        with open(out_dir / f"{TILE_Z}-{x}-{y}.bin", "wb") as fh:
            fh.write(b"CLT1")
            fh.write(struct.pack("<IIff", len(sel), len(vidx), float(ox), float(oy)))
            fh.write(xy.astype("<i2").tobytes())
            fh.write(np.clip(np.round(h[sel] * 10), 20, 65535).astype("<u2").tobytes())
            fh.write(np.floor(year[sel]).astype("<i2").tobytes())
            fh.write(nv[sel].astype("u1").tobytes())
            fh.write(method[sel].astype("u1").tobytes())
            size = fh.tell()
        total_bytes += size
        tiles[f"{x}/{y}"] = {"n": int(len(sel)), "bytes": size}

    kept = ~too_many
    stats = {
        "buildings": int(kept.sum()), "source_buildings": int(n0), "tiles": len(tiles), "bytes": total_bytes,
        "dated_documented": int((method[kept] == 2).sum()), "dated_ghsl_epoch": int((method[kept] == 1).sum()),
        "dated_generated": int((method[kept] == 0).sum()),
        "over_100m": int((h[kept] > 100).sum()),
    }
    (PUBLIC_DATA / f"{SLUG}-real.json").write_text(json.dumps({
        "slug": SLUG, "zoom": TILE_Z, "xy_unit": XY_UNIT, "switch_year": SWITCH_YEAR, "source": SOURCE,
        "dating": {
            "documented": "Wikidata inception or opening date for a matched tall building",
            "estimated": "GHSL epoch in which the building's 100 m cell first became built-up (1980 or later)",
            "generated": "cell already built-up in 1975: low buildings appear around 1975, taller ones get a seeded "
                         "year between 1975 and 2020, later the taller they are",
        },
        "stats": stats, "tiles": tiles,
    }, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
