import { afterEach, describe, expect, it, vi } from "vitest";

import { GatewayError, hasAccessToken, setAccessToken } from "../api/gateway";
import { dropSession, ensureSession, isGatewayDown } from "./session";

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("live session (audit W1)", () => {
  it("mints a development token and keeps it in memory only", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(200, { access_token: "t1", org_id: "org-dev", roles: ["analyst"], expires_in: 60 }));
    vi.stubGlobal("fetch", fetchMock);
    const s = await ensureSession();
    expect(s).toEqual({ kind: "ready", via: "dev-login", orgId: "org-dev" });
    expect(hasAccessToken()).toBe(true);
    expect(fetchMock.mock.calls[0]![0]).toMatch(/\/auth\/dev-token$/);
    // A second call reuses it.
    expect((await ensureSession()).kind).toBe("ready");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    dropSession();
    expect(hasAccessToken()).toBe(false);
  });

  it("asks for a credential when the gateway has no dev sign-in (404)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(404, { code: "NOT_FOUND", message: "Not found", details: [], trace_id: null })));
    const s = await ensureSession();
    expect(s.kind).toBe("needs-credential");
  });

  it("reports the gateway as down when nothing answers", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    const s = await ensureSession();
    expect(s.kind).toBe("gateway-down");
  });

  it("tells a bare proxy error from a real gateway answer", () => {
    const err = (status: number, code: string) => new GatewayError(status, { code, message: "", details: [], trace_id: null });
    expect(isGatewayDown(err(502, "http_502"))).toBe(true);
    expect(isGatewayDown(err(0, "network_unreachable"))).toBe(true);
    expect(isGatewayDown(err(500, "http_500"))).toBe(true);
    expect(isGatewayDown(err(503, "QUEUE_UNAVAILABLE"))).toBe(false);
    expect(isGatewayDown(err(422, "INVALID_AOI"))).toBe(false);
  });
});
