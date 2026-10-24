// P-08-T20: independent acceptance tests for the portal auth client (ADR-078; P-08-T11).
// Written from the row's acceptance ("An expired access token refreshes silently once, a failed
// refresh lands on /sign-in with the return path, and no token touches localStorage or
// sessionStorage"), ADR-168 and docs/contracts/portal-identity.md §2.2 (refresh: the cookie,
// `X-Abacus-CSRF`, the Origin), through the generated client end to end, not from bff.test.ts.
import { getPortalHome, portalVerify } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  configurePortalClient,
  portalAccessToken,
  portalSignOut,
  resetPortalAuthForTest,
  setPortalSession,
  setSignInNavigator,
} from "./bff";

interface Seen {
  path: string;
  authorization: string | null;
  csrf: string | null;
}

function answer(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The portal's API on the generated client's fetch: each route answers in turn. */
function api(routes: Record<string, (seen: Seen) => Response>): Seen[] {
  const seen: Seen[] = [];
  const fetchStub = (request: Request): Promise<Response> => {
    const call = {
      path: new URL(request.url).pathname,
      authorization: request.headers.get("Authorization"),
      csrf: request.headers.get("X-Abacus-CSRF"),
    };
    seen.push(call);
    const route = routes[`${request.method} ${call.path}`];
    return Promise.resolve(
      route === undefined ? answer({ detail: "not found" }, 404) : route(call),
    );
  };
  configurePortalClient();
  client.setConfig({ baseUrl: window.location.origin, fetch: fetchStub as typeof fetch });
  return seen;
}

const HOME = { scope: { kind: "client", id: "s", label: "L", role_label: "R" } };
const signedIn = (token: string) => ({ state: "signed_in", access_token: token, expires_in: 900 });
const only = (seen: Seen[], path: string) => seen.filter((s) => s.path === path);

let navigated: ReturnType<typeof vi.fn<(to: string) => void>>;
let writes: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  resetPortalAuthForTest();
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState(null, "", "/documents?tab=open#link=a-reminder-link-token-000");
  navigated = vi.fn<(to: string) => void>();
  setSignInNavigator(navigated);
  writes = vi.spyOn(Storage.prototype, "setItem");
});

afterEach(() => {
  expect(writes).not.toHaveBeenCalled();
  expect(localStorage.length + sessionStorage.length).toBe(0);
  vi.restoreAllMocks();
  resetPortalAuthForTest();
  window.history.replaceState(null, "", "/");
});

describe("P-08-T11 (independent): the access token and its refresh", () => {
  it("an expired access token refreshes silently once and the request succeeds", async () => {
    setPortalSession(signedIn("pst_old"));
    const seen = api({
      "GET /v1/portal/home": (s) =>
        s.authorization === "Bearer pst_new" ? answer(HOME) : answer({ detail: "x" }, 401),
      "POST /v1/portal/auth/refresh": () => answer(signedIn("pst_new")),
    });
    const { data } = await getPortalHome({ throwOnError: true });
    expect(data.scope.id).toBe("s");
    const refreshes = only(seen, "/v1/portal/auth/refresh");
    expect(refreshes).toHaveLength(1);
    expect(refreshes[0]?.csrf).toBe("1"); // the CSRF header; the cookie, never a bearer
    expect(refreshes[0]?.authorization).toBeNull();
    expect(portalAccessToken()).toBe("pst_new");
    expect(navigated).not.toHaveBeenCalled();
  });

  it("parallel 401s share one refresh (the rotating cookie is presented once)", async () => {
    setPortalSession(signedIn("pst_old"));
    const seen = api({
      "GET /v1/portal/home": (s) =>
        s.authorization === "Bearer pst_new" ? answer(HOME) : answer({ detail: "x" }, 401),
      "POST /v1/portal/auth/refresh": () => answer(signedIn("pst_new")),
    });
    await Promise.all([1, 2, 3].map(() => getPortalHome({ throwOnError: true })));
    expect(only(seen, "/v1/portal/auth/refresh")).toHaveLength(1);
  });

  it("a failed refresh lands on /sign-in with the path and query, never the fragment", async () => {
    setPortalSession(signedIn("pst_old"));
    api({
      "GET /v1/portal/home": () => answer({ detail: "x" }, 401),
      "POST /v1/portal/auth/refresh": () => answer({ detail: "session_expired" }, 401),
    });
    await getPortalHome({ throwOnError: false });
    await getPortalHome({ throwOnError: false });
    expect(navigated).toHaveBeenCalledTimes(1);
    const to = navigated.mock.calls[0]?.[0] ?? "";
    expect(to).toBe(`/sign-in?return=${encodeURIComponent("/documents?tab=open")}`);
    expect(to).not.toContain("link");
    expect(portalAccessToken()).toBeNull();
  });

  it("a wrong sign-in code's 401 is the screen's: no refresh, no redirect", async () => {
    const seen = api({
      "POST /v1/portal/auth/verify": () =>
        answer({ detail: "code_mismatch", facts: { tries_left: 2 } }, 401),
    });
    const { error } = await portalVerify({
      body: { challenge_id: "00000000-0000-4000-8000-000000000000", code: "000000" },
      throwOnError: false,
    });
    expect(error).toMatchObject({ detail: "code_mismatch" });
    expect(only(seen, "/v1/portal/auth/refresh")).toHaveLength(0);
    expect(navigated).not.toHaveBeenCalled();
  });

  it("sign-out carries the token and forgets it even when the call fails", async () => {
    setPortalSession(signedIn("pst_live"));
    const seen = api({ "POST /v1/portal/auth/sign-out": () => answer({ detail: "x" }, 500) });
    await portalSignOut();
    expect(only(seen, "/v1/portal/auth/sign-out")[0]?.authorization).toBe("Bearer pst_live");
    expect(portalAccessToken()).toBeNull();
  });
});
