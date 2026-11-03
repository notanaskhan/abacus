// AUD-08 Risk assessment register (A-04-T20; the handoff spec): the fixture scenarios this row
// builds (A-04-T29 adds c, e, f, g), each on Northwind PY2025 (seed/aud08.ts):
//
//   a            hannah-leclerc     Mon Sep 14, 2:30 PM  ten risks; R3 and R5 routed 12:31 PM
//   b            hannah-leclerc     2:30 PM              `?ov=risk:R3`: Routed to Margaret, Remind
//   b2           margaret-okonkwo   2:30 PM              `?ov=risk:R3`: Approve as significant risk
//   d            hannah-leclerc     4:40 PM              EP approved, G4 met
//   off          hannah-leclerc     2:30 PM              `assurance.risk_register` off: C-20
//   not_allowed  cole-hart          2:30 PM              walled from Northwind: 404
//   c            hannah-leclerc     2:30 PM              the Linkage tab; R8 Suggested (A-04-T26)
//   e            hannah-leclerc     2:30 PM              revising after Internal Control (A-04-T26)
//   f            hannah-leclerc     2:30 PM              `?ov=risk:R8`: rationale drafted, not adopted
//   g            hannah-leclerc     2:30 PM              Identify risks with agent: 10 of 10, R8
//   drafting_off hannah-leclerc     2:30 PM              workpapers.drafting off: Check coverage
//
// Dev and test only.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { type Aud08Variant, aud08Drawer, aud08Linkage, aud08Register } from "../seed/aud08";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-14T14:30:00-05:00";
const AT_D = "2026-09-14T16:40:00-05:00";
const P = "/v1/engagements/{engagement_id}/risks";

function capabilities(
  persona: string | undefined,
  on: boolean,
  drafting: boolean,
): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    flags: {
      ...base.flags,
      "audits.cockpit": true,
      "assurance.risk_register": on,
      "workpapers.drafting": drafting,
    },
  };
}

function frame(
  state: string,
  options: {
    persona?: string;
    variant?: Aud08Variant;
    on?: boolean;
    clock?: string;
    drafting?: boolean;
  } = {},
): Scenario {
  const on = options.on ?? true;
  const drafting = options.drafting ?? true;
  const variant = options.variant ?? "a";
  return {
    state,
    persona: options.persona ?? "hannah-leclerc",
    clock: options.clock ?? AT,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on, drafting)),
        // A-04-T26 (g): code's coverage (A-04-T13): 10 of 10 material areas, R8 unaddressed.
        [`POST ${P}/coverage`]: () =>
          json({
            material_areas: 10,
            covered: 10,
            unaddressed_codes: ["R8"],
            wording_run_id: null,
          }),
        [`GET ${P}/register`]: () => json(aud08Register(variant)),
        [`GET ${P}/linkage`]: () => json(aud08Linkage()),
        [`GET ${P}/{risk_id}`]: () => json(aud08Drawer(variant)),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  b2: frame("b2", { persona: "margaret-okonkwo", variant: "b2" }),
  d: frame("d", { variant: "d", clock: AT_D }),
  off: frame("off", { on: false }),
  not_allowed: frame("not_allowed", { persona: "cole-hart" }),
  c: frame("c"),
  e: frame("e"),
  f: frame("f", { variant: "f" }),
  g: frame("g"),
  drafting_off: frame("drafting_off", { drafting: false }),
});

export type Aud08State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud08State[];
