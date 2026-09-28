import { afterEach, describe, expect, it, vi } from "vitest";

import { GatewayError, request } from "./gateway";

/**
 * Error mapping at the browser/gateway boundary (P5-02, P1-10).
 *
 * The console's run poller decides "not registered yet" vs "really gone" from
 * `body.code === "RUN_NOT_FOUND"`. Downstream services render their errors as
 * {detail: {code, message}}, so this pins that the unwrapping happens and that
 * the other shapes still map the way the UI expects.
 */

function respond(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function failWith(status: number, body: unknown): Promise<GatewayError> {
  vi.stubGlobal("fetch", vi.fn(async () => respond(status, body)));
  try {
    await request("/api/v1/agent/runs/job-1", { timeoutMs: 1000 });
  } catch (e) {
    return e as GatewayError;
  }
  throw new Error("request unexpectedly succeeded");
}

afterEach(() => vi.unstubAllGlobals());

describe("gateway error mapping", () => {
  it("unwraps a FastAPI {detail: {code, message}} body", async () => {
    const err = await failWith(404, {
      detail: { code: "RUN_NOT_FOUND", message: "No run with that id." },
    });
    expect(err.status).toBe(404);
    expect(err.body.code).toBe("RUN_NOT_FOUND");
    expect(err.body.message).toBe("No run with that id.");
  });

  it("passes the canonical flat envelope through untouched", async () => {
    const err = await failWith(403, {
      code: "FORBIDDEN",
      message: "Role analyst required.",
      trace_id: "t-1",
    });
    expect(err.body).toMatchObject({ code: "FORBIDDEN", trace_id: "t-1" });
  });

  it("maps a validation array to validation_error, not to a fake envelope", async () => {
    const err = await failWith(422, { detail: [{ loc: ["body", "query"], msg: "required" }] });
    expect(err.body.code).toBe("validation_error");
    expect(err.body.details).toHaveLength(1);
  });

  it("falls back to an http_<status> code for an unrecognised body", async () => {
    const err = await failWith(404, { something: "else" });
    expect(err.body.code).toBe("http_404");
  });

  it("does not retry a 4xx", async () => {
    const fetchMock = vi.fn(async () => respond(404, { detail: { code: "X", message: "m" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("/api/v1/missions")).rejects.toBeInstanceOf(GatewayError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("gateway request guards", () => {
  it("refuses an absolute URL before any network call", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("https://evil.example.com/x")).rejects.toMatchObject({
      body: { code: "invalid_target" },
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("never sends credentials or an organization id", async () => {
    const fetchMock = vi.fn(async () => respond(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await request("/api/v1/missions", { method: "POST", body: { name: "m" } });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.credentials).toBe("omit");
    expect(String(init.body)).not.toMatch(/organi[sz]ation_id|org_id/);
  });
});
