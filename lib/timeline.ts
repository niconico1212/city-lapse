import type { CityData, Confidence, PopulationPoint } from "./types";

/**
 * Each city runs on its own clock, from its start year to 2026. Playing that span at a constant
 * number of years per second would spend almost the whole film in eras where little changes and
 * then rush the last century, so the timeline is warped: every era gets a fixed share of screen
 * time. The scrubber and the tick labels use the same warp, so what you see is what you scrub.
 */
export interface Timeline {
  start: number;
  end: number;
  /** total duration in seconds at 1x speed */
  duration: number;
  /** seconds (at 1x) -> year */
  yearAt(seconds: number): number;
  /** year -> seconds (at 1x) */
  secondsAt(year: number): number;
  /** years for scrubber tick labels */
  ticks: number[];
}

interface Segment {
  y0: number;
  y1: number;
  t0: number;
  t1: number;
  /** >1 compresses the early part of the segment (used for the long pre-1800 stretch) */
  power: number;
}

const ERAS: { from: number; to: number; seconds: number }[] = [
  { from: -Infinity, to: 1800, seconds: 12 },
  { from: 1800, to: 1900, seconds: 9 },
  { from: 1900, to: 1950, seconds: 9 },
  { from: 1950, to: 1975, seconds: 8 },
  { from: 1975, to: 2026, seconds: 16 },
];

export function buildTimeline(start: number, end: number): Timeline {
  const segs: Segment[] = [];
  let t = 0;
  for (const era of ERAS) {
    const y0 = Math.max(start, era.from);
    const y1 = Math.min(end, era.to);
    if (y1 <= y0) continue;
    let seconds: number;
    let power = 1;
    if (era.from === -Infinity) {
      const span = y1 - y0;
      seconds = 5 + 7 * Math.min(1, span / 1500);
      power = 1 + Math.min(2, span / 800);
    } else {
      seconds = Math.max(2.5, era.seconds * ((y1 - y0) / (era.to - era.from)));
    }
    segs.push({ y0, y1, t0: t, t1: t + seconds, power });
    t += seconds;
  }
  const duration = t;

  const yearAt = (seconds: number) => {
    const s = Math.min(Math.max(seconds, 0), duration);
    const seg = segs.find((g) => s <= g.t1) ?? segs[segs.length - 1];
    const v = (s - seg.t0) / (seg.t1 - seg.t0);
    // year = y1 - span * (1 - v)^power: fast through the distant past, slowing towards y1
    return seg.y1 - (seg.y1 - seg.y0) * Math.pow(1 - v, seg.power);
  };

  const secondsAt = (year: number) => {
    const y = Math.min(Math.max(year, start), end);
    const seg = segs.find((g) => y <= g.y1) ?? segs[segs.length - 1];
    const v = 1 - Math.pow((seg.y1 - y) / (seg.y1 - seg.y0), 1 / seg.power);
    return seg.t0 + v * (seg.t1 - seg.t0);
  };

  const candidates = [-3000, -2000, -1000, -500, 1, 500, 1000, 1200, 1400, 1500, 1600, 1700, 1800, 1850, 1900, 1925, 1950, 1975, 2000];
  const ticks: number[] = [];
  let last = -Infinity;
  for (const y of [start, ...candidates.filter((c) => c > start && c < end), end]) {
    const s = secondsAt(y) / duration;
    // the first label is left-aligned and so reaches further right: give it more room
    const room = ticks.length === 1 ? 0.13 : 0.09;
    if (s - last >= room || y === end) {
      if (y === end && ticks.length > 1 && 1 - last < 0.09) ticks.pop();
      ticks.push(y);
      last = s;
    }
  }
  return { start, end, duration, yearAt, secondsAt, ticks };
}

export function formatYear(year: number): string {
  const y = Math.floor(year);
  if (y < 0) return `${-y} BCE`;
  if (y < 1000) return `${Math.max(y, 1)} CE`;
  return String(y);
}

export function formatPopulation(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toFixed(v >= 1e7 ? 1 : 2)} million`;
  if (v >= 1e4) return `${Math.round(v / 1000).toLocaleString("en-US")},000`;
  if (v >= 1000) return `${(Math.round(v / 100) * 100).toLocaleString("en-US")}`;
  return String(Math.round(v / 10) * 10);
}

export interface PopulationReading {
  /** null when there is no sourced estimate yet */
  value: number | null;
  confidence: Confidence | null;
  /** what the label under the counter should say */
  label: string;
  definition: string | null;
  /** the sourced points on either side */
  before: PopulationPoint | null;
  after: PopulationPoint | null;
}

const RANK: Record<Confidence, number> = { documented: 0, estimated: 1, reconstructed: 2 };

/**
 * Population at a given year. Between two sourced points the value is a log-linear
 * interpolation, which is our own reconstruction unless the year falls exactly on a point, and
 * the label says so. Before the first sourced point there is no number at all.
 */
export function populationAt(points: PopulationPoint[], year: number): PopulationReading {
  if (!points.length || year < points[0].year) {
    return {
      value: null,
      confidence: null,
      label: points.length ? `No reliable estimate before ${formatYear(points[0].year)}` : "No reliable estimate",
      definition: null,
      before: null,
      after: points[0] ?? null,
    };
  }
  let i = 0;
  while (i + 1 < points.length && points[i + 1].year <= year) i++;
  const a = points[i];
  const b = points[i + 1] ?? null;
  if (!b || Math.floor(year) === a.year) {
    return { value: a.value, confidence: a.confidence, label: labelFor(a.confidence, false), definition: a.definition ?? null, before: a, after: b };
  }
  const f = (year - a.year) / (b.year - a.year);
  const value = Math.exp(Math.log(Math.max(a.value, 1)) * (1 - f) + Math.log(Math.max(b.value, 1)) * f);
  const worst: Confidence = RANK[a.confidence] >= RANK[b.confidence] ? a.confidence : b.confidence;
  // A short hop between two counted or estimated figures stays at their confidence;
  // a long gap, or any reconstructed endpoint, is flagged as a reconstruction.
  const gap = b.year - a.year;
  const confidence: Confidence = worst === "reconstructed" || gap > 30 ? "reconstructed" : worst === "documented" ? "estimated" : worst;
  return {
    value,
    confidence,
    label: labelFor(confidence, true, a, b),
    definition: (f < 0.5 ? a.definition : b.definition) ?? null,
    before: a,
    after: b,
  };
}

function labelFor(c: Confidence, interpolated: boolean, a?: PopulationPoint, b?: PopulationPoint): string {
  if (c === "reconstructed") {
    return a && b ? `Reconstructed estimate · interpolated ${formatYear(a.year)} to ${formatYear(b.year)}` : "Reconstructed estimate";
  }
  if (c === "estimated") return interpolated ? "Estimate · between sourced figures" : "Estimate";
  return "Documented count";
}

/** Footprint provenance at a year: GHSL from 1975, our reconstruction before. */
export function footprintStatus(city: CityData, year: number): { label: string; reconstructed: boolean } {
  if (year >= 2021) return { label: "Footprint: GHSL projection (2025 epoch)", reconstructed: false };
  if (year >= 1975) return { label: "Footprint: GHSL satellite record", reconstructed: false };
  return { label: "Footprint: reconstructed from the 1975 extent", reconstructed: true };
}

export function areaAt(city: CityData, year: number): number | null {
  const e = city.footprint.epochs;
  if (!e.length || year < e[0].year) return null;
  let i = 0;
  while (i + 1 < e.length && e[i + 1].year <= year) i++;
  const a = e[i];
  const b = e[i + 1];
  if (!b) return a.area_km2;
  const f = (year - a.year) / (b.year - a.year);
  return a.area_km2 + f * (b.area_km2 - a.area_km2);
}
