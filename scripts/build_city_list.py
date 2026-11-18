#!/usr/bin/env python3
"""Phase 2: build data/cities.json from the single ranking source.

Ranking source: United Nations, World Urbanization Prospects: The 2025 Revision,
File 18 (the 100 largest cities ranked by population, Degree of Urbanisation
"city" definition). We take the top 50 by 2025 mid-year population, exactly as
the UN ranks them, with no substitutions.

Also writes data/un_population.json: the UN series for every listed city
(WUP 2025 for 1975-2030, WUP 2018 for 1950-1970) so later steps can merge it
into the per-city files without anyone retyping numbers.

Inputs (downloaded into raw/wup/, gitignored):
  WUP2025-F18-DEGURBA-100_Largest_Cities.xlsx
  WUP2025-F19-DEGURBA-100_Largest_Cities_in_2025_by_time.xlsx
  WUP2018-F12-Cities_Over_300K.xls
"""
import json
from pathlib import Path

import openpyxl
import xlrd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "wup"

WUP25_URL = "https://population.un.org/wup/assets/Download/Cities/WUP2025-F18-DEGURBA-100_Largest_Cities.xlsx"
WUP25_TS_URL = "https://population.un.org/wup/assets/Download/Cities/WUP2025-F19-DEGURBA-100_Largest_Cities_in_2025_by_time.xlsx"
WUP18_URL = "https://population.un.org/wup/assets/Download/Archive/WUP2018-Excel-files.zip"

RANKING_SOURCE = {
    "id": "UN-WUP-2025",
    "title": "United Nations, Department of Economic and Social Affairs, Population Division (2025). "
             "World Urbanization Prospects: The 2025 Revision, Online Edition. File 18: The 100 Largest "
             "Cities Ranked by Population Size at Each Point in Time, 1975-2050 (POP/DB/WUP/Rev.2025/F18).",
    "url": WUP25_URL,
    "definition": "Cities as defined by the Degree of Urbanisation: contiguous 1 km2 grid cells with at "
                  "least 1,500 inhabitants per km2 and at least 50,000 inhabitants in total. This is an "
                  "urban-extent definition, not an administrative one.",
    "ranked_by": "2025 mid-year population",
    "licence": "CC BY 3.0 IGO",
}

# UN City_Code -> (slug, display name, country display, centre lat, centre lon, WUP2018 city code or None)
# Centres are the conventional city centre / historic core, hand-entered; the UN's
# population-weighted centroid is kept alongside as un_centroid.
CITIES = {
    5590: ("jakarta", "Jakarta", "Indonesia", -6.1754, 106.8272),
    6249: ("dhaka", "Dhaka", "Bangladesh", 23.7104, 90.4074),
    6030: ("tokyo", "Tokyo", "Japan", 35.6852, 139.7528),
    8364: ("delhi", "Delhi", "India", 28.6328, 77.2197),
    11738: ("shanghai", "Shanghai", "China", 31.2304, 121.4737),
    11306: ("guangzhou", "Guangzhou", "China", 23.1291, 113.2644),
    4435: ("cairo", "Cairo", "Egypt", 30.0444, 31.2357),
    2369: ("manila", "Manila", "Philippines", 14.5906, 120.9750),
    11821: ("kolkata", "Kolkata", "India", 22.5726, 88.3639),
    332: ("seoul", "Seoul", "South Korea", 37.5700, 126.9769),
    2578: ("karachi", "Karachi", "Pakistan", 24.8607, 67.0011),
    7945: ("mumbai", "Mumbai", "India", 18.9690, 72.8205),
    7303: ("sao-paulo", "São Paulo", "Brazil", -23.5505, -46.6333),
    2286: ("bangkok", "Bangkok", "Thailand", 13.7563, 100.5018),
    5439: ("mexico-city", "Mexico City", "Mexico", 19.4326, -99.1332),
    9020: ("beijing", "Beijing", "China", 39.9163, 116.3972),
    8021: ("lahore", "Lahore", "Pakistan", 31.5820, 74.3294),
    2626: ("istanbul", "Istanbul", "Türkiye", 41.0082, 28.9784),
    2485: ("moscow", "Moscow", "Russia", 55.7520, 37.6175),
    5435: ("ho-chi-minh-city", "Ho Chi Minh City", "Vietnam", 10.7769, 106.7009),
    4459: ("buenos-aires", "Buenos Aires", "Argentina", -34.6083, -58.3712),
    8354: ("new-york", "New York", "United States", 40.7400, -73.9900),
    11478: ("shenzhen", "Shenzhen", "China", 22.5431, 114.0579),
    9949: ("bengaluru", "Bengaluru", "India", 12.9716, 77.5946),
    4490: ("osaka", "Osaka", "Japan", 34.6937, 135.5023),
    1265: ("lagos", "Lagos", "Nigeria", 6.4541, 3.3947),
    1725: ("los-angeles", "Los Angeles", "United States", 34.0537, -118.2428),
    939: ("luanda", "Luanda", "Angola", -8.8147, 13.2302),
    10747: ("chennai", "Chennai", "India", 13.0827, 80.2707),
    1854: ("kinshasa", "Kinshasa", "DR Congo", -4.3033, 15.3105),
    3883: ("bogota", "Bogotá", "Colombia", 4.5981, -74.0760),
    1987: ("lima", "Lima", "Peru", -12.0464, -77.0428),
    5938: ("london", "London", "United Kingdom", 51.5099, -0.1181),
    11027: ("hajipur", "Hajipur", "India", 25.6858, 85.2146),
    7935: ("rio-de-janeiro", "Rio de Janeiro", "Brazil", -22.9068, -43.1729),
    2994: ("paris", "Paris", "France", 48.8566, 2.3522),
    9913: ("hyderabad", "Hyderabad", "India", 17.3616, 78.4747),
    5264: ("tehran", "Tehran", "Iran", 35.6892, 51.3890),
    12128: ("taipei", "Taipei", "Taiwan", 25.0375, 121.5637),
    5991: ("bandung", "Bandung", "Indonesia", -6.9175, 107.6191),
    1629: ("kuala-lumpur", "Kuala Lumpur", "Malaysia", 3.1478, 101.6953),
    3566: ("dar-es-salaam", "Dar es Salaam", "Tanzania", -6.8161, 39.2894),
    11632: ("suzhou", "Suzhou", "China", 31.2990, 120.5853),
    6408: ("ahmedabad", "Ahmedabad", "India", 23.0225, 72.5714),
    11700: ("hangzhou", "Hangzhou", "China", 30.2500, 120.1650),
    10474: ("wuhan", "Wuhan", "China", 30.5810, 114.2880),
    9414: ("tianjin", "Tianjin", "China", 39.1300, 117.2000),
    275: ("alexandria", "Alexandria", "Egypt", 31.2001, 29.9187),
    5245: ("nagoya", "Nagoya", "Japan", 35.1815, 136.9066),
    3664: ("johannesburg", "Johannesburg", "South Africa", -26.2041, 28.0473),
}

# Name of the matching urban agglomeration in WUP 2018 File 12 (None = not listed there).
WUP18_NAMES = {
    "jakarta": "Jakarta", "dhaka": "Dhaka", "tokyo": "Tokyo", "delhi": "Delhi", "shanghai": "Shanghai",
    "guangzhou": "Guangzhou, Guangdong", "cairo": "Al-Qahirah (Cairo)", "manila": "Manila",
    "kolkata": "Kolkata (Calcutta)", "seoul": "Seoul", "karachi": "Karachi", "mumbai": "Mumbai (Bombay)",
    "sao-paulo": "São Paulo", "bangkok": "Krung Thep (Bangkok)", "mexico-city": "Ciudad de México (Mexico City)",
    "beijing": "Beijing", "lahore": "Lahore", "istanbul": "Istanbul", "moscow": "Moskva (Moscow)",
    "ho-chi-minh-city": "Thành Pho Ho Chí Minh (Ho Chi Minh City)", "buenos-aires": "Buenos Aires",
    "new-york": "New York-Newark", "shenzhen": "Shenzhen", "bengaluru": "Bangalore",
    "osaka": "Kinki M.M.A. (Osaka)", "lagos": "Lagos", "los-angeles": "Los Angeles-Long Beach-Santa Ana",
    "luanda": "Luanda", "chennai": "Chennai (Madras)", "kinshasa": "Kinshasa", "bogota": "Bogotá",
    "lima": "Lima", "london": "London", "hajipur": None, "rio-de-janeiro": "Rio de Janeiro",
    "paris": "Paris", "hyderabad": "Hyderabad", "tehran": "Tehran", "taipei": "Taibei",
    "bandung": "Bandung", "kuala-lumpur": "Kuala Lumpur", "dar-es-salaam": "Dar es Salaam",
    "suzhou": "Suzhou, Jiangsu", "ahmedabad": "Ahmadabad", "hangzhou": "Hangzhou", "wuhan": "Wuhan",
    "tianjin": "Tianjin", "alexandria": "Al-Iskandariyah (Alexandria)",
    "nagoya": "Chukyo M.M.A. (Nagoya)", "johannesburg": "Johannesburg",
}


def read_wup25():
    wb = openpyxl.load_workbook(RAW / "WUP2025-F18-DEGURBA-100_Largest_Cities.xlsx", read_only=True, data_only=True)
    rows = list(wb["Data"].iter_rows(values_only=True))
    head = rows[0]
    recs = [dict(zip(head, r)) for r in rows[1:] if r[1] == 2025]
    recs.sort(key=lambda d: d["Rank_Order"])
    return recs[:50]


def read_wup25_series():
    wb = openpyxl.load_workbook(RAW / "WUP2025-F19-DEGURBA-100_Largest_Cities_in_2025_by_time.xlsx",
                                read_only=True, data_only=True)
    rows = list(wb["Data"].iter_rows(values_only=True))
    head = rows[0]
    out = {}
    for r in rows[1:]:
        d = dict(zip(head, r))
        out.setdefault(d["City_Code"], []).append(d)
    return out


def read_wup18():
    """Return {agglomeration name: {year: population}} for 1950..2035 (thousands -> persons)."""
    wb = xlrd.open_workbook(RAW / "WUP2018-F12-Cities_Over_300K.xls")
    ws = wb.sheet_by_index(0)
    header_row = None
    for i in range(ws.nrows):
        if str(ws.cell_value(i, 0)).strip() == "Index":
            header_row = i
            break
    head = [str(ws.cell_value(header_row, c)).strip() for c in range(ws.ncols)]
    name_col = head.index("Urban Agglomeration")
    year_cols = {}
    for c, h in enumerate(head):
        try:
            y = int(float(h))
            if 1950 <= y <= 2035:
                year_cols[y] = c
        except ValueError:
            pass
    out = {}
    for i in range(header_row + 1, ws.nrows):
        name = str(ws.cell_value(i, name_col)).strip()
        out[name] = {y: round(float(ws.cell_value(i, c)) * 1000) for y, c in year_cols.items()
                     if ws.cell_value(i, c) not in ("", None)}
    return out


def main():
    top = read_wup25()
    series25 = read_wup25_series()
    wup18 = read_wup18()
    cities, un_pop = [], {}
    for rec in top:
        code = rec["City_Code"]
        if code not in CITIES:
            raise SystemExit(f"UN city code {code} ({rec['City_Name']}) is in the top 50 but not mapped")
        slug, name, country, lat, lon = CITIES[code]
        cities.append({
            "slug": slug,
            "name": name,
            "country": country,
            "rank": rec["Rank_Order"],
            "ranking_source": RANKING_SOURCE["id"],
            "un_name": rec["City_Name"],
            "un_country": rec["Location"],
            "un_city_code": code,
            "population_2025": round(rec["Population"] * 1000),
            "un_plausibility": rec["Pop_plausibility"],
            "un_land_area_km2": rec["Land_area_km2"],
            "center": {"lat": lat, "lon": lon},
            "un_centroid": {"lat": round(rec["PWCent_Latitude"], 4), "lon": round(rec["PWCent_Longitude"], 4)},
            # default camera; zoom is refined from the real footprint extent in scripts/04_export_app_data.py
            "camera": {"zoom": 10.5, "pitch": 55, "bearing": -20},
        })
        s25 = sorted(series25.get(code, []), key=lambda d: d["Year"])
        s18 = wup18.get(WUP18_NAMES[slug]) if WUP18_NAMES[slug] else None
        if WUP18_NAMES[slug] and s18 is None:
            raise SystemExit(f"WUP2018 agglomeration name not found for {slug}: {WUP18_NAMES[slug]}")
        un_pop[slug] = {
            "wup2025": [{"year": d["Year"], "value": round(d["Population"] * 1000),
                         "plausibility": d["Pop_plausibility"], "land_area_km2": d["Land_area_km2"]}
                        for d in s25 if d["Year"] <= 2030],
            "wup2018_name": WUP18_NAMES[slug],
            "wup2018": [{"year": y, "value": v} for y, v in sorted(s18.items())] if s18 else [],
        }
    assert len(cities) == 50 and [c["rank"] for c in cities] == list(range(1, 51))
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "cities.json").write_text(json.dumps(
        {"ranking_source": RANKING_SOURCE, "generated_by": "scripts/build_city_list.py", "cities": cities},
        ensure_ascii=False, indent=2) + "\n")
    (ROOT / "data" / "un_population.json").write_text(json.dumps({
        "sources": {
            "wup2025": {"citation": "UN DESA Population Division (2025), World Urbanization Prospects: The 2025 "
                                    "Revision, File 19 (POP/DB/WUP/Rev.2025/F19)", "url": WUP25_TS_URL,
                        "definition": RANKING_SOURCE["definition"]},
            "wup2018": {"citation": "UN DESA Population Division (2018), World Urbanization Prospects: The 2018 "
                                    "Revision, File 12: Population of Urban Agglomerations with 300,000 "
                                    "Inhabitants or More in 2018, by country, 1950-2035", "url": WUP18_URL,
                        "definition": "Urban agglomeration (or the national statistical concept the UN adopted "
                                      "for that city); narrower than the 2025 revision's urban extents."},
        },
        "cities": un_pop}, ensure_ascii=False, indent=1) + "\n")
    for c in cities:
        print(f"{c['rank']:>2} {c['slug']:<18} {c['population_2025']:>11,}  wup18={'yes' if un_pop[c['slug']]['wup2018'] else 'NO'}")


if __name__ == "__main__":
    main()
