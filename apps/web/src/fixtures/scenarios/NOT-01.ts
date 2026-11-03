// NOT-01 Notices index: one fixture scenario per artboard (N-04-T05; docs/screens/NOT-01.md), all
// seen by Kevin Osei (Tax Preparer) at E0, Mon Sep 14, 2026, 9:24 AM CT. Data: seed/notices.ts
// through handlers/notices.ts on the notices v1 stub's shapes. Each artboard is a data condition:
//
//   a    nine open notices by deadline risk (N4 red 7 days, N1 amber 9 days)
//   e    the New tile pressed (`?tile=new`): N5 and N9
//   f    no visible notices: "No open notices."
//   g    `GET /v1/notices` never answers: skeleton rows
//   off  `notices.workspace` off: C-20
//
// b, c and d (the intake sheet) are N-04-T09's. Dev and test only; src/screens/NOT-01/scenarios.ts
// re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { noticeHandlers } from "../handlers/notices";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** Mon Sep 14, 2026, 9:24 AM CT (NOT-01 a). */
export const NOT01_INSTANT = "2026-09-14T09:24:00-05:00";
export const NOT01_PERSONA = "kevin-osei";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? NOT01_PERSONA);
  return {
    ...base,
    capabilities: [...base.capabilities, "notice.read", "notice_intake.create"],
    flags: { ...base.flags, "notices.workspace": on },
  };
}

function at(
  state: string,
  handlers: Record<string, FixtureHandler> = {},
  options: { on?: boolean } = {},
): Scenario {
  const on = options.on ?? true;
  return {
    state,
    persona: NOT01_PERSONA,
    clock: NOT01_INSTANT,
    handlers: {
      ...E0.handlers,
      ...noticeHandlers(),
      "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
      ...handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  e: at("e"),
  f: at("f", noticeHandlers([])),
  g: at("g", { "GET /v1/notices": () => never(), "GET /v1/notices/summary": () => never() }),
  off: at("off", {}, { on: false }),
});

export type Not01State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Not01State[];
/** The search each artboard opens on (journeys and the gallery). */
export const OPENS: Readonly<Record<string, string>> = { e: "?tile=new" };
