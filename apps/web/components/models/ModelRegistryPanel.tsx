"use client";

/**
 * The live model registry (P3 ↔ P5), read through the gateway.
 *
 * Every figure here comes from GET /api/v1/inference/models -- the registry reading
 * the checkpoint's own metrics.json and calibration.json -- and nothing is filled
 * in by the UI. In particular:
 *
 *   - `beats_baseline: null` renders as NOT MEASURED, not as a loss. The registry
 *     keeps "we did not measure" and "it lost" apart; so does this.
 *   - Calibration shows the ECE *against its bar*. "0.058" alone reads as good; "0.058
 *     against a 0.05 bar — did not pass" is what the number means.
 *   - `checksum_verified: null` means the model has not been loaded yet, not that it
 *     failed. A failed checksum never reaches this list: the registry refuses the
 *     checkpoint and every analysis degrades to the baseline instead.
 *
 * In demo mode there is no gateway, and this panel says so rather than showing a
 * fixture. The registry is a fact about a running service; a pinned copy of it
 * would be exactly the kind of stale claim the rest of the console avoids.
 */

import { useCallback, useEffect, useState } from "react";

import { GatewayError } from "../../lib/api/gateway";
import { listModels } from "../../lib/api/client";
import { demoModeEnabled } from "../../lib/api/source";
import type { ErrorResponse, ModelListResponse, ModelSummary } from "../../lib/api/types";
import { EmptyState, ErrorState, LoadingState } from "../system/ErrorBoundary";
import { Label, Panel, Readout, StatusChip } from "../system/primitives";

export function ModelRegistryPanel() {
  const demo = demoModeEnabled();
  const [data, setData] = useState<ModelListResponse | null>(null);
  const [error, setError] = useState<ErrorResponse | null>(null);

  const load = useCallback((signal?: AbortSignal) => {
    setError(null);
    listModels(signal)
      .then((r) => setData(r.data))
      .catch((e: unknown) => {
        if (signal?.aborted) return;
        setError(
          e instanceof GatewayError
            ? e.body
            : { code: "unknown", message: "The model registry could not be read.", trace_id: null },
        );
      });
  }, []);

  useEffect(() => {
    if (demo) return;
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [demo, load]);

  return (
    <Panel
      title="Model registry"
      actions={data ? <Label faint>{data.models.length} registered</Label> : undefined}
    >
      <div style={{ padding: 10 }}>
        {demo ? (
          <EmptyState
            title="Read live from the inference service"
            hint="Not available in demo mode — there is no gateway to ask"
          />
        ) : error ? (
          <ErrorState title="Model registry unavailable" error={error} onRetry={() => load()} />
        ) : data === null ? (
          <LoadingState label="Reading registry" />
        ) : data.models.length === 0 ? (
          <EmptyState
            title="No models registered"
            hint="Every analysis will run the deterministic baseline and say so"
          />
        ) : (
          <>
            <Readout
              label="Serving by default"
              value={data.default}
              reason="No registered model beats the baseline on held-out regions, so analyses use the baseline."
            />
            <div style={{ marginTop: 8 }}>
              {data.models.map((m) => (
                <ModelCard key={m.name} model={m} isDefault={m.name === data.default} />
              ))}
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

function ModelCard({ model: m, isDefault }: { model: ModelSummary; isDefault: boolean }) {
  const fmt = (v: number | null | undefined, digits = 3) =>
    v === null || v === undefined ? null : v.toFixed(digits);

  const calibration =
    m.calibration_ece === null || m.calibration_ece === undefined
      ? null
      : `ECE ${m.calibration_ece.toFixed(4)}` +
        (m.calibration_bar ? ` against a ${m.calibration_bar} bar` : "");

  return (
    <div
      style={{
        border: "1px solid var(--hairline)",
        borderLeft: `2px solid ${isDefault ? "var(--signal)" : "var(--hairline-bright)"}`,
        padding: 8,
        marginBottom: 8,
      }}
    >
      <div className="row" style={{ gap: 8, marginBottom: 4 }}>
        <span className="mono" style={{ fontSize: 11.5 }}>
          {m.name}@{m.version}
        </span>
        <div className="band-spacer" />
        {isDefault ? <StatusChip tone="active">Default</StatusChip> : null}
        <StatusChip
          tone={m.checksum_verified === true ? "ok" : m.checksum_verified === false ? "warn" : "idle"}
          title={
            m.checksum_verified === true
              ? "sha256 matched the committed manifest."
              : m.checksum_verified === false
                ? "Loaded without a manifest to check against."
                : "Not loaded yet, so not yet checked."
          }
        >
          {m.checksum_verified === true
            ? "Verified"
            : m.checksum_verified === false
              ? "Unverified"
              : "Not loaded"}
        </StatusChip>
      </div>

      <Readout label="Held-out IoU" value={fmt(m.validation_iou)} />
      <Readout label="Baseline IoU" value={fmt(m.baseline_iou)} />
      <Readout
        label="Beats baseline"
        value={m.beats_baseline === null ? null : m.beats_baseline ? "YES" : "NO"}
        reason="One of the two scores was not measured — which is not the same as losing."
        tone={m.beats_baseline === false ? "amber" : undefined}
      />
      <Readout
        label="Validated on"
        value={m.validation_regions.length ? m.validation_regions.join(", ") : null}
      />
      <Readout
        label="Inputs"
        value={
          m.in_channels === null || m.in_channels === undefined
            ? null
            : m.uses_permanent_water_prior
              ? `${m.in_channels}-channel (VV, VH, permanent-water prior)`
              : `${m.in_channels}-channel (VV, VH)`
        }
      />
      <Readout
        label="Calibration"
        value={calibration}
        reason="Calibration has not been measured for this model."
        tone={m.calibration_passes === false ? "amber" : undefined}
      />
      {m.calibration_passes === false ? (
        <p className="mono amb" style={{ margin: "4px 0 0", fontSize: 10, lineHeight: 1.45 }}>
          ▲ Did not pass, so this model reports no confidence value — its scores rank pixels
          but are not probabilities.
        </p>
      ) : null}
    </div>
  );
}
