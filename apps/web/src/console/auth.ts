// The console's staff auth client (G-04-T14; TASK-8548; DEC-5532), the firm client's shape
// (app-core/auth/session.ts) on the console BFF. The BFF holds the session in the httpOnly
// `__Host-abacus-console` cookie; the page keeps only a short-lived access token in this module's
// memory, never in web storage, and gets a fresh one from `POST /v1/platform/auth/refresh` (the
// cookie plus `X-Abacus-CSRF: 1`). One refresh at a time; a request carries the bearer; the BFF's
// own routes never wait for a refresh. Signing in is a top-level navigation (StaffAuth.tsx).
import { client } from "@abacus/api-client/client";
import { consoleRefresh, consoleSignOut } from "@abacus/api-client";

export const CSRF_HEADER = "X-Abacus-CSRF";
export const ACTIVITY_HEADER = "X-Abacus-Activity";
const AUTH_PREFIX = "/v1/platform/auth/";
/** Refresh this long before the token runs out, so a request never leaves with a stale one. */
const EXPIRY_MARGIN_MS = 30_000;

interface Held {
  token: string;
  expiresAt: number;
}

/** The wall clock, for token lifetime only (never business time; that is app-core/clock). */
function deviceNow(): number {
  return Date.now();
}

let held: Held | null = null;
let inFlight: Promise<boolean> | null = null;
let lastFailure: string | null = null;

/** The memory token while it is fresh, else null. */
export function consoleToken(now: number = deviceNow()): string | null {
  return held !== null && held.expiresAt - EXPIRY_MARGIN_MS > now ? held.token : null;
}

/** Why the last refresh failed (`session_expired`, `session_refresh_reused`), for the gate. */
export function lastConsoleFailure(): string | null {
  return lastFailure;
}

/** Ask the BFF for a fresh token (single flight). True when a session stands behind the cookie.
 * `active`: the person's own act (a page load, the callback), the only refresh that moves the
 * session's idle clock (`X-Abacus-Activity: user`, as the firm client); a request's background
 * refresh never does. */
export function refreshConsoleSession(
  now: number = deviceNow(),
  { active = false }: { active?: boolean } = {},
): Promise<boolean> {
  if (inFlight !== null) return inFlight;
  inFlight = (async () => {
    try {
      const { data, error } = await consoleRefresh({
        headers: active
          ? { [CSRF_HEADER]: "1", [ACTIVITY_HEADER]: "user" }
          : { [CSRF_HEADER]: "1" },
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

/** End the session behind the cookie and forget the token. */
export async function signOutConsole(): Promise<void> {
  held = null;
  await consoleSignOut({ headers: { [CSRF_HEADER]: "1" }, throwOnError: false });
}

async function onRequest(request: Request): Promise<Request> {
  if (new URL(request.url).pathname.startsWith(AUTH_PREFIX)) return request;
  const token = consoleToken() ?? ((await refreshConsoleSession()) ? consoleToken() : null);
  if (token !== null) request.headers.set("Authorization", `Bearer ${token}`);
  return request;
}

/** Same-origin `/v1`, the bearer on every call but the BFF's own. */
export function configureConsoleClient(): void {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
  if (!client.interceptors.request.exists(onRequest)) client.interceptors.request.use(onRequest);
}

/** Tests only: forget the held token and failure. */
export function resetConsoleAuth(): void {
  held = null;
  inFlight = null;
  lastFailure = null;
}
