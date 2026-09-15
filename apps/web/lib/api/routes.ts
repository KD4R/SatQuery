/**
 * The gateway route table (P5-02).
 *
 * This is the single declaration of every path the browser is allowed to call.
 * `lib/api/__tests__/routes.contract.test.ts` asserts that this table and
 * docs/openapi/gateway.json describe the same set of paths, so a route added or
 * renamed on either side fails CI instead of failing silently at runtime.
 *
 * Templated segments use the same `{name}` spelling as the OpenAPI document so the
 * two can be compared literally.
 */

export const GATEWAY_ROUTES = {
  health: "/api/v1/health",

  missions: "/api/v1/missions",
  mission: "/api/v1/missions/{mission_id}",
  missionRuns: "/api/v1/missions/{mission_id}/runs",

  job: "/api/v1/jobs/{job_id}",

  agentPlan: "/api/v1/agent/plan",
  agentExecute: "/api/v1/agent/execute",
  agentConfidence: "/api/v1/agent/confidence",
  agentSensorDecision: "/api/v1/agent/sensor-decision",
  agentRun: "/api/v1/agent/runs/{job_id}",
  agentTools: "/api/v1/agent/tools",
} as const;

export type RouteName = keyof typeof GATEWAY_ROUTES;

/** Every path this client may call, for the contract test. */
export const ALL_ROUTE_PATHS: readonly string[] = Object.values(GATEWAY_ROUTES);

/** Substitute `{name}` segments. Values are percent-encoded. */
export function buildPath(
  template: string,
  params: Record<string, string> = {},
): string {
  return template.replace(/\{(\w+)\}/g, (_match, key: string) => {
    const value = params[key];
    if (value === undefined) {
      throw new Error(`buildPath: missing path parameter "${key}" for ${template}`);
    }
    return encodeURIComponent(value);
  });
}
