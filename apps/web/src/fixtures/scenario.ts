// The Brightwater Hale E0 scenario as fixture mode wants it (F-04-T04's Scenario): the seed's
// handlers, the default persona and the demo instant. A screen's own scenarios start from it and
// override what their artboard changes:
//
//   defineScenarios({ b: { ...e0, state: "b", handlers: { ...e0.handlers, "GET /v1/...": ... } } })

import { type Scenario, defineScenarios } from "../app-core/fixture-mode";
import { DEFAULT_PERSONA, seedHandlers } from "./handlers";
import { clientHandlers } from "./handlers/clients";
import { engagementHandlers } from "./handlers/engagements";
import { DEMO_INSTANT } from "./seed";

export function seedScenario(): Scenario {
  return defineScenarios({
    e0: {
      state: "e0",
      persona: DEFAULT_PERSONA,
      clock: DEMO_INSTANT,
      // The v2 engagements index first: `/v1/engagements/{engagement_id}` would match "index".
      handlers: { ...engagementHandlers(), ...seedHandlers(), ...clientHandlers() },
    },
  }).e0;
}
