import type { CityData } from "./types";

const EARTH_R = 6_371_008.8;
const DEG = Math.PI / 180;
export const NO_END = 32767;

/** Typed arrays ready to hand to deck.gl's SolidPolygonLayer as binary attributes. */
export interface BuildingBuffers {
  count: number;
  vertexCount: number;
  /** lon/lat per vertex, 5 vertices per building (closed, clockwise ring) */
  positions: Float64Array;
  startIndices: Uint32Array;
  elevations: Float32Array;
  colors: Uint8Array;
  /** [year built, year replaced] per vertex */
  life: Float32Array;
  /** flat ground patches: the built-up cells each building stands for */
  ground: {
    count: number;
    positions: Float64Array;
    startIndices: Uint32Array;
    colors: Uint8Array;
    life: Float32Array;
  };
}

/** Colour by the era a building was put up in: warm for old fabric, cool for recent. */
const ERA_COLORS: [number, [number, number, number]][] = [
  [-10000, [168, 112, 86]],
  [1700, [176, 120, 90]],
  [1850, [198, 150, 108]],
  [1920, [212, 184, 142]],
  [1960, [208, 204, 190]],
  [1990, [176, 198, 214]],
  [2026, [150, 196, 232]],
];
export const ERA_LEGEND = ERA_COLORS.slice(1).map(([year, rgb]) => ({ year, rgb }));
const LANDMARK_COLOR: [number, number, number] = [255, 190, 92];

function eraColor(year: number, out: [number, number, number]) {
  let i = 0;
  while (i + 1 < ERA_COLORS.length && ERA_COLORS[i + 1][0] <= year) i++;
  const [ya, a] = ERA_COLORS[i];
  const next = ERA_COLORS[i + 1];
  if (!next) {
    out[0] = a[0];
    out[1] = a[1];
    out[2] = a[2];
    return;
  }
  const f = (year - ya) / (next[0] - ya);
  out[0] = a[0] + (next[1][0] - a[0]) * f;
  out[1] = a[1] + (next[1][1] - a[1]) * f;
  out[2] = a[2] + (next[1][2] - a[2]) * f;
}

/**
 * Decode public/data/<slug>.bin (see scripts/04_buildings.py for the layout) into rectangles in
 * lon/lat. Positions are stored as metres east/north of the city centre on a local
 * equirectangular plane; this inverts exactly the mapping the pipeline used.
 */
export interface DecodeOptions {
  /**
   * Draw at most this many buildings in 3D (the tallest ones, plus every landmark). The rest are
   * still shown by their ground patches. Used as the reduced-detail mode on slow devices.
   */
  maxExtruded?: number;
}

export function decodeBuildings(buf: ArrayBuffer, city: CityData, options: DecodeOptions = {}): BuildingBuffers {
  const view = new DataView(buf);
  const magic = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
  if (magic !== "CLB1") throw new Error(`unexpected building file header "${magic}"`);
  const n = view.getUint32(4, true);
  let off = 8;
  const i16 = () => {
    const a = new Int16Array(buf.slice(off, off + n * 2));
    off += n * 2;
    return a;
  };
  const u16 = () => {
    const a = new Uint16Array(buf.slice(off, off + n * 2));
    off += n * 2;
    return a;
  };
  const u8 = () => {
    const a = new Uint8Array(buf, off, n);
    off += n;
    return a;
  };
  const x = i16();
  const y = i16();
  const y0 = i16();
  const y1 = i16();
  const h = u16();
  const w = u8();
  const d = u8();
  const rot = u8();
  const flags = u8();
  const ground = city.buildings.layout.includes("g") ? u8() : new Uint8Array(n);

  const { xy_scale: xyScale, wd_unit: wdUnit } = city.buildings;
  const groundUnit = city.buildings.ground_unit ?? 2;
  const lon0 = city.center.lon;
  const lat0 = city.center.lat;
  const mPerDegLat = DEG * EARTH_R;
  const mPerDegLon = mPerDegLat * Math.cos(lat0 * DEG);

  // Reduced detail: keep only buildings at or above the height that leaves about maxExtruded.
  let minHeight = 0;
  if (options.maxExtruded && options.maxExtruded < n) {
    const sorted = Uint16Array.from(h).sort();
    minHeight = sorted[n - options.maxExtruded];
  }
  let kept = 0;
  for (let i = 0; i < n; i++) if (h[i] >= minHeight || (flags[i] & 1) === 1) kept++;

  const vertexCount = kept * 5;
  const positions = new Float64Array(vertexCount * 2);
  const startIndices = new Uint32Array(kept + 1);
  const elevations = new Float32Array(vertexCount);
  const colors = new Uint8Array(vertexCount * 4);
  const life = new Float32Array(vertexCount * 2);
  const rgb: [number, number, number] = [0, 0, 0];
  let nGround = 0;
  for (let i = 0; i < n; i++) if (ground[i] > 0) nGround++;
  const gPositions = new Float64Array(nGround * 10);
  const gStart = new Uint32Array(nGround + 1);
  const gColors = new Uint8Array(nGround * 20);
  const gLife = new Float32Array(nGround * 10);
  let gi = 0;
  let bi = 0;
  // corner order gives a clockwise ring (deck.gl's expected outer winding with _normalize: false)
  const cx = [-1, -1, 1, 1, -1];
  const cy = [-1, 1, 1, -1, -1];

  for (let i = 0; i < n; i++) {
    const px = x[i] * xyScale;
    const py = y[i] * xyScale;
    const hw = (w[i] * wdUnit) / 2;
    const hd = (d[i] * wdUnit) / 2;
    const a = (rot[i] / 256) * Math.PI;
    const ca = Math.cos(a);
    const sa = Math.sin(a);
    const height = h[i] / 10;
    const landmark = (flags[i] & 1) === 1;
    if (landmark) {
      rgb[0] = LANDMARK_COLOR[0];
      rgb[1] = LANDMARK_COLOR[1];
      rgb[2] = LANDMARK_COLOR[2];
    } else {
      eraColor(y0[i], rgb);
      if (ground[i] > 0) {
        // ground patch: a dim version of the era colour, slightly inset so blocks read as blocks
        const half = (ground[i] * groundUnit * 0.94) / 2;
        const g0 = gi * 5;
        gStart[gi] = g0;
        for (let k = 0; k < 5; k++) {
          const ox = cx[k] * half;
          const oy = cy[k] * half;
          const v = g0 + k;
          gPositions[v * 2] = lon0 + (px + ox * ca - oy * sa) / mPerDegLon;
          gPositions[v * 2 + 1] = lat0 + (py + ox * sa + oy * ca) / mPerDegLat;
          gColors[v * 4] = 30 + rgb[0] * 0.3;
          gColors[v * 4 + 1] = 34 + rgb[1] * 0.3;
          gColors[v * 4 + 2] = 42 + rgb[2] * 0.3;
          gColors[v * 4 + 3] = 255;
          gLife[v * 2] = y0[i];
          gLife[v * 2 + 1] = NO_END;
        }
        gi++;
      }
      // taller buildings read slightly lighter, so towers stand out from the low fabric
      const lift = Math.min(1, height / 120) * 0.22;
      rgb[0] += (255 - rgb[0]) * lift;
      rgb[1] += (255 - rgb[1]) * lift;
      rgb[2] += (255 - rgb[2]) * lift;
    }
    if (h[i] < minHeight && !landmark) continue;
    const v0 = bi * 5;
    startIndices[bi] = v0;
    bi++;
    for (let k = 0; k < 5; k++) {
      const ox = cx[k] * hw;
      const oy = cy[k] * hd;
      const ex = px + ox * ca - oy * sa;
      const ny = py + ox * sa + oy * ca;
      const v = v0 + k;
      positions[v * 2] = lon0 + ex / mPerDegLon;
      positions[v * 2 + 1] = lat0 + ny / mPerDegLat;
      elevations[v] = height;
      colors[v * 4] = rgb[0];
      colors[v * 4 + 1] = rgb[1];
      colors[v * 4 + 2] = rgb[2];
      colors[v * 4 + 3] = 255;
      life[v * 2] = y0[i];
      life[v * 2 + 1] = y1[i];
    }
  }
  startIndices[kept] = vertexCount;
  gStart[nGround] = nGround * 5;
  return {
    count: kept,
    vertexCount,
    positions,
    startIndices,
    elevations,
    colors,
    life,
    ground: { count: nGround, positions: gPositions, startIndices: gStart, colors: gColors, life: gLife },
  };
}

export function localToLngLat(city: { center: { lat: number; lon: number } }, x: number, y: number): [number, number] {
  const mPerDegLat = DEG * EARTH_R;
  const mPerDegLon = mPerDegLat * Math.cos(city.center.lat * DEG);
  return [city.center.lon + x / mPerDegLon, city.center.lat + y / mPerDegLat];
}
