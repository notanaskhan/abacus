// T-05-T13: the T-05 workbook v1 routes in fixture mode, one snapshot at a time (seed/tax-entity).
// Reads answer the snapshot's shapes; writes answer 501 as the contract stubs do until the live
// rows land (the gallery never persists).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
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
    [`GET ${R}/partners`]: () => json(partners(snapshot)),
    [`GET ${R}/workbook-runs`]: () => json({ items: runs(snapshot) }),
    [`POST ${R}/workbook-runs`]: notYet,
    [`PUT ${R}/ownership`]: notYet,
    [`PUT ${R}/workbook/cells/{address}`]: notYet,
    [`POST ${R}/workbook/imports`]: notYet,
  };
}
