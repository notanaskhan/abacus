import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { stubLocation } from "../testing/support";
import { codeChallenge } from "./pkce";
import { AUTHORITY, SignInFailed, accessToken, completeSignIn, safeReturnTo } from "./session";

const NOW = 1_700_000_000_000;

interface Pending {
  state: string;
  verifier: string;
  returnTo: string;
}

/** The pending sign-in request, wherever session.ts keeps it in sessionStorage. */
function pending(): Pending | null {
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    const raw = key === null ? null : sessionStorage.getItem(key);
    if (raw === null) continue;
    try {
      const value = JSON.parse(raw) as Partial<Pending>;
      if (
        typeof value.state === "string" &&
        typeof value.verifier === "string" &&
        typeof value.returnTo === "string"
      ) {
        return { state: value.state, verifier: value.verifier, returnTo: value.returnTo };
      }
    } catch {
      continue;
    }
  }
  return null;
}

function tokenResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

let assign: ReturnType<typeof vi.fn>;
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  sessionStorage.clear();
  assign = stubLocation("/engagements/e1").assign;
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

async function startSignIn(returnTo?: string): Promise<Pending> {
  // `signIn` is latched per page load; a fresh module copy stands in for a fresh page.
  vi.resetModules();
  const fresh = await import("./session");
  await (returnTo === undefined ? fresh.signIn() : fresh.signIn(returnTo));
  const stored = pending();
  if (stored === null) throw new Error("signIn stored no pending request");
  return stored;
}

describe("ac1 signIn", () => {
  it("stores state, verifier and returnTo, and navigates to the authorize endpoint", async () => {
    const stored = await startSignIn("/engagements/e9");
    expect(stored.returnTo).toBe("/engagements/e9");
    expect(stored.state.length).toBeGreaterThanOrEqual(43);
    expect(stored.verifier.length).toBeGreaterThanOrEqual(43);

    expect(assign).toHaveBeenCalledOnce();
    const url = new URL(String(assign.mock.calls[0]?.[0]));
    expect(`${url.origin}${url.pathname}`).toBe(`${AUTHORITY}/authorize`);
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("client_id")).toBe("abacus-web");
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost:5173/signin/callback");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("state")).toBe(stored.state);
    expect(url.searchParams.get("code_challenge")).toBe(await codeChallenge(stored.verifier));
  });

  it("returns to the current path by default", async () => {
    const stored = await startSignIn();
    expect(stored.returnTo).toBe("/engagements/e1");
  });

  it("never stores an unsafe return path", async () => {
    const stored = await startSignIn("//evil.test");
    expect(stored.returnTo).toBe("/");
  });

  it("uses a fresh state and verifier each time", async () => {
    const first = await startSignIn();
    const second = await startSignIn();
    expect(second.state).not.toBe(first.state);
    expect(second.verifier).not.toBe(first.verifier);
  });
});

describe("ac1 completeSignIn", () => {
  it("exchanges the code, stores the token with its expiry and returns the return path", async () => {
    const stored = await startSignIn("/engagements/e9");
    fetchMock.mockResolvedValue(
      tokenResponse({ access_token: "tok-1", token_type: "Bearer", expires_in: 600 }),
    );

    const returnTo = await completeSignIn(`?code=abc&state=${stored.state}`, NOW);

    expect(returnTo).toBe("/engagements/e9");
    expect(accessToken(NOW + 1000)).toBe("tok-1");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, { method: string; body: unknown }];
    expect(url).toBe(`${AUTHORITY}/token`);
    expect(init.method).toBe("POST");
    const form = new URLSearchParams(String(init.body));
    expect(form.get("grant_type")).toBe("authorization_code");
    expect(form.get("code")).toBe("abc");
    expect(form.get("client_id")).toBe("abacus-web");
    expect(form.get("redirect_uri")).toBe("http://localhost:5173/signin/callback");
    expect(form.get("code_verifier")).toBe(stored.verifier);
  });

  it("removes the pending request after success", async () => {
    const stored = await startSignIn();
    fetchMock.mockResolvedValue(tokenResponse({ access_token: "t", expires_in: 600 }));
    await completeSignIn(`?code=abc&state=${stored.state}`, NOW);
    expect(pending()).toBeNull();
  });

  it("fails without a pending request", async () => {
    await expect(completeSignIn("?code=abc&state=whatever", NOW)).rejects.toBeInstanceOf(
      SignInFailed,
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(accessToken(NOW)).toBeNull();
  });

  it("fails on a missing state, a mismatched state, or a missing code, and drops the request", async () => {
    for (const search of ["?code=abc", "?code=abc&state=wrong", "?state=SAME"]) {
      const stored = await startSignIn();
      const query = search.replace("SAME", stored.state);
      await expect(completeSignIn(query, NOW)).rejects.toBeInstanceOf(SignInFailed);
      expect(pending()).toBeNull();
    }
    expect(fetchMock).not.toHaveBeenCalled();
    expect(accessToken(NOW)).toBeNull();
  });

  it("fails when the token endpoint refuses, and drops the request", async () => {
    const stored = await startSignIn();
    fetchMock.mockResolvedValue(tokenResponse({ error: "invalid_grant" }, 400));
    await expect(completeSignIn(`?code=abc&state=${stored.state}`, NOW)).rejects.toBeInstanceOf(
      SignInFailed,
    );
    expect(pending()).toBeNull();
    expect(accessToken(NOW)).toBeNull();
  });

  it("fails on a malformed token response", async () => {
    for (const body of [{}, { access_token: 5, expires_in: 600 }, { access_token: "t" }]) {
      const stored = await startSignIn();
      fetchMock.mockResolvedValue(tokenResponse(body));
      await expect(completeSignIn(`?code=abc&state=${stored.state}`, NOW)).rejects.toBeInstanceOf(
        SignInFailed,
      );
      expect(pending()).toBeNull();
    }
    expect(accessToken(NOW)).toBeNull();
  });

  it("cannot be replayed: the second attempt has no pending request", async () => {
    const stored = await startSignIn();
    fetchMock.mockResolvedValue(tokenResponse({ access_token: "t", expires_in: 600 }));
    await completeSignIn(`?code=abc&state=${stored.state}`, NOW);
    await expect(completeSignIn(`?code=abc&state=${stored.state}`, NOW)).rejects.toBeInstanceOf(
      SignInFailed,
    );
  });
});

describe("ac1 accessToken", () => {
  it("is null before sign-in", () => {
    expect(accessToken(NOW)).toBeNull();
  });

  it("is null within 30 seconds of expiry, and until then the token", async () => {
    const stored = await startSignIn();
    fetchMock.mockResolvedValue(tokenResponse({ access_token: "tok", expires_in: 600 }));
    await completeSignIn(`?code=abc&state=${stored.state}`, NOW);
    expect(accessToken(NOW)).toBe("tok");
    expect(accessToken(NOW + 500_000)).toBe("tok");
    expect(accessToken(NOW + 571_000)).toBeNull();
    expect(accessToken(NOW + 600_000)).toBeNull();
    expect(accessToken(NOW + 700_000)).toBeNull();
  });
});

describe("ac1 signIn latch", () => {
  it("starts one redirect and writes one pending request for concurrent calls", async () => {
    vi.resetModules();
    const fresh = await import("./session");
    await Promise.all([fresh.signIn("/a"), fresh.signIn("/b"), fresh.signIn("/c")]);
    expect(assign).toHaveBeenCalledOnce();
    expect(pending()?.returnTo).toBe("/a");
  });
});

describe("ac1 handleUnauthorised", () => {
  async function signedInAt(now: number): Promise<void> {
    const stored = await startSignIn();
    fetchMock.mockResolvedValue(tokenResponse({ access_token: "tok", expires_in: 600 }));
    await completeSignIn(`?code=abc&state=${stored.state}`, now);
    assign.mockClear();
    expect(accessToken(now)).toBe("tok");
  }

  it("rejects, without redirecting, within 10 seconds of signing in, and drops the token", async () => {
    await signedInAt(NOW);
    vi.resetModules();
    const fresh = await import("./session");
    expect(fresh.handleUnauthorised(NOW + 9_000)).toBe("rejected");
    expect(assign).not.toHaveBeenCalled();
    expect(accessToken(NOW + 9_000)).toBeNull();
  });

  it("redirects through sign-in after that, and drops the token", async () => {
    await signedInAt(NOW);
    vi.resetModules();
    const fresh = await import("./session");
    expect(fresh.handleUnauthorised(NOW + 11_000)).toBe("redirected");
    await vi.waitFor(() => {
      expect(assign).toHaveBeenCalledOnce();
    });
    expect(String(assign.mock.calls[0]?.[0])).toContain("/authorize?");
    expect(accessToken(NOW + 11_000)).toBeNull();
  });

  it("redirects when the user never signed in during this session", async () => {
    vi.resetModules();
    const fresh = await import("./session");
    expect(fresh.handleUnauthorised(NOW)).toBe("redirected");
    await vi.waitFor(() => {
      expect(assign).toHaveBeenCalledOnce();
    });
  });
});

describe("ac1 safeReturnTo", () => {
  it("keeps same-origin paths", () => {
    expect(safeReturnTo("/")).toBe("/");
    expect(safeReturnTo("/engagements/e1")).toBe("/engagements/e1");
    expect(safeReturnTo("/engagements/e1?tab=1")).toBe("/engagements/e1?tab=1");
  });

  it("rejects protocol-relative and absolute URLs", () => {
    expect(safeReturnTo("//evil.test")).toBe("/");
    expect(safeReturnTo("//evil.test/path")).toBe("/");
    expect(safeReturnTo("https://evil.test/x")).toBe("/");
    expect(safeReturnTo("javascript:alert(1)")).toBe("/");
    expect(safeReturnTo("")).toBe("/");
  });

  it("rejects the callback path", () => {
    expect(safeReturnTo("/signin/callback")).toBe("/");
    expect(safeReturnTo("/signin/callback?code=x&state=y")).toBe("/");
  });
});
