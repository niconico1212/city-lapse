import type { CityData } from "./types";
import type { HistoricStyle, RGB } from "./styles";

const EARTH_R = 6_371_008.8;
const DEG = Math.PI / 180;
const NO_END = 32767;
const MODERN_LANDMARK: RGB = [255, 190, 92];

/** Buffers for a SolidPolygonLayer whose polygons carry their own base height (XYZ positions). */
export interface PrismBuffers {
  count: number;
  /** lon, lat, base z per vertex; 5 vertices per prism for boxes, variable for real shapes */
  positions: Float64Array;
  positionSize: 2 | 3;
  startIndices: Uint32Array;
  elevations: Float32Array;
  colors: Uint8Array;
  /** year built, year gone, mode (0 = rises from the ground, 1 = appears in place) */
  life: Float32Array;
}

function projector(city: { center: { lat: number; lon: number } }) {
  const mLat = DEG * EARTH_R;
  const mLon = mLat * Math.cos(city.center.lat * DEG);
  return (x: number, y: number): [number, number] => [city.center.lon + x / mLon, city.center.lat + y / mLat];
}

// ----------------------------------------------------------------------------- stylised fabric

/**
 * Decode public/data/<slug>-fabric.bin (scripts/04_buildings.py, generate_fabric) into two prisms
 * per house: walls up to the eave and a narrower roof block on top, so each reads as a roofed
 * house from above. Colours come from the chosen historic style.
 */
export function decodeFabric(buf: ArrayBuffer, city: CityData, style: HistoricStyle): PrismBuffers {
  const info = city.extras?.fabric;
  if (!info) throw new Error("city has no fabric layer");
  const view = new DataView(buf);
  const n = view.getUint32(4, true);
  let off = 8;
  const i16 = () => {
    const a = new Int16Array(buf.slice(off, off + n * 2));
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
  const len = u8();
  const wid = u8();
  const rot = u8();
  const h = u8();
  const kind = u8();

  const toLngLat = projector(city);
  const prisms = n * 2;
  const positions = new Float64Array(prisms * 5 * 3);
  const startIndices = new Uint32Array(prisms + 1);
  const elevations = new Float32Array(prisms * 5);
  const colors = new Uint8Array(prisms * 5 * 4);
  const life = new Float32Array(prisms * 5 * 3);
  const cx = [-1, -1, 1, 1, -1];
  const cy = [-1, 1, 1, -1, -1];

  const put = (p: number, px: number, py: number, hl: number, hw: number, ca: number, sa: number, z: number, height: number, c: RGB, shade: number, a: number, b: number) => {
    const v0 = p * 5;
    startIndices[p] = v0;
    for (let k = 0; k < 5; k++) {
      const ox = cx[k] * hl;
      const oy = cy[k] * hw;
      const [lng, lat] = toLngLat(px + ox * ca - oy * sa, py + ox * sa + oy * ca);
      const v = v0 + k;
      positions[v * 3] = lng;
      positions[v * 3 + 1] = lat;
      positions[v * 3 + 2] = z;
      elevations[v] = height;
      colors[v * 4] = Math.min(255, c[0] * shade);
      colors[v * 4 + 1] = Math.min(255, c[1] * shade);
      colors[v * 4 + 2] = Math.min(255, c[2] * shade);
      colors[v * 4 + 3] = 255;
      life[v * 3] = a;
      life[v * 3 + 1] = b;
      life[v * 3 + 2] = 0;
    }
  };

  for (let i = 0; i < n; i++) {
    const px = x[i] * info.xy_unit;
    const py = y[i] * info.xy_unit;
    const hl = (len[i] * info.lw_unit) / 2;
    const hw = (wid[i] * info.lw_unit) / 2;
    const a = (rot[i] / 256) * Math.PI;
    const ca = Math.cos(a);
    const sa = Math.sin(a);
    const eave = h[i] * info.h_unit;
    const k = kind[i];
    // small per-house variation so rows do not look stamped
    const shade = 0.93 + ((i * 2654435761) >>> 24) / 255 * 0.14;
    const wall = k === 2 ? style.storehouse : style.wall;
    const roof = k === 1 ? style.hallRoof : style.roof;
    // Seen from above a townscape is mostly roof: the roof block overhangs the walls slightly, so
    // the wall colour shows as a thin edge and the tile colour carries the picture.
    const roofH = Math.max(1.0, hw * (k === 1 ? 0.5 : 0.32));
    put(i * 2, px, py, hl, hw, ca, sa, 0, eave, wall, shade, y0[i], y1[i]);
    put(i * 2 + 1, px, py, hl * 1.03, hw * 1.07, ca, sa, eave, roofH, roof, shade, y0[i], y1[i]);
  }
  startIndices[prisms] = prisms * 5;
  return { count: prisms, positions, positionSize: 3, startIndices, elevations, colors, life };
}

// ----------------------------------------------------------------------------- real shapes

export interface RealIndex {
  slug: string;
  zoom: number;
  xy_unit: number;
  switch_year: number;
  source: { name: string; publisher: string; url: string; derived: string; licence: string };
  dating: { documented: string; estimated: string; generated: string };
  stats: {
    buildings: number;
    tiles: number;
    bytes: number;
    dated_documented: number;
    dated_ghsl_epoch: number;
    dated_generated: number;
    over_100m: number;
  };
  tiles: Record<string, { n: number; bytes: number }>;
}

/** Neutral, untextured palette for real shapes: concrete for low fabric, cooler glass for towers. */
function realColor(height: number, i: number, out: RGB) {
  const t = Math.min(1, Math.max(0, (height - 15) / 120));
  const v = (((i * 2246822519) >>> 24) / 255 - 0.5) * 16;
  out[0] = 198 - 34 * t + v;
  out[1] = 196 - 12 * t + v;
  out[2] = 190 + 30 * t + v;
}

/** Decode one tile of real building footprints (scripts/08_real_buildings.py). */
export function decodeRealTile(buf: ArrayBuffer, city: CityData, index: RealIndex): PrismBuffers {
  const view = new DataView(buf);
  const magic = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
  if (magic !== "CLT1") throw new Error(`unexpected tile header "${magic}"`);
  const n = view.getUint32(4, true);
  const nVerts = view.getUint32(8, true);
  const ox = view.getFloat32(12, true);
  const oy = view.getFloat32(16, true);
  let off = 20;
  const xy = new Int16Array(buf.slice(off, off + nVerts * 4));
  off += nVerts * 4;
  const h = new Uint16Array(buf.slice(off, off + n * 2));
  off += n * 2;
  const y0 = new Int16Array(buf.slice(off, off + n * 2));
  off += n * 2;
  const nv = new Uint8Array(buf, off, n);

  const toLngLat = projector(city);
  const total = nVerts + n; // each ring is closed by repeating its first vertex
  const positions = new Float64Array(total * 2);
  const startIndices = new Uint32Array(n + 1);
  const elevations = new Float32Array(total);
  const colors = new Uint8Array(total * 4);
  const life = new Float32Array(total * 3);
  const rgb: RGB = [0, 0, 0];
  let src = 0;
  let dst = 0;
  for (let i = 0; i < n; i++) {
    const count = nv[i];
    const height = h[i] / 10;
    realColor(height, i, rgb);
    startIndices[i] = dst;
    for (let k = 0; k <= count; k++) {
      const s = src + (k === count ? 0 : k);
      const [lng, lat] = toLngLat(ox + xy[s * 2] * index.xy_unit, oy + xy[s * 2 + 1] * index.xy_unit);
      positions[dst * 2] = lng;
      positions[dst * 2 + 1] = lat;
      elevations[dst] = height;
      colors[dst * 4] = rgb[0];
      colors[dst * 4 + 1] = rgb[1];
      colors[dst * 4 + 2] = rgb[2];
      colors[dst * 4 + 3] = 255;
      life[dst * 3] = y0[i];
      life[dst * 3 + 1] = NO_END;
      life[dst * 3 + 2] = 0;
      dst++;
    }
    src += count;
  }
  startIndices[n] = dst;
  return { count: n, positions, positionSize: 2, startIndices, elevations, colors, life };
}

export function tileXY(lng: number, lat: number, z: number): [number, number] {
  const n = 2 ** z;
  const x = Math.floor(((lng + 180) / 360) * n);
  const r = lat * DEG;
  const y = Math.floor(((1 - Math.asinh(Math.tan(r)) / Math.PI) / 2) * n);
  return [x, y];
}

/** lng/lat bounds [west, south, east, north] of a block of tiles. */
export function tileBounds(x0: number, y0: number, x1: number, y1: number, z: number): [number, number, number, number] {
  const n = 2 ** z;
  const lng = (x: number) => (x / n) * 360 - 180;
  const lat = (y: number) => Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n))) / DEG;
  return [lng(x0), lat(y1 + 1), lng(x1 + 1), lat(y0)];
}

// ----------------------------------------------------------------------------- landmark models

export interface ModelFile {
  slug: string;
  note: string;
  models: {
    name: string;
    construction_start: number | null;
    completed: number;
    demolished: number | null;
    shape: string;
    shape_source: string;
    color: RGB | null;
    /** prisms: [ring of [x, y] metres from the city centre, z0, z1, year it appears] */
    parts: { p: [number, number][]; z0: number; z1: number; y: number; c?: RGB }[];
  }[];
}

/** Landmark models as stacked prisms that appear in place, bottom to top, as construction proceeds. */
export function decodeModels(file: ModelFile, city: CityData, style: HistoricStyle): PrismBuffers {
  const toLngLat = projector(city);
  let prisms = 0;
  let verts = 0;
  for (const m of file.models) {
    for (const part of m.parts) {
      prisms++;
      verts += part.p.length + 1;
    }
  }
  const positions = new Float64Array(verts * 3);
  const startIndices = new Uint32Array(prisms + 1);
  const elevations = new Float32Array(verts);
  const colors = new Uint8Array(verts * 4);
  const life = new Float32Array(verts * 3);
  let p = 0;
  let v = 0;
  for (const m of file.models) {
    // documented colour if there is one; otherwise the historic style's accent for old structures
    // and the usual landmark gold for modern ones
    const base = m.color ?? (m.completed < 1900 ? style.landmark : MODERN_LANDMARK);
    for (const part of m.parts) {
      const c = part.c ?? base;
      startIndices[p++] = v;
      for (let k = 0; k <= part.p.length; k++) {
        const [px, py] = part.p[k === part.p.length ? 0 : k];
        const [lng, lat] = toLngLat(px, py);
        positions[v * 3] = lng;
        positions[v * 3 + 1] = lat;
        positions[v * 3 + 2] = part.z0;
        elevations[v] = part.z1 - part.z0;
        colors[v * 4] = c[0];
        colors[v * 4 + 1] = c[1];
        colors[v * 4 + 2] = c[2];
        colors[v * 4 + 3] = 255;
        life[v * 3] = part.y;
        life[v * 3 + 1] = m.demolished ?? NO_END;
        life[v * 3 + 2] = 1;
        v++;
      }
    }
  }
  startIndices[prisms] = v;
  return { count: prisms, positions, positionSize: 3, startIndices, elevations, colors, life };
}
