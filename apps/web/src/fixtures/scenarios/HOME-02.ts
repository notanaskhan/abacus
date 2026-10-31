// HOME-02 Approvals: one fixture scenario per artboard a–g (I-01-T15; HOME-02 handoff, Mon Sep 14,
// 2026, 9:31 AM CT), plus the queue's Show done, snoozed, reassigned and overdue conditions for
// Daniel Reyes and Samuel Ito. Rows are seed/home.ts's through handlers/human-gates.ts (the one
// count source), enriched with the facts the owner's resolver adds for the detail (I-01-T17); the
// per-class details (the §754 card, the section sign-offs, Samuel's agent outputs) are
// seed/approvals-detail.ts's through handlers/approvals.ts.
//
//   a  Decision 1 selected   b  decision decided   c  sign-off blocked   d  sign-off ready
//   e  bulk select           f  empty              g  manager (Samuel Ito)
import type { HumanGateOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { approvalsDetailHandlers } from "../handlers/approvals";
import { humanGateHandlers } from "../handlers/human-gates";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { APPROVALS_CLOCK } from "../seed/approvals";
import { DECIDED_AT, withDetailFacts } from "../seed/approvals-detail";
import { HOME_TODAY, homeGates } from "../seed/home";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** The persona's rows with the detail's facts (I-01-T17). */
const detailed = (p: string): HumanGateOut[] => withDetailFacts(p, homeGates(p));

interface At {
  rows?: (p: string) => HumanGateOut[];
  done?: (p: string) => HumanGateOut[];
  clock?: string;
  decided?: boolean;
}

function at(state: string, persona: string, options: At = {}): Scenario {
  return {
    state,
    persona,
    clock: options.clock ?? APPROVALS_CLOCK,
    handlers: {
      ...E0.handlers,
      ...humanGateHandlers(seed, {
        rows: options.rows ?? detailed,
        today: HOME_TODAY,
        ...(options.done === undefined ? {} : { done: options.done }),
      }),
      ...approvalsDetailHandlers({ decided: options.decided === true }),
      // I-01-T16 creates `home.approvals`; every artboard runs with it on.
      "GET /v1/me/capabilities": ({ persona: who }) => {
        const base = capabilitiesFor(seed, who ?? persona);
        return json({ ...base, flags: { ...base.flags, "home.approvals": true } });
      },
    },
  };
}

/** The queue with nothing waiting (f). */
const none = (): HumanGateOut[] => [];
/** Overdue: every gate due yesterday. */
const overdue = (p: string): HumanGateOut[] =>
  detailed(p).map((g) => ({ ...g, due_on: "2026-09-13" }));

/** b: the §754 gate is done; Basis loses its block ("Ready to sign · difference explained"). */
const afterDecision = (p: string): HumanGateOut[] =>
  detailed(p)
    .filter((_, i) => i !== 0)
    .map((g, i) =>
      i === 4
        ? {
            ...g,
            blocked: false,
            blocked_reason_code: null,
            bulk_eligible: true,
            context: "Ready to sign · difference explained",
          }
        : g,
    );
const decidedGate = (p: string): HumanGateOut[] =>
  detailed(p)
    .slice(0, 1)
    .map((g) => ({ ...g, state: "done" as const, created_at: DECIDED_AT }));

/** Every state, built afresh: Decide on a writes into its handlers, so a test takes its own copy
 * (`freshScenarios()`) and the gallery keeps the one below. */
export const freshScenarios = () =>
  defineScenarios({
    a: at("a", "daniel-reyes"),
    b: at("b", "daniel-reyes", {
      rows: afterDecision,
      done: decidedGate,
      clock: "2026-09-14T09:36:00-05:00",
      decided: true,
    }),
    c: at("c", "daniel-reyes"),
    d: at("d", "daniel-reyes"),
    e: at("e", "daniel-reyes"),
    f: at("f", "daniel-reyes", { rows: none }),
    g: at("g", "samuel-ito"),
    show_done: at("show_done", "daniel-reyes", { done: decidedGate, decided: true }),
    snoozed: at("snoozed", "daniel-reyes"),
    reassigned: at("reassigned", "samuel-ito"),
    overdue: at("overdue", "daniel-reyes", { rows: overdue }),
  });

export const scenarios = freshScenarios();

export type Home02State = keyof typeof scenarios;

/** The row each artboard selects (`?gate=`), by its n in the persona's queue: b the decided
 * §754 card (from Show done), c Capital Accounts, d the memo, g the Feld classification. */
export const SELECTED: Readonly<Partial<Record<Home02State, { persona: string; n: number }>>> = {
  b: { persona: "daniel-reyes", n: 1 },
  c: { persona: "daniel-reyes", n: 7 },
  d: { persona: "daniel-reyes", n: 4 },
  g: { persona: "samuel-ito", n: 6 },
};

/** The `?gate=` an artboard opens with, or null for the queue's first row. */
export function selectedGate(state: Home02State): string | null {
  const at = SELECTED[state];
  return at === undefined ? null : (homeGates(at.persona)[at.n - 1]?.id ?? null);
}
