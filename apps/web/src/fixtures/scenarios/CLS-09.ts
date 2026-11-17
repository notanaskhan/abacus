// CLS-09 Close plan editor's fixture scenarios (C-01-T36; handoff CLS-09): Copperleaf at E0, Mon
// Sep 14, 2026, 9:24 AM CT. a Published v3 (Priya Raman), a2 the first row's hover card, a3 its
// O2 drawer, b Raj Malhotra's draft v4 (Business Savings → Bank feed, 7 requests, "Request
// publish…"), b2 Priya publishing v4 (the confirm), c the Close Planner drafting v1 on Mar 5
// (15 of 21, outlined ticks), d no plan yet (the four templates), e Requests, f History. Data:
// seed/close-book.ts through handlers/closes.ts; `INITIAL` holds each state's open surfaces.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { copperleafPlanDraftV1, copperleafPlanDraftV4 } from "../seed/close-book";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function at(
  state: string,
  persona: string,
  handlers: Record<string, FixtureHandler> = {},
): Scenario {
  return {
    state,
    persona,
    clock: DEMO_INSTANT,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          return json({ ...base, flags: { ...base.flags, "closes.engine": true } });
        },
        ...handlers,
      };
    },
  };
}

const PR = "priya-raman";
const RM = "raj-malhotra";

export const scenarios = defineScenarios({
  a: at("a", PR),
  a2: at("a2", PR),
  a3: at("a3", PR),
  b: at("b", RM, {
    "GET /v1/clients/{client_id}/close-plan": () => json(copperleafPlanDraftV4("RM")),
  }),
  b2: at("b2", PR, {
    "GET /v1/clients/{client_id}/close-plan": () => json(copperleafPlanDraftV4("PR")),
  }),
  c: at("c", PR, {
    "GET /v1/clients/{client_id}/close-plan": () => json(copperleafPlanDraftV1()),
  }),
  d: at("d", PR, {
    "GET /v1/clients/{client_id}/close-plan": () => json({ detail: "not_found" }, 404),
  }),
  e: at("e", PR),
  f: at("f", PR),
});

export type PlanState = keyof typeof scenarios;

/** Each state's open surfaces, as CLS-09's `initial` prop takes them. */
export interface PlanInitial {
  tab?: "plan" | "requests" | "history";
  hover?: number;
  drawer?: number;
  publishOpen?: boolean;
  drafting?: { done: number; total: number; requestedBy: string; at: string };
}

export const INITIAL: Record<PlanState, PlanInitial> = {
  a: {},
  a2: { hover: 0 },
  a3: { drawer: 0 },
  b: {},
  b2: { publishOpen: true },
  c: {
    drafting: {
      done: 15,
      total: 21,
      requestedBy: "Raj Malhotra",
      at: "2026-03-05T10:00:00-06:00",
    },
  },
  d: {},
  e: { tab: "requests" },
  f: { tab: "history" },
};
