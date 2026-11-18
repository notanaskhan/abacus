// TXP-03 fixture scenarios (T-06-T23, DEC-5636; docs/screens/TXP-03.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// Ridgeline states read the entity workbook snapshot that seed stands on (T-05 handlers).
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "../handlers/tax-entity";
import type { Snapshot } from "../seed/tax-entity";

function at(state: string, persona: string, clock: string, snapshot: Snapshot): Scenario {
  return { state, persona, clock, handlers: taxEntityHandlers(snapshot) };
}

export const scenarios = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Register (roof flag; Larimer bonus Check) · `ridgeline-e0`
  a2: at("a2", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Asset detail drawer (O2) · `ridgeline-e0`
  b: at("b", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // By property (land 3,600,000; 733,500 to 8825) · `ridgeline-e0`
  c: at("c", "samuel-ito", "2026-09-14T10:12:00-05:00", "run2"), // Bonus check resolved (contract Feb 3, 2025) · `ridgeline-bonus-resolved`
  d: at("d", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Dispositions (EmptyState, §1245/§1250) · `ridgeline-e0`
  e: at("e", "samuel-ito", "2026-09-14T10:30:00-05:00", "run2"), // Signed off (✓ SI) · `ridgeline-signed-off`
});

export type Txp03State = keyof typeof scenarios;
