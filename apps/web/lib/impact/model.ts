/**
 * The Infrastructure Impact view model (PRD §2D).
 *
 * Pure layer between the raw PostGIS intersection (ConsoleScenario.impact) and the
 * panel: it groups the flat records into the Flood → category → items hierarchy and
 * derives the per-category aggregates. Like lib/evidence/graph.ts, it exists so the
 * aggregation rules are testable without a DOM, and so a future live adapter can
 * feed the same component the demo feeds today.
 *
 * AGGREGATION IS DELIBERATELY STRICT
 * ----------------------------------
 * An affected-length total is emitted only when *every* affected record in the
 * category carries a length. A partial sum printed as a total would understate
 * exposure ("2.46 km affected" when a third road is affected but unmeasured), and
 * the console's premise is that unknown stays visible. The panel still shows the
 * per-item figures it does have; the total renders NOT AVAILABLE with the reason.
 */

import type { ConsoleScenario, ImpactRecord } from "../model/console";

/** One leaf of the hierarchy: a single PostGIS record. */
export interface ImpactItem {
  id: string;
  name: string;
  affected: boolean;
  lengthKm: number | null;
  areaSqKm: number | null;
  /** Provenance, or why a figure is null. */
  note: string;
}

export interface ImpactCategory {
  name: string;
  /** Records in this category that intersect the flood extent. */
  affectedCount: number;
  totalCount: number;
  /**
   * Total length inside the flood extent, km — only when every affected record
   * has a length; null otherwise (see the header comment).
   */
  affectedLengthKm: number | null;
  lengthUnavailableReason: string | null;
  /** Affected records first; order within each group is stable. */
  items: ImpactItem[];
}

/** The top of the hierarchy: the hazard everything below is exposed to. */
export interface ImpactFloodNode {
  affectedAreaSqKm: number;
  aoiAreaSqKm: number;
  /** Fraction of the AOI the sensor could actually see. */
  coverageFraction: number;
}

export interface ImpactViewModel {
  flood: ImpactFloodNode;
  dataset: string;
  categories: ImpactCategory[];
}

const round2 = (v: number): number => Math.round(v * 100) / 100;

export function buildImpactModel(scenario: ConsoleScenario): ImpactViewModel | null {
  const impact = scenario.impact;
  if (!impact || impact.records.length === 0) return null;

  const byCategory = new Map<string, ImpactRecord[]>();
  for (const record of impact.records) {
    const group = byCategory.get(record.category);
    if (group) group.push(record);
    else byCategory.set(record.category, [record]);
  }

  const categories: ImpactCategory[] = [...byCategory.entries()].map(
    ([name, records]) => {
      const affected = records.filter((r) => r.affected);
      const missing = affected.filter((r) => r.lengthKm === null).length;
      const total = affected.reduce<number>((acc, r) => acc + (r.lengthKm ?? 0), 0);
      return {
        name,
        affectedCount: affected.length,
        totalCount: records.length,
        affectedLengthKm:
          affected.length === 0 ? 0 : missing === 0 ? round2(total) : null,
        lengthUnavailableReason:
          affected.length === 0 || missing === 0
            ? null
            : missing === affected.length
              ? "No affected record in this category publishes a linear extent."
              : `Linear extent is missing for ${missing} of ${affected.length} affected records; no total is asserted.`,
        items: [...records]
          .sort((a, b) => Number(b.affected) - Number(a.affected))
          .map((r) => ({
            id: r.id,
            name: r.name,
            affected: r.affected,
            lengthKm: r.lengthKm,
            areaSqKm: r.areaSqKm,
            note: r.note,
          })),
      };
    },
  );

  return {
    flood: {
      affectedAreaSqKm: scenario.change.areaSqKm,
      aoiAreaSqKm: scenario.aoiAreaSqKm,
      coverageFraction: scenario.change.coverageFraction,
    },
    dataset: impact.dataset,
    categories,
  };
}
