"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import maplibregl from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { AmbientLight, DirectionalLight, LightingEffect } from "@deck.gl/core";
import { LineLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from "@deck.gl/layers";
import { baseMapStyle } from "@/lib/mapStyle";
import { CityTimeExtension } from "@/lib/cityTimeExtension";
import { localToLngLat, type BuildingBuffers } from "@/lib/buildings";
import { formatYear } from "@/lib/timeline";
import type { CameraKey, CityData, Landmark } from "@/lib/types";

export interface MapViewHandle {
  /** Draw the city at `year`. `yearsPerSecond` sizes the rise animation; `playing` turns the orbit on. */
  frame(year: number, yearsPerSecond: number, playing: boolean, dtSeconds: number): void;
  /** Re-engage the automatic camera. */
  resumeAutoCamera(): void;
}

interface Props {
  city: CityData | null;
  buffers: BuildingBuffers | null;
  autoCamera: boolean;
  /** vertical exaggeration of the display (1 = true scale) */
  heightScale: number;
  onUserCamera: () => void;
  onReady?: () => void;
}

const timeExtension = new CityTimeExtension();
const lighting = new LightingEffect({
  ambient: new AmbientLight({ color: [255, 255, 255], intensity: 1.0 }),
  sun: new DirectionalLight({ color: [255, 244, 224], intensity: 1.25, direction: [-2, -5, -6] }),
  fill: new DirectionalLight({ color: [170, 200, 255], intensity: 0.35, direction: [4, 3, -3] }),
});

const ORBIT_DEG_PER_S = 2.2;
const PITCH = 56;

/** View target (centre, radius of what is standing) at a year, from the precomputed camera path. */
function cameraAt(keys: CameraKey[], year: number) {
  if (!keys.length) return { x: 0, y: 0, r: 5000 };
  if (year <= keys[0].year) return keys[0];
  let i = 0;
  while (i + 1 < keys.length && keys[i + 1].year <= year) i++;
  const a = keys[i];
  const b = keys[i + 1];
  if (!b) return a;
  const f = (year - a.year) / (b.year - a.year);
  return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, r: Math.exp(Math.log(a.r) * (1 - f) + Math.log(b.r) * f) };
}

function zoomForRadius(radiusM: number, lat: number, viewportPx: number) {
  // Fit a circle of this radius (plus margin) into the smaller viewport dimension. 512 px tiles.
  const metersPerPixel = (2.5 * radiusM) / Math.max(viewportPx, 320);
  const z = Math.log2((78271.517 * Math.cos((lat * Math.PI) / 180)) / metersPerPixel);
  return Math.min(Math.max(z, 9.4), 15.2);
}

interface Pin extends Landmark {
  position: [number, number, number];
  /** 0..1 drop-in progress */
  drop: number;
  labelled: boolean;
}

const MapView = forwardRef<MapViewHandle, Props>(function MapView({ city, buffers, autoCamera, heightScale, onUserCamera, onReady }, ref) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const state = useRef({
    city: null as CityData | null,
    buffers: null as BuildingBuffers | null,
    auto: true,
    year: 2026,
    revealedAt: new Map<string, number>(),
    cam: null as { lng: number; lat: number; zoom: number } | null,
    programmatic: false,
    heightScale: 1,
    lastFrame: 0,
  });
  const onUserCameraRef = useRef(onUserCamera);
  onUserCameraRef.current = onUserCamera;

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: baseMapStyle,
      center: [0, 20],
      zoom: 1.5,
      pitch: PITCH,
      bearing: -20,
      maxPitch: 75,
      attributionControl: { compact: true },
      fadeDuration: 0,
    });
    map.dragRotate.enable();
    map.touchZoomRotate.enableRotation();
    const overlay = new MapboxOverlay({
      interleaved: false,
      layers: [],
      effects: [lighting],
      getTooltip: ({ object }: { object?: unknown }) => {
        const lm = object as Pin | undefined;
        if (!lm || !lm.name) return null;
        return {
          html: `<strong>${lm.name}</strong><br/>${formatYear(lm.year)} · ${Math.round(lm.height_m)} m${
            lm.demolished_year ? `<br/>gone by ${formatYear(lm.demolished_year)}` : ""
          }`,
          className: "pin-tooltip",
          style: { background: "rgba(13,19,28,0.94)", color: "#e9edf2", border: "1px solid rgba(255,255,255,0.14)", borderRadius: "6px", padding: "6px 9px", fontSize: "12px", lineHeight: "1.35" },
        };
      },
    });
    map.addControl(overlay);
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showZoom: false }), "top-right");
    mapRef.current = map;
    overlayRef.current = overlay;
    // Any gesture from the person hands them the camera; the app stops steering until asked to resume.
    const handOver = (e: { originalEvent?: unknown }) => {
      if (e.originalEvent && state.current.auto) {
        state.current.auto = false;
        onUserCameraRef.current();
      }
    };
    map.on("dragstart", handOver);
    map.on("zoomstart", handOver);
    map.on("rotatestart", handOver);
    map.on("pitchstart", handOver);
    map.once("load", () => onReady?.());
    if (typeof window !== "undefined") (window as unknown as { __map?: maplibregl.Map }).__map = map;
    return () => {
      map.removeControl(overlay);
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    state.current.auto = autoCamera;
  }, [autoCamera]);

  useEffect(() => {
    state.current.heightScale = heightScale;
  }, [heightScale]);

  // New city: reset pins and jump the camera to its opening view.
  useEffect(() => {
    const s = state.current;
    s.city = city;
    s.revealedAt.clear();
    const map = mapRef.current;
    if (!map || !city) {
      overlayRef.current?.setProps({ layers: [] });
      return;
    }
    const k = cameraAt(city.camera, city.start_year);
    const [lng, lat] = localToLngLat(city, k.x, k.y);
    const size = Math.min(map.getCanvas().clientWidth, map.getCanvas().clientHeight);
    const zoom = zoomForRadius(k.r, city.center.lat, size);
    s.cam = { lng, lat, zoom };
    map.jumpTo({ center: [lng, lat], zoom, pitch: PITCH, bearing: -20 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city?.slug]);

  // Buffers can change without the city changing (switching detail level): keep the camera.
  useEffect(() => {
    state.current.buffers = buffers;
  }, [buffers]);

  useImperativeHandle(
    ref,
    () => ({
      resumeAutoCamera() {
        state.current.auto = true;
        const map = mapRef.current;
        if (map) {
          const c = map.getCenter();
          state.current.cam = { lng: c.lng, lat: c.lat, zoom: map.getZoom() };
        }
      },
      frame(year, yearsPerSecond, playing, dt) {
        const s = state.current;
        const map = mapRef.current;
        const overlay = overlayRef.current;
        if (!map || !overlay || !s.city) return;
        const cityData = s.city;
        s.year = year;

        // --- camera
        if (s.auto) {
          const k = cameraAt(cityData.camera, year);
          const [tLng, tLat] = localToLngLat(cityData, k.x, k.y);
          const canvas = map.getCanvas();
          const tZoom = zoomForRadius(k.r, cityData.center.lat, Math.min(canvas.clientWidth, canvas.clientHeight));
          const cam = s.cam ?? { lng: tLng, lat: tLat, zoom: tZoom };
          // wall-clock easing, so the camera keeps up on slow devices where frames are far apart
          const wall = Math.min(1.5, (performance.now() - s.lastFrame) / 1000);
          const ease = 1 - Math.exp(-Math.max(dt, wall) / 0.9);
          cam.lng += (tLng - cam.lng) * ease;
          cam.lat += (tLat - cam.lat) * ease;
          cam.zoom += (tZoom - cam.zoom) * ease;
          s.cam = cam;
          const bearing = map.getBearing() + (playing ? ORBIT_DEG_PER_S * dt : 0);
          const pitch = map.getPitch() + (PITCH - map.getPitch()) * ease;
          map.jumpTo({ center: [cam.lng, cam.lat], zoom: cam.zoom, bearing, pitch });
        }

        // --- layers
        const layers = [];
        const b = s.buffers;
        if (b) {
          const timeProps = {
            // extension props: the only thing that changes from frame to frame
            cityYear: year,
            cityRise: Math.max(0.6, yearsPerSecond * 0.7),
            cityGlow: Math.max(3, yearsPerSecond * 2.2),
            cityGlowStrength: playing ? 0.75 : 0.25,
          };
          layers.push(
            new SolidPolygonLayer({
              id: `ground-${cityData.slug}`,
              data: {
                length: b.ground.count,
                startIndices: b.ground.startIndices,
                attributes: {
                  getPolygon: { value: b.ground.positions, size: 2 },
                  getFillColor: { value: b.ground.colors, size: 4, normalized: true },
                  getLife: { value: b.ground.life, size: 2 },
                },
              },
              positionFormat: "XY",
              _normalize: false,
              extruded: false,
              pickable: false,
              extensions: [timeExtension],
              ...timeProps,
              cityGlowStrength: timeProps.cityGlowStrength * 0.6,
            } as ConstructorParameters<typeof SolidPolygonLayer>[0]),
            new SolidPolygonLayer({
              id: `buildings-${cityData.slug}`,
              data: {
                length: b.count,
                startIndices: b.startIndices,
                attributes: {
                  getPolygon: { value: b.positions, size: 2 },
                  getElevation: { value: b.elevations, size: 1 },
                  getFillColor: { value: b.colors, size: 4, normalized: true },
                  getLife: { value: b.life, size: 2 },
                },
              },
              positionFormat: "XY",
              _normalize: false,
              extruded: true,
              elevationScale: s.heightScale,
              pickable: false,
              material: { ambient: 0.5, diffuse: 0.55, shininess: 18, specularColor: [40, 44, 52] },
              extensions: [timeExtension],
              ...timeProps,
            } as ConstructorParameters<typeof SolidPolygonLayer>[0]),
          );
        }

        // --- landmark pins: appear in the year the structure was completed
        const now = performance.now();
        const pins: Pin[] = [];
        for (const lm of cityData.landmarks) {
          const up = year >= lm.year && (!lm.demolished_year || year < lm.demolished_year);
          const key = `${lm.name}|${lm.year}`;
          if (!up) {
            s.revealedAt.delete(key);
            continue;
          }
          if (!s.revealedAt.has(key)) s.revealedAt.set(key, playing ? now : now - 10_000);
          const t = Math.min(1, (now - (s.revealedAt.get(key) as number)) / 900);
          const drop = 1 - Math.pow(1 - t, 3);
          pins.push({ ...lm, position: [lm.lon, lm.lat, lm.height_m * s.heightScale + 3], drop, labelled: false });
        }
        // Label the most recently completed landmarks. Labels that would overlap on screen are
        // dropped (newest wins); every pin keeps its dot and a tooltip.
        {
          const zoomNow = map.getZoom();
          const mpp = (78271.517 * Math.cos((cityData.center.lat * Math.PI) / 180)) / Math.pow(2, zoomNow);
          const rise = Math.sin((map.getPitch() * Math.PI) / 180) / mpp;
          const taken: [number, number, number, number][] = [];
          const canvas = map.getCanvas();
          let shown = 0;
          for (const p of [...pins].sort((a, c) => c.year - a.year)) {
            if (shown >= 4) break;
            const pt = map.project([p.lon, p.lat]);
            const w = (p.name.length + 7) * 6.6 + 14;
            const top = pt.y - p.height_m * s.heightScale * rise - 16 - 22;
            const box: [number, number, number, number] = [pt.x - w / 2, top, pt.x + w / 2, top + 22];
            if (box[2] < 0 || box[0] > canvas.clientWidth || box[3] < 60 || box[1] > canvas.clientHeight - 120) continue;
            if (taken.some((t) => box[0] < t[2] + 6 && box[2] > t[0] - 6 && box[1] < t[3] + 4 && box[3] > t[1] - 4)) continue;
            taken.push(box);
            p.labelled = true;
            shown++;
          }
        }
        if (pins.length) {
          const lift = (p: Pin): [number, number, number] => [p.position[0], p.position[1], p.position[2] + (1 - p.drop) * 900];
          layers.push(
            new LineLayer<Pin>({
              id: "pin-stems",
              data: pins,
              getSourcePosition: (p) => [p.position[0], p.position[1], 0],
              getTargetPosition: lift,
              getColor: (p) => [255, 196, 110, 60 + 120 * p.drop],
              getWidth: 1,
              widthUnits: "pixels",
              parameters: { depthCompare: "always" },
            }),
            new ScatterplotLayer<Pin>({
              id: "pin-dots",
              data: pins,
              getPosition: lift,
              getRadius: (p) => (p.labelled ? 4.5 : 3.2),
              radiusUnits: "pixels",
              billboard: true,
              stroked: true,
              getLineWidth: 1.2,
              lineWidthUnits: "pixels",
              getFillColor: [255, 190, 92, 255],
              getLineColor: [20, 14, 4, 220],
              pickable: true,
              parameters: { depthCompare: "always" },
            }),
          );
          const labelled = pins.filter((p) => p.labelled);
          if (labelled.length) {
            layers.push(
              new TextLayer<Pin>({
                id: "pin-labels",
                data: labelled,
                getPosition: lift,
                getText: (p) => `${p.name} · ${formatYear(p.year)}`,
                getSize: 12,
                getColor: (p) => [255, 236, 204, 255 * p.drop],
                getPixelOffset: [0, -16],
                getTextAnchor: "middle",
                getAlignmentBaseline: "bottom",
                fontFamily: "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
                fontWeight: 600,
                characterSet: "auto",
                background: true,
                getBackgroundColor: [13, 19, 28, 215],
                backgroundPadding: [6, 3, 6, 3],
                parameters: { depthCompare: "always" },
              }),
            );
          }
        }
        overlay.setProps({ layers });
        s.lastFrame = performance.now();
      },
    }),
    [],
  );

  return <div ref={container} className="map" aria-label="3D map" />;
});

export default MapView;
