// TAX-02 · Return › Overview a–f (T-02-T14): T-02-T08's scenarios (tax-returns.ts), here for the
// screen's own entry; src/screens/TAX-02/scenarios.ts re-exports them.
import { TAX_RETURNS } from "../seed/tax";

export { tax02 as scenarios } from "./tax-returns";

function returnOf(client: string): string {
  const row = TAX_RETURNS.find((r) => r.client === client && !r.label.endsWith(":2"));
  if (row === undefined) throw new Error(`no TY2025 return for ${client}`);
  return row.id;
}

/** The return each artboard opens (f is a's, loading). */
export const OPENS = {
  a: returnOf("Jonah & Claire Feld"),
  b: returnOf("Rafael Quintero"),
  c: returnOf("Jonah & Claire Feld"),
  d: returnOf("Juliet Okonjo"),
  e: returnOf("Jonah & Claire Feld"),
  f: returnOf("Jonah & Claire Feld"),
} as const;

/** An entity return (the 1065, 1120-S and 1041 variant): Ridgeline's 1065. */
export const ENTITY_RETURN = returnOf("Ridgeline Property Partners, LP");
