// P-08-T11: the portal auth client against a stubbed portal BFF (ADR-168, DEC-212, DEC-231).
// Acceptance: an expired access token refreshes silently once, a failed refresh lands on /sign-in
// with the return path, and no token touches localStorage or sessionStorage.
import { getPortalHome, portalVerify } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  configurePortalClient,
  ensurePortalSession,
  goToSignIn,
  handlePortalUnauthorised,
  lastPortalRefreshFailure,
  notePortalActivity,
  portalAccessToken,
  portalSignOut,
  refreshPortalSession,
  resetPortalAuthForTest,
  returnFrom,
  safePortalReturn,
  setPortalSession,
  setSignInNavigator,
  signInPath,
} from "./bff";

const NOW = 1_700_000_000_000;
const SIGNED_IN = (token: string) => ({
  state: "signed_in",
  access_token: token,
  expires_in: 900,
  landing: "home",
});

interface Call {
  method: string;
  path: string;
  headers: Headers;
}
type Handler = (call: Call) => Response | Promise<Response>;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The portal BFF and API, stubbed on the generated client's fetch. */
function portalApi(routes: Record<string, Handler>): { calls: Call[] } {
  const calls: Call[] = [];
  const fetchMock = async (input: Request): Promise<Response> => {
    const call = {
      method: input.method,
      path: new URL(input.url).pathname,
      headers: input.headers,
    };
    calls.push(call);
    const handler = routes[`${call.method} ${call.path}`];
    return handler === undefined ? json({ detail: "no such route" }, 404) : handler(call);
  };
  configurePortalClient();
  client.setConfig({ fetch: fetchMock as typeof fetch });
  return { calls };
}

const refreshes = (calls: Call[]) => calls.filter((c) => c.path === "/v1/portal/auth/refresh");
const homes = (calls: Call[]) => calls.filter((c) => c.path === "/v1/portal/home");

/** Every value in web storage, to prove no token is there. */
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

let navigated: ReturnType<typeof vi.fn<(to: string) => void>>;
let setItem: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  resetPortalAuthForTest();
  sessionStorage.clear();
  localStorage.clear();
  window.history.replaceState(null, "", "/documents?tab=open#link=fixture-reminder-link-0000");
  navigated = vi.fn<(to: string) => void>();
  setSignInNavigator(navigated);
  setItem = vi.spyOn(Storage.prototype, "setItem");
});

afterEach(() => {
  // No token, and nothing at all, was written to web storage by any test here.
  expect(setItem).not.toHaveBeenCalled();
  expect(webStorage()).toBe("");
  vi.restoreAllMocks();
  resetPortalAuthForTest();
  window.history.replaceState(null, "", "/");
});

describe("P-08-T11 refresh through the host cookie", () => {
  it("holds no token before a session, then the BFF's token in memory only", async () => {
    expect(portalAccessToken(NOW)).toBeNull();
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_1")),
    });
    expect(await refreshPortalSession(NOW)).toBe(true);
    expect(portalAccessToken(NOW)).toBe("pst_1");
    const [call] = refreshes(calls);
    expect(call?.headers.get("x-abacus-csrf")).toBe("1");
    // The cookie authenticates the refresh, never a bearer.
    expect(call?.headers.get("authorization")).toBeNull();
  });

  it("is null within 30 seconds of the 15-minute expiry", async () => {
    portalApi({ "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_1")) });
    await refreshPortalSession(NOW);
    expect(portalAccessToken(NOW + 869_000)).toBe("pst_1");
    expect(portalAccessToken(NOW + 870_000)).toBeNull();
  });

  it("sends one refresh for parallel callers: the rotating cookie is used once", async () => {
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_1")),
    });
    const results = await Promise.all([
      refreshPortalSession(NOW),
      ensurePortalSession(NOW),
      refreshPortalSession(NOW),
    ]);
    expect(results).toEqual([true, true, true]);
    expect(refreshes(calls)).toHaveLength(1);
  });

  it("answers false with the BFF's reason when the session is over", async () => {
    portalApi({
      "POST /v1/portal/auth/refresh": () => json({ detail: "session_expired" }, 401),
    });
    expect(await refreshPortalSession(NOW)).toBe(false);
    expect(portalAccessToken(NOW)).toBeNull();
    expect(lastPortalRefreshFailure()).toBe("session_expired");
  });

  it("an unreachable BFF is no session", async () => {
    portalApi({});
    client.setConfig({ fetch: () => Promise.reject(new Error("offline")) });
    expect(await refreshPortalSession(NOW)).toBe(false);
    expect(lastPortalRefreshFailure()).toBe("network");
  });

  it("ensurePortalSession keeps a live token without asking the BFF", async () => {
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_1")),
    });
    setPortalSession(SIGNED_IN("pst_0"), NOW);
    expect(await ensurePortalSession(NOW + 1000)).toBe(true);
    expect(refreshes(calls)).toHaveLength(0);
  });
});

describe("DEC-583 only the person's own activity moves the idle clock", () => {
  it("marks the first refresh, then only a refresh after input", async () => {
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_1")),
    });
    await refreshPortalSession(NOW); // the page load: the person's own act
    await refreshPortalSession(NOW + 60_000); // a background poll, no input since
    notePortalActivity(NOW + 90_000);
    await refreshPortalSession(NOW + 120_000); // after a key or click
    const marks = refreshes(calls).map((c) => c.headers.get("x-abacus-activity"));
    expect(marks).toEqual(["user", null, "user"]);
  });
});

describe("P-08-T11 an expired access token refreshes silently once", () => {
  it("replays a GET once with the refreshed token after a 401", async () => {
    setPortalSession(SIGNED_IN("pst_old"));
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_new")),
      "GET /v1/portal/home": (call) =>
        call.headers.get("authorization") === "Bearer pst_new"
          ? json({ seen: "pst_new" })
          : json({ detail: "unauthenticated" }, 401),
    });
    const { data } = await getPortalHome({ throwOnError: true });
    expect(data).toEqual({ seen: "pst_new" });
    expect(refreshes(calls)).toHaveLength(1);
    expect(homes(calls)).toHaveLength(2);
    expect(navigated).not.toHaveBeenCalled();
  });

  it("parallel 401s share one refresh, and each replays once", async () => {
    setPortalSession(SIGNED_IN("pst_old"));
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": async () => {
        await gate;
        return json(SIGNED_IN("pst_new"));
      },
      "GET /v1/portal/home": (call) =>
        call.headers.get("authorization") === "Bearer pst_new"
          ? json({ ok: true })
          : json({ detail: "unauthenticated" }, 401),
    });
    const all = Promise.all([0, 1, 2].map(() => getPortalHome({ throwOnError: true })));
    await vi.waitFor(() => {
      expect(refreshes(calls)).toHaveLength(1);
    });
    release();
    const answers = await all;
    expect(answers.map((a) => a.data)).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(refreshes(calls)).toHaveLength(1);
    expect(homes(calls)).toHaveLength(6);
  });

  it("a late 401 for the old token reuses the newer one instead of refreshing again", async () => {
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_new")),
    });
    setPortalSession(SIGNED_IN("pst_new"), NOW);
    expect(await handlePortalUnauthorised("pst_old", NOW)).toBe("refreshed");
    expect(portalAccessToken(NOW)).toBe("pst_new");
    expect(refreshes(calls)).toHaveLength(0);
  });

  it("a replay that is refused again does not refresh a second time: the person signs in", async () => {
    setPortalSession(SIGNED_IN("pst_old"));
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_new")),
      "GET /v1/portal/home": () => json({ detail: "unauthenticated" }, 401),
    });
    await expect(getPortalHome({ throwOnError: true })).rejects.toBeTruthy();
    expect(refreshes(calls)).toHaveLength(1);
    expect(homes(calls)).toHaveLength(2);
    expect(navigated).toHaveBeenCalledExactlyOnceWith("/sign-in?return=%2Fdocuments%3Ftab%3Dopen");
  });

  it("refreshes before a request when the token is about to run out", async () => {
    // A token issued 880 seconds ago: inside the 30-second margin.
    setPortalSession(SIGNED_IN("pst_old"), Date.now() - 880_000);
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_new")),
      "GET /v1/portal/home": (call) => json({ seen: call.headers.get("authorization") }),
    });
    const { data } = await getPortalHome({ throwOnError: true });
    expect(data).toEqual({ seen: "Bearer pst_new" });
    expect(refreshes(calls)).toHaveLength(1);
    expect(homes(calls)).toHaveLength(1);
  });

  it("does not replay a request with a body (the caller retries it)", async () => {
    setPortalSession(SIGNED_IN("pst_old"));
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_new")),
      "PUT /v1/portal/preferences": () => json({ detail: "unauthenticated" }, 401),
    });
    await expect(
      client.put({ url: "/v1/portal/preferences", body: { scope_id: "s" }, throwOnError: true }),
    ).rejects.toBeTruthy();
    expect(calls.filter((c) => c.path === "/v1/portal/preferences")).toHaveLength(1);
    expect(portalAccessToken()).toBe("pst_new");
  });
});

describe("P-08-T11 a failed refresh lands on /sign-in with the return path", () => {
  it("goes to sign-in with the path and query, never the fragment", async () => {
    setPortalSession(SIGNED_IN("pst_old"));
    portalApi({
      "POST /v1/portal/auth/refresh": () => json({ detail: "session_expired" }, 401),
      "GET /v1/portal/home": () => json({ detail: "unauthenticated" }, 401),
    });
    await expect(getPortalHome({ throwOnError: true })).rejects.toBeTruthy();
    expect(navigated).toHaveBeenCalledExactlyOnceWith("/sign-in?return=%2Fdocuments%3Ftab%3Dopen");
    expect(String(navigated.mock.calls[0]?.[0])).not.toContain("link");
    expect(portalAccessToken()).toBeNull();
  });

  it("parallel failures make one trip to sign-in", async () => {
    setPortalSession(SIGNED_IN("pst_old"));
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json({ detail: "session_expired" }, 401),
      "GET /v1/portal/home": () => json({ detail: "unauthenticated" }, 401),
    });
    await Promise.allSettled([0, 1, 2].map(() => getPortalHome({ throwOnError: true })));
    expect(navigated).toHaveBeenCalledTimes(1);
    expect(refreshes(calls).length).toBeLessThanOrEqual(3);
  });

  it("the next sign-in clears the guard, so a later expiry goes to sign-in again", () => {
    goToSignIn("/a");
    goToSignIn("/b");
    setPortalSession(SIGNED_IN("pst_1"));
    goToSignIn("/c");
    expect(navigated.mock.calls).toEqual([["/sign-in?return=%2Fa"], ["/sign-in?return=%2Fc"]]);
  });

  it("the portal's root needs no return; a sign-in page reads only a safe one", () => {
    expect(signInPath("/")).toBe("/sign-in");
    expect(signInPath("/k1s?year=2025")).toBe("/sign-in?return=%2Fk1s%3Fyear%3D2025");
    expect(returnFrom("?return=%2Fk1s%3Fyear%3D2025")).toBe("/k1s?year=2025");
    expect(returnFrom("?return=https%3A%2F%2Fevil.example")).toBeNull();
    expect(returnFrom("?return=%2F")).toBeNull();
    expect(returnFrom("")).toBeNull();
  });

  it("refuses absolute, protocol-relative, backslash, fragment, sign-in and API paths", () => {
    for (const bad of [
      "https://evil.example",
      "//evil.example",
      "/\\evil",
      "evil",
      "/x#link=abc",
      "/sign-in",
      "/sign-in?return=%2Fx",
      "/v1/portal/home",
      "",
      null,
    ]) {
      expect(safePortalReturn(bad), String(bad)).toBe("/");
    }
    expect(safePortalReturn("/requests?open=1")).toBe("/requests?open=1");
    expect(safePortalReturn("/sign-in-help")).toBe("/sign-in-help");
  });
});

describe("P-08-T11 the pre-session family is never refreshed", () => {
  it("a wrong code's 401 is the screen's: no refresh, no trip to sign-in, no bearer sent", async () => {
    setPortalSession(SIGNED_IN("pst_old"));
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_new")),
      "POST /v1/portal/auth/verify": () =>
        json({ detail: "code_mismatch", facts: { tries_left: 2 } }, 401),
    });
    await expect(
      portalVerify({ body: { challenge_id: "c", code: "000000" }, throwOnError: true }),
    ).rejects.toEqual({ detail: "code_mismatch", facts: { tries_left: 2 } });
    expect(refreshes(calls)).toHaveLength(0);
    expect(navigated).not.toHaveBeenCalled();
    const verify = calls.find((c) => c.path === "/v1/portal/auth/verify");
    expect(verify?.headers.get("authorization")).toBeNull();
  });
});

describe("P-08-T11 sign-out", () => {
  it("ends the BFF session with the bearer token, then forgets it here", async () => {
    const { calls } = portalApi({
      "POST /v1/portal/auth/sign-out": () => json({ ended: true }),
    });
    setPortalSession(SIGNED_IN("pst_1"));
    await portalSignOut();
    const call = calls.find((c) => c.path === "/v1/portal/auth/sign-out");
    expect(call?.headers.get("authorization")).toBe("Bearer pst_1");
    expect(portalAccessToken()).toBeNull();
    expect(navigated).not.toHaveBeenCalled();
  });

  it("a 401 on sign-out is not refreshed", async () => {
    const { calls } = portalApi({
      "POST /v1/portal/auth/refresh": () => json(SIGNED_IN("pst_2")),
      "POST /v1/portal/auth/sign-out": () => json({ detail: "unauthenticated" }, 401),
    });
    setPortalSession(SIGNED_IN("pst_1"));
    await portalSignOut();
    expect(refreshes(calls)).toHaveLength(0);
    expect(portalAccessToken()).toBeNull();
  });

  it("forgets the session here even when the BFF cannot be reached", async () => {
    portalApi({});
    setPortalSession(SIGNED_IN("pst_1"));
    client.setConfig({ fetch: () => Promise.reject(new Error("offline")) });
    await portalSignOut().catch(() => undefined);
    expect(portalAccessToken()).toBeNull();
  });
});

describe("P-08-T11 no token touches web storage", () => {
  it("a whole session (verify, refresh, a 401, sign-out) writes nothing to either storage", async () => {
    let issued = 0;
    portalApi({
      "POST /v1/portal/auth/verify": () => json(SIGNED_IN("pst_v")),
      "POST /v1/portal/auth/refresh": () => {
        issued += 1;
        return json(SIGNED_IN(`pst_r${String(issued)}`));
      },
      "GET /v1/portal/home": (call) =>
        call.headers.get("authorization") === "Bearer pst_v"
          ? json({ detail: "unauthenticated" }, 401)
          : json({ ok: true }),
      "POST /v1/portal/auth/sign-out": () => json({ ended: true }),
    });
    const { data } = await portalVerify({
      body: { challenge_id: "c", code: "481027" },
      throwOnError: true,
    });
    setPortalSession(data);
    await getPortalHome({ throwOnError: true });
    expect(portalAccessToken()).toBe("pst_r1");
    await portalSignOut();
    // The afterEach checks Storage.setItem was never called and both stores are empty; and the
    // token was never in the address bar either.
    expect(window.location.href).not.toContain("pst_");
  });
});
