// SHL-23 Today brief panel: one fixture scenario per artboard (I-02-T12; docs/screens/SHL-23.md,
// States). Data: seed/today.ts (I-02-T03) through handlers/today.ts, over the E0 seed.
//
//   full  daniel-reyes, HOME-01 with Today as the left drawer (`?ov=today`), Mon Sep 14 9:24 AM CT
//   1     daniel-reyes: 3 · 6 · 2 · 0 (= HOME-01's 11), Needs you first §754, Capital Accounts,
//         Final approval; High risk 1, Late 0, Due tomorrow 9, Ready for sign-off 4
//   2     daniel-reyes: the Ridgeline K-1 release drill-in
//   3     daniel-reyes at 9:26 AM: the follow-up question accepted (three citation chips)
//   4     margaret-okonkwo: 2 · 0 · 2 · 0
//   5     margaret-okonkwo on Tue Dec 1, 8:30 AM CST: "Late · 1" (the Late provider is a fixture
//         override until A-09 registers `component_deliverable.late`)
//   6     felix-andersen: the quiet day (no gate waits on IT / Security in E0)
//   7     daniel-reyes: Building, skeleton rows
//
// Model prose appears only on why lines and summaries, as the FakeModel briefing's verified
// AgentBlocks (agents.briefing.today.fake_briefing on the backend); counts and rows are code's.
import type { TodayVm } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import {
  TODAY_CLOCK,
  TODAY_DEC1_CLOCK,
  buildingToday,
  danielToday,
  margaretDec1,
  margaretToday,
  quietToday,
} from "../seed/today";

const E0 = seedScenario();

/** SHL-23 3 stands two minutes after the brief opened. */
export const TODAY_QUESTION_CLOCK = "2026-09-14T09:26:00-05:00";

/** The quiet day's viewer: Felix Andersen, whose queue is empty in E0. */
export function felixQuiet(): TodayVm {
  return { ...quietToday(), first_name: "Felix" };
}

/** The opening search each state's panel needs: the drawer, and for 2 the drill-in. */
export const OPENS: Readonly<Record<string, string>> = {
  full: "?ov=today",
  "2": "?ov=today:work-item",
};

/** A Today override: `GET /v1/me/today` answers `vm()` (the Late provider, the layout, …). */
export function todayIs(vm: () => TodayVm): Record<string, FixtureHandler> {
  return { "GET /v1/me/today": () => json(vm()) };
}

function at(
  state: string,
  persona: string,
  options: { clock?: string; handlers?: Record<string, FixtureHandler> } = {},
): Scenario {
  return {
    state,
    persona,
    clock: options.clock ?? TODAY_CLOCK,
    handlers: { ...E0.handlers, ...options.handlers },
  };
}

export const scenarios = defineScenarios({
  full: at("full", "daniel-reyes"),
  "1": at("1", "daniel-reyes", { handlers: todayIs(danielToday) }),
  "2": at("2", "daniel-reyes"),
  "3": at("3", "daniel-reyes", { clock: TODAY_QUESTION_CLOCK }),
  "4": at("4", "margaret-okonkwo", { handlers: todayIs(margaretToday) }),
  "5": at("5", "margaret-okonkwo", {
    clock: TODAY_DEC1_CLOCK,
    handlers: todayIs(margaretDec1),
  }),
  "6": at("6", "felix-andersen", { handlers: todayIs(felixQuiet) }),
  "7": at("7", "daniel-reyes", { handlers: todayIs(buildingToday) }),
});
