// TXP-08 fixture scenarios (T-06-T23, DEC-5636; T-06-T31, TASK-8753; docs/screens/TXP-08.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// Ridgeline states read the entity workbook snapshot that seed stands on (T-05 handlers).
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { taxDepthHandlers } from "../handlers/tax-depth";
import type { Snapshot } from "../seed/tax-entity";

function at(state: string, persona: string, clock: string, snapshot: Snapshot): Scenario {
  return { state, persona, clock, handlers: taxDepthHandlers(snapshot) };
}

export const scenarios = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // All partners (4 of 5 reconcile) · `ridgeline-e0`
  b: at("b", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Partner = Jonah Feld (4,676,125) · `ridgeline-e0`
  c: at("c", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Partner = Pell Street II LLC (885,225 vs 913,820) · `ridgeline-e0`
  d: at("d", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // §754 DecisionCard inline · `ridgeline-e0`
  e: at("e", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // §752 shares · `ridgeline-e0`
});

export type Txp08State = keyof typeof scenarios;

/** The search each artboard opens on: the partner, the inline §754 card and the §752 view. */
export const TXP08_OPENS: Readonly<Record<string, string>> = {
  b: "?partner=_feldId_",
  c: "?partner=_pellIIId_",
  d: "?card=754",
  e: "?view=s752",
};
