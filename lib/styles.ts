/**
 * Historic styles: how the pre-satellite city is drawn where a city has the stylised era fabric.
 *
 * These are artist's impressions. They change colours and the look of the generated houses, never
 * the data: the footprint, the years and the population are the same in every style.
 */
export type RGB = [number, number, number];

export interface HistoricStyle {
  id: "woodblock" | "ink" | "lantern";
  name: string;
  blurb: string;
  /** base map colours at full historic mix */
  land: RGB;
  water: RGB;
  green: RGB;
  label: RGB;
  labelHalo: RGB;
  /** ground under built-up cells */
  ground: RGB;
  /** generated houses */
  wall: RGB;
  roof: RGB;
  hallRoof: RGB;
  storehouse: RGB;
  /** landmark models without a documented colour */
  landmark: RGB;
  /** tint of fresh construction */
  glow: number;
}

export const HISTORIC_STYLES: HistoricStyle[] = [
  {
    id: "woodblock",
    name: "Woodblock",
    blurb: "Paper ground, indigo water, grey tile roofs",
    land: [232, 220, 190],
    water: [96, 132, 158],
    green: [190, 196, 146],
    label: [120, 104, 78],
    labelHalo: [238, 228, 202],
    ground: [214, 198, 160],
    wall: [240, 232, 212],
    roof: [92, 102, 114],
    hallRoof: [66, 98, 88],
    storehouse: [250, 248, 240],
    landmark: [200, 70, 48],
    glow: 0.35,
  },
  {
    id: "ink",
    name: "Ink",
    blurb: "Pale paper, grey washes, black roofs",
    land: [236, 232, 222],
    water: [188, 196, 200],
    green: [214, 216, 204],
    label: [128, 124, 116],
    labelHalo: [240, 237, 229],
    ground: [212, 207, 194],
    wall: [222, 218, 208],
    roof: [58, 58, 62],
    hallRoof: [40, 40, 44],
    storehouse: [246, 244, 238],
    landmark: [150, 44, 34],
    glow: 0.2,
  },
  {
    id: "lantern",
    name: "Lantern",
    blurb: "Night map, warm timber, lit windows",
    land: [20, 22, 28],
    water: [8, 12, 18],
    green: [22, 30, 28],
    label: [104, 96, 86],
    labelHalo: [10, 12, 16],
    ground: [46, 38, 32],
    wall: [214, 150, 84],
    roof: [58, 46, 40],
    hallRoof: [70, 52, 40],
    storehouse: [236, 214, 176],
    landmark: [255, 190, 92],
    glow: 0.7,
  },
];

export const DEFAULT_STYLE: HistoricStyle["id"] = "woodblock";

export function styleById(id: string | null | undefined): HistoricStyle {
  return HISTORIC_STYLES.find((s) => s.id === id) ?? HISTORIC_STYLES[0];
}

/** The modern (satellite-era) base map colours, as in lib/mapStyle.ts. */
export const MODERN = {
  land: [17, 24, 33] as RGB,
  water: [7, 11, 17] as RGB,
  green: [19, 29, 33] as RGB,
  label: [93, 106, 122] as RGB,
  labelHalo: [8, 12, 18] as RGB,
  road: [27, 36, 48] as RGB,
};

/**
 * How much of the historic style applies in a given year: fully before 1880, fading out to the
 * modern dark map by 1960, so the base map has settled well before the satellite record begins.
 */
export function historicMix(year: number): number {
  if (year <= 1880) return 1;
  if (year >= 1960) return 0;
  const t = (year - 1880) / 80;
  return 1 - t * t * (3 - 2 * t);
}

export function mixRgb(a: RGB, b: RGB, t: number): RGB {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

export function css(c: RGB, alpha = 1): string {
  return `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${alpha})`;
}
