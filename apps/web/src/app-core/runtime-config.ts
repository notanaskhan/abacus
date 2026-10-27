// The runtime config (docs/contracts/platform-ops.md section 3.2): a static `/runtime-config.json`
// beside the SPA on each host, so one bundle is promoted unchanged (ADR-088). Every value in it is
// Public: it holds no secret and no tenant data. Unknown keys are ignored.
//
// Required before router boot (Q-01-T23, `app-core/boot.tsx`): a missing or malformed file renders
// a plain error state. Q-01-T50 reads it for browser error reporting. Sign-in goes through the
// session BFF, so the OIDC authority and client ID here are the deployed bundle's only copy.

export type RuntimeEnvironment = "local" | "staging" | "production";

export interface RuntimeConfig {
  environment: RuntimeEnvironment;
  oidc: { authority: string; client_id: string };
  /** Absent `dsn` or `tunnel` means browser error reporting is off. */
  sentry: { dsn?: string; tunnel?: string };
  /** The git SHA of the build. */
  release: string;
  portal_base_domain: string;
}

export const RUNTIME_CONFIG_PATH = "/runtime-config.json";

const ENVIRONMENTS: readonly string[] = ["local", "staging", "production"];

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

/** The contract's schema, checked: the config, or null when anything required is wrong. */
export function parseRuntimeConfig(value: unknown): RuntimeConfig | null {
  const root = record(value);
  if (root === null) return null;
  const environment = text(root.environment);
  const oidc = record(root.oidc);
  const authority = text(oidc?.authority);
  const clientId = text(oidc?.client_id);
  const release = text(root.release);
  const portalBaseDomain = text(root.portal_base_domain);
  if (
    environment === null ||
    !ENVIRONMENTS.includes(environment) ||
    authority === null ||
    clientId === null ||
    release === null ||
    portalBaseDomain === null
  ) {
    return null;
  }
  const sentryIn = root.sentry === undefined ? {} : record(root.sentry);
  if (sentryIn === null) return null;
  const sentry: RuntimeConfig["sentry"] = {};
  for (const key of ["dsn", "tunnel"] as const) {
    if (sentryIn[key] === undefined) continue;
    const entry = text(sentryIn[key]);
    if (entry === null) return null;
    sentry[key] = entry;
  }
  return {
    environment: environment as RuntimeEnvironment,
    oidc: { authority, client_id: clientId },
    sentry,
    release,
    portal_base_domain: portalBaseDomain,
  };
}

/**
 * Where browser errors go, or null when reporting is off: both a DSN and a same-origin tunnel
 * path. Events never go to the Sentry ingest directly (CSP `connect-src 'self'`; chapter 06).
 */
export function telemetryTarget(config: RuntimeConfig): { dsn: string; tunnel: string } | null {
  const { dsn, tunnel } = config.sentry;
  if (dsn === undefined || tunnel === undefined) return null;
  if (!tunnel.startsWith("/") || tunnel.startsWith("//") || tunnel.includes("\\")) return null;
  return { dsn, tunnel };
}

/** Fetch and check `/runtime-config.json`; null when it is missing, not JSON or invalid. */
export async function loadRuntimeConfig(): Promise<RuntimeConfig | null> {
  try {
    // A static file on this origin, not the API (ADR-011 governs the backend).
    const response = await fetch(RUNTIME_CONFIG_PATH, {
      cache: "no-store",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return null;
    return parseRuntimeConfig(await response.json());
  } catch {
    return null;
  }
}
