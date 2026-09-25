/**
 * The fixture boundary (P5-17).
 *
 * Everything demo-shaped is exported from here and nowhere else, so
 * `grep -rn "lib/fixtures" app components` lists every place the UI can show
 * something that did not come from the backend. Keeping that list short and
 * greppable is what makes the isolation claim checkable rather than a convention.
 */

export { ASSAM_SCENARIO, ASSAM_AOI, FIXTURE_EPOCH } from "./assam";
export { DEMO_STAGES, DEMO_TOTAL_MS, type RunStage } from "./script";
export { DEMO_AGENT_EVENTS, demoEventAt } from "./agentEvents";
