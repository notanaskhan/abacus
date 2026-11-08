// The portal shell's data (P-08-T07; DEC-129, DEC-45): the PortalToolbar's nav and the
// EntitySwitcher's scopes from `GET /v1/me` → `portal`. The server unions the person's grants
// into one shell; the client draws it and adds one rule of its own: Approvals shows only while
// the chosen scope is an entity (a household never approves). No bell (DEC-58(d)).

import type { MePortalOut, MePortalScopeOut } from "@abacus/api-client";
import { meOptions } from "@abacus/api-client/query";
import { PORTAL_AREAS, type PortalNavItem } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";

type NavCode = MePortalOut["nav"][number];

const LABEL: Readonly<Record<NavCode, string>> = {
  home: "Home",
  documents: "Documents",
  questions: "Questions",
  approvals: "Approvals",
  sign: "Sign",
  messages: "Messages",
  deliverables: "Deliverables",
};

/** Scope kinds that are an entity client: they may approve (POR-08). */
const ENTITY_SCOPES: ReadonlySet<MePortalScopeOut["kind"]> = new Set(["client_entity"]);

export interface PortalToolbarData {
  user: string;
  nav: PortalNavItem[];
  scopes: readonly MePortalScopeOut[];
  scope: MePortalScopeOut | undefined;
}

/** The toolbar for a portal shell and the chosen scope (the first when none is chosen). */
export function portalToolbarData(
  user: string,
  portal: MePortalOut | null | undefined,
  scopeId: string | null = null,
): PortalToolbarData {
  const scopes = portal?.scopes ?? [];
  const scope = scopes.find((s) => s.id === scopeId) ?? scopes[0];
  const entity = scope !== undefined && ENTITY_SCOPES.has(scope.kind);
  if (isGovernanceScope(scope)) return { user, nav: governanceNav(), scopes, scope };
  const codes = (portal?.nav ?? []).filter((code) => code !== "approvals" || entity);
  const nav = PORTAL_AREAS.filter((area) => codes.some((code) => LABEL[code] === area.label)).map(
    (area) => ({ ...area }),
  );
  return { user, nav, scopes, scope };
}

/** R-02-T06 (R-02 §5.1, POR-15): the governance room's reduced shell. A `tcwg` scope's nav is the
 * room's own three areas, never management's (privacy per role and per scope, DEC-93); the count is
 * the questionnaires addressed to the person ("Questions for you · 2"). */
export const GOVERNANCE_AREAS: readonly PortalNavItem[] = [
  { label: "Communications", icon: "file-text" },
  { label: "Reports", icon: "download" },
  { label: "Questions for you", icon: "circle-help" },
];

export function governanceNav(questionsForYou = 0): PortalNavItem[] {
  return GOVERNANCE_AREAS.map((item) =>
    item.label === "Questions for you" && questionsForYou > 0
      ? { ...item, count: questionsForYou }
      : { ...item },
  );
}

/** Whether a scope opens the governance room's reduced shell (a `tcwg` grant's room). */
export function isGovernanceScope(scope: MePortalScopeOut | undefined): boolean {
  return scope?.kind === "governance_room";
}

/** R-02-T06 (R-02 §5.1): T-02's DV-11 "My K-1s" banner opens POR-09's K-1 section once
 * Deliverables is built; until then the banner keeps its own `/k1s`. */
export const K1S_SECTION_TARGET = "/deliverables?section=k1s";

/** `GET /v1/me` as the portal reads it. */
export function usePortalToolbar(scopeId: string | null = null): PortalToolbarData | undefined {
  const { data } = useQuery({ ...meOptions(), retry: false });
  if (data === undefined) return undefined;
  return portalToolbarData(data.display_name, data.portal, scopeId);
}
