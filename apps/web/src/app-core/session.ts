import type { CapabilitiesOut, MembershipOut, PortalOut, RoleOut } from "@abacus/api-client";
import { meOptions, myCapabilitiesOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";

// The session (F-03-T32; ADR-145; SPEC-024 AC-5): who is signed in, in which firm, and what the
// permission matrix lets them do there, from `/v1/me` and `/v1/me/capabilities`. Screens ask
// through `useCan` (can.tsx) and `useFlag` / `useEntitlement` (flags.tsx), never by comparing
// role codes; ESLint refuses a role-literal comparison outside app-core.

/** The licensable modules (backend `platform.entitlements.Module`). */
export const MODULES = [
  "attest",
  "internal_audit",
  "group_audit",
  "statements_studio",
  "office_addins",
  "insights",
] as const;
export type Module = (typeof MODULES)[number];

export interface Scope {
  /** Evaluate on one engagement (sends `engagement_id`) rather than on the firm. */
  engagementId?: string | undefined;
}

export interface SessionUser {
  id: string;
  email: string;
  displayName: string;
}

export interface Session {
  /** "loading" until both `/v1/me` and `/v1/me/capabilities` answer. */
  status: "loading" | "ready" | "error";
  user: SessionUser | null;
  /** The membership of the active firm, or null before it is known. */
  tenant: MembershipOut | null;
  memberships: MembershipOut[];
  /** Role codes with their display labels: firm-wide, or on the engagement when scoped. */
  roles: RoleOut[];
  flags: Record<string, boolean | string>;
  entitlements: Module[];
  officeId: string | null;
  tz: string | null;
  mfaRecentUntil: string | null;
  serverNow: string | null;
  /** The portal shell and grant scopes, for client users only. */
  portal: PortalOut | null;
}

function capabilitiesQuery(engagementId: string | undefined) {
  return myCapabilitiesOptions(
    engagementId === undefined ? undefined : { query: { engagement_id: engagementId } },
  );
}

/** The capabilities answer, or undefined while it loads or after it fails (app-core only). */
export function useCapabilities(scope: Scope = {}): CapabilitiesOut | undefined {
  return useQuery(capabilitiesQuery(scope.engagementId)).data;
}

const isModule = (m: string): m is Module => (MODULES as readonly string[]).includes(m);

export function useSession(scope: Scope = {}): Session {
  const me = useQuery(meOptions());
  const caps = useQuery(capabilitiesQuery(scope.engagementId));
  const m = me.data;
  const c = caps.data;
  const status =
    me.isError || caps.isError
      ? "error"
      : m === undefined || c === undefined
        ? "loading"
        : "ready";
  return {
    status,
    user: m === undefined ? null : { id: m.user_id, email: m.email, displayName: m.display_name },
    tenant: m?.memberships.find((x) => x.tenant_id === m.active_tenant_id) ?? null,
    memberships: m?.memberships ?? [],
    roles: c?.roles ?? [],
    flags: c?.flags ?? {},
    entitlements: c?.entitlements.filter(isModule) ?? [],
    officeId: c?.office_id ?? null,
    tz: c?.tz ?? null,
    mfaRecentUntil: c?.mfa_recent_until ?? null,
    serverNow: c?.server_now ?? m?.server_now ?? null,
    portal: c?.portal ?? null,
  };
}
