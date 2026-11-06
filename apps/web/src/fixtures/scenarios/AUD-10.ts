// AUD-10 Service organizations & SOC 1 (A-04-T37; the handoff spec): the fixture scenarios.
//
//   a    marcus-delaney   Mon Sep 14, 2:30 PM   92-day gap; 2 of 6 CUECs; reliance pending
//   b    marcus-delaney   Tue Sep 22            bridge letter received: the gap outlined
//   c    marcus-delaney   2:30 PM               `?cuec=2` selected
//   d    marcus-delaney   12:24 PM              the `soc1` run drafting: skeletons
//   e    marcus-delaney   2:30 PM               CO 10 with High impact: red-tint row
//   off  marcus-delaney   2:30 PM               `assurance.service_orgs` off: C-20
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
import { type Aud10Variant, aud10Orgs, aud10Report } from "../seed/aud10";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const P = "/v1/engagements/{engagement_id}";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "marcus-delaney");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true, "assurance.service_orgs": on } };
}

function frame(
  state: string,
  options: { variant?: Aud10Variant; clock?: string; on?: boolean } = {},
): Scenario {
  const variant = options.variant ?? "a";
  return {
    state,
    persona: "marcus-delaney",
    clock: options.clock ?? "2026-09-14T14:30:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, options.on ?? true)),
        [`GET ${P}/service-organizations`]: () => json(aud10Orgs(variant)),
        [`GET ${P}/soc-reports/{soc_report_id}`]: () => json(aud10Report(variant)),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b", { variant: "b", clock: "2026-09-22T10:00:00-05:00" }),
  c: frame("c"),
  d: frame("d", { clock: "2026-09-14T12:24:00-05:00" }),
  e: frame("e", { variant: "e" }),
  off: frame("off", { on: false }),
});

export type Aud10State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud10State[];
