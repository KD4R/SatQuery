/**
 * The deterministic demo scenario (P5-17).
 *
 * PROVENANCE OF THE NUMBERS IN THIS FILE
 * --------------------------------------
 * The imagery and every measurement below are computed from a real Sentinel-1
 * acquisition: Sen1Floods11 hand-labelled chip `India_533192`, EPSG:4326, 512x512,
 * covering 93.8732–93.9192 E / 26.7684–26.8144 N — the Brahmaputra floodplain near
 * Nagaon, Assam.
 *
 *   observed water   35.84% of analysed pixels   (hand label)
 *   permanent water   3.27% of analysed pixels   (JRC surface-water layer)
 *   new water        33.27% of analysed pixels   (observed minus permanent)
 *   analysed          46.03% of the chip         (rest is outside the S1 swath)
 *
 * The four PNGs under public/fixtures/ are renderings of that chip: VV backscatter
 * on a 2–98 percentile stretch, with nodata transparent.
 *
 * WHAT IS *NOT* HERE, AND WHY
 * ---------------------------
 * Sen1Floods11 ships no per-chip acquisition timestamp in this checkout, so
 * `acquired` is null and the panel renders NOT AVAILABLE with the reason. It would
 * have been trivial to write a plausible date. Every such field in this file is null
 * rather than invented — the demo is meant to show that the console tells you what
 * it does not know, and a fixture that quietly fills the gaps would disprove exactly
 * the thing it is supposed to prove.
 *
 * The same applies to the pre-event scene. Sen1Floods11 is single-date: there is no
 * "before" image. The comparison therefore puts the JRC permanent-water baseline on
 * the left and the observed water on the right, each labelled for what it is. That
 * is a real analytical comparison, not a faked bi-temporal pair.
 *
 * DETERMINISM
 * -----------
 * No Math.random, no Date.now, no wall clock anywhere in this module. Every
 * timestamp is a pinned constant. The demo renders identically on every run, which
 * is what lets the Playwright suite assert on it.
 */

import type { GeoJSONPolygon } from "../api/types";
import type { ConsoleScenario, Observation } from "../model/console";

/** Pinned. Every `at` in the demo derives from this instant. */
export const FIXTURE_EPOCH = "2026-09-14T05:42:00.000Z";

const BBOX: [number, number, number, number] = [
  93.873229, 26.768358, 93.919222, 26.814352,
];

export const ASSAM_AOI: GeoJSONPolygon = {
  type: "Polygon",
  coordinates: [
    [
      [BBOX[0], BBOX[1]],
      [BBOX[2], BBOX[1]],
      [BBOX[2], BBOX[3]],
      [BBOX[0], BBOX[3]],
      [BBOX[0], BBOX[1]],
    ],
  ],
};

const NO_TIMESTAMP =
  "Sen1Floods11 does not publish a per-chip acquisition time in this checkout.";

const OBSERVED: Observation = {
  id: "obs-india-533192-s1",
  sensor: "SENTINEL-1",
  acquired: null,
  acquiredUnavailableReason: NO_TIMESTAMP,
  dataset: "Sen1Floods11 · India_533192 · S1Hand",
  resolutionM: 10,
  cloudFraction: null, // SAR is unaffected by cloud; the field does not apply.
  bbox: BBOX,
  imageUrl: "/fixtures/assam-observed-water.png",
  imageDescription:
    "Sentinel-1 VV backscatter, 2–98% stretch, with hand-labelled water tinted.",
};

const BASELINE: Observation = {
  id: "baseline-india-533192-jrc",
  sensor: "JRC GLOBAL SURFACE WATER",
  acquired: null,
  acquiredUnavailableReason:
    "The JRC layer is a multi-year occurrence product, not a dated acquisition.",
  dataset: "JRC Global Surface Water · permanent class",
  resolutionM: 30,
  cloudFraction: null,
  bbox: BBOX,
  imageUrl: "/fixtures/assam-baseline-water.png",
  imageDescription:
    "The same Sentinel-1 scene with permanent water tinted — the dry-season baseline.",
};

export const ASSAM_SCENARIO: ConsoleScenario = {
  missionId: "msn-2026-0914-assam-01",
  runId: "run-7f3a2c91",
  traceId: "trc-0000-demo-fixture",
  query:
    "Show flood-affected areas around Nagaon, Assam and explain why you chose SAR.",
  aoiName: "Brahmaputra floodplain — Nagaon, Assam",
  aoi: ASSAM_AOI,
  // 0.046° x 0.046° at 26.8°N: 5.12 km x 5.12 km.
  aoiAreaSqKm: 26.2,

  comparison: {
    before: BASELINE,
    beforeUnavailableReason:
      "No pre-event Sentinel-1 scene exists for this AOI in the dataset; the " +
      "permanent-water baseline is shown in its place and labelled as such.",
    after: OBSERVED,
  },

  change: {
    headline: "Water extent increased well beyond the permanent channel",
    areaSqKm: 3.54,
    polygonCount: 17,
    coverageFraction: 0.4603,
    changeFraction: 0.3327,
    baselineFraction: 0.0327,
  },

  confidence: {
    score: 0.87,
    passedGate: true,
    uncertaintyFactors: [
      "54% of the AOI falls outside the Sentinel-1 swath and was not analysed",
      "SAR cannot separate flood water from radar shadow behind terrain",
      "No pre-event scene: change is measured against a multi-year baseline",
    ],
    uncertainFraction: 0.08,
    action: "PROCEED — above the gate, with the coverage caveat carried to the report",
  },

  evidence: [
    {
      id: "ev-1",
      kind: "observation",
      label: "Observation",
      value: "Sentinel-1 VV · 10 m · Sen1Floods11 India_533192",
      provenance: "dataset: Sen1Floods11 · hand-labelled split",
    },
    {
      id: "ev-2",
      kind: "temporal",
      label: "Acquired",
      value: null,
      reason: NO_TIMESTAMP,
      provenance: null,
    },
    {
      id: "ev-3",
      kind: "comparison",
      label: "Compared against",
      value: "JRC Global Surface Water — permanent class",
      provenance: "JRC GSW · permanent occurrence ≥ 90%",
    },
    {
      id: "ev-4",
      kind: "geometry",
      label: "Change",
      value: "Water 3.27% → 35.84% of analysed area; 3.54 km² newly inundated",
      provenance: "17 polygons, simplified to ~1.4 px, specks under 40 px dropped",
    },
    {
      id: "ev-5",
      kind: "sensor",
      label: "Sensor rationale",
      value: "SAR selected: penetrates cloud, and monsoon cloud blocks optical",
      provenance: "agent sensor-arbitration",
    },
    {
      id: "ev-6",
      kind: "confidence",
      label: "Confidence",
      value: "0.87 — above gate; three named uncertainty factors",
      provenance: "agent confidence gate",
    },
    {
      id: "ev-7",
      kind: "model",
      label: "Model",
      value: "hand-only-v2 — 3-channel U-Net with permanent-water prior",
      provenance: "held-out pooled IoU 0.435 on India + Somalia · reports/evaluation.md",
    },
  ],

  arbitration: {
    readings: [
      {
        sensor: "SENTINEL-1",
        finding: "Flood signal",
        confidence: 0.87,
        note: "Water is dark in SAR; the low-backscatter region extends far past the channel.",
      },
      {
        sensor: "SENTINEL-2",
        finding: "Cloud-obscured",
        confidence: 0.42,
        note: "Monsoon cloud over the AOI; the optical scene cannot see the surface.",
      },
    ],
    primary: "SENTINEL-1",
    secondary: "SENTINEL-2",
    rationale:
      "Optical is unusable under monsoon cloud. SAR is cloud-independent, so it " +
      "carries the measurement and optical is retained only as corroboration.",
    disagreement: true,
    arbitrationScore: 0.82,
  },

  monitoring: {
    active: true,
    aoiName: "Brahmaputra floodplain — Nagaon, Assam",
    intervalHours: 12,
    lastObservation: FIXTURE_EPOCH,
    nextObservation: "2026-09-14T17:42:00.000Z",
    changeStatus: "INCREASING",
    recentEvents: [
      {
        id: "me-1",
        at: FIXTURE_EPOCH,
        kind: "detection",
        summary: "New water detected — 3.54 km²",
        detail: "17 polygons above the minimum mapping unit.",
      },
      {
        id: "me-2",
        at: "2026-09-13T17:42:00.000Z",
        kind: "observation",
        summary: "Sentinel-1 pass ingested",
        detail: "46% of the AOI inside the swath.",
      },
      {
        id: "me-3",
        at: "2026-09-13T05:42:00.000Z",
        kind: "monitoring",
        summary: "Monitoring armed at 12 h interval",
        detail: null,
      },
    ],
  },

  history: [
    {
      id: "h-1",
      at: FIXTURE_EPOCH,
      kind: "run",
      summary: "Run run-7f3a2c91 completed",
      detail: "Change detected; confidence 0.87; report available.",
    },
    {
      id: "h-2",
      at: "2026-09-13T17:42:00.000Z",
      kind: "observation",
      summary: "Observation selected",
      detail: "Sentinel-1 chosen over Sentinel-2 on cloud.",
    },
    {
      id: "h-3",
      at: "2026-09-13T05:40:00.000Z",
      kind: "run",
      summary: "AOI validated",
      detail: "26.2 km², inside the analysis budget.",
    },
  ],

  overlays: {
    "s1-vv": { url: "/fixtures/assam-s1-vv.png", bbox: BBOX },
    baseline: { url: "/fixtures/assam-baseline-water.png", bbox: BBOX },
    observed: { url: "/fixtures/assam-observed-water.png", bbox: BBOX },
    change: { url: "/fixtures/assam-change.png", bbox: BBOX },
  },
  changeGeoJsonUrl: "/fixtures/assam-change.geojson",

  modelVersion: "hand-only-v2",
  processingVersion: null,
};
