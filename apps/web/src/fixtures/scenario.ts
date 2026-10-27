// The Brightwater Hale E0 scenario as fixture mode wants it (F-04-T04's Scenario): the seed's
// handlers, the default persona and the demo instant. A screen's own scenarios start from it and
// override what their artboard changes:
//
//   defineScenarios({ b: { ...e0, state: "b", handlers: { ...e0.handlers, "GET /v1/...": ... } } })

import { type Scenario, defineScenarios } from "../app-core/fixture-mode";
import { DEFAULT_PERSONA, seedHandlers } from "./handlers";
import { clientRecordHandlers } from "./handlers/client-record";
import { clientHandlers } from "./handlers/clients";
import { engagementRecordHandlers } from "./handlers/engagement-record";
import { engagementHandlers } from "./handlers/engagements";
import { DEMO_INSTANT, getSeed } from "./seed";

export function seedScenario(): Scenario {
  return defineScenarios({
    e0: {
      state: "e0",
      persona: DEFAULT_PERSONA,
      clock: DEMO_INSTANT,
      // The v2 engagements index first: `/v1/engagements/{engagement_id}` would match "index".
      // The CLI-02 and ENG-02 record reads (P-07-T19, T20) answer behind `clients.v2` and
      // `engagements.v2`, so the app on fixtures opens a record once a journey turns them on.
      handlers: {
        ...engagementHandlers(),
        ...engagementRecordHandlers(getSeed()),
        ...clientRecordHandlers(getSeed()),
        ...seedHandlers(),
        ...clientHandlers(),
      },
    },
  }).e0;
}
