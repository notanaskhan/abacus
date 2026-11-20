// TXP-09 fixture scenarios (T-06-T23, DEC-5636; docs/screens/TXP-09.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// Ridgeline states read the entity workbook snapshot that seed stands on (T-05 handlers) and the
// T-06-T32 states seed (`seed/tax-depth-states.ts`) in its artboard's variant.
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { taxDepthHandlers } from "../handlers/tax-depth";
import type { Snapshot } from "../seed/tax-entity";
import type { StatesVariant } from "../seed/tax-depth-states";

function at(
  state: string,
  persona: string,
  clock: string,
  snapshot: Snapshot,
  variant: StatesVariant = "e0",
): Scenario {
  return { state, persona, clock, handlers: taxDepthHandlers(snapshot, { states: variant }) };
}

export const scenarios = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Apportionment & PTET (46.0 / 31.5 / 22.5) · `ridgeline-e0`
  b: at("b", "samuel-ito", "2026-09-14T09:24:00-05:00", "run1", "missingFactor"), // Missing factor data (CO Map…) · `ridgeline-run1`
  c: at("c", "samuel-ito", "2026-09-14T09:24:00-05:00", "run1", "paymentGap"), // Payment gap (NY Not paid; Paid 2 of 3) · `ridgeline-run1`
  d: at("d", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Nexus · `ridgeline-e0`
  e: at("e", "samuel-ito", "2026-09-14T09:51:00-05:00", "afterFix", "approved"), // Approved (Approved · SI · Sep 14) · `ridgeline-m2-accepted`
});

export type Txp09State = keyof typeof scenarios;

/** The search each artboard opens on: d is the Nexus view. */
export const TXP09_OPENS: Readonly<Record<string, string>> = { d: "?view=nexus" };
