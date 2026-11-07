// TAX-13 Extensions, estimates & payments (T-03-T11; the handoff spec): the fixture scenarios, Samuel
// Ito at Mon Sep 14, 2026, 9:24 AM CT.
//
//   a   161 extended (79 open + 82 filed) + 2 likely; Ridgeline and Harborview due tomorrow
//   b   TY2026 Q3 installments: Paid 2 · Scheduled 1 · Awaiting 2 = 5 due; Not required 2
//   c   Likely: Lakeshore's Prepare 8868…, Thornbury's Prepare 4768… disabled (G1, G3)
//
//   d   Fri Apr 10, 2026, 9:20 AM: 38 extended, 123 likely; Feld, Shah, Varga on the Extend sheet
//   e   Tue Apr 14, 2026, 4:05 PM: 149 extended; Feld Filed, ack pending; Varga Rejected IND-031-04
//   not-allowed   Kevin Osei on d: no reviewer function, so Submit for approval (T-03-T16)
//
// Dev and test only.

import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import {
  TAX13_SHEET_IDS,
  tax13Estimates,
  tax13FiledForm,
  tax13Extensions,
  tax13SeasonD,
  tax13SeasonE,
} from "../seed/tax13";

const E0 = seedScenario();

function frame(state: string): Scenario {
  return {
    state,
    persona: "samuel-ito",
    clock: "2026-09-14T09:24:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/tax/extensions": ({ query }) => json(tax13Extensions(query.get("segment"))),
        "GET /v1/tax/estimates": () => json(tax13Estimates()),
        "GET /v1/tax/extensions/export.xlsx": () =>
          new Response(new Blob(["PK"]), { status: 200 }),
        "GET /v1/tax/estimates/export.xlsx": () => new Response(new Blob(["PK"]), { status: 200 }),
      };
    },
  };
}

const BATCH = { extensions: [], checks: [] };

function season(state: string, persona: string, clock: string, reviewer: boolean): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/tax/extensions": ({ query }) =>
          json(state === "e" ? tax13SeasonE() : tax13SeasonD(query.getAll("return_id"), reviewer)),
        "GET /v1/tax/extensions/{extension_id}": ({ params }) => {
          const rows = state === "e" ? tax13SeasonE() : tax13SeasonD([], reviewer);
          const row = rows.items.find((r) =>
            r.lines.some((l) => l.extension_id === params.extension_id),
          );
          return row === undefined ? json({ code: "not_found" }, 404) : json(row);
        },
        "PATCH /v1/tax/extensions/{extension_id}": ({ params }) =>
          json(
            (state === "e" ? tax13SeasonE() : tax13SeasonD([], reviewer)).items.find((r) =>
              r.lines.some((l) => l.extension_id === params.extension_id),
            ),
          ),
        "GET /v1/engagements/{engagement_id}/evidence-versions": () => json([tax13FiledForm]),
        "POST /v1/tax/extensions:prepare": ({ body }) =>
          json({
            ...BATCH,
            extensions: tax13SeasonD((body as { return_ids: string[] }).return_ids, reviewer)
              .items,
          }),
        "POST /v1/tax/extensions:submit-for-approval": () => json(BATCH),
        "POST /v1/tax/extensions:approve-and-request": ({ body }) => {
          const ids = (body as { return_ids: string[] }).return_ids;
          return json({
            ...BATCH,
            approved_payment_ids: ids,
            confirmation_request_item_ids: ids,
          });
        },
      };
    },
  };
}

const APR_10 = "2026-04-10T09:20:00-05:00";
export const tax13SheetOverlay = `extend:${TAX13_SHEET_IDS.join(",")}`;

/** T-03-T17: d opens with the sheet up on Feld, Shah and Varga. */
export const TAX13_OPENS: Readonly<Record<string, string>> = {
  d: `?ov=${tax13SheetOverlay}`,
  "not-allowed": `?ov=${tax13SheetOverlay}`,
};

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c"),
  d: season("d", "samuel-ito", APR_10, true),
  e: season("e", "samuel-ito", "2026-04-14T16:05:00-05:00", true),
  "not-allowed": season("not-allowed", "kevin-osei", APR_10, false),
});
export type Tax13State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Tax13State[];
