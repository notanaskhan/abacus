// TAX-01 · Tax Returns practice board a–g (T-02-T12): T-02-T08's scenarios (tax-returns.ts), here
// for the screen's own entry; src/screens/TAX-01/scenarios.ts re-exports them.
import { TAX_RETURNS } from "../seed/tax";

export { tax01 as scenarios } from "./tax-returns";

/** Artboard d's selection: the Feld, Shah and Varga returns (docs/screens/TAX-01.md). */
export const SELECTED_CLIENTS: readonly string[] = [
  "Jonah & Claire Feld",
  "Meera Shah",
  "Elena Varga",
];

export const SELECTED_IDS: readonly string[] = TAX_RETURNS.filter(
  (r) => SELECTED_CLIENTS.includes(r.client) && !r.label.endsWith(":2"),
).map((r) => r.id);
