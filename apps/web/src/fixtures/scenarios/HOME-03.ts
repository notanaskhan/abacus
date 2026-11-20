// HOME-03 fixture scenarios (T-08-T16, TASK-8842; docs/screens/HOME-03.md): one per artboard, with
// the contract's persona and demo clock, over `seed/home03.ts`.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { type Home03Variant, calendar, ridgelineDetail } from "../seed/home03";

function handlers(variant: Home03Variant): Record<string, FixtureHandler> {
  return {
    "GET /v1/filing-deadlines": (req) => {
      const v = req.query.get("view");
      return json(calendar(variant, v === "week" || v === "list" ? v : "month"));
    },
    "GET /v1/filing-deadlines/{filing_deadline_id}": () => json(ridgelineDetail()),
  };
}

const CLOCK = "2026-09-14T09:24:00-05:00";
function at(state: string, persona: string, variant: Home03Variant): Scenario {
  return { state, persona, clock: CLOCK, handlers: handlers(variant) };
}

export const scenarios = defineScenarios({
  a: at("a", "grace-holloway", "e0"), // Month · `deadlines-e0`
  b: at("b", "grace-holloway", "e0"), // List · `deadlines-e0`
  c: at("c", "grace-holloway", "e0"), // Week · Sep 13–19 · `deadlines-e0`
  d: at("d", "daniel-reyes", "daniel"), // Person · Daniel Reyes · `deadlines-e0-daniel`
  e: at("e", "grace-holloway", "e0"), // Rule popover · `deadlines-e0`
  f: at("f", "grace-holloway", "e0"), // +9 more · Sep 15 · `deadlines-e0`
  x1: at("x1", "grace-holloway", "emptyFilter"), // Composed: empty filter · `deadlines-empty-filter`
  x2: at("x2", "grace-holloway", "postponed"), // Composed: postponed item · `deadlines-postponed`
  x3: { state: "x3", persona: "grace-holloway", clock: CLOCK, handlers: {} }, // C-20 flag off · `deadlines-flag-off`
});

/** The search each artboard opens on. */
export const HOME03_OPENS: Readonly<Record<string, string>> = {
  b: "?view=list",
  c: "?view=week",
  d: "?person=daniel-reyes",
  e: "?rule=ridgeline",
  f: "?more=2026-09-15",
};
