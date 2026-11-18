# Decisions log

`CLAUDE.md` is the spec. This file records every choice made where the spec
was silent or ambiguous, with the reason. Newest decisions are appended to
each section.

## City list (phase 2)

**D1. Ranking source: UN World Urbanization Prospects, 2025 Revision.**
The spec asks for the top 50 by metro / urban-area population from one
source applied consistently. We use File 18 of WUP 2025 (the 100 largest
cities ranked by population), ranked by 2025 mid-year population, taken
exactly as published with no substitutions.

Why this source: it is the current edition of a source the spec already
names (UN WUP); it publishes one consistent series for every city from 1975
to 2050; and it defines cities with the Degree of Urbanisation method, which
is built on the same GHSL grids we use for footprints, so the population
series and the footprint describe the same kind of object (an urban extent,
not an administrative unit).

Consequences worth knowing:

- The 2025 revision's urban extents are wider than older "urban
  agglomeration" figures for several Asian cities. Jakarta (41.9 M) and Dhaka
  (36.6 M) rank above Tokyo (33.4 M). That is the UN's current published
  ranking, not an error on our side.
- **Hajipur (India) is rank 34.** The method treats the dense, continuously
  settled belt of north Bihar around Hajipur as a single city of 9.9 M. It is
  a product of the definition rather than a conventional metropolis. We keep
  it because the spec says one source, applied consistently; the city's notes
  and the About panel say plainly what it is.
- Chongqing, Riyadh, Surat and others that appear in older top-50 lists fall
  just outside (ranks 51+).

**D2. City centres are hand-entered conventional centres** (historic core or
main square), not the UN's population-weighted centroid, which can sit tens
of kilometres from the city people recognise (Dhaka, Jakarta). The UN
centroid is kept in `data/cities.json` as `un_centroid`.

**D3. Display names** follow common English usage ("Delhi" for the UN's "New
Delhi", "Bangkok" for "Krung Thep Maha Nakhon"). The UN's own label is kept
as `un_name`.

## Population series

**D4. 1950 onward comes straight from UN files, merged by script.**
Research agents only supply points before 1950. `scripts/build_city_list.py`
extracts the UN numbers into `data/un_population.json` and
`scripts/02_merge_population.py` merges them, so nobody retypes them.

- 1950-1970: WUP 2018 (File 12, urban agglomerations), confidence
  `estimated`. WUP 2025 does not go back before 1975.
- 1975-2025: WUP 2025 (File 19), confidence `estimated` (UN estimates built
  on censuses and population grids, not direct counts).
- 2026: linear interpolation between the UN's 2025 and 2030 values,
  confidence `reconstructed`.

**D5. The definition changes at 1975 and the app says so.** Pre-1950
figures are whatever area the historical source covered (walled city,
municipality, agglomeration); 1950-1970 are WUP 2018 agglomerations; 1975+
are WUP 2025 urban extents. For some cities the 1975 value is far above the
1970 one (Jakarta 3.9 M to 11.7 M) because the area counted is wider, not
because the city tripled. We do not rescale either series to hide this.
Each population point carries a `definition` string, the counter shows which
definition is in force, and the About panel explains the break.

**D6. Taipei in WUP 2018** is listed as "Taibei" (Taipei city) with "Xinbei"
(New Taipei) separate. We use "Taibei" for 1950-1970.

## Schema extensions

The spec's schema is kept as is. These fields are added:

**D7. `confidence` on milestones and landmarks**, because accuracy rule 1
says every data point stores `source` and `confidence`, although the schema
example only shows it on population.

**D8. `historic_core` {name, lat, lon, source}** on each city. The pre-1975
footprint method contracts the 1975 footprint "toward the historic core",
so the core has to be recorded and sourced.

**D9. `start_source`, `start_confidence`** for the start year itself, and
optional `note` / `definition` on population points, `kind` and
`demolished_year` on landmarks.

**D10. BCE years are negative integers** (660 BCE is `-660`), no year 0.

## Research (phase 3)

**D11. Ten agents, five cities each, grouped by region** so each agent works
within one historiography. Agents may only record figures they saw on a page
they opened during the run; anything unsourced is left out and described in
`notes`.

## Stack

**D12. MapLibre GL JS pinned to v5.** v6 (current `latest`) ships its worker
as a separate ES module resolved from `import.meta.url`, which needs extra
bundler handling in a Next.js static export. v5 is the last line with the
self-contained bundle. Revisit when deck.gl's MapLibre integration documents
v6.
