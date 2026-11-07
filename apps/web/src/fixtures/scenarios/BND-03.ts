// BND-03 Questionnaire editor (T-03-T09; the handoff spec): the read states on the Feld 2025 Binder
// (seed/bnd03.ts), Kevin Osei at Mon Sep 14, 2026, 9:24 AM CT:
//
//   a            Payments & refunds selected: Q5 expanded with its follow-ups; the preview dock
//   b            a + Q5 open to edit (T-03-T10): the Required toggle drives the preview marker
//   c            a + a new card with the type picker (T-03-T10)
//   d            template Draft v7: its banner and no answers (T-03-T10)
//   e            Health coverage selected: "No questions in this section."
//   off          no `tax_returns` entitlement: C-20 (DEC-2605)
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
import { type Bnd03Variant, bnd03Editor, bnd03Preview } from "../seed/bnd03";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-14T09:24:00-05:00";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "kevin-osei");
  const entitlements = base.entitlements.filter((m) => m !== "tax_returns");
  return { ...base, entitlements: on ? [...entitlements, "tax_returns"] : entitlements };
}

function frame(state: string, options: { variant?: Bnd03Variant; on?: boolean } = {}): Scenario {
  const on = options.on ?? true;
  const variant = options.variant ?? "a";
  return {
    state,
    persona: "kevin-osei",
    clock: AT,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
        "GET /v1/questionnaires/{questionnaire_id}/editor": () => json(bnd03Editor(variant)),
        "GET /v1/questionnaires/{questionnaire_id}/client-preview": () => json(bnd03Preview()),
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

export type Bnd03State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Bnd03State[];
/** The section each artboard opens on. */
export const SECTION_OF: Record<Bnd03State, string> = {
  a: "payments",
  b: "payments",
  c: "payments",
  d: "payments",
  e: "health",
  off: "payments",
};
