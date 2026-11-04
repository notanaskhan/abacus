// EBP-04 Contributions & remittance timeliness (A-05-T31; the handoff spec): Northwind PY2025 in the
// AUD-02 cockpit with Testing › Contributions & Remittance selected (seed/ebp04.ts), Hannah Leclerc:
//
//   a            Thu Sep 24, 10:15 AM   late deposit found (Reconciliation)
//   b            10:15 AM               Timeliness: the 26 payrolls
//   c            10:15 AM               Testing: 25-participant recalculation (A-05-T32)
//   d            10:15 AM               agent running: tallies Pending, Card A skeleton
//   e            10:15 AM               concluded: AJE-1 Client approved
//   f            Wed Sep 30, 3:10 PM    Corrected: the correction a person recorded
//   off          10:15 AM               `ebp.modules` off: C-20
//
// Dev and test only.

import type { AuditCockpitOut, CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  type Ebp04Variant,
  ebp04Figures,
  ebp04Late,
  ebp04Payrolls,
  ebp04Schedule,
  ebp04Test,
} from "../seed/ebp04";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-24T10:15:00-05:00";
const AT_F = "2026-09-30T15:10:00-05:00";
const COCKPIT = "GET /v1/audits/{work_item_id}/cockpit";
const E = "/v1/audits/{work_item_id}/ebp";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": on } };
}

/** The Northwind cockpit with Testing › Contributions & Remittance ("In progress" or "Running"). */
function withContributions(base: FixtureHandler, running: boolean): FixtureHandler {
  return async (request) => {
    const response = await base(request);
    if (!response.ok) return response;
    const cockpit = (await response.json()) as AuditCockpitOut;
    const bands = (cockpit.bands ?? []).map((band, n, all) =>
      n !== all.length - 1
        ? band
        : {
            ...band,
            rows: [
              {
                key: "ebp_04",
                title: "Contributions & Remittance",
                route: "EBP-04",
                link: "planned" as const,
                work_item_ref: cockpit.work_item_id,
                grammar: "sub_line" as const,
                section_state: running ? ("running" as const) : ("in_progress" as const),
                sub_line: running ? "Running" : "In progress",
                allowed_actions: [],
              },
              ...(band.rows ?? []),
            ],
          },
    );
    return json({ ...cockpit, bands });
  };
}

function frame(
  state: string,
  options: { variant?: Ebp04Variant; running?: boolean; on?: boolean; clock?: string } = {},
): Scenario {
  const variant = options.variant ?? "a";
  const on = options.on ?? true;
  return {
    state,
    persona: "hannah-leclerc",
    clock: options.clock ?? AT,
    get handlers(): Record<string, FixtureHandler> {
      const audits = auditHandlers(seed, "run");
      const cockpit = audits[COCKPIT];
      return {
        ...E0.handlers,
        ...audits,
        ...(cockpit === undefined
          ? {}
          : { [COCKPIT]: withContributions(cockpit, options.running === true) }),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
        [`GET ${E}/contributions/reconciliation`]: () => json(ebp04Figures(variant)),
        [`GET ${E}/contributions/payrolls`]: () => json(ebp04Payrolls()),
        [`GET ${E}/late-remittances`]: () => json(ebp04Late(variant)),
        [`GET ${E}/schedule-h-4a`]: () => json(ebp04Schedule(variant)),
        [`GET ${E}/contributions/test`]: () => json(ebp04Test()),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c"),
  d: frame("d", { running: true }),
  e: frame("e", { variant: "e" }),
  f: frame("f", { variant: "f", clock: AT_F }),
  off: frame("off", { on: false }),
});

export type Ebp04State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp04State[];
export const TAB_OF: Record<Ebp04State, "reconciliation" | "timeliness" | "testing"> = {
  a: "reconciliation",
  b: "timeliness",
  c: "testing",
  d: "reconciliation",
  e: "reconciliation",
  f: "reconciliation",
  off: "reconciliation",
};
