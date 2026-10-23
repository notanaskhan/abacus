// The generated client, configured once: same-origin `/v1` (Vite proxies it locally), the bearer
// token and, for users in several firms, the chosen firm. A 401 means the session is over.
import { client } from "@abacus/api-client/client";
import { accessToken, chosenTenant, handleUnauthorised } from "./auth/session";

export const TENANT_HEADER = "X-Abacus-Tenant";

/**
 * The signed-in session's headers (bearer token and chosen firm), or null when signed out. The
 * telemetry tunnel sends these, so errors before sign-in are never reported (Q-01-T50).
 */
export function sessionHeaders(): Record<string, string> | null {
  const token = accessToken();
  if (token === null) return null;
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const tenant = chosenTenant();
  if (tenant !== null) headers[TENANT_HEADER] = tenant;
  return headers;
}

export function configureClient(): void {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
  client.interceptors.request.use((request) => {
    const token = accessToken();
    if (token !== null) request.headers.set("Authorization", `Bearer ${token}`);
    const tenant = chosenTenant();
    if (tenant !== null) request.headers.set(TENANT_HEADER, tenant);
    return request;
  });
  client.interceptors.response.use((response) => {
    if (response.status === 401) handleUnauthorised();
    return response;
  });
}

/** Retry transient failures once; never an auth or client error. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  const status =
    typeof error === "object" && error !== null && "status" in error ? error.status : undefined;
  return failureCount < 1 && !(typeof status === "number" && status >= 400 && status < 500);
}

// SPEC-025 AC-7: why client data isn't open yet, in plain words, wherever it's refused.
const GATE_REASONS: Record<string, string> = {
  acceptance_missing: "This opens once the engagement partner records acceptance.",
  acceptance_declined:
    "The engagement partner declined this engagement, so client data stays closed.",
  independence_conclusion_missing:
    "This opens once the engagement partner records their independence conclusion.",
  letter_missing: "Your firm requires the engagement letter to be recorded first.",
  // SPEC-025 AC-2 (TASK-048): roll-forward refusals.
  team_member_unavailable:
    "Someone on the proposed team has left the firm or been walled from this client. Go back and review the team.",
  proposal_changed: "The firm's template changed since this proposal. Go back and look again.",
  prior_mismatch: "That earlier engagement isn't for this client entity and type.",
  roll_forward_unavailable: "Rolling forward isn't available right now.",
};

// Q-01-T50: the platform's refusals. `read_only` is the maintenance kill switch (Q-01-T37);
// `service_unavailable` a dependency that is down (today's 503 body still says it with a space);
// `unscannable` a scanner that gave no verdict, which fails closed and can be retried (SPEC-050
// AC-16).
const PLATFORM_REASONS: Record<string, string> = {
  read_only: "This workspace is read-only for maintenance. Changes are paused.",
  service_unavailable: "This isn't available right now. Try again in a few minutes.",
  "service unavailable": "This isn't available right now. Try again in a few minutes.",
  unscannable:
    "We couldn't check this file just now, so nothing was saved. Try uploading it again.",
};

/** A readable message for an API error body (`{"detail": ...}`), never raw server text. */
export function errorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string" && detail.length <= 200) {
      return GATE_REASONS[detail] ?? PLATFORM_REASONS[detail] ?? detail;
    }
  }
  return "Something went wrong. Try again.";
}
