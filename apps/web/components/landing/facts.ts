/**
 * Every figure the landing page states, with where it comes from.
 *
 * reports/evaluation.md opens with the rule this file exists to keep: "No number
 * about this subsystem may appear in a slide, a README or a demo script unless it
 * appears here first." The landing page is the most-seen of those surfaces, so each
 * constant below names the report table it was copied from. When the reports are
 * regenerated, this is the one file to update -- and a figure that cannot be traced
 * to a table does not belong on the page.
 *
 * Not imported from lib/fixtures on purpose: those are demo-run values, badged as
 * FIXTURE wherever they render. The landing page quotes measurements, not the demo.
 */

/** reports/evaluation.md -- "Headline" table, hand-only-v2 vs deterministic baseline. */
export const HEADLINE = {
  model: "hand-only-v2",
  pooledIoU: 0.435,
  pooledF1: 0.606,
  baselinePooledIoU: 0.204,
  baselinePooledF1: 0.339,
  meanPerChipIoU: 0.254,
  baselineMeanPerChipIoU: 0.209,
  heldOutRegions: ["India", "Somalia"] as const,
  heldOutChips: 92,
  trainChips: 308,
  chipsScored: 395,
  chipsFetched: 400,
  regionCount: 10,
} as const;

/** reports/evaluation.md -- "Do not quote accuracy for this task." */
export const ACCURACY_TRAP = {
  waterFractionPct: 10.8,
  predictNothingAccuracyPct: 89.2,
  predictNothingIoU: 0.0,
} as const;

/** artifacts/hand-only-v2/metrics.json -- parameters, in_channels. */
export const MODEL = {
  architecture: "U-Net",
  parameters: 486_553,
  inputs: "SAR VV + VH + permanent-water prior",
} as const;

/** reports/calibration.md -- "Does it help?" and "Verdict". */
export const CALIBRATION = {
  eceRaw: 0.0896,
  eceScaled: 0.0583,
  bar: 0.05,
  passes: false,
  temperature: 0.749,
  fittedOn: "Somalia, 24 chips",
  reportedOn: "India, 68 chips",
} as const;

export type Split = "trained" | "held-out";

export interface RegionResult {
  name: string;
  split: Split;
  chips: number;
  baselineIoU: number;
  modelIoU: number;
  /** Country-level marker position [lon, lat]. Not a chip footprint. */
  at: [number, number];
}

/**
 * reports/evaluation.md -- "By region". The coordinates are country centroids for
 * placing a marker on the globe; they are geography, not data from the report.
 * Mekong is placed on the lower Mekong basin.
 */
export const REGIONS: readonly RegionResult[] = [
  { name: "Ghana", split: "trained", chips: 48, baselineIoU: 0.104, modelIoU: 0.216, at: [-1.0, 7.9] },
  { name: "India", split: "held-out", chips: 68, baselineIoU: 0.255, modelIoU: 0.309, at: [79.0, 22.0] },
  { name: "Mekong", split: "trained", chips: 30, baselineIoU: 0.531, modelIoU: 0.513, at: [105.0, 12.5] },
  { name: "Nigeria", split: "trained", chips: 18, baselineIoU: 0.331, modelIoU: 0.319, at: [8.0, 9.6] },
  { name: "Pakistan", split: "trained", chips: 28, baselineIoU: 0.141, modelIoU: 0.197, at: [69.3, 30.0] },
  { name: "Paraguay", split: "trained", chips: 67, baselineIoU: 0.224, modelIoU: 0.342, at: [-58.4, -23.4] },
  { name: "Somalia", split: "held-out", chips: 24, baselineIoU: 0.08, modelIoU: 0.098, at: [46.2, 5.2] },
  { name: "Spain", split: "trained", chips: 24, baselineIoU: 0.261, modelIoU: 0.342, at: [-3.7, 40.4] },
  { name: "Sri Lanka", split: "trained", chips: 33, baselineIoU: 0.202, modelIoU: 0.299, at: [80.7, 7.9] },
  { name: "USA", split: "trained", chips: 55, baselineIoU: 0.14, modelIoU: 0.334, at: [-98.6, 39.8] },
];

/** The demo AOI: Sen1Floods11 chip India_533192, Brahmaputra floodplain, Assam. */
export const DEMO_AOI = {
  name: "Assam, India",
  detail: "Brahmaputra floodplain · the console's demo area",
  at: [93.896, 26.791] as [number, number],
} as const;

/** Formatting helpers so every figure renders to the precision its report gives. */
export const f3 = (v: number) => v.toFixed(3);
export const ratio = (a: number, b: number) => `${(a / b).toFixed(1)}×`;
