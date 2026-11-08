// AUD-27 Estimates, related parties & parties in interest (A-05-T57; the handoff spec):
//
//   a    simone-baptiste  Tue Oct 6, 11:20 AM  Estimates (default), inventory reserve pending EP
//   b    simone-baptiste  11:20 AM             Related parties, Peakline a candidate exception
//   c    marcus-delaney   Thu Sep 24, 10:15 AM Northwind EBP: parties in interest and the PT card
//   d    simone-baptiste  11:20 AM             unevaluated: every estimate neutral
//   e    simone-baptiste  11:20 AM             exception raised: Peakline links Finding F-3
//   off  simone-baptiste  11:20 AM             `assurance.estimates_rp` off: C-20
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
import { PARTIES_IN_INTEREST, estimatesView, relatedPartiesView } from "../seed/aud27";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const A = "/v1/audits/{work_item_id}";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "simone-baptiste");
  return {
    ...base,
    flags: { ...base.flags, "audits.cockpit": true, "assurance.estimates_rp": on },
  };
}

function frame(
  state: string,
  options: {
    estimates?: "a" | "d";
    related?: "b" | "e";
    persona?: string;
    clock?: string;
    on?: boolean;
  } = {},
): Scenario {
  return {
    state,
    persona: options.persona ?? "simone-baptiste",
    clock: options.clock ?? "2026-10-06T11:20:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona }) =>
          json(capabilities(persona, options.on ?? true)),
        [`GET ${A}/estimates`]: () => json(estimatesView(options.estimates ?? "a")),
        [`GET ${A}/related-parties`]: () => json(relatedPartiesView(options.related ?? "b")),
        [`GET ${A}/parties-in-interest`]: () => json(PARTIES_IN_INTEREST),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c", { persona: "marcus-delaney", clock: "2026-09-24T10:15:00-05:00" }),
  d: frame("d", { estimates: "d" }),
  e: frame("e", { related: "e" }),
  off: frame("off", { on: false }),
});

export type Aud27State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud27State[];
