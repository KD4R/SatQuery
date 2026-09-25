import { describe, expect, it } from "vitest";

import { ASSAM_SCENARIO } from "../fixtures";
import type { ConsoleScenario } from "../model/console";
import { buildImpactModel } from "./model";

const model = buildImpactModel(ASSAM_SCENARIO);

if (!model) throw new Error("the Assam fixture must build an impact model");

describe("buildImpactModel", () => {
  it("groups the flat records into the PRD's Flood → category → items hierarchy", () => {
    expect(model.categories.map((c) => c.name)).toEqual(["Roads", "Hospitals"]);

    const [roads, hospitals] = model.categories;
    expect(roads?.affectedCount).toBe(2);
    expect(roads?.totalCount).toBe(4);
    expect(hospitals?.affectedCount).toBe(1);
    expect(hospitals?.totalCount).toBe(3);
  });

  it("totals the affected length over affected records that carry one", () => {
    const roads = model.categories[0];
    // 1.84 + 0.62 — the two clear-of-flood roads contribute nothing.
    expect(roads?.affectedLengthKm).toBe(2.46);
    expect(roads?.lengthUnavailableReason).toBeNull();
  });

  it("gives a reason instead of a total when the category has none to publish", () => {
    const hospitals = model.categories[1];
    expect(hospitals?.affectedLengthKm).toBeNull();
    expect(hospitals?.lengthUnavailableReason).toMatch(/linear extent/i);
    // Point features: no item invents a length either.
    expect(hospitals?.items.every((i) => i.lengthKm === null)).toBe(true);
  });

  it("refuses a total when an affected record is missing its length", () => {
    const impact = ASSAM_SCENARIO.impact;
    if (!impact) throw new Error("fixture should carry impact data");

    const scenario: ConsoleScenario = {
      ...ASSAM_SCENARIO,
      impact: {
        dataset: impact.dataset,
        records: [
          ...impact.records,
          {
            id: "imp-road-unmeasured",
            category: "Roads",
            name: "OSM way 99999",
            affected: true,
            lengthKm: null,
            areaSqKm: null,
            note: "Affected, but the extract carries no measured length.",
          },
        ],
      },
    };

    const roads = buildImpactModel(scenario)?.categories[0];
    expect(roads?.affectedCount).toBe(3);
    expect(roads?.affectedLengthKm).toBeNull();
    expect(roads?.lengthUnavailableReason).toContain("1 of 3");
  });

  it("lists unaffected records too, affected first", () => {
    const roads = model.categories[0];
    if (!roads) throw new Error("roads category missing");

    expect(roads.items.some((i) => !i.affected)).toBe(true);
    expect(
      roads.items.slice(0, roads.affectedCount).every((i) => i.affected),
    ).toBe(true);
  });

  it("mirrors the change figures into the flood node rather than inventing new ones", () => {
    expect(model.flood.affectedAreaSqKm).toBe(ASSAM_SCENARIO.change.areaSqKm);
    expect(model.flood.aoiAreaSqKm).toBe(ASSAM_SCENARIO.aoiAreaSqKm);
    expect(model.flood.coverageFraction).toBe(ASSAM_SCENARIO.change.coverageFraction);
  });

  it("returns null when the pipeline produced no intersection", () => {
    expect(buildImpactModel({ ...ASSAM_SCENARIO, impact: null })).toBeNull();
    expect(
      buildImpactModel({
        ...ASSAM_SCENARIO,
        impact: { dataset: "empty", records: [] },
      }),
    ).toBeNull();
  });
});
