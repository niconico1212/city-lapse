"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MapView, { type Extras, type MapViewHandle } from "./MapView";
import CityPicker from "./CityPicker";
import BottomBar from "./BottomBar";
import AboutPanel from "./AboutPanel";
import { decodeBuildings, ERA_LEGEND, type BuildingBuffers } from "@/lib/buildings";
import { decodeFabric, decodeModels, type ModelFile, type RealIndex } from "@/lib/extras";
import { DEFAULT_STYLE, HISTORIC_STYLES, styleById } from "@/lib/styles";
import { areaAt, buildTimeline, footprintStatus, formatPopulation, formatYear, populationAt } from "@/lib/timeline";
import type { CityData, CityIndex, Milestone } from "@/lib/types";

const DEFAULT_CITY = "tokyo";
const SPEEDS = [0.5, 1, 2, 4];
/** In reduced detail only this many buildings are extruded; the rest show as ground patches. */
const LOW_DETAIL_BUILDINGS = 15_000;

type Detail = "full" | "low";

const NO_EXTRAS: Extras = { fabric: null, models: null, realIndex: null };

function styleFromUrl(): string {
  if (typeof window === "undefined") return DEFAULT_STYLE;
  return styleById(new URLSearchParams(window.location.search).get("style")).id;
}

function detailFromUrl(): Detail | null {
  if (typeof window === "undefined") return null;
  const d = new URLSearchParams(window.location.search).get("detail");
  return d === "low" || d === "full" ? d : null;
}

function slugFromHash(): string | null {
  if (typeof window === "undefined") return null;
  const h = window.location.hash.replace(/^#\/?/, "").trim().toLowerCase();
  return h || null;
}

export default function CityLapseApp() {
  const [index, setIndex] = useState<CityIndex | null>(null);
  const [slug, setSlug] = useState<string | null>(null);
  const [city, setCity] = useState<CityData | null>(null);
  const [buffers, setBuffers] = useState<BuildingBuffers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [autoCamera, setAutoCamera] = useState(true);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [heightScale, setHeightScale] = useState(1);
  const [detail, setDetail] = useState<Detail>("full");
  const [extras, setExtras] = useState<Extras>(NO_EXTRAS);
  const [styleId, setStyleId] = useState<string>(DEFAULT_STYLE);
  const styleRef = useRef(styleById(DEFAULT_STYLE));
  const extrasRaw = useRef<{ fabric?: ArrayBuffer; models?: ModelFile; meta?: CityData }>({});
  const raw = useRef<{ bin: ArrayBuffer; meta: CityData } | null>(null);
  const perf = useRef({ forced: false, samples: [] as number[], decided: false });
  const [hud, setHud] = useState({ year: 2026, seconds: 0 });
  const [caption, setCaption] = useState<{ m: Milestone; key: number } | null>(null);

  const mapRef = useRef<MapViewHandle>(null);
  /** pending start of the film after a city loads; cancelled if the person pauses or scrubs first */
  const autoplay = useRef<number | undefined>(undefined);
  const detailRef = useRef<Detail>("full");
  const clock = useRef({ seconds: 0, playing: false, speed: 1, last: 0, dirtyUntil: 0, lastHud: 0, lastMilestone: -1 });

  const timeline = useMemo(() => (city ? buildTimeline(city.start_year, city.end_year) : null), [city]);

  // ---- city index + hash routing
  useEffect(() => {
    fetch("data/cities.json")
      .then((r) => {
        if (!r.ok) throw new Error(`city list: HTTP ${r.status}`);
        return r.json();
      })
      .then((idx: CityIndex) => {
        setIndex(idx);
        const wanted = slugFromHash();
        const ok = (s: string | null) => idx.cities.find((c) => c.slug === s && c.status !== "missing");
        setSlug((ok(wanted) ?? ok(DEFAULT_CITY) ?? idx.cities.find((c) => c.status !== "missing"))?.slug ?? null);
      })
      .catch((e) => setError(String(e.message ?? e)));
    const onHash = () => {
      const s = slugFromHash();
      if (s) setSlug((cur) => (cur === s ? cur : s));
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // ---- load one city
  useEffect(() => {
    if (!slug || !index) return;
    if (!index.cities.some((c) => c.slug === slug && c.status !== "missing")) {
      setError(`No data for "${slug}".`);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPlaying(false);
    clock.current.playing = false;
    if (window.location.hash !== `#${slug}`) window.history.replaceState(null, "", `#${slug}`);
    (async () => {
      try {
        const meta: CityData = await fetch(`data/${slug}.json`).then((r) => {
          if (!r.ok) throw new Error(`${slug}: HTTP ${r.status}`);
          return r.json();
        });
        const bin = await fetch(`data/${meta.buildings.file}`).then((r) => {
          if (!r.ok) throw new Error(`${slug} buildings: HTTP ${r.status}`);
          return r.arrayBuffer();
        });
        if (cancelled) return;
        raw.current = { bin, meta };
        const forced = detailFromUrl();
        const level: Detail = forced ?? (perf.current.decided ? detailRef.current : "full");
        perf.current.forced = forced !== null;
        perf.current.samples = [];
        if (level !== detailRef.current) {
          detailRef.current = level;
          setDetail(level);
        }
        const decoded = decodeBuildings(bin, meta, level === "low" ? { maxExtruded: LOW_DETAIL_BUILDINGS } : {});
        clock.current.seconds = 0;
        clock.current.lastMilestone = -1;
        clock.current.dirtyUntil = performance.now() + 4000;
        setCaption(null);
        setExtras(NO_EXTRAS);
        extrasRaw.current = { meta };
        // The artistic layers load after the city itself, so the film can start straight away.
        const ex = meta.extras ?? {};
        const late = <T,>(url: string, read: (r: Response) => Promise<T>, apply: (v: T) => void) =>
          fetch(url)
            .then((r) => {
              if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
              return read(r);
            })
            .then((v) => {
              if (cancelled) return;
              apply(v);
              clock.current.dirtyUntil = performance.now() + 2500;
            })
            .catch((e) => console.warn("optional layer failed to load:", e));
        if (ex.fabric) {
          late(`data/${ex.fabric.file}`, (r) => r.arrayBuffer(), (buf) => {
            extrasRaw.current.fabric = buf;
            setExtras((cur) => ({ ...cur, fabric: decodeFabric(buf, meta, styleRef.current) }));
          });
        }
        if (ex.models) {
          late(`data/${ex.models.file}`, (r) => r.json() as Promise<ModelFile>, (file) => {
            extrasRaw.current.models = file;
            setExtras((cur) => ({ ...cur, models: decodeModels(file, meta, styleRef.current) }));
          });
        }
        if (ex.real) {
          late(`data/${ex.real.index}`, (r) => r.json() as Promise<RealIndex>, (idx) => setExtras((cur) => ({ ...cur, realIndex: idx })));
        }
        setBuffers(decoded);
        setCity(meta);
        setHud({ year: meta.start_year, seconds: 0 });
        setAutoCamera(true);
        setLoading(false);
        document.title = `${meta.name} · city-lapse`;
        // start the film shortly after the first frame is on screen
        window.clearTimeout(autoplay.current);
        autoplay.current = window.setTimeout(() => {
          if (!cancelled) {
            clock.current.playing = true;
            setPlaying(true);
          }
        }, 900);
      } catch (e) {
        if (!cancelled) {
          setError(String((e as Error).message ?? e));
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug, index]);

  // ---- the clock: one requestAnimationFrame loop drives the map; React state is only the HUD
  useEffect(() => {
    if (!timeline || !city) return;
    let raf = 0;
    const c = clock.current;
    c.last = performance.now();
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const rawDt = (now - c.last) / 1000;
      const dt = Math.min(0.25, rawDt);
      c.last = now;
      // Slow device? If the first couple of seconds of playback average under about 12 frames a
      // second at full detail, switch to reduced detail (fewer extruded buildings) for the session.
      const p = perf.current;
      if (c.playing && !p.forced && !p.decided && detailRef.current === "full" && rawDt < 2) {
        p.samples.push(rawDt);
        const total = p.samples.reduce((a, b) => a + b, 0);
        if (total > 2.5) {
          p.decided = true;
          if (total / p.samples.length > 0.085 && raw.current) {
            detailRef.current = "low";
            setDetail("low");
            setBuffers(decodeBuildings(raw.current.bin, raw.current.meta, { maxExtruded: LOW_DETAIL_BUILDINGS }));
          }
        }
      }
      if (c.playing) {
        c.seconds += dt * c.speed;
        if (c.seconds >= timeline.duration) {
          c.seconds = timeline.duration;
          c.playing = false;
          setPlaying(false);
        }
        c.dirtyUntil = now + 2500;
      }
      if (now > c.dirtyUntil) return; // paused and settled: draw nothing
      const year = timeline.yearAt(c.seconds);
      const ahead = timeline.yearAt(Math.min(timeline.duration, c.seconds + 0.1 * c.speed));
      const yearsPerSecond = c.playing ? Math.max(0.5, (ahead - year) / 0.1) : 1.5;
      mapRef.current?.frame(year, yearsPerSecond, c.playing, dt);
      if (now - c.lastHud > 50) {
        c.lastHud = now;
        setHud({ year, seconds: c.seconds });
        // milestone captions: show the one we have just passed
        let i = -1;
        for (let k = 0; k < city.milestones.length; k++) if (city.milestones[k].year <= year) i = k;
        if (i !== c.lastMilestone) {
          c.lastMilestone = i;
          setCaption(i >= 0 ? { m: city.milestones[i], key: now } : null);
        }
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [timeline, city]);

  // captions fade out a few seconds after their year passes while playing
  useEffect(() => {
    if (!caption || !playing) return;
    const id = window.setTimeout(() => setCaption((cur) => (cur && cur.key === caption.key ? null : cur)), 6500);
    return () => window.clearTimeout(id);
  }, [caption, playing]);

  const poke = useCallback(() => {
    clock.current.dirtyUntil = performance.now() + 2500;
  }, []);

  useEffect(() => {
    setStyleId(styleFromUrl());
  }, []);

  // Changing the historic style recolours the generated houses and the landmark models.
  useEffect(() => {
    const st = styleById(styleId);
    styleRef.current = st;
    const rawEx = extrasRaw.current;
    if (!rawEx.meta) return;
    const meta = rawEx.meta;
    setExtras((cur) => ({
      ...cur,
      fabric: rawEx.fabric ? decodeFabric(rawEx.fabric, meta, st) : cur.fabric,
      models: rawEx.models ? decodeModels(rawEx.models, meta, st) : cur.models,
    }));
    poke();
  }, [styleId, poke]);

  const togglePlay = useCallback(() => {
    const c = clock.current;
    if (!timeline) return;
    window.clearTimeout(autoplay.current);
    if (!c.playing && c.seconds >= timeline.duration - 0.01) {
      c.seconds = 0;
      c.lastMilestone = -1;
    }
    c.playing = !c.playing;
    setPlaying(c.playing);
    poke();
  }, [timeline]);

  const seek = useCallback((seconds: number) => {
    window.clearTimeout(autoplay.current);
    clock.current.seconds = seconds;
    poke();
  }, []);

  const changeSpeed = useCallback((s: number) => {
    clock.current.speed = s;
    setSpeed(s);
  }, []);

  const chooseCity = useCallback((s: string) => {
    setSlug(s);
    window.location.hash = s;
  }, []);

  // Small console/testing handle: window.__cityLapse.seekYear(1900), .pause(), .play(), .state()
  useEffect(() => {
    if (!timeline) return;
    (window as unknown as { __cityLapse?: unknown }).__cityLapse = {
      seekYear: (y: number) => seek(timeline.secondsAt(y)),
      seekFraction: (f: number) => seek(f * timeline.duration),
      pause: () => {
        window.clearTimeout(autoplay.current);
        clock.current.playing = false;
        setPlaying(false);
      },
      play: () => {
        clock.current.playing = true;
        setPlaying(true);
      },
      freeCamera: () => setAutoCamera(false),
      setStyle: (id: string) => setStyleId(id),
      state: () => ({ seconds: clock.current.seconds, duration: timeline.duration, year: timeline.yearAt(clock.current.seconds), playing: clock.current.playing }),
    };
  }, [timeline, seek]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if ((e.code === "ArrowRight" || e.code === "ArrowLeft") && timeline) {
        const step = (e.code === "ArrowRight" ? 1 : -1) * timeline.duration * 0.02;
        seek(Math.min(timeline.duration, Math.max(0, clock.current.seconds + step)));
      } else if (e.code === "Escape") {
        setAboutOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, seek, timeline]);

  const pop = city ? populationAt(city.population, hud.year) : null;
  const area = city ? areaAt(city, hud.year) : null;
  const fp = city ? footprintStatus(city, hud.year) : null;
  const entry = index?.cities.find((c) => c.slug === slug) ?? null;

  return (
    <main className="app">
      <MapView
        ref={mapRef}
        city={city}
        buffers={buffers}
        autoCamera={autoCamera}
        heightScale={heightScale}
        extras={extras}
        style={styleById(styleId)}
        fullDetail={detail === "full"}
        requestFrames={poke}
        onUserCamera={() => setAutoCamera(false)}
      />

      <header className="topbar">
        <div className="brand" title="city-lapse">
          <span className="brand-mark" aria-hidden />
          <span className="brand-name">city-lapse</span>
        </div>
        <CityPicker index={index} current={entry} onChoose={chooseCity} />
        <button className="ghost-btn" onClick={() => setAboutOpen(true)} disabled={!city}>
          About the data
        </button>
      </header>

      {city && pop && fp && (
        <section className="stats" aria-live="off">
          <div className="stat">
            <div className="stat-label">Population</div>
            <div className="stat-value">{pop.value === null ? "—" : formatPopulation(pop.value)}</div>
            <div className={`tag ${pop.confidence ?? "none"}`}>{pop.label}</div>
            {pop.definition && <div className="stat-note">{pop.definition}</div>}
          </div>
          <div className="stat">
            <div className="stat-label">Built-up area</div>
            <div className="stat-value small">
              {area === null ? "—" : area < 10 ? `${area.toFixed(1)} km²` : `${Math.round(area).toLocaleString("en-US")} km²`}
            </div>
            <div className={`tag ${fp.reconstructed ? "reconstructed" : "documented"}`}>{fp.label}</div>
          </div>
          {detail === "low" && (
            <button
              className="tag detail-tag"
              title="This device was drawing slowly, so only the tallest buildings are shown in 3D. Click for full detail."
              onClick={() => {
                if (!raw.current) return;
                perf.current.decided = true;
                detailRef.current = "full";
                setDetail("full");
                setBuffers(decodeBuildings(raw.current.bin, raw.current.meta));
                poke();
              }}
            >
              Reduced detail · show all
            </button>
          )}
          {city.status === "partial" && (
            <div className="tag partial" title={city.status_reasons.join("; ")}>
              Partial data · see About
            </div>
          )}
        </section>
      )}

      {city && (
        <aside className="legend" aria-label="Colour legend">
          <div className="legend-title">Built in</div>
          <div className="legend-ramp">
            {ERA_LEGEND.map((e) => (
              <span key={e.year} style={{ background: `rgb(${e.rgb.join(",")})` }} />
            ))}
          </div>
          <div className="legend-scale">
            <span>before 1700</span>
            <span>today</span>
          </div>
          <div className="legend-row">
            <span className="swatch landmark" /> Landmark (real height)
          </div>
          {city.extras?.fabric && (
            <>
              <div className="legend-title vscale-title" title="How the city before satellite records is drawn. An artist's impression: it changes the look, not the data.">
                Historic style
              </div>
              <div className="vscale" role="group" aria-label="Historic style">
                {HISTORIC_STYLES.map((st) => (
                  <button key={st.id} className={st.id === styleId ? "on" : ""} aria-pressed={st.id === styleId} title={st.blurb} onClick={() => setStyleId(st.id)}>
                    {st.name}
                  </button>
                ))}
              </div>
            </>
          )}
          <div className="legend-title vscale-title">Vertical scale</div>
          <div className="vscale" role="group" aria-label="Vertical scale">
            {[1, 2, 4].map((v) => (
              <button
                key={v}
                className={v === heightScale ? "on" : ""}
                aria-pressed={v === heightScale}
                title={v === 1 ? "True scale" : `Heights drawn ${v} times taller than real, to read better from far away`}
                onClick={() => {
                  setHeightScale(v);
                  poke();
                }}
              >
                {v === 1 ? "true" : `${v}×`}
              </button>
            ))}
          </div>
        </aside>
      )}

      {caption && (
        <div className="caption" key={caption.key}>
          <div className="caption-year">{formatYear(caption.m.year)}</div>
          <div className="caption-title">{caption.m.title}</div>
          <div className="caption-detail">{caption.m.detail}</div>
        </div>
      )}

      {!autoCamera && city && (
        <button
          className="recenter"
          onClick={() => {
            mapRef.current?.resumeAutoCamera();
            setAutoCamera(true);
            poke();
          }}
        >
          Resume auto camera
        </button>
      )}

      {city && timeline && (
        <BottomBar
          city={city}
          timeline={timeline}
          seconds={hud.seconds}
          year={hud.year}
          playing={playing}
          speed={speed}
          speeds={SPEEDS}
          onTogglePlay={togglePlay}
          onSeek={seek}
          onSpeed={changeSpeed}
        />
      )}

      {(loading || error) && (
        <div className="veil" role="status">
          {error ? (
            <div className="veil-box">
              <strong>Could not load this city.</strong>
              <span>{error}</span>
            </div>
          ) : (
            <div className="veil-box">
              <span className="spinner" aria-hidden />
              <span>Loading {entry ? entry.name : "city"}…</span>
            </div>
          )}
        </div>
      )}

      {aboutOpen && city && index && <AboutPanel city={city} index={index} realIndex={extras.realIndex} onClose={() => setAboutOpen(false)} />}
    </main>
  );
}
