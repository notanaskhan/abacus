// EBP-07 Form 5500 tie-out (A-05-T58; the handoff spec): the fixture scenarios.
//
//   a    hannah-leclerc  Thu Sep 24, 10:15 AM  consistent with reconciling items (Schedule H)
//   b    hannah-leclerc  10:15 AM              Part IV
//   c    hannah-leclerc  10:15 AM              Schedules (4i and 4a)
//   d    hannah-leclerc  10:15 AM              draft not received: the empty canvas, Remind Summit
//   e    hannah-leclerc  10:15 AM              4a answered "No" on the draft: inconsistent
//   off  hannah-leclerc  10:15 AM              `ebp.modules` off: C-20
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
import { ebp04Schedule } from "../seed/ebp04";
import { ebp06View } from "../seed/ebp06";
import { type Ebp07Variant, ebp07View } from "../seed/ebp07";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const E = "/v1/audits/{work_item_id}/ebp";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": on } };
}

function frame(state: string, options: { variant?: Ebp07Variant; on?: boolean } = {}): Scenario {
  const variant = options.variant ?? "a";
  return {
    state,
    persona: "hannah-leclerc",
    clock: "2026-09-24T10:15:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona }) =>
          json(capabilities(persona, options.on ?? true)),
        [`GET ${E}/form-5500`]: () => json(ebp07View(variant)),
        [`GET ${E}/investments`]: () => json(ebp06View("a")),
        [`GET ${E}/schedule-h-4a`]: () => json(ebp04Schedule("a")),
        [`POST ${E}/form-5500/reconciliation-note`]: () => json({ id: crypto.randomUUID() }, 201),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c"),
  d: frame("d", { variant: "d" }),
  e: frame("e", { variant: "e" }),
  off: frame("off", { on: false }),
});

export type Ebp07State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp07State[];
