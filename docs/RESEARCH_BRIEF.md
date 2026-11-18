# Research brief for per-city data files

This is the brief every research agent works from (phase 3). It restates the
schema and accuracy rules from `CLAUDE.md` and pins down the details that
`CLAUDE.md` leaves open. Extensions to the schema are logged in
`docs/DECISIONS.md`.

## What you produce

One file per city: `data/cities/<slug>.json`. The file holds the data; your
reply to the orchestrator is only a short summary of gaps.

```json
{
  "slug": "tokyo",
  "name": "Tokyo",
  "country": "Japan",
  "start_year": 1457,
  "start_label": "Edo Castle founded by Ōta Dōkan",
  "start_source": "https://...",
  "start_confidence": "documented",
  "historic_core": { "name": "Edo Castle (Imperial Palace)", "lat": 35.6852, "lon": 139.7528, "source": "https://..." },
  "population": [
    { "year": 1457, "value": 5000, "confidence": "reconstructed", "source": "...", "note": "method ..." }
  ],
  "milestones": [
    { "year": 1603, "title": "Edo becomes the shogunate's capital", "detail": "One or two sentences.", "source": "https://...", "confidence": "documented" }
  ],
  "landmarks": [
    { "name": "Tokyo Skytree", "year": 2012, "height_m": 634, "lat": 35.7101, "lon": 139.8107, "kind": "tower", "source": "https://...", "confidence": "documented" }
  ],
  "footprint_epochs": "footprints/tokyo/",
  "notes": "Data gaps, caveats, and the methods used"
}
```

### Field rules

- **Years** are integers in the proleptic Gregorian calendar. BCE years are
  negative: 660 BCE is `-660`. There is no year 0.
- **`start_year` / `start_label`**: the earliest *documented* founding or
  settlement of the city itself (not of the wider region, and not legend). If
  a legendary date exists alongside a documented one, use the documented one
  and mention the legend in `notes`. Archaeologically dated continuous
  settlement on the site counts as documented when a published excavation or
  standard reference states it.
- **`historic_core`**: the point the city grew out from (old fort, walled
  city, first harbour, main square). Used as the centre of the backward
  footprint reconstruction. Must be inside today's city.
- **`population`**: the city's population at points **before 1950 only**.
  The UN series for 1950 onward is merged in automatically from
  `data/un_population.json`; do not retype it.
  - Aim for 8-15 points spread from `start_year` to the 1940s, more where
    censuses exist. Include every census you can source for the 19th and
    early 20th century.
  - Each point needs `year`, `value` (persons, integer), `confidence`,
    `source`. Add `note` when the figure covers an unusual area (walled city
    only, municipality, metropolitan county) or when you derived it.
  - Do not pad. If the sources give three points before 1900, record three
    and say so in `notes`. A thin series shown honestly beats a smooth
    invented one.
  - A point at `start_year` is welcome if a source gives one. If none does,
    you may add one `reconstructed` point with the method in `note`, or leave
    it out; the app then shows "no reliable estimate" until the first point.
- **`milestones`**: 10-16 dated events that changed the city's size, shape or
  status (founding, becoming a capital, walls, fires, earthquakes, sieges,
  plagues, railways, annexations, major planning schemes, metro openings,
  Olympics). `title` is at most 60 characters; `detail` is one or two plain
  sentences. Spread them across the whole timeline, not just the last
  century.
- **`landmarks`**: 10-20 real structures with real completion years and real
  heights, spread across the city's history: the oldest surviving or
  best-documented monuments (forts, temples, mosques, cathedrals, palaces,
  gates, towers) and the tallest/most recognisable modern towers.
  - `year` is the completion year of the structure as it stands or stood at
    that height. `height_m` is the architectural height in metres.
  - `lat`/`lon` to at least four decimals, on the structure itself.
  - `kind` is one of `tower`, `skyscraper`, `temple`, `mosque`, `church`,
    `palace`, `fort`, `gate`, `monument`, `bridge`, `stadium`, `other`.
  - Add `"demolished_year"` if it no longer stands.
  - Skyscraper heights and years come from the CTBUH Skyscraper Center
    (skyscrapercenter.com) where it lists the building.
  - If you cannot source a height, leave the landmark out rather than guess.
- **`notes`**: plain prose. What is thin, what is contested, which
  definitions the population figures use, and any method you applied.

### Confidence values

| Value | Meaning |
|---|---|
| `documented` | A census or official count, a figure recorded at the time, a surveyed height, or a securely dated event. |
| `estimated` | A published scholarly estimate (Chandler, Modelski, a historian, an archaeologist, the UN). |
| `reconstructed` | Our own interpolation or derivation. Requires a `note` giving the method. |

## Accuracy rules (non-negotiable, from CLAUDE.md)

1. Every number has a `source` (a URL, or a full citation when the source is
   a book) and a `confidence`.
2. Don't invent. Record only figures you actually saw on a page you opened in
   this session. Do not fill in numbers from memory, even if you are sure.
3. Prefer primary or academic sources over blogs. Wikipedia is acceptable as
   a pointer; when it cites a source for the figure, cite that source (and
   you may add the Wikipedia URL after it, e.g.
   `"Chandler (1987), Four Thousand Years of Urban Growth, via https://en.wikipedia.org/wiki/..."`).
4. Early data is thin for some cities (Dhaka, Kinshasa, Lagos before 1900).
   Show that honestly instead of smoothing it over.

Preferred sources for historical population: Chandler, *Four Thousand Years
of Urban Growth* (1987); Modelski, *World Cities: -3000 to 2000* (2003); Reba,
Reitsma & Seto (2016) which digitises both; national censuses; city
statistical yearbooks; academic urban histories.

## Before you finish

Run the validator on each file and fix what it reports:

```
/home/user/city-lapse/.venv/bin/python /home/user/city-lapse/scripts/validate_city.py <slug>
```
