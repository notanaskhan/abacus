// ENG-04 a–c (N-02-T34): the Ridgeline letter composer in fixture mode, one scenario per artboard,
// seen by Daniel Reyes at Mon Sep 14, 2026, 8:35 AM CT with `engagements.letter_composer` on. The
// data is fixtures/seed/letters.ts; the handlers keep the letter as state (fixtures/handlers).
import type { CapabilitiesOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { letterHandlers } from "../handlers/letters";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  ENG04_CLOCK,
  ENG04_PERSONA,
  type Eng04Frame,
  RIDGELINE_ENGAGEMENT,
  RIDGELINE_LETTERS,
} from "../seed/letters";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? ENG04_PERSONA);
  return { ...base, flags: { ...base.flags, "engagements.letter_composer": true } };
}

function at(state: Eng04Frame): Scenario {
  return {
    state,
    persona: ENG04_PERSONA,
    clock: ENG04_CLOCK,
    handlers: {
      ...E0.handlers,
      "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
      ...letterHandlers(RIDGELINE_LETTERS[state]),
    },
  };
}

export const scenarios = defineScenarios({ a: at("a"), b: at("b"), c: at("c") });

export type Eng04State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Eng04State[];

/** Every frame opens Ridgeline's cost segregation & §754 analysis engagement. */
export const OPENS = RIDGELINE_ENGAGEMENT;

/** A fresh copy of a scenario: the handlers keep the letter as state, so a test starts over. */
export function freshScenario(state: Eng04State): Scenario {
  return at(state);
}
