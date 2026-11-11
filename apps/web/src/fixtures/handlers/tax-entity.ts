// T-05-T13: the T-05 workbook v1 routes in fixture mode, one snapshot at a time (seed/tax-entity).
// Reads answer the snapshot's shapes; writes answer 501 as the contract stubs do until the live
// rows land (the gallery never persists).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { partners, runs, type Snapshot, trialBalance } from "../seed/tax-entity";

const notYet = () => json({ detail: "not_implemented" }, 501);
const R = "/v1/tax-returns/{return_id}";

export function taxEntityHandlers(snapshot: Snapshot): Record<string, FixtureHandler> {
  return {
    [`GET ${R}/trial-balance`]: (req) => {
      const view = req.query.get("view") === "line";
      return json(trialBalance(snapshot, view ? "line" : "account"));
    },
    [`GET ${R}/partners`]: () => json(partners(snapshot)),
    [`GET ${R}/workbook-runs`]: () => json({ items: runs(snapshot) }),
    [`POST ${R}/workbook-runs`]: notYet,
    [`PUT ${R}/ownership`]: notYet,
    [`PUT ${R}/workbook/cells/{address}`]: notYet,
    [`POST ${R}/workbook/imports`]: notYet,
  };
}
