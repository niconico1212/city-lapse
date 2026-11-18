# city-lapse

Pick one of the world's 50 largest cities and watch it grow in 3D, from its earliest documented
founding to 2026. The built-up area spreads outward, buildings rise, and real landmark towers go up
in the years they were actually built.

`CLAUDE.md` is the spec. `docs/DECISIONS.md` records every choice made where the spec was silent,
and `docs/DATA_LOG.md` says, city by city, what is documented, what is reconstructed and how.

## What is real and what is generated

| Real | Generated |
|---|---|
| The built-up footprint at each five-year epoch from 1975 (GHSL GHS-BUILT-S, 100 m) | The individual generic buildings: outline, orientation, lot split |
| How much of each 100 m cell is built on | The height of each building around its cell's average |
| Present-day average building height per cell (GHS-BUILT-H, 2018) | The years in which low early buildings give way to taller ones |
| Every landmark's position, height and completion year | The schematic shape of each landmark |
| Population figures, each with a source and a confidence | **The footprint before 1975**, reconstructed by contracting the 1975 footprint toward the historic core |

Reconstructed eras are labelled on screen, and the "About the data" panel lists every source.

## Artistic layers (pilot: Tokyo)

Tokyo has three extra layers, switched on in `data/extras.json`:

- **Landmark models** that go up over their real construction period (`scripts/09_landmark_models.py`,
  facts in `data/models/tokyo.facts.json`). Position, height and years are sourced; shapes are schematic.
- **Real building shapes from 1975**, shown when zoomed in: 1.7 million footprints with measured heights
  from PLATEAU, Japan's open 3D city model (`scripts/08_real_buildings.py`, tiles in
  `public/data/tokyo-real/`). Their construction years are mostly unknown and are assigned by rule.
- **Stylised fabric before 1900**, an artist's impression in one of three historic styles (woodblock, ink,
  lantern), chosen in the legend or with `?style=ink` in the URL.

The About panel in the app says which parts are sourced, which are assigned by rule and which are
drawn for effect. `docs/pilot/` holds reference frames.

## Run the app

```bash
npm install
```

```bash
npm run dev
```

Then open http://localhost:3000. The city is in the URL hash, so `http://localhost:3000/#tokyo`
links straight to Tokyo.

To build the static site that gets deployed (output in `out/`):

```bash
npm run build
```

## Deploy

The site is a static export. With the Vercel CLI, from the repository root:

```bash
npx vercel --prod
```

## Rebuild the data

The processed data is committed (`data/`, `public/data/`), so this is only needed after changing the
research files or the pipeline. Raw downloads go to `raw/` (gitignored, about 6 GB).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

| Step | Script | What it does |
|---|---|---|
| City list | `scripts/build_city_list.py` | Top 50 from UN WUP 2025 into `data/cities.json`, UN series into `data/un_population.json` (needs the UN workbooks in `raw/wup/`) |
| Validate | `scripts/validate_city.py [--merged] [slug]` | Checks `data/cities/<slug>.json` against the schema and accuracy rules |
| GHSL | `scripts/01_fetch_ghsl.py` | Downloads GHS-BUILT-S 1975-2025 and GHS-BUILT-H tiles, clips them to each city's GHS-UCDB urban centre (needs the UCDB GeoPackage in `raw/ucdb/`) |
| Population | `scripts/02_merge_population.py` | Merges the UN series (1950 onward) into the per-city files |
| Footprints | `scripts/03_footprints.py` | Per-cell entry years, the pre-1975 reconstruction, `data/footprints/<slug>/<year>.geojson` |
| Buildings | `scripts/04_buildings.py` | Seeded procedural generation, `public/data/<slug>.bin` and `.json` |
| Real shapes | `scripts/08_real_buildings.py` | Tokyo only: PLATEAU footprints into tiles (needs the GeoParquet files in `raw/plateau/`) |
| Landmark models | `scripts/09_landmark_models.py` | Tokyo only: models from `data/models/tokyo.facts.json` |
| Index | `scripts/05_export_index.py` | `public/data/cities.json` for the picker |
| Log | `scripts/06_data_log.py` | Regenerates `docs/DATA_LOG.md` |

`scripts/run_pipeline.sh [slug ...]` runs footprints, buildings and the index in order.

## Layout

```
app/, components/, lib/   Next.js app (App Router, static export), MapLibre + deck.gl
data/cities.json          the 50 cities and the ranking source
data/cities/<slug>.json   per-city research: start, population, milestones, landmarks, notes
data/footprints/<slug>/   footprint polygon per epoch, urban-centre extent, summary
data/verification/        independent spot-check results (phase 7)
public/data/              what the app loads: <slug>.json (data + sources), <slug>.bin (buildings)
scripts/                  the Python pipeline
docs/                     DECISIONS.md, DATA_LOG.md, RESEARCH_BRIEF.md
```

## Sources

- Built-up surface, building height, urban centres: Global Human Settlement Layer (European
  Commission, JRC): GHS-BUILT-S R2023A, GHS-BUILT-H R2023A, GHS-UCDB R2024A.
- Ranking and population from 1950: UN World Urbanization Prospects, 2025 and 2018 revisions.
- Historical population, milestones and landmarks: cited per data point in each city file.
- Era-typical density: Angel, Parent, Civco & Blei (2010), *The Persistent Decline in Urban
  Densities*.
- Base map: OpenFreeMap vector tiles, © OpenMapTiles, © OpenStreetMap contributors.

## What was checked, and what was not

- All 50 cities build through the pipeline: 48 complete, 2 flagged partial (Shenzhen: no sourced
  population before 1950; Hajipur: no landmark with a sourced height, and no UN series before 1975).
- 500 randomly sampled figures (10 per city) were checked against their cited sources by agents
  that did not produce the data; see `data/verification/` and the per-city lines in
  `docs/DATA_LOG.md`.
- The app was run in headless Chromium: six cities played start to finish (Lagos, London, Cairo,
  São Paulo, Shenzhen, Hajipur) and six more stepped through their timelines at full detail
  (Tokyo, New York, Delhi, Istanbul, Mexico City, Kinshasa), with no page errors.
- **Not measured: frame rate on real hardware.** The build machine has no GPU, so the browser
  used a software renderer, far slower than any real device. The scene is about 90,000 extruded
  boxes per city (roughly a million triangles) with the year filter on the GPU, and the app falls
  back to reduced detail if playback starts slowly, but real-device performance should be checked
  after deploying.
