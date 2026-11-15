// CLS-01 Closes index: one fixture scenario per artboard (C-01-T33; C-01 §5.3; docs/screens/
// CLS-01.md). All stand at E0, Mon Sep 14, 2026, 9:24 AM CT, seen by Priya Raman (Partner,
// reviewer on closes). Data: the Copperleaf figure book (seed/close-book.ts, C-01-T13) through
// fixtures/handlers/closes.ts (`GET /v1/closes` filters by status, past due, attest and q).
//
//   a  August 2026: 22 closes, tiles 3 · 11 · 5 · 3, "22 closes · 51 open issues · 2 past due ·
//      3 running"; the running pill "Running closing agent · 3 closes"
//   b  the In progress tile: 11 rows, "Showing 11 of 22"
//   c  Status │ Past due: Copperleaf (4 days) and Bluebird Bakery (2 days)
//   d  Attest │ Attest clients: "No attest clients this period"
//   e  `GET /v1/closes` never answers: skeleton tiles and 8 skeleton rows
//   f  row hover on C11 (Bluebird Bakery) with its "···" menu (an interact script)
//
// They live under fixtures/ (dev and test only); src/screens/CLS-01/scenarios.ts re-exports them.

import {
  type Scenario,
  defineScenarios,
  json,
  never,
  type FixtureHandler,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function at(state: string, handlers: Record<string, FixtureHandler> = {}): Scenario {
  return {
    state,
    persona: "priya-raman",
    clock: DEMO_INSTANT,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), persona ?? "priya-raman");
          return json({
            ...base,
            capabilities: [...base.capabilities, "close.read", "close_run.start"],
            flags: { ...base.flags, "closes.engine": true },
          });
        },
        ...handlers,
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e", { "GET /v1/closes": () => never() }),
  f: at("f"),
});

export type Cls01State = keyof typeof scenarios;
