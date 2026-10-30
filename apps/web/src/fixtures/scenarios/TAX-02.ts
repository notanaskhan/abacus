// TAX-02 · Return › Overview a–f (T-02-T14): T-02-T08's scenarios (tax-returns.ts), here for the
// screen's own entry; src/screens/TAX-02/scenarios.ts re-exports them.
import { type FixtureHandler, type Scenario, json } from "../../app-core/fixture-mode";
import { scenariosOf } from "../handlers/review";
import { IMPORT_ARTBOARDS } from "../seed/review";
import { TAX_RETURNS } from "../seed/tax";
import { tax02 } from "./tax-returns";

export { tax02 as scenarios };

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

/**
 * P-04-T47: the j06 coordination step in fixture mode. Samuel Ito on the Feld 2025 Form 1040 (a's
 * return): the CCH Axcess import of 2025I:FeldJ:V3 is Checkpoint 7, pending, and the sync chip
 * reads "Import pending approval"; once he approves it on SHL-16 the history and the chip move to
 * "Out of sync". Stateful, so each call is a fresh walk (a page load, a test).
 */
export function j06Scenario(): Scenario {
  const base = tax02.a;
  const review = scenariosOf(IMPORT_ARTBOARDS);
  const pending = review.ia?.handlers ?? {};
  const done = review.ib?.handlers ?? {};
  let approved = false;
  const from =
    (key: string): FixtureHandler =>
    (request) => {
      const handler = (approved ? done : pending)[key];
      return handler === undefined ? json({ detail: "not_found" }, 404) : handler(request);
    };
  const record = base.handlers["GET /v1/tax-returns/{return_id}"];
  const approve = pending["POST /v1/checkpoints/{checkpoint_id}/approve"];
  return {
    ...base,
    state: "j06",
    handlers: {
      ...base.handlers,
      "GET /v1/checkpoints": from("GET /v1/checkpoints"),
      "GET /v1/checkpoints/{checkpoint_id}": from("GET /v1/checkpoints/{checkpoint_id}"),
      "POST /v1/checkpoints/{checkpoint_id}/approve": async (request) => {
        if (approve === undefined) return json({ detail: "not_found" }, 404);
        approved = true;
        const body = (await (await approve(request)).json()) as Record<string, unknown>;
        // The decision names the record it moved: the return the walk opened.
        return json({ ...body, target_id: OPENS.a });
      },
      "GET /v1/tax-returns/{return_id}": async (request) => {
        if (record === undefined) return json({ detail: "not_found" }, 404);
        const body = (await (await record(request)).json()) as { row: Record<string, unknown> };
        return json({
          ...body,
          row: { ...body.row, sync: approved ? "out_of_sync" : "import_pending_approval" },
        });
      },
    },
  };
}
