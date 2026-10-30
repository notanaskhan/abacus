// KNW-03 Program editor: K-01-T13's scenarios (K-01 §3.4; handoff KNW-03 a, b, e). Margaret Okonkwo
// on Mon Sep 14, 2026, 2:30 PM CT, `methodology.programs` on, BH Audit Methodology · EBP v3
// published:
//
//   a  arrived from an AUD-04 citation: `?step=4&from=citation`, step 4 lit
//   b  a with the SHL-07 popover open on step 4
//   e  the Change log segment: v2 → v3 for BH-EBP-110 (7, 9, 10 changed; 15 new)
import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
import { knw03Handlers } from "../handlers/knw03";
import { programId } from "../handlers/methodology-versions";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { KNW03_CLOCK } from "../seed/knw03";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "margaret-okonkwo");
  return {
    ...base,
    flags: { ...base.flags, "methodology.lifecycle": true, "methodology.programs": true },
  };
}

function at(state: string) {
  return {
    state,
    persona: "margaret-okonkwo",
    clock: KNW03_CLOCK,
    handlers: {
      ...E0.handlers,
      ...knw03Handlers(),
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({ a: at("a"), b: at("b"), e: at("e") });

export type Knw03State = keyof typeof scenarios;

export type Knw03Segment = "steps" | "guidance" | "pbc" | "rules" | "changes";

/** The program, the search and what each artboard opens with. */
export const OPENS: Readonly<
  Record<
    Knw03State,
    { programId: string; segment: Knw03Segment; step?: number; from?: "citation"; popover?: true }
  >
> = {
  a: { programId: programId("BH-EBP-110"), segment: "steps", step: 4, from: "citation" },
  b: { programId: programId("BH-EBP-110"), segment: "steps", step: 4, from: "citation", popover: true },
  e: { programId: programId("BH-EBP-110"), segment: "changes" },
};
