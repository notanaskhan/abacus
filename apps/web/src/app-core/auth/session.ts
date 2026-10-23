// The staff auth client (P-01-T11; P-01 AC 5.1.3 to 5.1.6; ADR-141, ADR-165). The BFF holds the
// session: an httpOnly `__Host-` cookie the page never sees. The SPA keeps only a short-lived
// access token, in this module's memory, never in web storage, and gets a fresh one from
// `POST /v1/auth/refresh` (the cookie plus `X-Abacus-CSRF: 1`). Signing in is a top-level
// navigation to `GET /v1/auth/sign-in?return_to=`; the BFF sends the browser to the provider and
// back to SHL-06g at `/signin/callback?to=…` (or `?error=<code>`). No token is exchanged here.
import { refresh, signOut as endServerSession } from "@abacus/api-client";

export const CALLBACK_PATH = "/signin/callback";
export const SIGN_IN_PATH = "/v1/auth/sign-in";
/** The BFF's own routes: never retried or refreshed on a 401 (the refresh answers 401 itself). */
export const AUTH_PREFIX = "/v1/auth/";
export const CSRF_HEADER = "X-Abacus-CSRF";

const TENANT_KEY = "abacus.tenant";
/** Refresh this long before the token runs out, so a request never leaves with a stale one. */
const EXPIRY_MARGIN_MS = 30_000;
// A 401 this soon after a session started means the API rejects fresh tokens (misconfiguration):
// signing in again would loop, so the caller shows an error instead.
const LOOP_WINDOW_MS = 10_000;

interface Held {
  token: string;
  expiresAt: number;
}

/** The access token: memory only (AC 5.1.5). A reload starts without one and refreshes. */
let held: Held | null = null;
/** When the current session last produced a token on the callback page (the loop guard). */
let signedInAt = 0;
/** One refresh at a time: parallel callers share it, so the rotating cookie is used once. */
let inFlight: Promise<boolean> | null = null;
/** `signIn` navigates away once per page load; parallel 401s start one sign-in. */
let signingIn = false;

/** The wall clock, for token lifetime only (never business time; that is app-core/clock). */
function deviceNow(): number {
  return Date.now();
}

export function accessToken(now: number = deviceNow()): string | null {
  if (held === null || held.expiresAt - EXPIRY_MARGIN_MS <= now) return null;
  return held.token;
}

/** A token is held but is about to run out: refresh before the next request. */
function stale(now: number): boolean {
  return held !== null && held.expiresAt - EXPIRY_MARGIN_MS <= now;
}

/** Why the last refresh failed: the BFF's code (`session_expired`, `session_refresh_reused`). */
export type RefreshFailure = string;
let lastFailure: RefreshFailure | null = null;

export function lastRefreshFailure(): RefreshFailure | null {
  return lastFailure;
}

/**
 * `POST /v1/auth/refresh`: a fresh access token from the session cookie, which the BFF rotates.
 * Resolves false when there is no live session (no cookie, idle or absolute limit, reuse).
 */
export function refreshSession(now: number = deviceNow()): Promise<boolean> {
  if (inFlight !== null) return inFlight;
  inFlight = (async () => {
    try {
      const { data, error } = await refresh({
        headers: { [CSRF_HEADER]: "1" },
        throwOnError: false,
      });
      if (data === undefined) {
        held = null;
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        lastFailure = typeof detail === "string" ? detail : "session_expired";
        return false;
      }
      held = { token: data.access_token, expiresAt: now + data.expires_in * 1000 };
      lastFailure = null;
      return true;
    } catch {
      held = null;
      lastFailure = "sign_in_failed";
      return false;
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

/** SHL-06g: the callback page's refresh, which also starts the loop guard's window. */
export async function startSession(now: number = deviceNow()): Promise<boolean> {
  const ok = await refreshSession(now);
  if (ok) signedInAt = now;
  return ok;
}

/** A token for the next request: the held one, refreshed first when it is about to run out. A
 * page that holds none waits for `ensureSession` (the shell's bootstrap), not for this. */
export async function freshToken(now: number = deviceNow()): Promise<string | null> {
  if (stale(now)) await refreshSession(now);
  return accessToken(now);
}

/** A held token, or one refreshed from the cookie: false means the person must sign in. */
export async function ensureSession(now: number = deviceNow()): Promise<boolean> {
  if (accessToken(now) !== null) return true;
  return refreshSession(now);
}

/** The firm chosen when the user belongs to several (sent as X-Abacus-Tenant). An identifier,
 * not a credential, so it may stay in this tab's storage. */
export function chosenTenant(): string | null {
  try {
    return sessionStorage.getItem(TENANT_KEY);
  } catch {
    return null;
  }
}

export function chooseTenant(tenantId: string): void {
  try {
    sessionStorage.setItem(TENANT_KEY, tenantId);
  } catch {
    // Storage refused: the firm is asked for again on the next load.
  }
}

/** Only same-origin paths may be returned to after sign-in (no open redirect). */
export function safeReturnTo(path: string | null | undefined): string {
  return typeof path === "string" &&
    path.startsWith("/") &&
    !path.startsWith("//") &&
    !path.includes("\\") &&
    !path.startsWith(CALLBACK_PATH) &&
    !path.startsWith(AUTH_PREFIX)
    ? path
    : "/";
}

/** Where the person is now: the route an expired session returns to (AC 5.1.4). */
export function currentRoute(): string {
  return safeReturnTo(`${window.location.pathname}${window.location.search}`);
}

/** The BFF's sign-in URL: a top-level navigation, never a fetch (AC 5.1.6). */
export function signInUrl(returnTo: string, options: { forceLogin?: boolean } = {}): string {
  const params = new URLSearchParams({ return_to: safeReturnTo(returnTo) });
  // SPEC-016 AC-6, P-01 AC 5.1.5: a fresh sign-in (and its MFA) for actions that need recent MFA.
  if (options.forceLogin === true) params.set("reauthenticate", "true");
  return `${SIGN_IN_PATH}?${params.toString()}`;
}

export function signIn(
  returnTo: string = currentRoute(),
  options: { forceLogin?: boolean } = {},
): void {
  if (signingIn) return;
  signingIn = true;
  window.location.assign(signInUrl(returnTo, options));
}

/** What a 401 led to: a fresh token (retry once), a redirect to sign in, or a refusal that would
 * loop (the API rejects tokens the BFF just issued). */
export type Unauthorised = "refreshed" | "redirected" | "rejected";

/** On a 401 from the API: refresh from the cookie, else sign in and come back to this route. */
export async function handleUnauthorised(now: number = deviceNow()): Promise<Unauthorised> {
  held = null;
  if (now - signedInAt < LOOP_WINDOW_MS) return "rejected";
  if (await refreshSession(now)) return "refreshed";
  signIn(currentRoute());
  return "redirected";
}

/** Forget the session in this page: the token and the chosen firm. */
export function endSession(): void {
  held = null;
  signedInAt = 0;
  try {
    sessionStorage.removeItem(TENANT_KEY);
  } catch {
    // Nothing kept.
  }
}

/** `POST /v1/auth/sign-out` (the BFF ends the session and clears the cookie), then forget it
 * here. A failed call still signs this page out. */
export async function signOut(): Promise<void> {
  try {
    await endServerSession({ throwOnError: false });
  } finally {
    endSession();
  }
}

/** Tests only: a fresh page load's module state. */
export function resetAuthForTest(): void {
  held = null;
  signedInAt = 0;
  inFlight = null;
  signingIn = false;
  lastFailure = null;
}
