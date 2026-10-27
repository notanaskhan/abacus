// HOME-01 Home dashboard: one fixture scenario per artboard and state (I-01-T05;
// docs/screens/HOME-01.md, States). E0 is Mon Sep 14, 2026, 9:24 AM CT; h and i stand at 12:40 PM.
// Data: seed/home.ts through handlers/home.ts (`GET /v1/home`) and handlers/human-gates.ts (the
// list and the one count source, computed from the same rows).
//
//   a, a2           daniel-reyes: 11 = 3 + 6 + 2 (a2 scrolls to "Your returns 6")
//   b, c, d, e      margaret-okonkwo 4 = 2 + 2 · samuel-ito 6 = 0 + 4 + 2 · kevin-osei "My work 4" ·
//                   grace-holloway 2 (spec-only role states, DF-06)
//   f               daniel-reyes on a quiet day: the counts read 0
//   g               daniel-reyes while `GET /v1/home` and the counts never answer
//   h, i            hannah-leclerc and marcus-delaney at 12:40 PM (their R2 bands are I-01-T24's)
//   office-denver   daniel-reyes with the Office chip on Denver (TPL-11f's counts)
//   tile-popover    daniel-reyes; the popover over a tile is I-01-T11's (by_office is in the data)
//   today-brief-off daniel-reyes with `today_brief.enabled` off: no "Open Today →"
//   walled          lena-park, walled from Ashford: nothing of Ashford in any count or row
//
// They live under fixtures/ (dev and test only); src/screens/HOME-01/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { homeHandlers } from "../handlers/home";
import { humanGateHandlers } from "../handlers/human-gates";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { HOME_AFTERNOON } from "../seed/home";
import { capabilitiesFor, meV3For, officeIdOf } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

function capabilities(persona: string | undefined, brief: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "daniel-reyes");
  return {
    ...base,
    flags: { ...base.flags, "home.dashboard": true, "today_brief.enabled": brief },
  };
}

function at(
  state: string,
  persona: string,
  options: { clock?: string; brief?: boolean; handlers?: Record<string, FixtureHandler> } = {},
): Scenario {
  const brief = options.brief ?? true;
  return {
    state,
    persona,
    clock: options.clock ?? DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      ...homeHandlers(),
      ...humanGateHandlers(seed),
      "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who, brief)),
      // `/v1/me` v3: the firm's offices name the Office chip's options.
      "GET /v1/me": ({ persona: who }) => json(meV3For(seed, who ?? persona)),
      ...options.handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "daniel-reyes"),
  a2: at("a2", "daniel-reyes"),
  b: at("b", "margaret-okonkwo"),
  c: at("c", "samuel-ito"),
  d: at("d", "kevin-osei"),
  e: at("e", "grace-holloway"),
  f: at("f", "daniel-reyes", { handlers: humanGateHandlers(seed, { rows: () => [] }) }),
  g: at("g", "daniel-reyes", {
    handlers: {
      "GET /v1/home": () => never(),
      "GET /v1/human-gates/counts": () => never(),
      "GET /v1/human-gates": () => never(),
    },
  }),
  h: at("h", "hannah-leclerc", { clock: HOME_AFTERNOON }),
  i: at("i", "marcus-delaney", { clock: HOME_AFTERNOON }),
  "office-denver": at("office-denver", "daniel-reyes"),
  "tile-popover": at("tile-popover", "daniel-reyes"),
  "today-brief-off": at("today-brief-off", "daniel-reyes", { brief: false }),
  walled: at("walled", "lena-park"),
});

/** The office each state opens on (null: all offices): office-denver opens on Denver. */
export const OFFICE: Readonly<Partial<Record<keyof typeof scenarios, string>>> = {
  "office-denver": officeIdOf("Denver"),
};
