"""Shared helpers for the data pipeline (paths, city list, projections, seeded RNG)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
DATA = ROOT / "data"
PUBLIC_DATA = ROOT / "public" / "data"
CLIPS = RAW / "clips"

END_YEAR = 2026
GHSL_EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]
MOLLWEIDE = "ESRI:54009"
CELL = 100.0  # GHSL grid cell size in metres (Mollweide)
EARTH_R = 6_371_008.8

GHSL_BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
GHSL_BUILT_S_CITATION = (
    "Pesaresi M., Politis P. (2023): GHS-BUILT-S R2023A - GHS built-up surface grid, derived from "
    "Sentinel2 composite and Landsat, multitemporal (1975-2030). European Commission, Joint Research "
    "Centre (JRC). doi:10.2905/9F06F36F-4B11-47EC-ABB0-4F8B7B1D72EA"
)
GHSL_BUILT_H_CITATION = (
    "Pesaresi M., Politis P. (2023): GHS-BUILT-H R2023A - GHS building height, derived from AW3D30, "
    "SRTM30, and Sentinel2 composite (2018). European Commission, Joint Research Centre (JRC). "
    "doi:10.2905/85005901-3A49-48DD-9D19-6261354F56FE"
)
GHSL_UCDB_CITATION = (
    "Mari Rivero I. et al. (2024): GHS-UCDB R2024A - GHS Urban Centre Database 2025. European "
    "Commission, Joint Research Centre (JRC). doi:10.2905/1A338BE6-7EAF-480C-9664-3A8ADE88CBCD"
)


def load_cities() -> list[dict]:
    return json.loads((DATA / "cities.json").read_text())["cities"]


def city_seed(slug: str, salt: str = "") -> int:
    """Deterministic 64-bit seed per city (and purpose), so every rebuild gives identical output."""
    h = hashlib.sha256(f"city-lapse:{slug}:{salt}".encode()).digest()
    return int.from_bytes(h[:8], "little")


def rng_for(slug: str, salt: str = "") -> np.random.Generator:
    return np.random.default_rng(city_seed(slug, salt))


def local_xy(lon, lat, lon0: float, lat0: float):
    """Lon/lat -> metres east/north of (lon0, lat0) on a local equirectangular plane.

    The app inverts exactly this mapping, so it introduces no positional error of its own.
    """
    k = math.pi / 180.0 * EARTH_R
    x = (np.asarray(lon) - lon0) * k * math.cos(math.radians(lat0))
    y = (np.asarray(lat) - lat0) * k
    return x, y


def local_to_lonlat(x, y, lon0: float, lat0: float):
    k = math.pi / 180.0 * EARTH_R
    lon = lon0 + np.asarray(x) / (k * math.cos(math.radians(lat0)))
    lat = lat0 + np.asarray(y) / k
    return lon, lat


def interp_log(years: np.ndarray, pts_year: list[float], pts_val: list[float]) -> np.ndarray:
    """Log-linear interpolation through (year, value) points; flat outside the range."""
    py = np.asarray(pts_year, dtype=float)
    pv = np.log(np.maximum(np.asarray(pts_val, dtype=float), 1.0))
    return np.exp(np.interp(years, py, pv))


def un_switch_year(u: dict) -> int:
    """Year from which the UN WUP 2025 series is used for a city (WUP 2018 before it).

    Normally 1975, the first year WUP 2025 covers. Exception (docs/DECISIONS.md, D13): where the
    2025 revision has no 1975 value, or its 1975 value is below 60 % of the 2018 revision's, its
    back-cast is treated as unusable for the early years and the 2018 agglomeration series is kept
    until the 2025 series catches up with it.
    """
    w18 = {p["year"]: p["value"] for p in u["wup2018"]}
    w25 = {p["year"]: p["value"] for p in u["wup2025"]}
    if not w18:
        return 1975
    if 1975 in w25 and 1975 in w18 and w25[1975] >= 0.6 * w18[1975]:
        return 1975
    for y in range(1975, 2030, 5):
        if y in w25 and y in w18 and w25[y] >= w18[y]:
            return y
    return 2025


def merge_un(city: dict, un: dict) -> list[dict]:
    """Return the city's population points with the UN series (1950 onward) merged in.

    Researched points (before 1950) are kept untouched; anything carrying a "series" key is
    dropped and rebuilt, so this is idempotent.
    """
    slug = city["slug"]
    src18, src25 = un["sources"]["wup2018"], un["sources"]["wup2025"]
    u = un["cities"][slug]
    switch = un_switch_year(u)
    w25 = {p["year"]: p for p in u["wup2025"]}
    pts = [p for p in city["population"] if "series" not in p and p["year"] < 1950]
    for p in pts:
        p.setdefault("definition", "historical city (area as described by the source)")
    for p in u["wup2018"]:
        if 1950 <= p["year"] < switch:
            pt = {
                "year": p["year"], "value": p["value"], "confidence": "estimated",
                "source": f"{src18['citation']}. {src18['url']}",
                "definition": f"urban agglomeration \"{u['wup2018_name']}\" (UN WUP 2018)",
                "series": "UN-WUP-2018",
            }
            if p["year"] >= 1975:
                alt = w25.get(p["year"])
                pt["note"] = ("The UN's 2025 revision " + (f"gives {alt['value']:,} for this year (plausibility: "
                              f"{alt['plausibility']})" if alt else "has no value for this year")
                              + ", far below its own 2018 revision; the 2018 figure is kept until the two "
                                "series meet.")
            pts.append(pt)
    for y in sorted(w25):
        if switch <= y <= 2025:
            pts.append({
                "year": y, "value": w25[y]["value"], "confidence": "estimated",
                "source": f"{src25['citation']}. {src25['url']}",
                "definition": "urban extent (UN WUP 2025, Degree of Urbanisation city)",
                "note": f"UN plausibility rating for this estimate: {w25[y]['plausibility']}.",
                "series": "UN-WUP-2025",
            })
    if 2025 in w25 and 2030 in w25:
        f = (END_YEAR - 2025) / 5
        v = round(w25[2025]["value"] + f * (w25[2030]["value"] - w25[2025]["value"]))
        pts.append({
            "year": END_YEAR, "value": v, "confidence": "reconstructed",
            "source": f"{src25['citation']}. {src25['url']}",
            "definition": "urban extent (UN WUP 2025, Degree of Urbanisation city)",
            "note": "Linear interpolation between the UN's 2025 estimate and 2030 projection.",
            "series": "UN-WUP-2025",
        })
    pts.sort(key=lambda p: p["year"])
    return pts
