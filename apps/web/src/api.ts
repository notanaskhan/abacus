// The generated client, configured once: same-origin `/v1` (Vite proxies it locally), the bearer
// token and, for users in several firms, the chosen firm. A 401 means the session is over.
import { client } from "@abacus/api-client/client";
import { accessToken, chosenTenant, handleUnauthorised } from "./auth/session";

export const TENANT_HEADER = "X-Abacus-Tenant";

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

/** A readable message for an API error body (`{"detail": ...}`), never raw server text. */
export function errorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string" && detail.length <= 200) return GATE_REASONS[detail] ?? detail;
  }
  return "Something went wrong. Try again.";
}
