// TXP-03 fixture scenarios (T-06-T23, DEC-5636; T-06-T29, TASK-8751; docs/screens/TXP-03.md): one
// per artboard, with the contract's persona and demo clock, over the Ridgeline depth seed
// (seed/tax-depth-assets). The register's variant is the server state each artboard stands on;
// the view and the open drawer are the URL's (screen-scenarios `opens`).
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { type DepthOptions, taxDepthHandlers } from "../handlers/tax-depth";
import type { Snapshot } from "../seed/tax-entity";

function at(
  state: string,
  persona: string,
  clock: string,
  snapshot: Snapshot,
  options: DepthOptions = {},
): Scenario {
  return { state, persona, clock, handlers: taxDepthHandlers(snapshot, options) };
}

export const scenarios = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Register (roof flag; Larimer bonus Check) · `ridgeline-e0`
  a2: at("a2", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Asset detail drawer (O2) · `ridgeline-e0`
  b: at("b", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // By property (land 3,600,000; 733,500 to 8825) · `ridgeline-e0`
  c: at("c", "samuel-ito", "2026-09-14T10:12:00-05:00", "run2", { assets: "bonusResolved" }), // Bonus check resolved (contract Feb 3, 2025) · `ridgeline-bonus-resolved`
  d: at("d", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // Dispositions (EmptyState, §1245/§1250) · `ridgeline-e0`
  e: at("e", "samuel-ito", "2026-09-14T10:30:00-05:00", "run2", { assets: "signedOff" }), // Signed off (✓ SI) · `ridgeline-signed-off`
});

export type Txp03State = keyof typeof scenarios;

/** The search each artboard opens on (the view and the drawer are the URL's). */
export const TXP03_OPENS: Readonly<Record<string, string>> = {
  a2: "?asset=_assetId_",
  b: "?view=by_property",
  d: "?view=dispositions",
};
