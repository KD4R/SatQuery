"use client";

/**
 * The dashboard's map card, wrapping the console's MapWorkspace so the map
 * speaks the same language on both surfaces. In demo mode, once the run
 * completes, the Earth Time Machine rail (Before → After → Change) appears on
 * the map, built from the same pinned Assam scenario the console uses — one
 * source of truth, no invented dates (the fixture's honesty rules carry over).
 *
 * The run itself belongs to the Dashboard (its QueryConsole drives it); this
 * card only observes its phase. Owning a second run here would leave it idle
 * forever — its `complete` would never turn true and the Time Machine rail
 * would never appear.
 */

import { useMemo } from "react";

import { ProvenanceBadge } from "./system/primitives";
import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../lib/fixtures";
import { buildTimeMachine } from "../lib/map/timeLayers";
import { demoModeEnabled } from "../lib/api/source";
import { MapWorkspace } from "./map/MapWorkspace";
import type { LayerId } from "./map/MapWorkspace";
import type { GeoJSONPolygon } from "../lib/api/types";

const ALL_LAYERS: Record<LayerId, boolean> = {
  observation: true,
  baseline: true,
  change: true,
  confidence: true,
  aoi: true,
};

export default function MapCanvas({ complete = false }: { complete?: boolean }) {
  const demo = demoModeEnabled();

  const timeMachine = useMemo(
    () => (demo && complete ? buildTimeMachine(ASSAM_SCENARIO) : null),
    [demo, complete],
  );

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
        center={[93.8962, 26.7914]}
        zoom={12.4}
        aoi={ASSAM_SCENARIO.aoi as GeoJSONPolygon}
        onAoiChange={() => {
          /* AOI editing stays console-only for now. */
        }}
        overlays={Object.entries(ASSAM_SCENARIO.overlays).map(([id, ov]) => ({
          id,
          url: ov.url,
          bbox: ov.bbox,
        }))}
        changeGeoJsonUrl={
          complete && demo ? ASSAM_SCENARIO.changeGeoJsonUrl : null
        }
        timeMachine={timeMachine}
        visible={ALL_LAYERS}
        onToggleLayer={() => {
          /* Layer toggles stay console-only for now. */
        }}
      />
    </div>
  );
}
