// TAX-11 fixture scenarios (T-06-T23, DEC-5636; docs/screens/TAX-11.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// Ridgeline states read the entity workbook snapshot that seed stands on (T-05 handlers).
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "../handlers/tax-entity";
import type { Snapshot } from "../seed/tax-entity";

function at(state: string, persona: string, clock: string, snapshot: Snapshot): Scenario {
  return { state, persona, clock, handlers: taxEntityHandlers(snapshot) };
}

export const scenarios = defineScenarios({
  a: at("a", "daniel-reyes", "2026-09-14T09:24:00-05:00", "run2"), // Page 1 (2 blocking diagnostics + §754 pending) · `ridgeline-e0`
  b: at("b", "daniel-reyes", "2026-09-14T09:24:00-05:00", "run2"), // K-1 · Jonah Feld (Item L 1,550 expected) · `ridgeline-e0`
  c: at("c", "daniel-reyes", "2026-09-14T09:24:00-05:00", "run2"), // Schedule K page · `ridgeline-e0`
  d: at("d", "daniel-reyes", "2026-09-14T09:51:00-05:00", "afterFix"), // Diagnostics clear (Approve return… enabled) · `ridgeline-m2-accepted`
  e: at("e", "daniel-reyes", "2026-09-14T09:24:00-05:00", "run2"), // Loading (form-rule skeleton) · `ridgeline-e0`
});

export type Tax11State = keyof typeof scenarios;
