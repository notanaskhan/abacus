// HOME-02 Approvals: one fixture scenario per artboard a–g (I-01-T15; HOME-02 handoff, Mon Sep 14,
// 2026, 9:31 AM CT), plus the queue's Show done, snoozed, reassigned and overdue conditions for
// Daniel Reyes and Samuel Ito. Rows are seed/home.ts's through handlers/human-gates.ts (the one
// count source); the per-class details (decision cards, sign-off eligibility, agent output, final
// approval and send) are P-04-T34's C3 fixtures (seed/review.ts) the screen opens.
//
//   a  Decision 1 selected   b  decision decided   c  sign-off blocked   d  sign-off ready
//   e  bulk select           f  empty              g  manager (Samuel Ito)
import type { HumanGateOut } from "@abacus/api-client";
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { humanGateHandlers } from "../handlers/human-gates";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { APPROVALS_CLOCK } from "../seed/approvals";
import { HOME_TODAY, homeGates } from "../seed/home";

const E0 = seedScenario();
const seed = getSeed();

function at(
  state: string,
  persona: string,
  rows: (p: string) => HumanGateOut[] = homeGates,
): Scenario {
  return {
    state,
    persona,
    clock: APPROVALS_CLOCK,
    handlers: { ...E0.handlers, ...humanGateHandlers(seed, { rows, today: HOME_TODAY }) },
  };
}

/** The queue with nothing waiting (f). */
const none = (): HumanGateOut[] => [];
/** Overdue: every gate due yesterday. */
const overdue = (p: string): HumanGateOut[] =>
  homeGates(p).map((g) => ({ ...g, due_on: "2026-09-13" }));

export const scenarios = defineScenarios({
  a: at("a", "daniel-reyes"),
  b: at("b", "daniel-reyes"),
  c: at("c", "daniel-reyes"),
  d: at("d", "daniel-reyes"),
  e: at("e", "daniel-reyes"),
  f: at("f", "daniel-reyes", none),
  g: at("g", "samuel-ito"),
  show_done: at("show_done", "daniel-reyes"),
  snoozed: at("snoozed", "daniel-reyes"),
  reassigned: at("reassigned", "samuel-ito"),
  overdue: at("overdue", "daniel-reyes", overdue),
});

export type Home02State = keyof typeof scenarios;
