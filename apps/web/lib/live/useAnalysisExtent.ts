"use client";

/**
 * The water polygons an analysis measured, for the map (audit W8).
 *
 * Fetched once per inference trace id through the gateway
 * (GET /api/v1/inference/analyses/{trace_id}/extent). The inference service
 * stores them when the analysis runs; when no artifact store is configured the
 * route answers 503 and the map says the outline is unavailable instead of
 * drawing nothing silently.
 */

import { useEffect, useState } from "react";

import { GatewayError } from "../api/gateway";
import { getAnalysisExtent } from "../api/client";

export type ExtentState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: GeoJSON.FeatureCollection; features: number }
  | { status: "unavailable"; message: string };

export function useAnalysisExtent(traceId: string | null): ExtentState {
  const [state, setState] = useState<ExtentState>({ status: "idle" });

  useEffect(() => {
    if (!traceId) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading" });
    getAnalysisExtent(traceId, controller.signal)
      .then((res) => {
        const fc = res.data;
        const features = Array.isArray(fc?.features) ? fc.features.length : 0;
        setState({ status: "ready", data: fc, features });
      })
      .catch((caught) => {
        if (controller.signal.aborted) return;
        const message =
          caught instanceof GatewayError
            ? caught.status === 503
              ? "The water outline was not stored (no artifact store is configured on the inference service)."
              : caught.status === 404
                ? "No stored water outline for this analysis."
                : caught.body.message
            : "The water outline could not be loaded.";
        setState({ status: "unavailable", message });
      });
    return () => controller.abort();
  }, [traceId]);

  return state;
}
