import type { StyleSpecification } from "maplibre-gl";

/**
 * A deliberately quiet dark base map built on OpenFreeMap's vector tiles (free, no API key).
 *
 * Only land, water, large green areas and a few place names are drawn. Present-day roads are
 * shown very faintly as orientation only: the base map is today's geography, while the
 * buildings on top of it are the time-lapse.
 */
export const baseMapStyle: StyleSpecification = {
  version: 8,
  name: "city-lapse dark",
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {
    openmaptiles: {
      type: "vector",
      url: "https://tiles.openfreemap.org/planet",
      attribution:
        '<a href="https://openfreemap.org" target="_blank" rel="noreferrer">OpenFreeMap</a> ' +
        '<a href="https://www.openmaptiles.org/" target="_blank" rel="noreferrer">© OpenMapTiles</a> ' +
        '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>',
    },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#111821" } },
    {
      id: "landcover_wood",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "landcover",
      filter: ["in", ["get", "class"], ["literal", ["wood", "grass", "farmland"]]],
      paint: { "fill-color": "#131d24", "fill-opacity": 0.7 },
    },
    {
      id: "park",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "park",
      paint: { "fill-color": "#13201f", "fill-opacity": 0.6 },
    },
    {
      id: "water",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "water",
      paint: { "fill-color": "#070b11" },
    },
    {
      id: "waterway",
      type: "line",
      source: "openmaptiles",
      "source-layer": "waterway",
      minzoom: 8,
      paint: {
        "line-color": "#070b11",
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.6, 14, 3],
      },
    },
    {
      id: "roads_major",
      type: "line",
      source: "openmaptiles",
      "source-layer": "transportation",
      minzoom: 9,
      filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#1b2430",
        "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.4, 14, 2.5],
      },
    },
    {
      id: "place_labels",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "place",
      minzoom: 9,
      filter: ["in", ["get", "class"], ["literal", ["city", "town", "suburb"]]],
      layout: {
        "text-field": ["coalesce", ["get", "name_en"], ["get", "name:latin"], ["get", "name"]],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 9, 10, 14, 13],
        "text-max-width": 8,
        "text-letter-spacing": 0.04,
      },
      paint: {
        "text-color": "#5d6a7a",
        "text-halo-color": "rgba(8, 12, 18, 0.9)",
        "text-halo-width": 1.2,
      },
    },
    {
      id: "water_labels",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "water_name",
      minzoom: 8,
      layout: {
        "text-field": ["coalesce", ["get", "name_en"], ["get", "name:latin"], ["get", "name"]],
        "text-font": ["Noto Sans Italic"],
        "text-size": 11,
        "text-max-width": 7,
      },
      paint: { "text-color": "#34465a", "text-halo-color": "rgba(7, 11, 17, 0.9)", "text-halo-width": 1 },
    },
  ],
};
