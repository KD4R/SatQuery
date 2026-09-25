"use client";

/**
 * Infrastructure impact (PRD §2D).
 *
 * A side-panel section, not a separate dashboard route: the operator reads it next
 * to the Change and Confidence sections that produced the exposure, and the PRD's
 * hierarchy (Flood → Roads → Hospitals) is three levels deep — a panel carries that;
 * a route would bury it.
 *
 * Everything comes from buildImpactModel over ConsoleScenario.impact. Where the
 * intersection has no figure — a hospital has no linear extent, an unmeasured road
 * way, or the pipeline produced no intersection at all — the section renders
 * NOT AVAILABLE with a reason rather than a zero or a blank.
 */

import "./impact.css";
import { formatPercent } from "../../lib/geo/format";
import type { ImpactViewModel } from "../../lib/impact/model";
import {
  Label,
  NotAvailable,
  PanelSection,
  Readout,
  StatusChip,
} from "../system/primitives";

export function InfrastructureImpact({ model }: { model: ImpactViewModel | null }) {
  if (!model) {
    return (
      <PanelSection title="Infrastructure impact">
        <NotAvailable reason="The pipeline has not produced an infrastructure intersection for this run." />
      </PanelSection>
    );
  }

  const { flood, dataset, categories } = model;

  return (
    <PanelSection title="Infrastructure impact">
      <div className="impact-root">
        {/* ── Level 1: the hazard ─────────────────────────────────────────── */}
        <div className="impact-node impact-node-root">
          <div className="impact-head">
            <span className="impact-glyph" aria-hidden="true">
              ◆
            </span>
            <Label>Flood</Label>
          </div>
          <Readout
            label="New water"
            value={`${flood.affectedAreaSqKm.toFixed(2)} km²`}
            tone="signal"
          />
          <Readout
            label="Coverage"
            value={formatPercent(flood.coverageFraction)}
            tone={flood.coverageFraction < 0.6 ? "amber" : undefined}
          />
        </div>

        {/* ── Level 2: categories ─────────────────────────────────────────── */}
        {categories.map((category) => (
          <div key={category.name} className="impact-node impact-node-category">
            <div className="impact-head">
              <span className="impact-glyph" aria-hidden="true">
                ◆
              </span>
              <Label>{category.name}</Label>
              <div className="band-spacer" />
              <StatusChip tone={category.affectedCount > 0 ? "warn" : "idle"}>
                {category.affectedCount}/{category.totalCount} affected
              </StatusChip>
            </div>
            <Readout
              label="Affected length"
              value={
                category.affectedLengthKm === null
                  ? null
                  : `${category.affectedLengthKm.toFixed(2)} km`
              }
              reason={category.lengthUnavailableReason ?? undefined}
            />
            {/* ── Level 3: records ─────────────────────────────────────────── */}
            <ul className="impact-items" role="list">
              {category.items.map((item) => (
                <li
                  key={item.id}
                  className={item.affected ? "impact-item is-affected" : "impact-item"}
                  title={item.note}
                >
                  <span className="impact-item-glyph" aria-hidden="true">
                    {item.affected ? "◆" : "◇"}
                  </span>
                  <span className="impact-item-name mono">{item.name}</span>
                  <span className="impact-item-figure mono">
                    {item.affected && item.lengthKm !== null
                      ? `${item.lengthKm.toFixed(2)} km`
                      : null}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="mono faint impact-source">Source: {dataset}</p>
    </PanelSection>
  );
}
