"use client";

/**
 * The mission console's map card, wrapping MapWorkspace (MapLibre, AOI draw/edit,
 * layer toggles).
 *
 * The AOI, the layer visibility and the run phase all belong to the Dashboard,
 * because the query, the parameters card and the intelligence section have to
 * quote the same AOI the map is drawing — this card only renders them. In demo
 * mode, once the run completes, the Earth Time Machine rail (Before → After →
 * Change) appears, built from the pinned Assam scenario — one source of truth, no
 * invented dates.
 *
 * Nothing scenario-shaped is drawn in live mode. The pinned rasters are a demo
 * artefact; painting them over a live AOI would present a fixture as an observation.
 */

import dynamic from "next/dynamic";
import { useMemo } from "react";

import { ProvenanceBadge } from "./system/primitives";
import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../lib/fixtures";
import { buildTimeMachine } from "../lib/map/timeLayers";
import { demoModeEnabled } from "../lib/api/source";
import type { LayerId } from "./map/MapWorkspace";
import type { GeoJSONPolygon } from "../lib/api/types";

/**
 * MapLibre is ~800 KB of WebGL. Loading it on demand keeps it off the critical
 * path (P5-16); ssr:false because it needs a canvas.
 */
const MapWorkspace = dynamic(
  () => import("./map/MapWorkspace").then((m) => m.MapWorkspace),
  {
    ssr: false,
    loading: () => (
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>
        <span className="label label-faint">Loading map…</span>
      </div>
    ),
  },
);

/** Where the map opens with no AOI: India, country scale. */
const INDIA_CENTER: [number, number] = [78.9, 22.6];
const ASSAM_CENTER: [number, number] = [93.8962, 26.7914];

export default function MapCanvas({
  complete = false,
  aoi,
  onAoiChange,
  visible,
  onToggleLayer,
  extent = null,
  aoiLocked = false,
}: {
  complete?: boolean;
  aoi: GeoJSONPolygon | null;
  onAoiChange: (aoi: GeoJSONPolygon | null) => void;
  visible: Record<LayerId, boolean>;
  onToggleLayer: (id: LayerId) => void;
  /** Live: the measured water polygons for the completed run. */
  extent?: GeoJSON.FeatureCollection | null;
  aoiLocked?: boolean;
}) {
  const demo = demoModeEnabled();

  const timeMachine = useMemo(
    () => (demo && complete ? buildTimeMachine(ASSAM_SCENARIO) : null),
    [demo, complete],
  );

  // Only the pre-run backdrop lives here: once a run completes the Time Machine
  // owns the baseline/observed/change rasters as crossfade epochs, so listing
  // them as static overlays too would draw every scene twice.
  const overlays = useMemo(() => {
    if (!demo) return [];
    const s = ASSAM_SCENARIO.overlays["s1-vv"];
    return s ? [{ id: "s1-vv", url: s.url, bbox: s.bbox }] : [];
  }, [demo]);

  // Only layers that exist are offered (audit F6): the demo's pinned rasters
  // and change polygons, or in live mode the AOI and, once measured, the water.
  const availableLayers = useMemo<LayerId[]>(() => {
    if (demo) return complete ? ["observation", "baseline", "change", "aoi"] : ["observation", "aoi"];
    const ids: LayerId[] = [];
    if (extent && extent.features.length > 0) ids.push("observation");
    if (aoi) ids.push("aoi");
    return ids;
  }, [demo, complete, extent, aoi]);

  return (
    <div className="map-canvas-host">
      {demo && (
        <div
          style={{
            position: "absolute",
            top: 10,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 20,
          }}
        >
          <ProvenanceBadge source="fixture" at={FIXTURE_EPOCH} />
        </div>
      )}
      <MapWorkspace
        center={demo ? ASSAM_CENTER : INDIA_CENTER}
        zoom={demo ? 12.4 : 4}
        aoi={aoi}
        onAoiChange={onAoiChange}
        overlays={overlays}
        changeGeoJsonUrl={
          complete && demo ? ASSAM_SCENARIO.changeGeoJsonUrl : null
        }
        timeMachine={timeMachine}
        visible={visible}
        onToggleLayer={onToggleLayer}
        availableLayers={availableLayers}
        extent={demo ? null : extent}
        placeSearch={!demo}
        aoiLocked={aoiLocked}
      />
    </div>
  );
}
