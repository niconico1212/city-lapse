# city-lapse

A public website where you pick one of the world's 50 largest cities at the top of the screen and watch it grow in 3D. The time-lapse runs from the city's earliest documented founding or settlement to 2026: the built-up area spreads outward, buildings rise, and real landmark towers go up in the years they were actually built.

Owner: Nico (GitHub `niconico1212`). Deploy target: Vercel.

---

## Product decisions (locked — don't re-ask)

| Decision | Choice |
|---|---|
| View | **3D extruded city**: a tilted map where the footprint spreads and buildings extrude upward over time |
| City list | **Top 50 by metro / urban-area population**, using one ranking source applied consistently. Record which source in `data/cities.json`. |
| Start year | **Earliest documented** for each city (its founding, or its earliest known settlement). Each city runs on its own clock. |
| Building realism | **Honest procedural fill.** The footprint, density and height profile are real by era; individual generic buildings are generated. Landmark towers are modeled to their real heights and completion years. A "How this was made" note says so. |
| Overlays | Year counter, population counter, milestone captions, landmark pins |
| Not in v1 | Side-by-side city comparison, the skyline side view |

## Accuracy rules (non-negotiable)

1. **Every number has a source.** Each data point stores `source` (a URL or citation) and `confidence`: `documented` | `estimated` | `reconstructed`.
2. **Don't invent.** If no source exists for a year, interpolate, mark it `reconstructed`, and log the method.
3. On screen, reconstructed eras get a subtle label (for example "Reconstructed estimate" under the population counter).
4. Prefer primary or academic sources over blogs. Wikipedia is acceptable as a pointer, but cite what it cites when possible.
5. Expect early data to be thin for some cities (Dhaka, Kinshasa, Lagos before 1900). Show that honestly instead of smoothing it over.

## Data sources

**Built-up footprint (real, 1975 onward)**
- GHSL **GHS-BUILT-S** (JRC, Global Human Settlement Layer): built-up surface for every 5-year epoch, 1975–2030. This is the main footprint source.
- GHSL **GHS-BUILT-H**: building heights (around 2018). Used to calibrate the procedural height distribution.
- GHSL **GHS-UCDB**: urban-centre boundaries, used to define each city's extent.
- Atlas of Urban Expansion (NYU/Lincoln Institute): a cross-check for the cities it covers.

**Historical (before 1975)**
- Reba, Reitsma & Seto (2016), *Spatializing 6,000 years of global urbanization* (historical city populations with coordinates)
- Chandler, *Four Thousand Years of Urban Growth*; Modelski, *World Cities −3000 to 2000*
- UN *World Urbanization Prospects* (1950 onward)
- HYDE 3.x historical urban land
- Historical maps (for example the David Rumsey collection) for footprint anchor points where they exist

**Landmarks**
- CTBUH Skyscraper Center (heights, completion years), plus city-specific sources for older landmarks (castles, cathedrals, temples, forts)

**Pre-1975 footprint method:** start from the 1975 GHSL footprint and contract it backward toward the historic core, driven by population and era-typical density. Anchor to dated historical maps where available. Mark it all `reconstructed`.

## Data schema

`data/cities.json` holds the list of 50: slug, name, country, rank, ranking source, center lat/lon, and the default camera.

`data/cities/<slug>.json`:
```json
{
  "slug": "tokyo",
  "name": "Tokyo",
  "country": "Japan",
  "start_year": 1457,
  "start_label": "Edo Castle founded by Ōta Dōkan",
  "population": [
    { "year": 1457, "value": 5000, "confidence": "reconstructed", "source": "..." }
  ],
  "milestones": [
    { "year": 1603, "title": "Edo becomes the shogunate's capital", "detail": "...", "source": "..." }
  ],
  "landmarks": [
    { "name": "Tokyo Skytree", "year": 2012, "height_m": 634, "lat": 35.7101, "lon": 139.8107, "source": "..." }
  ],
  "footprint_epochs": "footprints/tokyo/",
  "notes": "Data gaps, caveats, and the methods used"
}
```

Footprints: `data/footprints/<slug>/<year>.geojson` (simplified). The app consumes precomputed per-city building data from `public/data/<slug>.bin` or compact JSON. Each building has a footprint polygon, a height, and a `year_built`.

## Procedural building generation (`scripts/`)

- Seeded RNG per city, so every rebuild is deterministic.
- A building's `year_built` is the epoch in which its cell first enters the footprint, plus jitter.
- Heights are capped by era (for example almost nothing over 30 m before 1900 unless the building is a landmark) and calibrated to GHS-BUILT-H for the present.
- Some cells get redeveloped, with low buildings replaced by taller ones later, so the core densifies vertically.
- Landmarks are placed at their real coordinates and heights, and never generated.
- Budget is about 50–150k buildings per city for smooth browser performance. Simplify geometry aggressively.

## Stack

- **Next.js** (App Router, static export where possible) + TypeScript
- **MapLibre GL** with **OpenFreeMap** tiles: free, no API key
- **deck.gl**: extruded polygon layers for the buildings, filtered by year through GPU uniforms (no per-frame CPU rebuild)
- Python in `scripts/` for the data pipeline (rasterio, geopandas, shapely)
- Deploy: Vercel

## UI

- **Top bar:** a city picker (searchable dropdown, ordered by rank)
- **Main view:** the 3D map with a slow camera orbit during playback
- **Bottom bar:** play/pause, speed control, a timeline scrubber with milestone ticks, and a large year readout
- **Corner overlays:** a population counter (with a "reconstructed" tag when relevant), milestone captions that fade in as their year passes, and landmark pins that drop in at completion
- An "About the data" panel with sources and method for each city
- Mobile friendly. The city goes in the URL hash (`#tokyo`) so links are shareable.

## Build phases

1. **Scaffold.** Next.js app, map rendering, one hardcoded test city.
2. **City list.** Pick the ranking source and write `data/cities.json`.
3. **Research (parallel subagents on the Fable model).** About 10 agents with 5 cities each. Each agent writes `data/cities/<slug>.json` following the schema and accuracy rules. Return only a summary of gaps; the files hold the data.
4. **Footprint pipeline.** Download GHSL tiles for each city, extract 1975–2025 epochs, and run the backward reconstruction. Run this locally, because the data is large.
5. **Building generation.** Run the procedural pipeline and export compact per-city files.
6. **App polish.** Overlays, playback, picker, about panel, and performance.
7. **Verification.** A separate agent that didn't produce the data spot-checks about 10 random figures per city against the cited sources and fixes or flags problems.
8. **Deploy** to Vercel.

## Conventions

- Large raw downloads go in `raw/` (gitignored). Only processed, simplified outputs get committed.
- Commit after each phase with a clear message.
- Keep `docs/DATA_LOG.md` up to date: per city, what's documented, what's reconstructed, and how.
