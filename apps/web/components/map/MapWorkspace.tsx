"use client";

/**
 * The map (P5-05, P5-06, P5-08).
 *
 * The map is the product, not a widget inside it: it fills the shell's flexible
 * column, has no card, no border radius and no padding, and every control floats
 * over it as a hairline box rather than occupying layout space.
 *
 * The basemap is Esri World Imagery with Esri's reference labels, credited in the
 * attribution control as its licence requires. Those tiles and the optional place
 * search (OpenStreetMap Nominatim) are the only non-gateway requests the browser
 * makes; both are listed in next.config.ts's CSP and carry no mission data.
 *
 * MapLibre is loaded on demand so the ~800 KB of GL does not sit in the first paint
 * of a route that may never show a map (P5-16).
 */

import * as maplibregl from "maplibre-gl";
import type {
  GeoJSONSource,
  LngLatBoundsLike,
  MapMouseEvent,
  Map as MapLibreMap,
} from "maplibre-gl";
import { useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { formatArea, formatLat, formatLon, formatZoom } from "../../lib/geo/format";
import { rectanglePolygon, searchPlace, GeocodeError, type PlaceResult } from "../../lib/geo/geocode";
import { validateAOI, type ValidationResult } from "../../lib/geo/validate";
import { epochOpacities, type TimeMachineModel } from "../../lib/map/timeLayers";
import type { GeoJSONPolygon } from "../../lib/api/types";
import { Label, StatusChip } from "../system/primitives";
import { TimeMachine } from "./TimeMachine";

export type LayerId = "observation" | "baseline" | "change" | "confidence" | "aoi";

export interface RasterOverlay {
  id: string;
  url: string;
  bbox: [number, number, number, number];
  opacity?: number;
}

export interface MapWorkspaceProps {
  center: [number, number];
  zoom: number;
  aoi: GeoJSONPolygon | null;
  onAoiChange: (aoi: GeoJSONPolygon | null) => void;
  overlays: RasterOverlay[];
  changeGeoJsonUrl: string | null;
  /** When present, renders the Earth Time Machine rail and its epoch layers. */
  timeMachine?: TimeMachineModel | null;
  visible: Record<LayerId, boolean>;
  onToggleLayer: (id: LayerId) => void;
  onSelectChange?: (featureId: string | null) => void;
  /** Layers that exist right now; the panel lists only these (audit F6). */
  availableLayers?: LayerId[];
  /** Measured water polygons (EPSG:4326) from the inference service (audit W8). */
  extent?: GeoJSON.FeatureCollection | null;
  /** Place search box (audit F4). Off in demo, where the AOI is pinned. */
  placeSearch?: boolean;
  /** Freeze AOI editing (while a run is in flight). */
  aoiLocked?: boolean;
}

const LAYER_LABELS: Record<LayerId, string> = {
  observation: "Water extent",
  baseline: "Baseline water",
  change: "Change",
  confidence: "Confidence",
  aoi: "Area of interest",
};

/** Reference-design checkbox colours, one per layer family. */
const LAYER_ACCENT: Record<LayerId, string> = {
  observation: "#60a0f8",
  baseline: "#30d098",
  change: "#f87010",
  confidence: "#f8c810",
  aoi: "#f87010",
};

/** Colour of the measured-water fill: the "earth/data" blue, not the action orange. */
const WATER = "#60a0f8";
const ACCENT = "#f87010";

/** Esri World Imagery's required credit (see Esri's attribution guidelines). */
const ESRI_CREDIT =
  "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community · Labels © Esri";

const EMPTY_STYLE = {
  version: 8 as const,
  sources: {
    "esri-world-imagery": {
      type: "raster" as const,
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
      ],
      tileSize: 256,
      attribution: ESRI_CREDIT
    },
    "esri-world-labels": {
      type: "raster" as const,
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
      ],
      tileSize: 256
    }
  },
  layers: [
    {
      id: "world-imagery",
      type: "raster" as const,
      source: "esri-world-imagery",
      minzoom: 0,
      maxzoom: 22
    },
    {
      id: "world-labels",
      type: "raster" as const,
      source: "esri-world-labels",
      minzoom: 0,
      maxzoom: 22
    }
  ]
};

let workerConfigured = false;

export function MapWorkspace({
  center,
  zoom,
  aoi,
  onAoiChange,
  overlays,
  changeGeoJsonUrl,
  timeMachine = null,
  visible,
  onToggleLayer,
  onSelectChange,
  availableLayers,
  extent = null,
  placeSearch = false,
  aoiLocked = false,
}: MapWorkspaceProps) {
  const holder = useRef<HTMLDivElement | null>(null);
  const map = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [cursor, setCursor] = useState<{ lat: number; lon: number; zoom: number }>({
    lat: center[1],
    lon: center[0],
    zoom,
  });

  const [drawMode, setDrawMode] = useState<"polygon" | "rectangle" | null>(null);
  const drawing = drawMode !== null;
  const [draft, setDraft] = useState<number[][]>([]);
  const [hover, setHover] = useState<[number, number] | null>(null);
  const [overlayOpacity, setOverlayOpacity] = useState(0.55);
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<PlaceResult[] | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const corner = useRef<[number, number] | null>(null);
  const setDrawing = useCallback((on: boolean) => {
    corner.current = null;
    setDraft([]);
    setDrawMode(on ? "polygon" : null);
  }, []);

  // Which time machine epoch is on screen; owned here so the map can tween the
  // raster opacities while the rail only reports indices.
  const [tmIndex, setTmIndex] = useState(0);
  const reduce = useReducedMotion();

  /* ── init ───────────────────────────────────────────────────────────────── */

  useEffect(() => {
    if (!holder.current || map.current) return;

    // maplibre-gl v6 looks for its worker beside its own (bundled) module file,
    // where it does not exist; without a worker no GeoJSON layer ever renders.
    // scripts/copy-maplibre-worker.mjs puts the matching worker in public/.
    if (!workerConfigured) {
      maplibregl.setWorkerUrl(`${window.location.origin}/vendor/maplibre/maplibre-gl-worker.mjs`);
      workerConfigured = true;
    }

    const m = new maplibregl.Map({
      container: holder.current,
      style: EMPTY_STYLE,
      center,
      zoom,
      // Esri's licence requires the credit on screen (audit F6).
      attributionControl: { compact: true, customAttribution: "SatQuery" },
      // Pitch and rotate are on: the PRD asks for them, and they cost nothing here.
      pitchWithRotate: true,
      dragRotate: true,
    });

    m.on("load", () => setReady(true));
    m.on("mousemove", (e: MapMouseEvent) => {
      setCursor({ lat: e.lngLat.lat, lon: e.lngLat.lng, zoom: m.getZoom() });
    });
    m.on("zoom", () => {
      setCursor((c) => ({ ...c, zoom: m.getZoom() }));
    });

    map.current = m;
    return () => {
      m.remove();
      map.current = null;
    };
    // Mount once. Centre and zoom changes are applied by the effect below, not by
    // rebuilding the map, which would drop every layer and the operator's view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── raster overlays ────────────────────────────────────────────────────── */

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;

    for (const ov of overlays) {
      const srcId = `src-${ov.id}`;
      const layerId = `lyr-${ov.id}`;
      const [w, s, e, n] = ov.bbox;

      if (!m.getSource(srcId)) {
        m.addSource(srcId, {
          type: "image",
          url: ov.url,
          // MapLibre wants the corners clockwise from top-left.
          coordinates: [
            [w, n],
            [e, n],
            [e, s],
            [w, s],
          ],
        });
        m.addLayer({
          id: layerId,
          type: "raster",
          source: srcId,
          paint: {
            "raster-opacity": ov.opacity ?? 1,
            "raster-fade-duration": 180,
            "raster-resampling": "nearest",
          },
        }, "world-labels");
      }
    }
  }, [overlays, ready]);

  /* ── time machine epochs (PRD §2A) ─────────────────────────────────────── */

  // A newly-arrived model resets the scrubber to the run's opening epoch, so
  // the map never shows index 0 of a model the rail opened in the middle of.
  useEffect(() => {
    if (timeMachine) setTmIndex(timeMachine.initialIndex);
  }, [timeMachine]);

  // Epoch rasters get their own sources/layers so the crossfade runs between
  // neighbouring states without touching the operator's layer toggles. They
  // start at opacity 0 — 0, not visibility:none, is what makes the fade possible.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !timeMachine) return;

    for (const e of timeMachine.epochs) {
      const srcId = `src-${e.id}`;
      const layerId = `lyr-${e.id}`;
      const [w, s, ea, n] = e.bbox;
      if (!m.getSource(srcId)) {
        m.addSource(srcId, {
          type: "image",
          url: e.url,
          // MapLibre wants the corners clockwise from top-left.
          coordinates: [
            [w, n],
            [ea, n],
            [ea, s],
            [w, s],
          ],
        });
      }
      if (!m.getLayer(layerId)) {
        m.addLayer({
          id: layerId,
          type: "raster",
          source: srcId,
          paint: {
            "raster-opacity": 0,
            "raster-fade-duration": 0,
            "raster-resampling": "nearest",
          },
        }, "world-labels");
      }
    }
  }, [timeMachine, ready]);

  // The crossfade itself. MapLibre does not tween paint properties, so the
  // walk toward the target opacities is done here, one rAF tick at a time.
  // Reduced motion cuts instead of tweens (the rail sets data-reduce too, so
  // both halves of the transition agree).
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !timeMachine) return;

    const targets = epochOpacities(timeMachine, tmIndex);
    const layerIds = Object.keys(targets).filter((id) => m.getLayer(`lyr-${id}`));
    if (layerIds.length === 0) return;

    if (reduce) {
      for (const id of layerIds) {
        m.setPaintProperty(`lyr-${id}`, "raster-opacity", targets[id]!);
      }
      return;
    }

    const from = new Map<string, number>(
      layerIds.map((id) => [
        id,
        (m.getPaintProperty(`lyr-${id}`, "raster-opacity") as number | undefined) ?? 0,
      ]),
    );
    const DURATION = 380;
    const start = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      // Clamp low as well as high: rAF timestamps can arrive earlier than the
      // captured start (vsync alignment), and a negative t sends the eased
      // opacity below 0 — MapLibre rejects that with a validation error.
      const t = Math.min(Math.max((now - start) / DURATION, 0), 1);
      const eased = t * (2 - t); // ease-out quad
      for (const id of layerIds) {
        const a = from.get(id)!;
        const b = targets[id]!;
        m.setPaintProperty(`lyr-${id}`, "raster-opacity", Math.min(Math.max(a + (b - a) * eased, 0), 1));
      }
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [timeMachine, tmIndex, ready, reduce]);

  /* ── layer visibility ───────────────────────────────────────────────────── */

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const map_: Record<string, LayerId> = {
      "lyr-observed": "observation",
      "lyr-baseline": "baseline",
      "lyr-change": "change",
      "lyr-s1-vv": "observation",
    };
    for (const [layerId, key] of Object.entries(map_)) {
      if (m.getLayer(layerId)) {
        m.setLayoutProperty(
          layerId,
          "visibility",
          visible[key] ? "visible" : "none",
        );
      }
    }
    // Time machine epochs are gated by the same category toggles: Before is a
    // baseline scene, After an observation, Change the change layer. The rail
    // controls *time*; these still own *what*.
    const tm_: Record<string, boolean> = {
      "lyr-tm-baseline": visible.baseline,
      "lyr-tm-observed": visible.observation,
      "lyr-tm-change": visible.change,
    };
    for (const [layerId, on] of Object.entries(tm_)) {
      if (m.getLayer(layerId)) {
        m.setLayoutProperty(layerId, "visibility", on ? "visible" : "none");
      }
    }
    for (const id of ["extent-fill", "extent-line"]) {
      if (m.getLayer(id)) {
        m.setLayoutProperty(id, "visibility", visible.observation ? "visible" : "none");
      }
    }
    for (const id of ["aoi-fill", "aoi-line", "aoi-vertices"]) {
      if (m.getLayer(id)) {
        m.setLayoutProperty(id, "visibility", visible.aoi ? "visible" : "none");
      }
    }
    if (m.getLayer("change-fill")) {
      m.setLayoutProperty(
        "change-fill",
        "visibility",
        visible.change ? "visible" : "none",
      );
      m.setLayoutProperty(
        "change-outline",
        "visibility",
        visible.change ? "visible" : "none",
      );
    }
  }, [visible, ready]);

  /* ── change polygons ────────────────────────────────────────────────────── */

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !changeGeoJsonUrl) return;
    if (m.getSource("change-src")) return;

    m.addSource("change-src", { type: "geojson", data: changeGeoJsonUrl });
    m.addLayer({
      id: "change-fill",
      type: "fill",
      source: "change-src",
      paint: { "fill-color": ACCENT, "fill-opacity": 0.22 },
    }, "world-labels");
    m.addLayer({
      id: "change-outline",
      type: "line",
      source: "change-src",
      paint: { "line-color": ACCENT, "line-width": 1 },
    }, "world-labels");

    if (onSelectChange) {
      m.on("click", "change-fill", (e) => {
        const f = e.features?.[0];
        onSelectChange(f ? String(f.id ?? f.properties?.rank ?? "") : null);
      });
      m.on("mouseenter", "change-fill", () => {
        m.getCanvas().style.cursor = "pointer";
      });
      m.on("mouseleave", "change-fill", () => {
        m.getCanvas().style.cursor = "";
      });
    }
  }, [changeGeoJsonUrl, ready, onSelectChange]);

  /* ── measured water extent (live) ──────────────────────────────────────── */

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const data: GeoJSON.FeatureCollection = extent ?? { type: "FeatureCollection", features: [] };
    const src = m.getSource("extent-src") as GeoJSONSource | undefined;
    if (src) {
      src.setData(data);
    } else {
      m.addSource("extent-src", { type: "geojson", data });
      m.addLayer({
        id: "extent-fill",
        type: "fill",
        source: "extent-src",
        paint: { "fill-color": WATER, "fill-opacity": overlayOpacity },
      }, "world-labels");
      m.addLayer({
        id: "extent-line",
        type: "line",
        source: "extent-src",
        paint: { "line-color": WATER, "line-width": 1, "line-opacity": 0.9 },
      }, "world-labels");
    }
    // overlayOpacity is applied by its own effect; adding it here would rebuild
    // the source on every slider move.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extent, ready]);

  // One opacity for whatever result overlay is on the map: the measured water
  // fill in live mode, the scene rasters in the demo.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    if (m.getLayer("extent-fill")) m.setPaintProperty("extent-fill", "fill-opacity", overlayOpacity);
    if (m.getLayer("change-fill")) m.setPaintProperty("change-fill", "fill-opacity", overlayOpacity * 0.5);
    for (const ov of overlays) {
      const id = `lyr-${ov.id}`;
      if (m.getLayer(id)) m.setPaintProperty(id, "raster-opacity", Math.min(1, overlayOpacity + 0.3));
    }
  }, [overlayOpacity, ready, overlays, extent]);

  /* ── AOI render ─────────────────────────────────────────────────────────── */

  const aoiFeature = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: aoi
        ? [{ type: "Feature" as const, geometry: aoi, properties: {} }]
        : [],
    }),
    [aoi],
  );

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;

    const src = m.getSource("aoi-src") as GeoJSONSource | undefined;
    if (src) {
      src.setData(aoiFeature);
      return;
    }

    m.addSource("aoi-src", { type: "geojson", data: aoiFeature });
    m.addLayer({
      id: "aoi-fill",
      type: "fill",
      source: "aoi-src",
      paint: { "fill-color": ACCENT, "fill-opacity": 0.06 },
    });
    m.addLayer({
      id: "aoi-line",
      type: "line",
      source: "aoi-src",
      paint: {
        "line-color": ACCENT,
        "line-width": 1.5,
        "line-dasharray": [3, 2],
      },
    });
  }, [aoiFeature, ready]);

  /* ── AOI drawing ────────────────────────────────────────────────────────── */

  const draftPolygon = useMemo<GeoJSONPolygon | null>(() => {
    if (drawMode === "rectangle") {
      const a = draft[0];
      if (!a || !hover) return null;
      return rectanglePolygon([a[0]!, a[1]!], hover);
    }
    if (draft.length < 3) return null;
    return { type: "Polygon", coordinates: [[...draft, draft[0] as number[]]] };
  }, [draft, drawMode, hover]);

  const validation: ValidationResult = useMemo(
    () => validateAOI(drawing ? draftPolygon : aoi),
    [drawing, draftPolygon, aoi],
  );

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !drawing) return;

    const onClick = (e: MapMouseEvent) => {
      const p: [number, number] = [e.lngLat.lng, e.lngLat.lat];
      if (drawMode === "rectangle") {
        const first = corner.current;
        if (!first) {
          corner.current = p;
          setDraft([p]);
          return;
        }
        const rect = rectanglePolygon(first, p);
        if (validateAOI(rect).valid) {
          corner.current = null;
          onAoiChange(rect);
          setDrawMode(null);
          setHover(null);
          setDraft([]);
        }
        return;
      }
      setDraft((d) => [...d, p]);
    };
    const onMove = (e: MapMouseEvent) => {
      if (drawMode === "rectangle") setHover([e.lngLat.lng, e.lngLat.lat]);
    };
    m.on("click", onClick);
    m.on("mousemove", onMove);
    m.getCanvas().style.cursor = "crosshair";
    // A drag would pan the map away from the corner being placed.
    if (drawMode === "rectangle") m.dragPan.disable();
    return () => {
      m.off("click", onClick);
      m.off("mousemove", onMove);
      m.getCanvas().style.cursor = "";
      m.dragPan.enable();
    };
  }, [drawing, drawMode, ready, onAoiChange]);

  // Live draft outline while drawing.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const data = {
      type: "FeatureCollection" as const,
      features: draftPolygon
        ? [{ type: "Feature" as const, geometry: draftPolygon, properties: {} }]
        : [],
    };
    const src = m.getSource("draft-src") as GeoJSONSource | undefined;
    if (src) {
      src.setData(data);
      return;
    }
    m.addSource("draft-src", { type: "geojson", data });
    m.addLayer({
      id: "draft-line",
      type: "line",
      source: "draft-src",
      paint: { "line-color": ACCENT, "line-width": 1.5 },
    });
  }, [draftPolygon, ready]);

  const commitDraw = useCallback(() => {
    if (draftPolygon && validateAOI(draftPolygon).valid) {
      onAoiChange(draftPolygon);
      setDrawing(false);
      setDraft([]);
    }
  }, [draftPolygon, onAoiChange, setDrawing]);

  const cancelDraw = useCallback(() => {
    corner.current = null;
    setDrawMode(null);
    setDraft([]);
    setHover(null);
  }, []);

  const runSearch = useCallback(async () => {
    setSearchError(null);
    setResults(null);
    setSearching(true);
    try {
      const found = await searchPlace(search);
      setResults(found);
      if (found.length === 0) setSearchError("No place found.");
    } catch (caught) {
      setSearchError(caught instanceof GeocodeError ? caught.message : "Place search failed.");
    } finally {
      setSearching(false);
    }
  }, [search]);

  const flyToPlace = useCallback((place: PlaceResult) => {
    const m = map.current;
    if (!m) return;
    const [w, s, e, n] = place.bbox;
    m.fitBounds([[w, s], [e, n]], { padding: 48, duration: 900, maxZoom: 13 });
    setResults(null);
  }, []);

  // Escape cancels a draw in progress (P5-15: no mode without a keyboard exit).
  useEffect(() => {
    if (!drawing) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") cancelDraw();
      if (e.key === "Enter") commitDraw();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawing, cancelDraw, commitDraw]);

  /* ── fit to AOI ─────────────────────────────────────────────────────────── */

  const fitToAoi = useCallback(() => {
    const m = map.current;
    if (!m || !aoi) return;
    const ring = aoi.coordinates[0] ?? [];
    const lons = ring.map((p) => p[0] as number);
    const lats = ring.map((p) => p[1] as number);
    const bounds: LngLatBoundsLike = [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ];
    m.fitBounds(bounds, { padding: { top: 120, bottom: 90, left: 70, right: 70 }, duration: 600 });
  }, [aoi]);

  useEffect(() => {
    if (ready && aoi) fitToAoi();
  }, [ready, aoi, fitToAoi]);

  /* ── render ─────────────────────────────────────────────────────────────── */

  const layerList = (availableLayers ?? (Object.keys(LAYER_LABELS) as LayerId[])).filter(
    (id) => id in LAYER_LABELS,
  );
  const hasOverlay = layerList.some((id) => id !== "aoi");

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div
        ref={holder}
        style={{ position: "absolute", inset: 0 }}
        role="application"
        aria-label="Mission map. Use the layer controls to change what is shown."
      />

      {/* Place search — top left (audit F4). Searches on submit only, per
          Nominatim's usage policy. */}
      {placeSearch ? (
        <form
          className="mw-search"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            void runSearch();
          }}
        >
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search a place, e.g. Nagaon, Assam"
            aria-label="Search a place"
          />
          <button className="btn" type="submit" disabled={searching || search.trim().length < 2}>
            {searching ? "…" : "Go"}
          </button>
          {results && results.length > 0 ? (
            <ul className="mw-search-results" role="listbox" aria-label="Places found">
              {results.map((r) => (
                <li key={`${r.center[0]},${r.center[1]}`}>
                  <button type="button" role="option" aria-selected="false" onClick={() => flyToPlace(r)}>
                    <b>{r.name.split(",")[0]}</b>
                    <small>{r.name.split(",").slice(1, 4).join(",")}</small>
                  </button>
                </li>
              ))}
              <li className="mw-search-credit">Search © OpenStreetMap contributors</li>
            </ul>
          ) : null}
          {searchError ? <p className="mw-search-error" role="status">{searchError}</p> : null}
        </form>
      ) : null}

      {/* Layers — bottom left, above the coordinates: only layers that exist,
          each with its legend colour, plus one overlay opacity (audit F6). */}
      <div className="mw-layers">
        <div className="mw-layers-head">
          <Label>Layers</Label>
        </div>
        <div className="mw-layers-body" role="group" aria-label="Map layers">
          {layerList.length === 0 ? (
            <span className="label label-faint">Nothing on the map yet</span>
          ) : (
            layerList.map((id) => (
              <label key={id} className="mw-layers-row">
                <input
                  type="checkbox"
                  checked={visible[id]}
                  onChange={() => onToggleLayer(id)}
                  style={{ accentColor: LAYER_ACCENT[id] }}
                />
                <i
                  className={`mw-swatch ${id === "aoi" ? "is-line" : ""}`}
                  style={{ ["--sw" as string]: LAYER_ACCENT[id] }}
                  aria-hidden="true"
                />
                <span className="label">{LAYER_LABELS[id]}</span>
              </label>
            ))
          )}
          {hasOverlay ? (
            <label className="mw-opacity">
              <span className="label label-faint">Opacity</span>
              <input
                type="range"
                min={0.1}
                max={1}
                step={0.05}
                value={overlayOpacity}
                onChange={(e) => setOverlayOpacity(Number(e.target.value))}
                aria-label="Result overlay opacity"
              />
            </label>
          ) : null}
        </div>
      </div>

      {/* Zoom + AOI tools — top right */}
      <div className="mw-tools">
        <div className="row" style={{ gap: 0 }}>
          <button
            className="btn btn-icon"
            style={{ borderRight: "none" }}
            onClick={() => map.current?.zoomIn()}
            aria-label="Zoom in"
          >
            +
          </button>
          <button
            className="btn btn-icon"
            onClick={() => map.current?.zoomOut()}
            aria-label="Zoom out"
          >
            −
          </button>
        </div>

        {drawing ? (
          <div className="row" style={{ gap: 6 }}>
            <button className="btn" onClick={cancelDraw}>
              Cancel
            </button>
            {drawMode === "polygon" ? (
              <button
                className="btn btn-primary"
                onClick={commitDraw}
                disabled={!validation.valid}
              >
                Commit
              </button>
            ) : null}
          </div>
        ) : (
          <div className="mw-tool-row">
            <button className="btn" onClick={() => setDrawing(true)} disabled={aoiLocked}>
              Draw AOI
            </button>
            <button
              className="btn"
              onClick={() => {
                corner.current = null;
                setDraft([]);
                setDrawMode("rectangle");
              }}
              disabled={aoiLocked}
              aria-label="Draw rectangle"
            >
              Rectangle
            </button>
            {aoi ? (
              <>
                <button className="btn" onClick={fitToAoi} aria-label="Zoom to AOI">
                  Fit
                </button>
                <button
                  className="btn"
                  onClick={() => onAoiChange(null)}
                  disabled={aoiLocked}
                  aria-label="Clear AOI"
                >
                  Clear
                </button>
              </>
            ) : null}
          </div>
        )}
      </div>

      {/* Validation — shown the moment it is known, never hidden (P5-06) */}
      {(drawing || (aoi !== null && validation.findings.length > 0)) && (
        <div className="mw-validation" role="status" aria-live="polite">
          <div className="row" style={{ marginBottom: 6 }}>
            <Label>AOI</Label>
            <div className="band-spacer" />
            <StatusChip tone={validation.valid ? "ok" : "warn"}>
              {validation.valid ? "Valid" : drawing ? "Drawing" : "Invalid"}
            </StatusChip>
          </div>
          <div className="readout">
            <Label faint>{drawMode === "rectangle" ? "Corners" : "Vertices"}</Label>
            <span className="readout-value">
              {drawing ? draft.length : (aoi?.coordinates[0]?.length ?? 1) - 1}
            </span>
          </div>
          <div className="readout">
            <Label faint>Area</Label>
            <span className="readout-value">{formatArea(validation.areaSqM)}</span>
          </div>
          {validation.findings
            .filter((f) => !(drawing && f.rule === "aoi.missing"))
            .map((f) => (
              <p
                key={f.rule}
                className="mono"
                style={{
                  margin: "6px 0 0",
                  fontSize: 10,
                  lineHeight: 1.45,
                  color: f.severity === "error" ? "var(--danger)" : "var(--warn)",
                }}
              >
                {f.severity === "error" ? "✕" : "▲"} {f.message}
              </p>
            ))}
          {drawing && (
            <p className="label label-faint" style={{ marginTop: 8 }}>
              {drawMode === "rectangle"
                ? "Click one corner, then the opposite corner · Esc cancels"
                : "Click to add corners · Enter commits · Esc cancels"}
            </p>
          )}
        </div>
      )}

      {/* Earth Time Machine — bottom centre, above the telemetry strip (PRD §2A). */}
      {timeMachine ? (
        <TimeMachine
          model={timeMachine}
          onChange={setTmIndex}
        />
      ) : null}

      {/* Coordinate telemetry — bottom left */}
      <div className="mw-coords">
        <Pair k="LAT" v={formatLat(cursor.lat)} />
        <Pair k="LON" v={formatLon(cursor.lon)} />
        <Pair k="ZOOM" v={formatZoom(cursor.zoom)} />
      </div>
    </div>
  );
}

function Pair({ k, v }: { k: string; v: string }) {
  return (
    <span className="row" style={{ gap: 5 }}>
      <Label faint>{k}</Label>
      <span className="mono" style={{ fontSize: 10 }}>
        {v}
      </span>
    </span>
  );
}
