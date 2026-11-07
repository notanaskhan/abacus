// NOT-02 Notice workspace (N-04-T14; the handoff spec): the fixture scenarios on N1 (seed/not02.ts):
//
//   a            kevin-osei     Mon Sep 14, 9:24 AM  analysis ready; position reserved to Daniel Reyes
//   b            kevin-osei     8:58 AM              analysis running: spinners, skeleton action
//   c            daniel-reyes   9:51 AM              decided: Agree · decided by Daniel Reyes
//   d            kevin-osei     9:24 AM              1099 corrections lit: two sources "1 / 2"
//   a2           kevin-osei     9:24 AM              Activity timeline
//   e            kevin-osei     9:24 AM              Collins CP2000 (N3): Disagree, Awaiting IRS
//   f            kevin-osei     9:24 AM              Santos CP14 (N5): None on file, Form 2848 to send
//   off          kevin-osei     9:24 AM              `notices.workspace` off: C-20
//
// Dev and test only.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  type Not02Variant,
  not02Activity,
  not02Analysis,
  not02Card,
  not02Notice,
} from "../seed/not02";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-14T09:24:00-05:00";
const AT_B = "2026-09-14T08:58:00-05:00";
const AT_C = "2026-09-14T09:51:00-05:00";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "kevin-osei");
  return { ...base, flags: { ...base.flags, "notices.workspace": on } };
}

function frame(
  state: string,
  options: { persona?: string; variant?: Not02Variant; on?: boolean; clock?: string } = {},
): Scenario {
  const on = options.on ?? true;
  const variant = options.variant ?? "a";
  const persona = options.persona ?? "kevin-osei";
  return {
    state,
    persona,
    clock: options.clock ?? AT,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who, on)),
        "GET /v1/notices/{notice_id}": ({ persona: who }) =>
          json(not02Notice(variant, who ?? persona)),
        "GET /v1/notices/{notice_id}/analysis": () => json(not02Analysis(variant)),
        "GET /v1/notices/{notice_id}/activity": () => json(not02Activity()),
        "GET /v1/decision-cards/{card_id}": ({ persona: who }) =>
          json(not02Card(variant, who ?? persona)),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b", { variant: "b", clock: AT_B }),
  c: frame("c", { persona: "daniel-reyes", variant: "c", clock: AT_C }),
  d: frame("d"),
  a2: frame("a2"),
  e: frame("e", { variant: "e" }),
  f: frame("f", { variant: "f" }),
  off: frame("off", { on: false }),
});

export type Not02State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Not02State[];
