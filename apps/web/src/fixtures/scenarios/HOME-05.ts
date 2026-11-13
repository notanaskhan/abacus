// HOME-05 Home with Today brief: one fixture scenario per artboard a–f (I-02-T12;
// docs/screens/HOME-05.md, States), Mon Sep 14, 2026, 9:24 AM CT. The right region is HOME-01's
// own scenario (the same handlers, string for string); the brief is seed/today.ts's.
//
//   a  daniel-reyes: brief open, "11 items across 4 engagements", 3 · 6 · 2 · 0
//   b  daniel-reyes: the Ridgeline drill-in, HOME-01 Sign-off rows 7 and 8 lit
//   c  daniel-reyes: collapsed, HOME-01 plus "Open Today ›"
//   d  margaret-okonkwo: "4 items across 3 engagements", 2 · 0 · 2 · 0
//   e  daniel-reyes: Building on the first open of the day
//   f  daniel-reyes: flag off (HOME-01, no toggle, no link, `/v1/me/today*` 404), with the
//      `by_engagement` layout override (the Q1 fallback) for the fixture artboard
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { buildingToday, byEngagementToday, margaretToday } from "../seed/today";
import { scenarios as home01 } from "./HOME-01";
import { todayIs } from "./SHL-23";

/** The opening search: the brief open (a, d, e, f), the drill-in (b), collapsed (c: none). */
export const OPENS: Readonly<Record<string, string>> = {
  a: "?today=open",
  b: "?today=open&ov=today:work-item",
  d: "?today=open",
  e: "?today=open",
  f: "?today=open",
};

const NOT_FOUND = (): Response => json({ code: "not_found" }, 404);

/** HOME-05 f with the flag off: every Today route answers 404, as the API does. */
const TODAY_OFF: Record<string, FixtureHandler> = {
  "GET /v1/me/today": NOT_FOUND,
  "POST /v1/me/today/builds": NOT_FOUND,
  "GET /v1/me/today/work-items/{work_item_id}": NOT_FOUND,
  "GET /v1/me/today/history": NOT_FOUND,
};

function on(
  base: Scenario,
  state: string,
  handlers: Record<string, FixtureHandler> = {},
): Scenario {
  return { ...base, state, handlers: { ...base.handlers, ...handlers } };
}

export const scenarios = defineScenarios({
  a: on(home01.a, "a"),
  b: on(home01.a, "b"),
  c: on(home01.a, "c"),
  d: on(home01.b, "d", todayIs(margaretToday)),
  e: on(home01.a, "e", todayIs(buildingToday)),
  f: on(home01["today-brief-off"], "f", TODAY_OFF),
  // The Q1 fallback's artboard: one card per engagement briefing, with the brief on.
  "f-layout": on(home01.a, "f-layout", todayIs(byEngagementToday)),
});
