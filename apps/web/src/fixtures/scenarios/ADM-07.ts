// ADM-07 Audit log explorer: one fixture scenario per artboard (G-02-T04; G-02 §5.4). a, b, e, f
// and g are Felix Andersen (security_admin: metadata only) at E0; c is the Copperleaf drawer
// rendered for Margaret Okonkwo, who reads the values (DEC-60, DEC-415 Q1), with Felix's
// values-withheld variant as `c_withheld`; d is the dormant policy principal, fixture-only
// (ADR-187). The screen (G-02-T13) reaches b, c, e, f and g from a by filtering, opening a row,
// exporting and searching; each scenario serves the same handlers. Mon Sep 14, 2026, 9:24 AM CT.

import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
import { auditLogHandlers } from "../handlers/audit-log";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";
import { type AuditView, AUDIT_E0, COPPERLEAF_SEQ, EMPTY_SEARCH } from "../seed/audit-log";

const E0 = seedScenario();
const seed = getSeed();

/** The screen's flag on, so a fixture journey reaches it through the real route (DEC-457). */
function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "felix-andersen");
  return { ...base, flags: { ...base.flags, "audit_log.explorer": true } };
}

function at(state: string, persona: string, view: AuditView = "default", clock = AUDIT_E0) {
  return {
    state,
    persona,
    clock,
    handlers: {
      ...E0.handlers,
      ...auditLogHandlers(view),
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "felix-andersen"),
  b: at("b", "felix-andersen"),
  c: at("c", "margaret-okonkwo"),
  c_withheld: at("c_withheld", "felix-andersen"),
  d: at("d", "felix-andersen", "policy", "2026-09-14T14:18:00Z"),
  e: at("e", "felix-andersen"),
  f: at("f", "felix-andersen"),
  g: at("g", "felix-andersen"),
});

export type Adm07State = keyof typeof scenarios;

/** The search each state opens with (G-02-T13): b filters, c opens the Copperleaf drawer, f
 * searches. */
export const OPENS: Record<Adm07State, string> = {
  a: "",
  b: "?actor=via_agent",
  c: `?event=${String(COPPERLEAF_SEQ)}`,
  c_withheld: `?event=${String(COPPERLEAF_SEQ)}`,
  d: "",
  e: "",
  f: `?q=${encodeURIComponent(EMPTY_SEARCH)}`,
  g: "",
};
