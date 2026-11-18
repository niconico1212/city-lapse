#!/usr/bin/env python3
"""Phase 4, step 1: download GHSL tiles and clip them to each city's urban centre.

For every city in data/cities.json:
  1. Find its urban centre polygon in GHS-UCDB R2024A (the polygon containing the city centre).
  2. Work out which GHSL 100 m Mollweide tiles cover it.
  3. Download GHS-BUILT-S (built-up surface) for the epochs 1975..2025 and GHS-BUILT-H
     (average net building height, 2018), caching tile zips under raw/ghsl/tiles/.
  4. Clip everything to the urban centre's bounding box (+2 km) and save
     raw/clips/<slug>.npz: S[epoch, row, col] in m2 of built surface per 100 m cell,
     H[row, col] in metres, mask[row, col] = inside the urban centre.
  5. Write the urban centre outline to data/footprints/<slug>/extent.geojson.

Fallback (logged in raw/clips/<slug>.json and docs/DATA_LOG.md): if a 100 m tile cannot be
downloaded after retries, the epoch is filled from the 1 km product resampled to 100 m and the
city's clip is flagged `resolution_fallback`. Nothing is ever synthesised.

Usage: 01_fetch_ghsl.py [slug ...] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyproj
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from shapely.geometry import Point, mapping
import shapely

from common import CELL, CLIPS, DATA, GHSL_BASE, GHSL_EPOCHS, GHSL_UCDB_CITATION, MOLLWEIDE, RAW, load_cities

TILE = 1_000_000.0
X0, Y0 = -18_041_000.0, 9_000_000.0
TILES_DIR = RAW / "ghsl" / "tiles"
UCDB = RAW / "ucdb" / "GHS_UCDB_GLOBE_R2024A.gpkg"
UCDB_LAYER = "GHS_UCDB_THEME_GENERAL_CHARACTERISTICS_GLOBE_R2024A"
BUFFER_M = 2_000.0


def layer_name(kind: str, epoch: int | None, res: int = 100) -> str:
    if kind == "S":
        return f"GHS_BUILT_S_E{epoch}_GLOBE_R2023A_54009_{res}"
    return f"GHS_BUILT_H_ANBH_E2018_GLOBE_R2023A_54009_{res}"


def tile_url(kind: str, epoch: int | None, r: int, c: int) -> str:
    name = layer_name(kind, epoch)
    product = "GHS_BUILT_S_GLOBE_R2023A" if kind == "S" else "GHS_BUILT_H_GLOBE_R2023A"
    return f"{GHSL_BASE}/{product}/{name}/V1-0/tiles/{name}_V1_0_R{r}_C{c}.zip"


def tiles_for_bounds(minx, miny, maxx, maxy):
    c0, c1 = int((minx - X0) // TILE) + 1, int((maxx - X0) // TILE) + 1
    r0, r1 = int((Y0 - maxy) // TILE) + 1, int((Y0 - miny) // TILE) + 1
    return [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


def fetch_tile(kind: str, epoch: int | None, r: int, c: int, retries: int = 4) -> Path | None:
    """Download and unzip one tile; return the .tif path, or None if the tile does not exist."""
    name = layer_name(kind, epoch)
    out_dir = TILES_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    tif = out_dir / f"{name}_V1_0_R{r}_C{c}.tif"
    missing = out_dir / f"R{r}_C{c}.missing"
    if tif.exists():
        return tif
    if missing.exists():
        return None
    url = tile_url(kind, epoch, r, c)
    zpath = out_dir / f"R{r}_C{c}.zip"
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=(20, 300)) as resp:
                if resp.status_code == 404:
                    missing.write_text(url)  # ocean / no-data tile: GHSL simply does not publish it
                    return None
                resp.raise_for_status()
                with open(zpath, "wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            with zipfile.ZipFile(zpath) as zf:
                member = next(m for m in zf.namelist() if m.endswith(".tif"))
                zf.extract(member, out_dir)
                (out_dir / member).rename(tif)
            zpath.unlink(missing_ok=True)
            return tif
        except Exception as exc:  # noqa: BLE001 - retry any network/zip failure
            zpath.unlink(missing_ok=True)
            wait = 2 ** (attempt + 1)
            print(f"  retry {attempt + 1}/{retries} for {url}: {exc} (sleep {wait}s)", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"could not download {url}")


def read_window(tifs: list[Path | None], bounds, shape, dtype, nodata_to=0):
    """Mosaic the given tiles into one array covering `bounds` (minx, miny, maxx, maxy)."""
    out = np.zeros(shape, dtype=dtype)
    minx, miny, maxx, maxy = bounds
    for tif in tifs:
        if tif is None:
            continue
        with rasterio.open(tif) as ds:
            ix0, iy0 = max(minx, ds.bounds.left), max(miny, ds.bounds.bottom)
            ix1, iy1 = min(maxx, ds.bounds.right), min(maxy, ds.bounds.top)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            win = from_bounds(ix0, iy0, ix1, iy1, ds.transform).round_offsets().round_lengths()
            arr = ds.read(1, window=win)
            if ds.nodata is not None:
                arr = np.where(arr == ds.nodata, nodata_to, arr)
            col = int(round((ix0 - minx) / CELL))
            row = int(round((maxy - iy1) / CELL))
            out[row:row + arr.shape[0], col:col + arr.shape[1]] = arr.astype(dtype)
    return out


def match_urban_centres(cities):
    g = gpd.read_file(UCDB, layer=UCDB_LAYER)
    g.columns = [c.replace("﻿", "") for c in g.columns]
    tr = pyproj.Transformer.from_crs("EPSG:4326", MOLLWEIDE, always_xy=True)
    out = {}
    for c in cities:
        p = Point(*tr.transform(c["center"]["lon"], c["center"]["lat"]))
        cand = [i for i in g.sindex.query(p.buffer(15_000)) if g.geometry.iloc[i].distance(p) < 15_000]
        if not cand:
            raise SystemExit(f"no urban centre near {c['slug']}")
        cand.sort(key=lambda i: -g["GC_POP_TOT_2025"].iloc[i])
        row = g.iloc[cand[0]]
        out[c["slug"]] = {
            "geometry": row.geometry,
            "uc_id": int(row["ID_UC_G0"]),
            "uc_name": str(row["GC_UCN_MAI_2025"]).replace("﻿", ""),
            "uc_area_km2": float(row["GC_UCA_KM2_2025"]),
            "uc_pop_2025": float(row["GC_POP_TOT_2025"]),
            "contains_centre": bool(row.geometry.contains(p)),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cities = [c for c in load_cities() if not args.slugs or c["slug"] in args.slugs]
    ucs = match_urban_centres(cities)
    CLIPS.mkdir(parents=True, exist_ok=True)

    # Plan: per-city snapped bounds and the tiles they need.
    plan, needed = {}, set()
    for c in cities:
        uc = ucs[c["slug"]]
        minx, miny, maxx, maxy = uc["geometry"].bounds
        minx = np.floor((minx - BUFFER_M) / CELL) * CELL
        miny = np.floor((miny - BUFFER_M) / CELL) * CELL
        maxx = np.ceil((maxx + BUFFER_M) / CELL) * CELL
        maxy = np.ceil((maxy + BUFFER_M) / CELL) * CELL
        tiles = tiles_for_bounds(minx, miny, maxx - 1, maxy - 1)
        plan[c["slug"]] = {"bounds": (minx, miny, maxx, maxy), "tiles": tiles}
        for rc in tiles:
            for e in GHSL_EPOCHS:
                needed.add(("S", e, *rc))
            needed.add(("H", None, *rc))
    print(f"{len(cities)} cities, {len({t[2:] for t in needed})} distinct tiles, {len(needed)} tile files", flush=True)

    # Download.
    paths, failed = {}, {}
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(fetch_tile, *t): t for t in sorted(needed, key=str)}
        for n, fut in enumerate(as_completed(futs), 1):
            t = futs[fut]
            try:
                paths[t] = fut.result()
            except Exception as exc:  # noqa: BLE001
                failed[t] = str(exc)
                paths[t] = None
            if n % 25 == 0 or n == len(futs):
                print(f"  tiles {n}/{len(futs)} ({len(failed)} failed)", flush=True)

    to_wgs = pyproj.Transformer.from_crs(MOLLWEIDE, "EPSG:4326", always_xy=True)
    for c in cities:
        slug = c["slug"]
        uc, pl = ucs[slug], plan[slug]
        out_npz = CLIPS / f"{slug}.npz"
        minx, miny, maxx, maxy = pl["bounds"]
        shape = (int(round((maxy - miny) / CELL)), int(round((maxx - minx) / CELL)))
        failures = [f"{k}{e or ''} R{r}_C{c2}: {failed[(k, e, r, c2)]}"
                    for (k, e, r, c2) in failed if (r, c2) in pl["tiles"]]
        S = np.stack([read_window([paths[("S", e, *rc)] for rc in pl["tiles"]], pl["bounds"], shape, np.uint16)
                      for e in GHSL_EPOCHS])
        H = read_window([paths[("H", None, *rc)] for rc in pl["tiles"]], pl["bounds"], shape, np.float32)
        tfm = rasterio.transform.from_origin(minx, maxy, CELL, CELL)
        mask = rasterize([(uc["geometry"], 1)], out_shape=shape, transform=tfm, fill=0, dtype="uint8").astype(bool)
        np.savez_compressed(out_npz, S=S, H=H, mask=mask)
        meta = {
            "slug": slug, "x0": minx, "y_top": maxy, "cell": CELL, "shape": shape, "epochs": GHSL_EPOCHS,
            "uc_id": uc["uc_id"], "uc_name": uc["uc_name"], "uc_area_km2": uc["uc_area_km2"],
            "uc_pop_2025": uc["uc_pop_2025"], "tiles": [f"R{r}_C{c2}" for r, c2 in pl["tiles"]],
            "resolution_m": 100, "download_failures": failures,
            "status": "partial" if failures else "ok",
        }
        (CLIPS / f"{slug}.json").write_text(json.dumps(meta, indent=1))

        # Urban centre outline, simplified, in WGS84.
        geom = shapely.transform(uc["geometry"].simplify(150), lambda xy: np.column_stack(to_wgs.transform(xy[:, 0], xy[:, 1])))
        fdir = DATA / "footprints" / slug
        fdir.mkdir(parents=True, exist_ok=True)
        (fdir / "extent.geojson").write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "slug": slug, "kind": "urban_centre_extent", "uc_id": uc["uc_id"], "uc_name": uc["uc_name"],
                    "area_km2": round(uc["uc_area_km2"], 1), "source": GHSL_UCDB_CITATION,
                    "confidence": "documented",
                },
                "geometry": json.loads(json.dumps(mapping(geom), default=float)),
            }],
        }, separators=(",", ":")).replace(".0,", ",") + "\n")
        built = (S[-1] > 0) & mask
        print(f"{slug:<18} {shape[1]}x{shape[0]} cells  uc={uc['uc_name']} {uc['uc_area_km2']:.0f} km2  "
              f"built2025={built.sum() / 100:.0f} km2  maxH={H[mask].max():.0f} m  {meta['status']}", flush=True)
    if failed:
        print(f"{len(failed)} tile downloads failed; affected cities are flagged partial", file=sys.stderr)


if __name__ == "__main__":
    main()
