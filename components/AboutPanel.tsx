"use client";

import { Fragment, useEffect, useRef, type ReactNode } from "react";
import { formatYear } from "@/lib/timeline";
import type { CityData, CityIndex, Confidence } from "@/lib/types";
import type { RealIndex } from "@/lib/extras";

/** Turn the URLs inside a citation string into links, leaving the rest as text. */
function Cite({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  const re = /https?:\/\/[^\s)\]>,;"']+/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const url = m[0].replace(/[.]+$/, "");
    let host = url;
    try {
      host = new URL(url).hostname.replace(/^www\./, "");
    } catch {
      /* keep raw */
    }
    parts.push(
      <a key={m.index} href={url} target="_blank" rel="noreferrer noopener">
        {host}
      </a>,
    );
    last = m.index + url.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <span className="cite">{parts.map((p, i) => <Fragment key={i}>{p}</Fragment>)}</span>;
}

function Conf({ c }: { c: Confidence }) {
  return <span className={`tag ${c}`}>{c}</span>;
}

export default function AboutPanel({ city, index, realIndex, onClose }: { city: CityData; index: CityIndex; realIndex?: RealIndex | null; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  const r = city.footprint.reconstruction;
  const counts = { documented: 0, estimated: 0, reconstructed: 0 };
  for (const p of city.population) counts[p.confidence]++;

  return (
    <div className="about-wrap" onClick={onClose}>
      <aside className="about" role="dialog" aria-modal="true" aria-label={`About the data: ${city.name}`} tabIndex={-1} ref={ref} onClick={(e) => e.stopPropagation()}>
        <header>
          <div>
            <h2>
              {city.name} <small>{city.country}</small>
            </h2>
            <p className="about-sub">
              Rank {city.rank} of 50 by 2025 population ({(city.population_2025 / 1e6).toFixed(1)} million; the UN lists it as “{city.un_name}”).
            </p>
          </div>
          <button className="ghost-btn" onClick={onClose} aria-label="Close">
            Close
          </button>
        </header>

        {city.status === "partial" && (
          <section className="callout">
            <strong>Partial data.</strong> {city.status_reasons.join(". ")}.
          </section>
        )}

        <section>
          <h3>How this was made</h3>
          <p>
            What you are watching is an honest procedural fill, not a survey of every building. Three things are real:
            where the built-up area was at each point in time, how tall the city is on average in each 100 m cell
            today, and every landmark’s position, height and completion year. The individual generic buildings are
            generated to match those facts.
          </p>
          <ul>
            <li>
              <strong>Footprint, 1975 to 2025.</strong> From the Global Human Settlement Layer (GHS-BUILT-S), which maps
              built surface every five years from satellite imagery. A 100 m cell counts as built-up once at least 5 %
              of it is covered. The 2025 epoch is a GHSL projection.
            </li>
            <li>
              <strong>Footprint before 1975: reconstructed.</strong> No global map exists, so the 1975 footprint is
              contracted backward toward the historic core ({r.historic_core.name}). The area for each year is scaled
              from the population series and era-typical density (cities are taken to have been denser in the past:
              1.25 % a year back to 1890, the middle of the range in Angel et al. 2010, and constant before that); cells closest to the core, and most densely built in 1975, are assumed
              oldest. The footprint never shrinks, so wars and plagues show in the population counter only. This is a
              model, and the timeline marks it as reconstructed.
            </li>
            <li>
              <strong>Heights.</strong> Present-day heights are calibrated to GHS-BUILT-H (average building height per
              cell, 2018). Earlier generations of buildings are capped by era (almost nothing above 30 m before 1900)
              and replaced by taller ones later, so the core densifies over time.
            </li>
            <li>
              <strong>Landmarks</strong> stand at their real coordinates with their real heights and appear in their
              completion year. Their shapes are schematic.
            </li>
            <li>
              <strong>Base map.</strong> Today’s coastline, rivers and main roads (OpenStreetMap via OpenFreeMap) are
              shown throughout as orientation; they are not redrawn for earlier centuries.
            </li>
            <li>
              <strong>Timeline.</strong> Early centuries are compressed so the film spends its time where the city
              changes most. The tick labels show the real years.
            </li>
          </ul>
        </section>

        {city.extras && (city.extras.fabric || city.extras.real || city.extras.models) && (
          <section>
            <h3>Artistic layers in {city.name}</h3>
            <p>
              {city.name} has three extra layers. They change how the city is drawn, not the data behind it, and each
              is labelled here for what it is.
            </p>
            <ul>
              {city.extras.models && (
                <li>
                  <strong>Landmark models: real facts, schematic shapes.</strong> Position, height and completion year
                  are the sourced values. The shapes are simple massings built from published dimensions (base width,
                  deck heights, tiers) where those were found, and default proportions where they were not. Each model
                  goes up over its real construction period where the start year was sourced.
                </li>
              )}
              {city.extras.real && (
                <li>
                  <strong>Real building shapes from 1975: zoom in.</strong> When you are zoomed in, the generated boxes
                  give way to today’s real building footprints and measured heights
                  {realIndex ? ` (${realIndex.stats.buildings.toLocaleString("en-US")} buildings; ${realIndex.source.name}, ${realIndex.source.publisher})` : ""}.
                  They are untextured. <strong>Their construction years are mostly not recorded</strong>
                  {realIndex
                    ? `: ${realIndex.stats.dated_documented.toLocaleString("en-US")} tall buildings are dated from Wikidata, ${realIndex.stats.dated_ghsl_epoch.toLocaleString("en-US")} by the satellite epoch in which their block was first built up, and the remaining ${realIndex.stats.dated_generated.toLocaleString("en-US")} are placed by rule: low buildings appear around 1975, taller ones in a generated year between 1975 and 2020`
                    : ""}
                  . A building always wears its present-day shape, including in years when something else stood on the
                  lot. Footprints include podiums, so some towers are drawn wider than they are.
                </li>
              )}
              {city.extras.fabric && (
                <li>
                  <strong>Before 1900: an artist’s impression.</strong> {city.extras.fabric.count.toLocaleString("en-US")} low
                  roofed houses are generated for the blocks the reconstruction places inside the city before 1900, and
                  stand until a generated modernisation year between 1900 and 1965. They show the kind of fabric the
                  city had, not actual buildings or the real street plan. The historic style (woodblock, ink or
                  lantern) recolours them and the base map and fades into the modern map by 1960.
                </li>
              )}
            </ul>
            {realIndex && (
              <p className="src">
                <Cite text={`${realIndex.source.name}. ${realIndex.source.url} Derived from ${realIndex.source.derived}. Licence: ${realIndex.source.licence}`} />
              </p>
            )}
          </section>
        )}

        <section>
          <h3>Start of the timeline</h3>
          <p>
            <strong>{formatYear(city.start_year)}</strong> · {city.start_label} <Conf c={city.start_confidence} />
          </p>
          <p className="src">
            <Cite text={city.start_source} />
          </p>
        </section>

        <section>
          <h3>Notes, gaps and caveats for {city.name}</h3>
          <p>{city.notes}</p>
        </section>

        <section>
          <h3>Population</h3>
          <p>
            {counts.documented} documented, {counts.estimated} estimated and {counts.reconstructed} reconstructed points.
            Between points the counter interpolates and says so. The area counted changes over time: early figures
            cover the historical city as each source defined it, the decades from 1950 use the UN’s 2018 urban
            agglomerations, and from 1975 (later for a few cities, as marked in the table) the UN’s 2025 urban
            extents, which are often much wider. A jump where the series switch reflects that change of definition,
            not a sudden influx.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Population</th>
                  <th>Confidence</th>
                  <th>Source and scope</th>
                </tr>
              </thead>
              <tbody>
                {city.population.map((p) => (
                  <tr key={p.year}>
                    <td>{formatYear(p.year)}</td>
                    <td className="num">{p.value.toLocaleString("en-US")}</td>
                    <td>
                      <Conf c={p.confidence} />
                    </td>
                    <td>
                      <Cite text={p.source} />
                      {p.definition && <div className="scope">Area: {p.definition}</div>}
                      {p.note && <div className="scope">{p.note}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h3>Built-up footprint</h3>
          <p>
            Extent: GHSL urban centre “{city.footprint.urban_centre.name}” ({Math.round(city.footprint.urban_centre.area_km2).toLocaleString("en-US")} km²).
            {city.footprint.shared_urban_centre_split &&
              ` GHSL maps this city and ${city.footprint.shared_urban_centre_split.with} as one continuous urban centre; it is split here by weighted distance to the two centres so that each share matches the land area the UN publishes.`}{" "}
            Reconstruction basis: {r.population_basis}. Density in 1975: {r.density_1975_per_ha} people per built-up
            hectare{r.satellite_seeds.length ? `; ${r.satellite_seeds.length} secondary centres treated as satellite towns` : ""}.
            {r.start_site && !r.start_site.unused ? ` The earliest settlement is placed at ${r.start_site.name}.` : ""} GHSL’s 1975
            epoch is itself a back-cast from later imagery and tends to overstate how much was built in 1975 in
            cities that grew fast afterwards.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Built-up area</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {city.footprint.epochs.map((e) => (
                  <tr key={e.year}>
                    <td>{formatYear(e.year)}</td>
                    <td className="num">{e.area_km2.toLocaleString("en-US")} km²</td>
                    <td>
                      <Conf c={e.confidence} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="src">
            <Cite text={city.footprint.sources.built_surface} />
            <br />
            <Cite text={city.footprint.sources.building_height} />
            <br />
            <Cite text={city.footprint.sources.extent} />
            <br />
            Angel S., Parent J., Civco D. L., Blei A. M. (2010), The Persistent Decline in Urban Densities: Global and
            Historical Evidence of Sprawl, Lincoln Institute of Land Policy working paper.
          </p>
          <p>
            {city.buildings.generic.toLocaleString("en-US")} generated building instances from {city.buildings.cells.toLocaleString("en-US")} built-up
            cells; {city.landmarks.length} landmarks.
          </p>
        </section>

        <section>
          <h3>Milestones</h3>
          <ul className="rows">
            {city.milestones.map((m, i) => (
              <li key={i}>
                <div>
                  <strong>{formatYear(m.year)}</strong> · {m.title} <Conf c={m.confidence} />
                </div>
                <div className="src">
                  <Cite text={m.source} />
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3>Landmarks</h3>
          <ul className="rows">
            {city.landmarks.map((l, i) => (
              <li key={i}>
                <div>
                  <strong>{l.name}</strong> · {formatYear(l.year)} · {l.height_m} m{l.demolished_year ? ` · gone by ${formatYear(l.demolished_year)}` : ""}{" "}
                  <Conf c={l.confidence} />
                </div>
                <div className="src">
                  <Cite text={l.source} />
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3>Which cities, and why these 50</h3>
          <p>
            The list is the top 50 of {index.ranking_source.title} <Cite text={index.ranking_source.url} />. {index.ranking_source.definition} That
            definition produces some entries that differ from older lists: Jakarta and Dhaka rank above Tokyo, and
            Hajipur in Bihar appears because the dense, continuously settled belt around it counts as one city.
          </p>
        </section>
      </aside>
    </div>
  );
}
