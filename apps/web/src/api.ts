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

/** A readable message for an API error body (`{"detail": ...}`), never raw server text. */
export function errorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string" && detail.length <= 200) return detail;
  }
  return "Something went wrong. Try again.";
}
