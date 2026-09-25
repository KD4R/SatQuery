import { describe, expect, it } from "vitest";

import { envelopeToAgentEvent } from "./useMissionEvents";

/**
 * The mapping is the security-relevant part of the WS client: everything the
 * socket delivers crosses it before React ever sees it. These tests pin the
 * honesty and the shape rules — unknown types dropped, missing text dropped,
 * agreement mapped to its own retiring event.
 */
describe("envelopeToAgentEvent", () => {
  it("maps a disagreement envelope to a toast event with the server reason", () => {
    const event = envelopeToAgentEvent({
      event_id: "evt-1",
      event_type: "SENSOR_DISAGREEMENT",
      payload: {
        sensors: ["S1_SAR", "S2_OPTICAL"],
        reason: "Optical and SAR disagree on flood extent — acquiring an additional radar observation to arbitrate.",
        disagreement: true,
      },
      trace_id: "tr-1",
    });
    expect(event).not.toBeNull();
    expect(event!.type).toBe("SENSOR_DISAGREEMENT");
    expect(event!.message).toContain("disagree");
  });

  it("maps the agreement counterpart to a retiring event", () => {
    const event = envelopeToAgentEvent({
      event_id: "evt-2",
      event_type: "SENSOR_DISAGREEMENT",
      payload: { sensors: ["S1_SAR"], reason: "Sensors agree.", disagreement: false },
      trace_id: "tr-1",
    });
    expect(event!.type).toBe("SENSOR_AGREEMENT");
  });

  it("drops a disagreement envelope without a reason rather than inventing one", () => {
    const event = envelopeToAgentEvent({
      event_id: "evt-3",
      event_type: "SENSOR_DISAGREEMENT",
      payload: { sensors: ["S1_SAR", "S2_OPTICAL"] },
      trace_id: "tr-1",
    });
    expect(event).toBeNull();
  });

  it("drops unknown event types instead of rendering them", () => {
    const event = envelopeToAgentEvent({
      event_id: "evt-4",
      event_type: "SOMETHING_ELSE",
      payload: { reason: "inject" },
      trace_id: "tr-1",
    });
    expect(event).toBeNull();
  });

  it("drops non-string payload text (an object cannot become a message)", () => {
    const event = envelopeToAgentEvent({
      event_id: "evt-5",
      event_type: "AGENT_THOUGHT",
      payload: { stage: "analyzing", text: { evil: "<script>" } },
      trace_id: "tr-1",
    });
    expect(event).toBeNull();
  });

  it("maps ACQUIRING_EVIDENCE and AGENT_THOUGHT from their text fields", () => {
    const acquiring = envelopeToAgentEvent({
      event_id: "evt-6",
      event_type: "ACQUIRING_EVIDENCE",
      payload: { reason: "Selecting the observations that cover the area of interest.", sensors: ["S1_SAR"] },
      trace_id: "tr-1",
    });
    expect(acquiring!.type).toBe("ACQUIRING_EVIDENCE");

    const thought = envelopeToAgentEvent({
      event_id: "evt-7",
      event_type: "AGENT_THOUGHT",
      payload: { stage: "analyzing", text: "Water segmentation complete." },
      trace_id: "tr-1",
    });
    expect(thought!.type).toBe("AGENT_THOUGHT");
    expect(thought!.message).toBe("Water segmentation complete.");
  });
});
