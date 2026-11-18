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

## Added during phases 3 to 5

**D13. Three cities keep the UN's 2018 series past 1975.** For Luanda, Kuala Lumpur and Dar es
Salaam the 2025 revision's back-cast is unusable in the early years: Luanda has no value before
1995 and then 306,000 (the 2018 revision says 2.1 M); Kuala Lumpur's 1975 value is 26 % of the
2018 revision's; Dar es Salaam's is 52 %, and the UN itself rates several of these "Low"
plausibility. An urban extent cannot plausibly hold a fraction of the people of the agglomeration
inside it. Rule, applied by script to every city: if WUP 2025 has no 1975 value, or it is below
60 % of WUP 2018's 1975 value, WUP 2018 is kept until the first five-year step at which WUP 2025
reaches it (Luanda 2015, Kuala Lumpur 1990, Dar es Salaam 2015). The affected points carry a note
quoting the 2025 revision's figure. All other cities switch at 1975 as in D4.

**D14. Contested start dates follow the researcher's documented choice.** The spec asks for the
earliest documented founding or earliest known settlement. Where a traditional or archaeologically
attested early date exists on today's city territory (Seoul 18 BCE, Beijing 1045 BCE, Delhi
c. 300 BCE, Manila 900, Shenzhen 331), it is used and marked `estimated`, with the conventional
later date and the reasoning in the city's notes. Legend without a datable settlement (Delhi's
Indraprastha, Tokyo's Sensō-ji tradition) is not used.

**D15. Fewer than five landmarks is allowed.** A landmark with no sourced height is left out
rather than guessed. Hajipur ends up with none, and several African cities with five to seven.
Cities with fewer than three landmarks or fewer than three pre-1950 population points are flagged
`partial` in the picker and the About panel.

**D16. Research agents did not use Reba, Reitsma & Seto directly from SEDAC** (it needs a login).
Chandler and Modelski figures were taken from a public copy of the Reba dataset and from the
secondary sources cited on each point.

## Footprints and buildings (phases 4 and 5)

**D17. GHSL at 100 m, by tile.** GHS-BUILT-S R2023A (epochs 1975-2025) and GHS-BUILT-H R2023A
(ANBH, 2018) were downloaded as 100 m Mollweide tiles: 38 tiles, 456 files, all successful, so no
resolution fallback was needed. The 2030 epoch is not used. A cell is built-up at 5 % built
surface (500 m2).

**D18. City extent = the GHS-UCDB R2024A urban centre containing the city centre.** This is the
same object the UN ranking measures, and its area matches the UN's land area closely for almost
every city.

**D19. Guangzhou and Shenzhen share one GHSL urban centre** (43 M people, 6,454 km2), but the UN
lists them separately. The polygon is split by weighted distance to the two centres so that each
city's share of the area equals its share of the UN's published land areas (4,542 and 1,459 km2).
The boundary is ours, not an administrative one.

**D20. Pre-1975 reconstruction parameters.** Density is assumed to decline 1.25 % a year from
1890 to 1975 and to be flat before 1890, capped at 500 people per built-up hectare. Angel et al.
(2010) report a peak around 1890 and a decline of "1.0-1.5 percent" a year; the first build used
1.5 %, and the phase 7 cross-check of the paper showed that is the top of the range, so it was
moved to the middle. Holding density flat before 1890 is our simplification (the paper has no
data before 1800).
Ranking is by least-cost distance from the historic core with satellite seeds; see
`docs/DATA_LOG.md`. No historical maps were used as anchors: nothing machine-readable and dated
exists across 50 cities, and hand-georeferencing maps was out of scope for this build. This is the
largest single caveat in the project and the app labels the whole pre-1975 footprint
`reconstructed`.

**D21. The footprint never shrinks.** Buildings have a year built; the reconstruction has no
notion of abandonment. Population collapses (London after 410, Tokyo 1945, Tenochtitlan 1521) are
shown by the population counter and milestone captions only.

**D22. Level of detail instead of one building per cell.** A megacity has 300-400 thousand
built-up cells, above the 50-150k budget. Units are chosen greedily by built volume weighted
toward the core: 400 m blocks split into 200 m blocks, then 100 m cells, then four lots per cell,
until about 90k units. Every unit's footprint area equals the GHSL built surface it stands for.

**D23. Landmark shapes are schematic** (two or three nested boxes by kind). Height, position and
year are the sourced values. Generic buildings on a landmark's site are cleared in its year.

**D24. Building file format.** `public/data/<slug>.bin`: header `CLB1`, uint32 count, then
struct-of-arrays columns x, y (int16, local metres / xy_scale), y0, y1 (int16 years; 32767 = still
standing), h (uint16, decimetres), w, d (uint8, x 2 m), rot (uint8, 180/256 degrees), flags
(uint8, bit 0 = landmark), g (uint8, ground patch side x 2 m). About 1.3 MB per city.

## App (phase 6)

**D25. The timeline is warped.** Each era gets a fixed share of screen time (before 1800: 5-12 s,
1800-1900: 9 s, 1900-1950: 9 s, 1950-1975: 8 s, 1975-2026: 16 s at 1x), with the long pre-1800
stretch compressed toward its start. The scrubber uses the same warp and labels real years.

**D26. Auto camera.** It follows the spreading footprint until 1975 (never pulling back beyond a
14 km radius), then eases in on the tallest part of the city so the skyline's rise is visible.
Any gesture hands the camera to the viewer; a button resumes it.

**D27. True vertical scale by default, with an optional 2x / 4x exaggeration** in the legend,
labelled as such. At metropolitan scale real building heights are a few pixels; the toggle is a
display aid and changes no data.

**D28. Colour encodes the era a building was put up in** (warm = old, cool = recent); landmarks
are gold. New construction glows briefly while playing.

**D29. Present-day geography on the base map.** OpenStreetMap coastlines, rivers and main roads
are shown for every year, faintly. Land reclamation and river engineering are therefore
anachronistic for early years; the About panel says so.

**D30. Reduced detail on slow devices.** If the first seconds of playback average under about 12
frames a second, the app keeps every ground patch (so the footprint still spreads exactly as in
full detail) but extrudes only the 15,000 tallest buildings plus all landmarks. A tag in the
stats panel says so and restores full detail on click; `?detail=low` or `?detail=full` in the URL
forces either mode.

## Verification (phase 7)

**D31. Five independent verifiers plus one method checker.** Checking 500 figures against their
sources is too much for one agent in one run, so the 50 cities were split across five fresh
agents, none of which had produced any data. The 10 figures per city were drawn by a seeded
script (`scripts/07_pick_checks.py`), not chosen by the verifiers. A sixth agent checked the
density citation against the paper, compared our footprints with the Atlas of Urban Expansion,
and sourced start-site coordinates for four cities. Results: `data/verification/`.

**D32. Follow-ups made from the verification findings.**
- The density decline rate was moved from 1.5 % to 1.25 % a year (see D20).
- Seoul, Beijing, Shenzhen and Delhi got a `start_site` (the earliest settlement stood away from
  the later historic core); the reconstruction opens there.
- A verifier found CTBUH floor-count estimates stored as `documented`. A scripted sweep of all
  320 CTBUH pages cited in the project found 10 such heights; the two still marked `documented`
  were changed to `estimated` (`data/verification/_ctbuh_sweep.json`).
- The Atlas comparison shows our 1990-2014 footprints growing far more slowly than the Atlas's
  (median x1.29 against x2.52). GHSL's early epochs probably overstate built-up area. Nothing was
  changed for this; it is recorded as a caveat in `docs/DATA_LOG.md` and the About panel.
