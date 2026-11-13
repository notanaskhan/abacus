// T-05-T13: the T-05 workbook v1 routes in fixture mode, one snapshot at a time (seed/tax-entity).
// Reads answer the snapshot's shapes; writes answer 501 as the contract stubs do until the live
// rows land (the gallery never persists).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  cellProvenance,
  formLines,
  journalEntries,
  mappingAnswer,
  partners,
  runs,
  type Snapshot,
  type Statement,
  tallies,
  trialBalance,
} from "../seed/tax-entity";
import { sheetCells } from "../seed/tax-entity-sheets";

const notYet = () => json({ detail: "not_implemented" }, 501);
const R = "/v1/tax-returns/{return_id}";

export function taxEntityHandlers(
  snapshot: Snapshot,
  options: { proposed?: boolean } = {},
): Record<string, FixtureHandler> {
  return {
    [`GET ${R}/workbook/sheets/{sheet}`]: (req) =>
      json(sheetCells(snapshot, req.params.sheet ?? "05", options.proposed === true)),
    [`GET ${R}/trial-balance`]: (req) => {
      const view = req.query.get("view") === "line";
      const statement = (req.query.get("statement") ?? "full") as Statement;
      const unmapped = req.query.get("filter") === "unmapped";
      return json(trialBalance(snapshot, view ? "line" : "account", statement, unmapped));
    },
    [`GET ${R}/trial-balance/tallies`]: () => json(tallies(snapshot)),
    // T-05-T37 rest (DEC-4629): the drawer's entries, the picker's lines and a pick's answer,
    // and SHL-09's tray on a sheet 01 cell (a2).
    [`GET ${R}/journal-entries`]: () => json({ items: journalEntries() }),
    [`GET /v1/form-lines`]: (req) => json({ items: formLines(req.query.get("q")) }),
    [`POST ${R}/mappings`]: (req) => {
      const body = req.body as { account_code: string; form_line_key: string };
      return json(mappingAnswer(req.persona, body.account_code, body.form_line_key), 201);
    },
    [`GET /v1/fields/{target_type}/{target_id}/{field_key}/provenance`]: (req) =>
      req.params.target_type === "tax_workbook"
        ? json(cellProvenance(req.params.target_id ?? "", req.params.field_key ?? ""))
        : json({ detail: "not_found" }, 404),
    [`GET ${R}/partners`]: () => json(partners(snapshot)),
    [`GET ${R}/workbook-runs`]: () => json({ items: runs(snapshot) }),
    [`POST ${R}/workbook-runs`]: notYet,
    [`PUT ${R}/ownership`]: notYet,
    [`PUT ${R}/workbook/cells/{address}`]: notYet,
    [`POST ${R}/workbook/imports`]: notYet,
  };
}
