// AUD-17 Review notes & sign-off matrix (A-06-T24; the handoff spec): the fixture scenarios.
//
//   a  margaret-okonkwo  Fri Oct 2, 2:10 PM  RN-13 selected, the matrix with one stale cell
//   b  margaret-okonkwo  2:12 PM             RN-13 cleared: Responded empties
//   c  margaret-okonkwo  2:10 PM             the EP involvement segment
//   d  margaret-okonkwo  2:10 PM             a stale cell's popover
//   e  margaret-okonkwo  2:10 PM             SHL-12 blocked on Contributions (RN-12 open)
//   f  margaret-okonkwo  2:10 PM             no review notes
//
// Dev and test only.

import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  type Aud17Variant,
  aud17Detail,
  aud17Involvement,
  aud17Matrix,
  aud17Notes,
} from "../seed/aud17";

const E0 = seedScenario();
const seed = getSeed();

function frame(state: string, variant: Aud17Variant = "a"): Scenario {
  return {
    state,
    persona: "margaret-okonkwo",
    clock: "2026-10-02T14:10:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/review-notes": () => json(aud17Notes(variant)),
        "GET /v1/review-notes/{note_id}": ({ params }) =>
          json(aud17Detail(String(params.note_id), variant)),
        "POST /v1/review-notes/{note_id}/clear": ({ params }) =>
          json(aud17Detail(String(params.note_id), "b")),
        "POST /v1/review-notes/{note_id}/reopen": ({ params }) =>
          json(aud17Detail(String(params.note_id), "a")),
        "GET /v1/work-items/{work_item_id}/sign-off-matrix": () => json(aud17Matrix()),
        "GET /v1/work-items/{work_item_id}/ep-involvement": () => json(aud17Involvement()),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b", "b"),
  c: frame("c"),
  d: frame("d"),
  e: frame("e"),
  f: frame("f", "f"),
});

export type Aud17State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud17State[];
