// EBP-06 Investments & certification (A-05-T40; the handoff spec): the fixture scenarios.
//
//   a    ana-cruz        Thu Sep 24, 10:15 AM  prepared, Final layer
//   b    ana-cruz        10:15 AM              Unadjusted: receivable 0.00, net assets 16,812,400
//   c    ana-cruz        Mon Sep 14, 9:24 AM   certification pending: the hold banner
//   d    ana-cruz        10:15 AM              the agent agreeing
//   e    hannah-leclerc  10:15 AM              signed off
//   off  ana-cruz        10:15 AM              `ebp.modules` off: C-20
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
import { type Ebp06Variant, ebp06View } from "../seed/ebp06";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const E = "/v1/audits/{work_item_id}/ebp";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "ana-cruz");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": on } };
}

function frame(
  state: string,
  options: { variant?: Ebp06Variant; persona?: string; clock?: string; on?: boolean } = {},
): Scenario {
  const variant = options.variant ?? "a";
  return {
    state,
    persona: options.persona ?? "ana-cruz",
    clock: options.clock ?? "2026-09-24T10:15:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona }) =>
          json(capabilities(persona, options.on ?? true)),
        [`GET ${E}/investments`]: ({ query }) =>
          json(ebp06View(variant, (query.get("layer") ?? "final") as "final" | "unadjusted")),
        [`PUT ${E}/certification/points/{point_key}`]: () => json({ id: crypto.randomUUID() }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b", { variant: "b" }),
  c: frame("c", { variant: "c", clock: "2026-09-14T09:24:00-05:00" }),
  d: frame("d", { variant: "d" }),
  e: frame("e", { variant: "e", persona: "hannah-leclerc" }),
  off: frame("off", { on: false }),
});

export type Ebp06State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp06State[];
