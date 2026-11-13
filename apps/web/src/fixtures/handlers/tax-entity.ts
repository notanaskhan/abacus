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
import { CITATIONS, sheetCells } from "../seed/tax-entity-sheets";

const notYet = () => json({ detail: "not_implemented" }, 501);
const R = "/v1/tax-returns/{return_id}";

export function taxEntityHandlers(
  snapshot: Snapshot,
  options: { proposed?: boolean } = {},
): Record<string, FixtureHandler> {
  return {
    [`GET ${R}/workbook/sheets/{sheet}`]: (req) =>
      json(sheetCells(snapshot, req.params.sheet ?? "05", options.proposed === true)),
    // T-05-T38 rest (DEC-4630): the workbook's versions (Run 1 and Run 2 finished) and the
    // cells' citations.
    [`GET ${R}/workbook`]: (req) =>
      json({
        return_id: req.params.return_id ?? "",
        version: snapshot === "run1" ? 1 : 2,
        sheets: [],
        allowed_actions: ["workbook.edit"],
        versions: [
          ...(snapshot === "run1"
            ? []
            : [{ version: 2, run_no: 2, finished_at: "2026-09-14T14:20:00Z" }]),
          { version: 1, run_no: 1, finished_at: "2026-09-08T15:10:00Z" },
        ],
      }),
    "GET /v1/citations/{citation_id}": (req) => {
      const found = CITATIONS.find((c) => c.id === req.params.citation_id);
      return found === undefined ? json({ detail: "not_found" }, 404) : json(found);
    },
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
