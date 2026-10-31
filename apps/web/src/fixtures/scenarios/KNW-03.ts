// KNW-03 Program editor: K-01-T13's scenarios (K-01 §3.4; handoff KNW-03 a, b, e). Margaret Okonkwo
// on Mon Sep 14, 2026, 2:30 PM CT, `methodology.programs` on, BH Audit Methodology · EBP v3
// published:
//
//   a  arrived from an AUD-04 citation: `?step=4&from=citation`, step 4 lit
//   b  a with the SHL-07 popover open on step 4
//   e  the Change log segment: v2 → v3 for BH-EBP-110 (7, 9, 10 changed; 15 new)
//
// K-01-T15 adds c (Hannah Leclerc editing her draft v4), d (BH-EBP-110 tailored on the Northwind
// engagement, A-04's tailoring in fixture mode) and f (Fix in Knowledge from the 9:58 AM Internal
// Control run: BH-EBP-140, step 8 lit, the run's error quoted).
import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
import { DRAFT_110, knw03Handlers } from "../handlers/knw03";
import { programId } from "../handlers/methodology-versions";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { KNW03_CLOCK, KNW03_RUN_ID } from "../seed/knw03";
import { stableId } from "../seed/prng";

/** d: the Northwind PY2025 EBP audit the tailoring belongs to (A-04 writes it). */
export const NORTHWIND_ENGAGEMENT =
  getSeed().engagementIds.A1 ?? stableId("engagement:northwind:py2025");
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

function at(state: string, persona = "margaret-okonkwo") {
  return {
    state,
    persona,
    clock: KNW03_CLOCK,
    handlers: {
      ...E0.handlers,
      ...knw03Handlers(),
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c", "hannah-leclerc"),
  d: at("d"),
  e: at("e"),
  f: at("f", "hannah-leclerc"),
});

export type Knw03State = keyof typeof scenarios;

export type Knw03Segment = "steps" | "guidance" | "pbc" | "rules" | "changes";

/** The program, the search and what each artboard opens with. */
export const OPENS: Readonly<
  Record<
    Knw03State,
    {
      programId: string;
      segment: Knw03Segment;
      step?: number;
      from?: "citation" | "run";
      popover?: true;
      /** f: the failed run the arrival quotes. */
      run?: string;
      /** d: the engagement the program is tailored on. */
      tailoredFor?: string;
    }
  >
> = {
  a: { programId: programId("BH-EBP-110"), segment: "steps", step: 4, from: "citation" },
  b: {
    programId: programId("BH-EBP-110"),
    segment: "steps",
    step: 4,
    from: "citation",
    popover: true,
  },
  c: { programId: DRAFT_110, segment: "steps" },
  d: { programId: programId("BH-EBP-110"), segment: "steps", tailoredFor: NORTHWIND_ENGAGEMENT },
  e: { programId: programId("BH-EBP-110"), segment: "changes" },
  f: {
    programId: programId("BH-EBP-140"),
    segment: "steps",
    step: 8,
    from: "run",
    run: KNW03_RUN_ID,
  },
};
