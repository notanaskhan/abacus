// The client portal's auth client (P-08-T11; ADR-168, DEC-212, DEC-231), the portal twin of the
// staff client in ./session.ts (P-01-T11). The BFF holds the session: the `__Host-abacus-portal`
// cookie on the firm's portal host, httpOnly, which the page never sees. The SPA keeps only the
// opaque access token verify (or a refresh) returned, in this module's memory: never in web
// storage, a URL or a log. A fresh one comes from `POST /v1/portal/auth/refresh`: the browser
// sends the cookie (same origin) and its own Origin, and this module adds `X-Abacus-CSRF: 1`.
//
// A 401 from the API refreshes once (one refresh for any number of parallel 401s, because the
// cookie rotates and a reused one ends the session) and replays a request without a body once;
// when the refresh fails the person goes to `/sign-in?return=<path and query>` (never the
// fragment, which can hold a reminder link). The pre-session family (`/v1/portal/auth/*`) is never
// refreshed or replayed: a wrong code's 401 is the screen's to show. Same-origin calls only, so
// the portal's CSP keeps `connect-src 'self'` (ADR-163 §4).
//
// In app-core with no design-system import: the portal entry loads it on its first chunk.
import { portalRefresh, portalSignOut as endServerSession } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";

export const CSRF_HEADER = "X-Abacus-CSRF";
/** The portal BFF's routes: never refreshed or replayed on a 401. */
export const PORTAL_AUTH_PREFIX = "/v1/portal/auth/";
export const PORTAL_SIGN_OUT_PATH = "/v1/portal/auth/sign-out";
/** POR-01's route and its return parameter (docs/screens/POR-01.md: `?return=`). */
export const SIGN_IN_PAGE = "/sign-in";
export const RETURN_PARAM = "return";

/** Refresh this long before the token runs out, so a request never leaves with a stale one. */
const EXPIRY_MARGIN_MS = 30_000;
/** The BFF's access-token lifetime (ADR-168: 15 minutes), when an answer does not say. */
const DEFAULT_EXPIRES_IN = 900;

interface Held {
  token: string;
  expiresAt: number;
}

/** The access token: memory only. A reload starts without one and refreshes from the cookie. */
let held: Held | null = null;
/** One refresh at a time: parallel callers share it, so the rotating cookie is used once. */
let inFlight: Promise<boolean> | null = null;
/** One trip to sign-in for any number of failed refreshes; cleared by the next sign-in. */
let redirecting = false;
let lastFailure: string | null = null;

/** The wall clock, for token lifetime only (never business time; that is app-core/clock). */
function deviceNow(): number {
  return Date.now();
}

export function portalAccessToken(now: number = deviceNow()): string | null {
  if (held === null || held.expiresAt - EXPIRY_MARGIN_MS <= now) return null;
  return held.token;
}

/** A signed-in answer (verify or refresh): hold its token in memory. */
export function setPortalSession(
  answer: { access_token?: string | null; expires_in?: number | null },
  now: number = deviceNow(),
): boolean {
  if (typeof answer.access_token !== "string" || answer.access_token === "") {
    held = null;
    return false;
  }
  const seconds = answer.expires_in ?? DEFAULT_EXPIRES_IN;
  held = { token: answer.access_token, expiresAt: now + seconds * 1000 };
  redirecting = false;
  lastFailure = null;
  return true;
}

/** Hold a token (or forget it with null). The screens' older entry point; prefer
 * `setPortalSession` with the BFF's whole answer. */
export function setPortalAccessToken(token: string | null, expiresIn = DEFAULT_EXPIRES_IN): void {
  if (token === null) held = null;
  else setPortalSession({ access_token: token, expires_in: expiresIn });
}

/** Why the last refresh failed (`session_expired`, `forbidden`, `network`), for diagnostics. */
export function lastPortalRefreshFailure(): string | null {
  return lastFailure;
}

/**
 * `POST /v1/portal/auth/refresh`: a fresh access token from the host cookie, which the BFF rotates.
 * Resolves false when there is no live session (no cookie, idle or absolute limit, reuse).
 */
export function refreshPortalSession(now: number = deviceNow()): Promise<boolean> {
  if (inFlight !== null) return inFlight;
  inFlight = (async () => {
    try {
      const { data, error, response } = await portalRefresh({
        headers: { [CSRF_HEADER]: "1" },
        throwOnError: false,
      });
      if (data?.state === "signed_in" && setPortalSession(data, now)) return true;
      held = null;
      const detail = (error as { detail?: unknown } | undefined)?.detail;
      lastFailure =
        typeof detail === "string"
          ? detail
          : response === undefined
            ? "network"
            : "session_expired";
      return false;
    } catch {
      held = null;
      lastFailure = "network";
      return false;
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

/** A token for the next request: the held one, refreshed first when it is about to run out. */
export async function freshPortalToken(now: number = deviceNow()): Promise<string | null> {
  if (held !== null && held.expiresAt - EXPIRY_MARGIN_MS <= now) await refreshPortalSession(now);
  return portalAccessToken(now);
}

/** A held token, or one refreshed from the cookie (a reload): false means sign in. */
export async function ensurePortalSession(now: number = deviceNow()): Promise<boolean> {
  if (portalAccessToken(now) !== null) return true;
  return refreshPortalSession(now);
}

/** Only same-origin paths may be returned to after sign-in (no open redirect, no loop). */
export function safePortalReturn(path: string | null | undefined): string {
  return typeof path === "string" &&
    path.startsWith("/") &&
    !path.startsWith("//") &&
    !path.includes("\\") &&
    !path.includes("#") &&
    path !== SIGN_IN_PAGE &&
    !path.startsWith(`${SIGN_IN_PAGE}?`) &&
    !path.startsWith(`${SIGN_IN_PAGE}/`) &&
    !path.startsWith("/v1/")
    ? path
    : "/";
}

/** Where the person is now: path and query, never the fragment. */
export function currentPortalRoute(): string {
  return safePortalReturn(`${window.location.pathname}${window.location.search}`);
}

/** `/sign-in?return=<path>`; plain `/sign-in` for the portal's root. */
export function signInPath(returnTo: string = currentPortalRoute()): string {
  const target = safePortalReturn(returnTo);
  if (target === "/") return SIGN_IN_PAGE;
  return `${SIGN_IN_PAGE}?${new URLSearchParams({ [RETURN_PARAM]: target }).toString()}`;
}

/** The `?return=` a sign-in page was opened with, if it is safe; null otherwise. */
export function returnFrom(search: string): string | null {
  const value = new URLSearchParams(search).get(RETURN_PARAM);
  if (value === null) return null;
  const safe = safePortalReturn(value);
  return safe === "/" ? null : safe;
}

type Navigate = (to: string) => void;
let navigate: Navigate = (to) => {
  window.location.assign(to);
};

/** The portal router's history, so going to sign-in keeps the page (and its caches) alive. */
export function setSignInNavigator(next: Navigate): void {
  navigate = next;
}

/** Go to sign-in once, coming back to `returnTo` (the current route by default). */
export function goToSignIn(returnTo: string = currentPortalRoute()): void {
  if (redirecting) return;
  redirecting = true;
  navigate(signInPath(returnTo));
}

export type PortalUnauthorised = "refreshed" | "redirected";

/**
 * A 401 for a request that carried `sentToken`. When a newer token is already held (another 401
 * refreshed first), it is used as is; otherwise one refresh, shared by every caller. A failed
 * refresh sends the person to sign-in with the route to come back to.
 */
export async function handlePortalUnauthorised(
  sentToken: string | null,
  now: number = deviceNow(),
): Promise<PortalUnauthorised> {
  const current = portalAccessToken(now);
  if (current !== null && current !== sentToken) return "refreshed";
  if (held?.token === sentToken) held = null;
  if (await refreshPortalSession(now)) return "refreshed";
  goToSignIn();
  return "redirected";
}

/** Forget the session in this page. */
export function endPortalSession(): void {
  held = null;
  lastFailure = null;
}

/** `POST /v1/portal/auth/sign-out` with the bearer (the BFF ends the session and clears the
 * cookie), then forget it here. A failed call still signs this page out. */
export async function portalSignOut(): Promise<void> {
  try {
    const token = await freshPortalToken();
    await endServerSession({
      throwOnError: false,
      ...(token === null ? {} : { headers: { Authorization: `Bearer ${token}` } }),
    });
  } finally {
    endPortalSession();
  }
}

function pathOf(request: Request): string {
  return new URL(request.url).pathname;
}

/** The pre-session family: start, verify, resend, refresh (and the second step). */
function isPreSession(path: string): boolean {
  return path.startsWith(PORTAL_AUTH_PREFIX) && path !== PORTAL_SIGN_OUT_PATH;
}

function bearerOf(request: Request): string | null {
  const value = request.headers.get("Authorization");
  return value?.startsWith("Bearer ") === true ? value.slice("Bearer ".length) : null;
}

function withToken(request: Request, token: string | null): Request {
  if (token !== null) request.headers.set("Authorization", `Bearer ${token}`);
  return request;
}

/** The bearer on every call but the pre-session family; refreshed first when about to expire.
 * The BFF's own routes never wait for a refresh: the refresh is one of them. */
async function onRequest(request: Request): Promise<Request> {
  const path = pathOf(request);
  if (isPreSession(path)) return request;
  if (path.startsWith(PORTAL_AUTH_PREFIX)) return withToken(request, portalAccessToken());
  return withToken(request, await freshPortalToken());
}

/** A 401 from the API: refresh once and replay a request without a body, once. A second 401 on
 * the replay is not refreshed again: the person signs in. */
async function onResponse(
  response: Response,
  request: Request,
  options: { fetch?: typeof globalThis.fetch },
): Promise<Response> {
  if (response.status !== 401 || pathOf(request).startsWith(PORTAL_AUTH_PREFIX)) return response;
  const outcome = await handlePortalUnauthorised(bearerOf(request));
  if (outcome !== "refreshed" || request.body !== null || options.fetch === undefined) {
    return response;
  }
  const replay = await options.fetch(withToken(new Request(request), portalAccessToken()));
  if (replay.status === 401) goToSignIn();
  return replay;
}

/** The generated client for the portal: same-origin `/v1`, the in-memory bearer, refresh on 401. */
export function configurePortalClient(): void {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
  if (!client.interceptors.request.exists(onRequest)) client.interceptors.request.use(onRequest);
  if (!client.interceptors.response.exists(onResponse)) {
    client.interceptors.response.use(onResponse);
  }
}

/** Tests only: a fresh page load's module state. */
export function resetPortalAuthForTest(): void {
  held = null;
  inFlight = null;
  redirecting = false;
  lastFailure = null;
  navigate = (to) => {
    window.location.assign(to);
  };
}
