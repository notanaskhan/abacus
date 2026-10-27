// ADM-06 Security center: one fixture scenario per artboard (G-02-T11; G-02 §5.4) and T03's new
// states. a, b, c, d, g and h are Felix Andersen (security_admin, the QI) at E0, Mon Sep 14, 2026,
// 9:24 AM CT; e is the dated snapshot of Sun Jan 11, 2026 (41 of 46 enrolled, SSO not yet
// enforced); f is Margaret Okonkwo read-only, with Felix's export waiting for her approval.
// T03's rows: `sessions` (the drawer), `unlock` (a lock the identity provider keeps: "Unlocks
// automatically at 9:39 AM"), `d_waiting` (Felix's decision waiting for Margaret) and the support
// card's `support_requested`, `support_granted` and `support_revoked`. ADM-06 i and j are
// revision R2's fixture-only frames (G-02-T16): the screen draws the enterprise-identity rows
// from `ENTERPRISE` only when a scenario passes it, never from the route, until G-03-T29. The screen (G-02-T16) reaches
// b, c, d and g from a by its own actions; each scenario serves the same handlers. Retention
// (fieldset F) is Q-02's contract and has no fixture yet (see seed/security-center.ts).

import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
import { complianceHandlers } from "../handlers/compliance";
import { type SecurityOptions, securityCenterHandlers } from "../handlers/security-center";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";
import { SEATS } from "../seed/people";
import { SECURITY_E0, SECURITY_JAN_11 } from "../seed/security-center";
import { stableId } from "../seed/prng";

const E0 = seedScenario();
const seed = getSeed();

/** The screen's flag on, so a fixture journey reaches it through the real route (DEC-457). */
function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "felix-andersen");
  return { ...base, flags: { ...base.flags, "security_center.v1": true } };
}

function at(
  state: string,
  persona: string,
  options: SecurityOptions & { requested?: boolean; approver?: boolean } = {},
  clock = SECURITY_E0,
) {
  return {
    state,
    persona,
    clock,
    // The schedule's handlers first: Q-02's `/{export_id}/approve` would take `schedule/approve`.
    handlers: {
      ...E0.handlers,
      ...securityCenterHandlers(options),
      ...complianceHandlers({
        requested: options.requested === true,
        approver: options.approver === true,
      }),
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "felix-andersen"),
  b: at("b", "felix-andersen"),
  c: at("c", "felix-andersen"),
  d: at("d", "felix-andersen"),
  d_waiting: at("d_waiting", "felix-andersen", { waiting: true }),
  e: at("e", "felix-andersen", { view: "jan_11" }, SECURITY_JAN_11),
  f: at("f", "margaret-okonkwo", { requested: true, approver: true }),
  g: at("g", "felix-andersen", { requested: true }),
  h: at("h", "felix-andersen"),
  sessions: at("sessions", "felix-andersen"),
  unlock: at("unlock", "felix-andersen"),
  support_requested: at("support_requested", "felix-andersen", { support: "requested" }),
  support_granted: at("support_granted", "felix-andersen", { support: "active" }),
  support_revoked: at("support_revoked", "felix-andersen", { support: "revoked" }),
  i: at("i", "felix-andersen"),
  j: at("j", "felix-andersen"),
});

/** Revision R2 (fixture only until G-03-T29): Require SSO · Per user over the 46 seat holders and
 * the break-glass account (exempt, locked); SCIM Connected · Microsoft Entra ID, 46 of 46 seats,
 * the five groups, last sync 9:00 AM with 0 errors; j adds "1 user not provisioned". */
export interface EnterpriseFixture {
  mode: "all" | "per_user";
  provider: string;
  idpInitiated: boolean;
  provisioned: number;
  seats: number;
  groups: readonly string[];
  seasonalEnds: string;
  lastSyncAt: string;
  errors: number;
  unprovisioned?: number;
  seatHolders: readonly { userId: string; name: string; sso: boolean; exempt: boolean }[];
}
const ENTERPRISE_E0: EnterpriseFixture = {
  mode: "all",
  provider: "Microsoft Entra ID",
  idpInitiated: true,
  provisioned: 46,
  seats: 46,
  groups: ["Audit & assurance", "Tax", "Client accounting (CAS)", "Firm operations", "Seasonal"],
  seasonalEnds: "Oct 31, 2026",
  lastSyncAt: "2026-09-14T14:00:00Z",
  errors: 0,
  seatHolders: [
    ...SEATS.map((seat) => ({
      userId: stableId(`user:${seat.name.toLowerCase().replace(/[^a-z]+/g, "-")}`),
      name: seat.name,
      sso: true,
      exempt: false,
    })),
    {
      userId: stableId("user:break-glass-account"),
      name: "Break-glass account",
      sso: false,
      exempt: true,
    },
  ],
};
export const ENTERPRISE: Partial<Record<Adm06State, EnterpriseFixture>> = {
  i: { ...ENTERPRISE_E0, mode: "per_user" },
  j: { ...ENTERPRISE_E0, errors: 1, unprovisioned: 1 },
};

/** The search each state opens with (G-02-T16). */
export const OPENS: Record<Adm06State, string> = {
  a: "",
  b: "",
  c: "?export=history",
  d: "?incident=INC-2026-005",
  d_waiting: "?incident=INC-2026-005",
  e: "",
  f: "",
  g: "",
  h: "",
  sessions: "?sessions=1",
  unlock: "?sessions=1",
  support_requested: "",
  support_granted: "",
  support_revoked: "",
  i: "",
  j: "",
};

export type Adm06State = keyof typeof scenarios;
