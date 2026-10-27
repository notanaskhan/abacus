// P-01-T11: the staff auth client against a stubbed BFF (P-01 AC 5.1.3 to 5.1.6; SPEC-000 AC-1).
// The token is memory only; refresh carries the CSRF header and rotates once for parallel callers;
// a 401 refreshes, else signs in and returns to the same route; sign-out ends the BFF session.
import { me as getMe } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { configureClient } from "../../api";
import { type Call, json, mockApi, stubLocation } from "../../testing/support";
import {
  accessToken,
  ensureSession,
  handleUnauthorised,
  lastRefreshFailure,
  noteUserActivity,
  refreshSession,
  resetAuthForTest,
  safeReturnTo,
  signIn,
  signInUrl,
  signOut,
  startSession,
} from ".";

const NOW = 1_700_000_000_000;
const TOKEN = { access_token: "tok-1", expires_in: 600 };

let assign: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetAuthForTest();
  sessionStorage.clear();
  localStorage.clear();
  assign = stubLocation("/engagements/e1", "?tab=requests").assign;
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetAuthForTest();
});

/** Every value in web storage, to prove no token is there (AC 5.1.5). */
function webStorage(): string {
  const all: string[] = [];
  for (const store of [sessionStorage, localStorage]) {
    for (let i = 0; i < store.length; i++) {
      const key = store.key(i);
      if (key !== null) all.push(`${key}=${store.getItem(key) ?? ""}`);
    }
  }
  return all.join("\n");
}

function refreshes(calls: Call[]): Call[] {
  return calls.filter((c) => c.method === "POST" && c.path === "/v1/auth/refresh");
}

describe("P-01-T11 refresh (AC 5.1.4)", () => {
  it("is null before a session, then holds the BFF's token in memory only", async () => {
    expect(accessToken(NOW)).toBeNull();
    const { calls } = mockApi({ "POST /v1/auth/refresh": () => json(TOKEN) });
    expect(await refreshSession(NOW)).toBe(true);
    expect(accessToken(NOW)).toBe("tok-1");
    expect(webStorage()).not.toContain("tok-1");
    const [call] = refreshes(calls);
    expect(call?.headers.get("x-abacus-csrf")).toBe("1");
    expect(call?.headers.get("authorization")).toBeNull();
  });

  it("is null within 30 seconds of expiry, and the token until then", async () => {
    mockApi({ "POST /v1/auth/refresh": () => json(TOKEN) });
    await refreshSession(NOW);
    expect(accessToken(NOW + 569_000)).toBe("tok-1");
    expect(accessToken(NOW + 570_000)).toBeNull();
  });

  it("sends one refresh for parallel callers: the rotating cookie is used once", async () => {
    const { calls } = mockApi({ "POST /v1/auth/refresh": () => json(TOKEN) });
    const results = await Promise.all([refreshSession(NOW), ensureSession(NOW), refreshSession()]);
    expect(results).toEqual([true, true, true]);
    expect(refreshes(calls)).toHaveLength(1);
  });

  it("answers false with the BFF's reason when the session is over", async () => {
    mockApi({
      "POST /v1/auth/refresh": () => json({ detail: "session_refresh_reused" }, 401),
    });
    expect(await refreshSession(NOW)).toBe(false);
    expect(accessToken(NOW)).toBeNull();
    expect(lastRefreshFailure()).toBe("session_refresh_reused");
  });

  it("ensureSession keeps a live token without asking the BFF", async () => {
    const { calls } = mockApi({ "POST /v1/auth/refresh": () => json(TOKEN) });
    await refreshSession(NOW);
    expect(await ensureSession(NOW + 1000)).toBe(true);
    expect(refreshes(calls)).toHaveLength(1);
  });
});

describe("P-01-T11 sign-in (AC 5.1.2, 5.1.5)", () => {
  it("navigates to the BFF's sign-in with the current route to return to", () => {
    signIn();
    expect(assign).toHaveBeenCalledWith(
      "/v1/auth/sign-in?return_to=%2Fengagements%2Fe1%3Ftab%3Drequests",
    );
    expect(webStorage()).toBe("");
  });

  it("starts one navigation for concurrent calls", () => {
    signIn("/a");
    signIn("/b");
    expect(assign).toHaveBeenCalledTimes(1);
  });

  it("never sends an unsafe return path", () => {
    expect(signInUrl("https://evil.example/x")).toBe("/v1/auth/sign-in?return_to=%2F");
    expect(signInUrl("//evil.example")).toBe("/v1/auth/sign-in?return_to=%2F");
  });

  it("asks for a fresh sign-in for step-up (ConfirmItsYou)", () => {
    expect(signInUrl("/settings", { forceLogin: true })).toBe(
      "/v1/auth/sign-in?return_to=%2Fsettings&reauthenticate=true",
    );
  });
});

describe("P-01-T11 safeReturnTo", () => {
  it("keeps same-origin paths with their query", () => {
    expect(safeReturnTo("/engagements/e1?tab=requests")).toBe("/engagements/e1?tab=requests");
    expect(safeReturnTo("/")).toBe("/");
  });

  it("refuses absolute, protocol-relative and backslash paths, and missing values", () => {
    for (const bad of ["https://evil.example", "//evil.example", "/\\evil", "evil", "", null]) {
      expect(safeReturnTo(bad), String(bad)).toBe("/");
    }
  });

  it("refuses the callback and the BFF's own routes", () => {
    expect(safeReturnTo("/signin/callback?to=/x")).toBe("/");
    expect(safeReturnTo("/v1/auth/sign-out")).toBe("/");
  });
});

describe("P-01-T11 handleUnauthorised (AC 5.1.4)", () => {
  it("refreshes from the cookie when it can", async () => {
    mockApi({ "POST /v1/auth/refresh": () => json(TOKEN) });
    expect(await handleUnauthorised(NOW)).toBe("refreshed");
    expect(accessToken(NOW)).toBe("tok-1");
    expect(assign).not.toHaveBeenCalled();
  });

  it("otherwise signs in and comes back to the same route", async () => {
    mockApi({ "POST /v1/auth/refresh": () => json({ detail: "session_expired" }, 401) });
    expect(await handleUnauthorised(NOW)).toBe("redirected");
    expect(assign).toHaveBeenCalledWith(
      "/v1/auth/sign-in?return_to=%2Fengagements%2Fe1%3Ftab%3Drequests",
    );
  });

  it("refuses to loop within 10 seconds of a session starting, and drops the token", async () => {
    mockApi({ "POST /v1/auth/refresh": () => json(TOKEN) });
    expect(await startSession(NOW)).toBe(true);
    expect(await handleUnauthorised(NOW + 9_000)).toBe("rejected");
    expect(accessToken(NOW + 9_000)).toBeNull();
    expect(assign).not.toHaveBeenCalled();
  });
});

describe("P-01-T11 the generated client (AC 5.1.4)", () => {
  it("replays a GET once with the refreshed token after a 401", async () => {
    let first = true;
    const { calls } = mockApi({
      "POST /v1/auth/refresh": () => json({ access_token: "tok-2", expires_in: 600 }),
      "GET /v1/me": (call) => {
        if (first) {
          first = false;
          return json({ detail: "Unauthorized" }, 401);
        }
        return json({ seen: call.headers.get("authorization") });
      },
    });
    const { data } = await getMe({ throwOnError: true });
    expect(data).toEqual({ seen: "Bearer tok-2" });
    expect(refreshes(calls)).toHaveLength(1);
    expect(assign).not.toHaveBeenCalled();
  });

  it("an expired session returns the person to the same route", async () => {
    mockApi({
      "POST /v1/auth/refresh": () => json({ detail: "session_expired" }, 401),
      "GET /v1/me": () => json({ detail: "Unauthorized" }, 401),
    });
    await expect(getMe({ throwOnError: true })).rejects.toBeTruthy();
    expect(assign).toHaveBeenCalledWith(
      "/v1/auth/sign-in?return_to=%2Fengagements%2Fe1%3Ftab%3Drequests",
    );
  });

  it("refreshes before a request when the token is about to run out", async () => {
    let issued = 0;
    const { calls } = mockApi({
      "POST /v1/auth/refresh": () => {
        issued += 1;
        return json({ access_token: `tok-${String(issued)}`, expires_in: 600 });
      },
      "GET /v1/me": (call) => json({ seen: call.headers.get("authorization") }),
    });
    // A token issued 590 seconds ago: inside the 30-second margin.
    await refreshSession(Date.now() - 590_000);
    const { data } = await getMe({ throwOnError: true });
    expect(data).toEqual({ seen: "Bearer tok-2" });
    expect(refreshes(calls)).toHaveLength(2);
  });
});

describe("P-01-T11 sign-out (AC 2.1.6)", () => {
  it("ends the BFF session with the bearer token, then forgets it here", async () => {
    const { calls } = mockApi({
      "POST /v1/auth/refresh": () => json(TOKEN),
      "POST /v1/auth/sign-out": () => json({ ended: true }),
    });
    await refreshSession();
    sessionStorage.setItem("abacus.tenant", "t1");
    await signOut();
    const call = calls.find((c) => c.path === "/v1/auth/sign-out");
    expect(call?.headers.get("authorization")).toBe("Bearer tok-1");
    expect(accessToken()).toBeNull();
    expect(webStorage()).toBe("");
  });

  it("forgets the session here even when the BFF cannot be reached", async () => {
    mockApi({ "POST /v1/auth/refresh": () => json(TOKEN) });
    configureClient();
    await refreshSession();
    client.setConfig({ fetch: () => Promise.reject(new Error("offline")) });
    await signOut().catch(() => undefined);
    expect(accessToken()).toBeNull();
  });
});

describe("G-02-T14 the idle clock (security review M3)", () => {
  it("marks a refresh as activity only after the person's own input", async () => {
    const { calls } = mockApi({ "POST /v1/auth/refresh": () => json(TOKEN) });
    const marked = (): (string | null)[] =>
      refreshes(calls).map((c) => c.headers.get("X-Abacus-Activity"));
    await refreshSession(NOW); // the page's first refresh: a load is the person's act
    await refreshSession(NOW + 60_000); // a background poll's: no input since
    noteUserActivity(NOW + 90_000);
    await refreshSession(NOW + 120_000);
    expect(marked()).toEqual(["user", null, "user"]);
  });
});
