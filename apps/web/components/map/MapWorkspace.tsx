"use client";

/**
 * The map (P5-05, P5-06, P5-08).
 *
 * The map is the product, not a widget inside it: it fills the shell's flexible
 * column, has no card, no border radius and no padding, and every control floats
 * over it as a hairline box rather than occupying layout space.
 *
 * Base style is a plain dark canvas with no basemap tiles. That is deliberate:
 * the browser may only call the gateway (PRD section 3), so pulling raster tiles
 * from a third-party host would breach the same rule the API client enforces. The
 * imagery that matters here is the observation overlay, which is the subject anyway.
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
}

const LAYER_LABELS: Record<LayerId, string> = {
  observation: "Observation",
  baseline: "Baseline",
  change: "Change",
  confidence: "Confidence",
  aoi: "AOI",
};

/** A bare dark canvas — no third-party tile hosts. See the note above. */
const EMPTY_STYLE = {
  version: 8 as const,
  sources: {},
  layers: [
    { id: "bg", type: "background" as const, paint: { "background-color": "#04060a" } },
  ],
};

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
}: MapWorkspaceProps) {
  const holder = useRef<HTMLDivElement | null>(null);
  const map = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [cursor, setCursor] = useState<{ lat: number; lon: number; zoom: number }>({
    lat: center[1],
    lon: center[0],
    zoom,
  });

  const [drawing, setDrawing] = useState(false);
  const [draft, setDraft] = useState<number[][]>([]);

  // Which time machine epoch is on screen; owned here so the map can tween the
  // raster opacities while the rail only reports indices.
  const [tmIndex, setTmIndex] = useState(0);
  const reduce = useReducedMotion();

  /* ── init ───────────────────────────────────────────────────────────────── */

  useEffect(() => {
    if (!holder.current || map.current) return;

    const m = new maplibregl.Map({
      container: holder.current,
      style: EMPTY_STYLE,
      center,
      zoom,
      attributionControl: false,
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
        });
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
        });
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
      const t = Math.min((now - start) / DURATION, 1);
      const eased = t * (2 - t); // ease-out quad
      for (const id of layerIds) {
        const a = from.get(id)!;
        const b = targets[id]!;
        m.setPaintProperty(`lyr-${id}`, "raster-opacity", a + (b - a) * eased);
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
      paint: { "fill-color": "#ff3b30", "fill-opacity": 0.22 },
    });
    m.addLayer({
      id: "change-outline",
      type: "line",
      source: "change-src",
      paint: { "line-color": "#ff3b30", "line-width": 1 },
    });

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
      paint: { "fill-color": "#ffffff", "fill-opacity": 0.04 },
    });
    m.addLayer({
      id: "aoi-line",
      type: "line",
      source: "aoi-src",
      paint: {
        "line-color": "#ffffff",
        "line-width": 1,
        "line-dasharray": [4, 3],
      },
    });
  }, [aoiFeature, ready]);

  /* ── AOI drawing ────────────────────────────────────────────────────────── */

  const draftPolygon = useMemo<GeoJSONPolygon | null>(() => {
    if (draft.length < 3) return null;
    return { type: "Polygon", coordinates: [[...draft, draft[0] as number[]]] };
  }, [draft]);

  const validation: ValidationResult = useMemo(
    () => validateAOI(drawing ? draftPolygon : aoi),
    [drawing, draftPolygon, aoi],
  );

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !drawing) return;

    const onClick = (e: MapMouseEvent) => {
      setDraft((d) => [...d, [e.lngLat.lng, e.lngLat.lat]]);
    };
    m.on("click", onClick);
    m.getCanvas().style.cursor = "crosshair";
    return () => {
      m.off("click", onClick);
      m.getCanvas().style.cursor = "";
    };
  }, [drawing, ready]);

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
      paint: { "line-color": "#ff3b30", "line-width": 1.5 },
    });
  }, [draftPolygon, ready]);

  const commitDraw = useCallback(() => {
    if (draftPolygon && validateAOI(draftPolygon).valid) {
      onAoiChange(draftPolygon);
      setDrawing(false);
      setDraft([]);
    }
  }, [draftPolygon, onAoiChange]);

  const cancelDraw = useCallback(() => {
    setDrawing(false);
    setDraft([]);
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
    m.fitBounds(bounds, { padding: 64, duration: 600 });
  }, [aoi]);

  useEffect(() => {
    if (ready && aoi) fitToAoi();
  }, [ready, aoi, fitToAoi]);

  /* ── render ─────────────────────────────────────────────────────────────── */

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div
        ref={holder}
        style={{ position: "absolute", inset: 0 }}
        role="application"
        aria-label="Mission map. Use the layer controls to change what is shown."
      />

      {/* Layers — top left */}
      <div
        style={{
          position: "absolute",
          top: 10,
          left: 10,
          background: "var(--surface-1)",
          border: "1px solid var(--hairline)",
          borderRadius: "var(--radius)",
        }}
      >
        <div
          style={{ padding: "5px 8px", borderBottom: "1px solid var(--hairline)" }}
        >
          <Label>Layers</Label>
        </div>
        <div style={{ padding: 4 }} role="group" aria-label="Map layers">
          {(Object.keys(LAYER_LABELS) as LayerId[]).map((id) => (
            <label
              key={id}
              className="row"
              style={{ padding: "3px 6px", cursor: "pointer", gap: 7 }}
            >
              <input
                type="checkbox"
                checked={visible[id]}
                onChange={() => onToggleLayer(id)}
                style={{ accentColor: "#ff3b30", width: 11, height: 11 }}
              />
              <span className="label" style={{ color: "var(--ink)" }}>
                {LAYER_LABELS[id]}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Zoom + AOI — top right */}
      <div
        style={{
          position: "absolute",
          top: 10,
          right: 10,
          display: "flex",
          flexDirection: "column",
          gap: 6,
          alignItems: "flex-end",
        }}
      >
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
            <button
              className="btn btn-primary"
              onClick={commitDraw}
              disabled={!validation.valid}
            >
              Commit
            </button>
          </div>
        ) : (
          <button className="btn" onClick={() => setDrawing(true)}>
            Draw AOI
          </button>
        )}
      </div>

      {/* Validation — shown the moment it is known, never hidden (P5-06) */}
      {(drawing || validation.findings.length > 0) && (
        <div
          role="status"
          aria-live="polite"
          style={{
            position: "absolute",
            top: 78,
            right: 10,
            width: 280,
            background: "var(--surface-1)",
            border: "1px solid var(--hairline)",
            borderRadius: "var(--radius)",
            padding: 8,
          }}
        >
          <div className="row" style={{ marginBottom: 6 }}>
            <Label>AOI</Label>
            <div className="band-spacer" />
            <StatusChip tone={validation.valid ? "ok" : "warn"}>
              {validation.valid ? "Valid" : "Invalid"}
            </StatusChip>
          </div>
          <div className="readout">
            <Label faint>Vertices</Label>
            <span className="readout-value">
              {drawing ? draft.length : (aoi?.coordinates[0]?.length ?? 1) - 1}
            </span>
          </div>
          <div className="readout">
            <Label faint>Area</Label>
            <span className="readout-value">{formatArea(validation.areaSqM)}</span>
          </div>
          {validation.findings.map((f) => (
            <p
              key={f.rule}
              className="mono"
              style={{
                margin: "6px 0 0",
                fontSize: 10,
                lineHeight: 1.45,
                color: f.severity === "error" ? "var(--signal)" : "var(--amber)",
              }}
            >
              {f.severity === "error" ? "✕" : "▲"} {f.message}
            </p>
          ))}
          {drawing && (
            <p className="label label-faint" style={{ marginTop: 8 }}>
              Click to add corners · Enter commits · Esc cancels
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
      <div
        style={{
          position: "absolute",
          left: 10,
          bottom: 10,
          display: "flex",
          gap: 14,
          background: "var(--surface-1)",
          border: "1px solid var(--hairline)",
          borderRadius: "var(--radius)",
          padding: "4px 10px",
        }}
      >
        <Pair k="LAT" v={formatLat(cursor.lat)} />
        <Pair k="LON" v={formatLon(cursor.lon)} />
        <Pair k="ZOOM" v={formatZoom(cursor.zoom)} />
        <Pair k="CRS" v="EPSG:4326" />
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
