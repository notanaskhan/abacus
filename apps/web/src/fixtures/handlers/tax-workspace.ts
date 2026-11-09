// T-04-T07: RW-1 and WS-1 in fixture mode, one artboard state at a time (seed/tax-workspace.ts).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  FELD_RETURN_ID,
  IDS,
  REVIEW_TREE,
  residency,
  TREATMENTS,
  workspace,
} from "../seed/tax-workspace";

const R = "/v1/tax/returns/{return_id}";

export interface TaxWorkspaceState {
  workspace?: Parameters<typeof workspace>[0];
  residency?: Parameters<typeof residency>[0];
}

export function taxWorkspaceHandlers(
  state: TaxWorkspaceState = {},
): Record<string, FixtureHandler> {
  return {
    [`GET ${R}/workspace`]: () => json(workspace(state.workspace ?? "a")),
    [`GET ${R}/review-tree`]: () =>
      json({
        items: REVIEW_TREE,
        total: 36,
        review_count: workspace(state.workspace ?? "a").review_count,
      }),
    [`GET ${R}/k1-activities`]: () =>
      json({
        items: [
          {
            id: IDS.ridgelineActivity,
            label: "Ridgeline Property Partners, LP",
            status: "draft_pre_release",
            released_on: null,
            treatments: TREATMENTS,
            pending_proposal_id: null,
          },
        ],
      }),
    [`GET ${R}/residency`]: () => json(residency(state.residency ?? "a")),
    // Writes stay out until the build rows (T-04-T15 onward); the routes answer 501 live.
    [`POST ${R}/document-approvals`]: () => json({ detail: "not_implemented" }, 501),
  };
}

export const FELD = FELD_RETURN_ID;
