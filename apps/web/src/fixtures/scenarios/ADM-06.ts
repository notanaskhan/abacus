// ADM-06 Security center: one fixture scenario per artboard (G-02-T11; G-02 §5.4) and T03's new
// states. a, b, c, d, g and h are Felix Andersen (security_admin, the QI) at E0, Mon Sep 14, 2026,
// 9:24 AM CT; e is the dated snapshot of Sun Jan 11, 2026 (41 of 46 enrolled, SSO not yet
// enforced); f is Margaret Okonkwo read-only, with Felix's export waiting for her approval.
// T03's rows: `sessions` (the drawer), `unlock` (a lock the identity provider keeps: "Unlocks
// automatically at 9:39 AM"), `d_waiting` (Felix's decision waiting for Margaret) and the support
// card's `support_requested`, `support_granted` and `support_revoked`. ADM-06 i and j are
// fixture-only R2 frames owned by G-03-T29 and are not served here. The screen (G-02-T16) reaches
// b, c, d and g from a by its own actions; each scenario serves the same handlers. Retention
// (fieldset F) is Q-02's contract and has no fixture yet (see seed/security-center.ts).

import { defineScenarios } from "../../app-core/fixture-mode";
import { complianceHandlers } from "../handlers/compliance";
import { type SecurityOptions, securityCenterHandlers } from "../handlers/security-center";
import { seedScenario } from "../scenario";
import { SECURITY_E0, SECURITY_JAN_11 } from "../seed/security-center";

const E0 = seedScenario();

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
});

export type Adm06State = keyof typeof scenarios;
