"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { SolidPolygonLayer } from "@deck.gl/layers";
import { baseMapStyle } from "@/lib/mapStyle";

/**
 * Phase 1 scaffold: one hardcoded test city (Tokyo) to prove the stack end to end:
 * MapLibre + OpenFreeMap tiles underneath, deck.gl extruded polygons on top.
 * The real per-city data, time filtering and UI replace this in later phases.
 */
const TEST_CITY = { name: "Tokyo", lat: 35.6852, lon: 139.7528 };

type TestBuilding = { polygon: [number, number][]; height: number; landmark?: boolean };

function box(lat: number, lon: number, sizeM: number, height: number, landmark = false): TestBuilding {
  const dLat = sizeM / 2 / 111_320;
  const dLon = sizeM / 2 / (111_320 * Math.cos((lat * Math.PI) / 180));
  return {
    polygon: [
      [lon - dLon, lat - dLat],
      [lon + dLon, lat - dLat],
      [lon + dLon, lat + dLat],
      [lon - dLon, lat + dLat],
      [lon - dLon, lat - dLat],
    ],
    height,
    landmark,
  };
}

function testBuildings(): TestBuilding[] {
  const out: TestBuilding[] = [];
  let seed = 1457;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
  for (let i = 0; i < 2500; i++) {
    const r = Math.sqrt(rnd()) * 0.06;
    const a = rnd() * Math.PI * 2;
    const falloff = Math.exp(-r / 0.02);
    out.push(box(TEST_CITY.lat + r * Math.sin(a), TEST_CITY.lon + r * 1.2 * Math.cos(a), 60, 8 + rnd() * 120 * falloff));
  }
  // The example landmark from the spec: Tokyo Skytree, 634 m, at its real position.
  out.push(box(35.7101, 139.8107, 70, 634, true));
  return out;
}

export default function CityLapseApp() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: baseMapStyle,
      center: [TEST_CITY.lon, TEST_CITY.lat],
      zoom: 11.5,
      pitch: 55,
      bearing: -20,
      maxPitch: 75,
    });
    const overlay = new MapboxOverlay({
      interleaved: false,
      layers: [
        new SolidPolygonLayer<TestBuilding>({
          id: "test-buildings",
          data: testBuildings(),
          extruded: true,
          getPolygon: (d) => d.polygon,
          getElevation: (d) => d.height,
          getFillColor: (d) => (d.landmark ? [255, 180, 84] : [150, 170, 195]),
          material: { ambient: 0.45, diffuse: 0.6, shininess: 12 },
        }),
      ],
    });
    map.addControl(overlay);
    return () => {
      map.removeControl(overlay);
      map.remove();
    };
  }, []);

  return (
    <main style={{ position: "fixed", inset: 0 }}>
      <div ref={container} style={{ position: "absolute", inset: 0 }} />
      <div
        style={{
          position: "absolute",
          top: 16,
          left: 16,
          padding: "8px 12px",
          background: "var(--panel)",
          border: "1px solid var(--line)",
          borderRadius: 8,
        }}
      >
        city-lapse · scaffold test: {TEST_CITY.name}
      </div>
    </main>
  );
}
