// AUD-02 Audit cockpit: one fixture scenario per artboard A-01-T12 builds (a–e, g), and f
// (A-01-T31; h is A-09's, i K-04's). docs/screens/AUD-02.md. All seen by Hannah Leclerc on Northwind's PY2025 EBP
// audit at E0; clocks are the state labels' times (DV-3):
//
//   a  9:41 AM  Marcus Delaney's run #4127: the run grammar; overview pill "Processing"
//   b  9:20 AM  no run: every phase "Not started"; overview pill "Planning" (live)
//   c  9:23 AM  the plan proposed, not yet run: the rail as b (the proposal card is P-09's dock)
//   d  9:41 AM  the run, `?section=materiality`: "Waiting on Margaret Okonkwo"
//   e  9:58 AM  the run with Internal Control "Failed — see run"
//   f  9:41 AM  the run, Auto mode pressed: the O3 confirm (fixture only until P-10-T39)
//   g  9:41 AM  no run, the audit-program grammar: "Ready" / "In progress" (live)
//
// The dock of a, c, d and e (RunCard, transcript, plan approval, Retry) reads C6 v1 / P-10 and is
// masked in parity; here the dock is the v1 Agent tab every state shares. Data: the cockpit
// projections of seed/audit-cockpit.ts and the Source Documents aggregate of seed/audits-index.ts
// through fixtures/handlers/audits.ts. src/screens/AUD-02/scenarios.ts re-exports them.

import type { AuditCockpitOut, CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers, northwindAuditId } from "../handlers/audits";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import type { CockpitGrammar } from "../seed/audit-cockpit";
import { capabilitiesFor } from "../seed/shell";
import { DOCUMENTS } from "../seed/trust";

const E0 = seedScenario();
const seed = getSeed();

/** Every artboard is Northwind's PY2025 EBP audit (`$auditId`). */
export const AUDIT_ID = northwindAuditId(seed);

function capabilities(
  persona: string | undefined,
  extra: readonly string[] = [],
): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    capabilities: [...base.capabilities, "engagement.read_metadata", ...extra],
    flags: { ...base.flags, "audits.cockpit": true },
  };
}

function at(state: string, time: string, grammar: CockpitGrammar): Scenario {
  return {
    state,
    persona: "hannah-leclerc",
    clock: `2026-09-14T${time}:00-05:00`,
    handlers: {
      ...E0.handlers,
      // The Viewer tab reads the seeded Harborline document (SHL-08 b's).
      ...trustHandlers({ documents: DOCUMENTS, citations: [] }),
      ...auditHandlers(seed, grammar),
      "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
    },
  };
}

/** P-10-T39's route (not in the OpenAPI document yet; domain/audits/mutations.ts, DEC-405). */
export const AUTO_MODE_ROUTE = "PUT /v1/engagements/{engagement_id}/auto-mode";

/** The server's refusal for a real firm in Season 1 (P-10 AC-E3, DEC-50). The client reads the
 * 409 status, not this code. */
export const autoModeRefused: FixtureHandler = () =>
  json({ detail: "auto_mode_unavailable" }, 409);

/** f: Hannah holds `engagement_run.auto_mode` (P-10-T39's capability), the projection reports Auto
 * mode off, and Brightwater Hale is synthetic, so the server accepts Turn on (P-10 AC-E3). The
 * rail is the run's, as the artboard draws it ("Started 9:24 AM", "Processing"). */
function autoMode(): Scenario {
  const base = at("f", "09:41", "run");
  const read = base.handlers["GET /v1/audits/{work_item_id}/cockpit"];
  return {
    ...base,
    handlers: {
      ...base.handlers,
      "GET /v1/me/capabilities": ({ persona }) =>
        json(capabilities(persona, ["engagement_run.auto_mode"])),
      "GET /v1/audits/{work_item_id}/cockpit": async (request) => {
        const answer = await read?.(request);
        if (answer === undefined || !answer.ok) return answer ?? json({}, 500);
        const cockpit = (await answer.json()) as AuditCockpitOut;
        return json({ ...cockpit, audit_bar: { ...cockpit.audit_bar, auto_mode: false } });
      },
      [AUTO_MODE_ROUTE]: ({ body }) =>
        json({ enabled: (body as { enabled?: unknown } | null)?.enabled === true }),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "09:41", "run"),
  b: at("b", "09:20", "idle"),
  c: at("c", "09:23", "idle"),
  d: at("d", "09:41", "run"),
  e: at("e", "09:58", "failed"),
  f: autoMode(),
  g: at("g", "09:41", "pills"),
});
