# Verification brief (phase 7)

You are an independent verifier. You did not produce any of the data in
`data/cities/`; research agents did. Your job is to spot-check it against the
sources it cites and to fix or flag what does not hold up.

## What to check

`data/verification/_sample.json` holds, for each city, 10 figures drawn at
random by `scripts/07_pick_checks.py`: the start year, and a mix of population
points, landmarks and milestones. Check exactly those items for the cities you
are assigned. Each item has the claim and the source the researcher cited.

For each item:

1. Open the cited source (the URL in `source`; if it cites a book "via" a web
   page, open the web page). If it is unreachable, find another reputable
   source for the same fact and use that.
2. Compare. For a population point: the number, the year, and the area it
   covers. For a landmark: completion year, height in metres, and that the
   coordinates are on the structure (within about 300 m). For a milestone or
   start: the year and that the event is described correctly.
3. Record one of these results:

| Result | When | What you do to the data |
|---|---|---|
| `confirmed` | The source (or an equally good one) states the figure. Small rounding differences are fine. | Nothing. |
| `corrected` | The source clearly gives a different value, or the citation was wrong but the fact can be fixed from a good source. | Edit `data/cities/<slug>.json`: fix the value and/or the `source`, and add or extend the point's `note` with what changed. |
| `flagged` | The claim is doubtful, contested between good sources, or the cited source does not actually support it and you could not settle it. | Lower `confidence` if warranted (for example `documented` to `estimated`) and add a `note` saying why. Do not delete it. |
| `removed` | The figure is wrong and you cannot find a correct one, or a landmark's height has no real source. | Delete the data point from the city file. |
| `unverifiable` | You could not reach the cited source or any substitute after reasonable effort. | Nothing. Say what you tried. |

Rules:

- Record only what you saw on a page you opened in this session. Do not
  confirm from memory.
- Edit only the items you were asked to check, plus anything in the same city
  file that you notice is plainly wrong while you are there (record those as
  extra checks). Do not rewrite files wholesale, do not touch points with a
  `"series"` key (the UN series, merged by script), and do not reformat.
- Keep the JSON valid and the lists in chronological order. After editing a
  city file run:
  `/home/user/city-lapse/.venv/bin/python /home/user/city-lapse/scripts/validate_city.py --merged <slug>`
- Do not run git. Do not edit any file other than `data/cities/<slug>.json`
  for your cities and your own `data/verification/<slug>.json` files.
- Tools: WebSearch and WebFetch, or curl from Bash. Do not use Firecrawl (out
  of credits). Wikipedia rate-limits bursts: space requests out, and prefer
  `curl -sL "https://en.wikipedia.org/w/index.php?title=TITLE&action=raw"`
  with a pause between calls. If it returns 429, wait a minute and go on to
  another item meanwhile.
- Budget your effort: about 10 items per city, a few minutes each. If an item
  is eating time, mark it `unverifiable` with what you tried and move on.

## What to write

One file per city, `data/verification/<slug>.json`:

```json
{
  "slug": "tokyo",
  "verified_by": "independent verification agent (phase 7)",
  "date": "2026-11-18",
  "checks": [
    {
      "kind": "population",
      "item": "population 1,084,745 in 1880 (documented)",
      "source_opened": "https://...",
      "found": "what that page actually says, briefly",
      "result": "confirmed",
      "detail": "one sentence; for corrected/flagged/removed, say exactly what you changed"
    }
  ],
  "summary": "One or two sentences on how the city's data held up."
}
```

`item` should be the claim text from the sample (shortened if long).

Your final reply to the orchestrator: under 200 words. Per city, the counts of
each result and a one-line description of anything corrected, flagged or
removed. No data dump.
