// SHL-07 Citation popover: one fixture scenario per artboard (P-03-T07; handoff SHL-07 README),
// all as Hannah Leclerc at Mon Sep 14, 2026, 9:41 AM CT on the Northwind Service Organizations
// workpaper (AUD-04), its Keystone Retirement Services cell cited:
//
//   a  single citation: BH-EBP-110 step 4, pinned; footer "1 citation"
//   b  multi-source stack: the step, the Keystone SOC 1 Type 2 report (Section I, p. 3, with its
//      page thumb) and the Northwind SPD 2025 (p. 14); "‹ 1 / 3 ›", "3 citations"
//   c  methodology guidance: AUD-05 Risk Assessment, 420 wide, no doc icon and no footer
//   d  hover preview at 95% opacity, not pinned (`interact: hover`)
//   e  broken: the step was cited on EBP v2, superseded by EBP v3 on Jan 1, 2026; Re-link…
//
// The data is fixtures/seed/trust.ts; the routes are the C4 reads (fixtures/handlers/trust.ts).

import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { CLOCK_POPOVER, DOCUMENTS, type SeededCitation, SHL07 } from "../seed/trust";

export {
  KEYSTONE_CELL,
  RISK_GUIDANCE_REF,
  RISK_WORKPAPER,
  SERVICE_ORGANIZATIONS,
  SERVICE_ORGS_SECTION,
  SERVICE_ORGS_WORKPAPER,
} from "../seed/trust";

const E0 = seedScenario();

export type Shl07State = "a" | "b" | "c" | "d" | "e";

/** What each artboard shows: the popover variant, whether it opens pinned or on hover. */
export const OPENS: Record<
  Shl07State,
  { variant: "citation" | "guidance"; interact: "pin" | "hover" }
> = {
  a: { variant: "citation", interact: "pin" },
  b: { variant: "citation", interact: "pin" },
  c: { variant: "guidance", interact: "pin" },
  d: { variant: "citation", interact: "hover" },
  e: { variant: "citation", interact: "pin" },
};

function scenario(state: Shl07State, citations: readonly SeededCitation[]): Scenario {
  return {
    state,
    persona: "hannah-leclerc",
    clock: CLOCK_POPOVER,
    handlers: { ...E0.handlers, ...trustHandlers({ citations, documents: DOCUMENTS }) },
  };
}

export const scenarios = defineScenarios({
  a: scenario("a", SHL07.single),
  b: scenario("b", SHL07.stack),
  c: scenario("c", SHL07.guidance),
  d: scenario("d", SHL07.single),
  e: scenario("e", SHL07.moved),
});
