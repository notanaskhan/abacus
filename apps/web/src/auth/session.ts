// The signed-in session: an access token kept in sessionStorage (this tab only) until it expires.
// No refresh tokens yet (ADR-030): an expired or rejected token sends the user to sign in again.
import { codeChallenge, randomString } from "./pkce";

export const AUTHORITY = import.meta.env.VITE_OIDC_AUTHORITY ?? "http://127.0.0.1:9000";
export const CLIENT_ID = import.meta.env.VITE_OIDC_CLIENT_ID ?? "abacus-web";
export const CALLBACK_PATH = "/signin/callback";

const TOKEN_KEY = "abacus.session";
const PENDING_KEY = "abacus.signin";
const TENANT_KEY = "abacus.tenant";
const EXPIRY_MARGIN_MS = 30_000;
const SIGNED_IN_AT_KEY = "abacus.signedInAt";
// A 401 this soon after signing in means the API rejects fresh tokens (misconfiguration):
// redirecting again would loop, so the app shows an error instead.
const LOOP_WINDOW_MS = 10_000;
let signingIn = false;

interface Stored {
  accessToken: string;
  expiresAt: number;
}

interface Pending {
  state: string;
  verifier: string;
  returnTo: string;
}

function redirectUri(): string {
  return `${window.location.origin}${CALLBACK_PATH}`;
}

function read(key: string): unknown {
  const raw = sessionStorage.getItem(key);
  if (raw === null) return null;
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}

function isStored(value: unknown): value is Stored {
  return (
    typeof value === "object" &&
    value !== null &&
    "accessToken" in value &&
    typeof value.accessToken === "string" &&
    "expiresAt" in value &&
    typeof value.expiresAt === "number"
  );
}

function isPending(value: unknown): value is Pending {
  return (
    typeof value === "object" &&
    value !== null &&
    "state" in value &&
    typeof value.state === "string" &&
    "verifier" in value &&
    typeof value.verifier === "string" &&
    "returnTo" in value &&
    typeof value.returnTo === "string"
  );
}

export function accessToken(now: number = Date.now()): string | null {
  const stored = read(TOKEN_KEY);
  if (!isStored(stored) || stored.expiresAt - EXPIRY_MARGIN_MS <= now) return null;
  return stored.accessToken;
}

/** The firm chosen when the user belongs to several (sent as X-Abacus-Tenant). */
export function chosenTenant(): string | null {
  return sessionStorage.getItem(TENANT_KEY);
}

export function chooseTenant(tenantId: string): void {
  sessionStorage.setItem(TENANT_KEY, tenantId);
}

/** Only same-origin paths may be returned to after sign-in (no open redirect). */
export function safeReturnTo(path: string): string {
  return path.startsWith("/") && !path.startsWith("//") && !path.startsWith(CALLBACK_PATH)
    ? path
    : "/";
}

export async function signIn(returnTo: string = window.location.pathname): Promise<void> {
  if (signingIn) return; // parallel 401s start one sign-in, not several racing ones
  signingIn = true;
  const pending: Pending = {
    state: randomString(),
    verifier: randomString(48),
    returnTo: safeReturnTo(returnTo),
  };
  sessionStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  const params = new URLSearchParams({
    response_type: "code",
    client_id: CLIENT_ID,
    redirect_uri: redirectUri(),
    state: pending.state,
    code_challenge: await codeChallenge(pending.verifier),
    code_challenge_method: "S256",
  });
  window.location.assign(`${AUTHORITY}/authorize?${params.toString()}`);
}

export class SignInFailed extends Error {}

/** Finish sign-in on the callback page; returns where to go next. */
export async function completeSignIn(search: string, now: number = Date.now()): Promise<string> {
  const params = new URLSearchParams(search);
  const pending = read(PENDING_KEY);
  sessionStorage.removeItem(PENDING_KEY);
  const code = params.get("code");
  if (!isPending(pending) || code === null || params.get("state") !== pending.state) {
    throw new SignInFailed("The sign-in response did not match this browser's request.");
  }
  const response = await fetchToken(
    new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri(),
      client_id: CLIENT_ID,
      code_verifier: pending.verifier,
    }),
  );
  if (!response.ok) throw new SignInFailed("The sign-in code was not accepted.");
  const body = (await response.json()) as { access_token?: unknown; expires_in?: unknown };
  if (typeof body.access_token !== "string" || typeof body.expires_in !== "number") {
    throw new SignInFailed("The sign-in response was malformed.");
  }
  const stored: Stored = {
    accessToken: body.access_token,
    expiresAt: now + body.expires_in * 1000,
  };
  sessionStorage.setItem(TOKEN_KEY, JSON.stringify(stored));
  sessionStorage.setItem(SIGNED_IN_AT_KEY, String(now));
  return pending.returnTo;
}

/** On a 401: sign in again, unless we just did (the API rejects fresh tokens: don't loop). */
export function handleUnauthorised(now: number = Date.now()): "redirected" | "rejected" {
  const signedInAt = Number(sessionStorage.getItem(SIGNED_IN_AT_KEY) ?? "0");
  sessionStorage.removeItem(TOKEN_KEY);
  if (now - signedInAt < LOOP_WINDOW_MS) return "rejected";
  void signIn();
  return "redirected";
}

export function signOut(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TENANT_KEY);
}

// The identity provider's token endpoint is not our API, so the generated client doesn't cover
// it: this is the one direct network call outside packages/api-client (the ESLint config allows
// `fetch` in this file only).
function fetchToken(body: URLSearchParams): Promise<Response> {
  return fetch(`${AUTHORITY}/token`, { method: "POST", body });
}
