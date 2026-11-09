// SHL-13's later frames of run #4127 (P-09-T09; handoff SHL-13 frames 6 and 7), built from the 9:41
// snapshot so every count still foots: 1 + 5 + 1 + 4 + 3 = 14 workpapers.
// Frame 6, 9:58 AM: Internal Control fails on the pack-configuration error (BH-EBP-140 step 8).
// Frame 7, Fri Oct 2, 4:05 PM: the run is complete and "Sign off run" is enabled for a person.
// Frames 1, 2 and 5 (9:20, 9:23 and the Sampling question) and frame 8 (CLS-02 Copperleaf, Run 2)
// are their own runs below (P-09-T09 partials round; DEC-3023).
import type { RunItemOut } from "@abacus/api-client";
import { DEMO_INSTANT } from "./clock";
import { stableId } from "./prng";
import {
  type E0Run,
  HEADER_4127,
  ITEMS_4127_941,
  LEVELS_4127_941,
  RUN_4127,
  RUN_4127_E0,
  sep14,
} from "./agent-runs";

const prose = (text: string): NonNullable<RunItemOut["blocks"]> => ({
  version: 1,
  parts: [{ kind: "p", segments: [{ kind: "text", text }] }],
});

export const RUN_4127_FAILED_ID = stableId("agent-run:northwind-py2025-planning-4127-958");
export const RUN_4127_DONE_ID = stableId("agent-run:northwind-py2025-planning-4127-done");

const failedItems: RunItemOut[] = [
  ...ITEMS_4127_941.filter((i) => i.seq !== 10),
  {
    ...(ITEMS_4127_941.find((i) => i.seq === 10) as RunItemOut),
    seq: 12,
    at: sep14("9:58:00"),
    outcome: "failed",
    blocks: prose(
      "Pack configuration error: BH-EBP-140 step 8 points to a SOC 1 bridge-letter template that EBP v3 does not include. No evidence written.",
    ),
  },
  {
    seq: 13,
    at: sep14("9:58:10"),
    kind: "line",
    session_kind: "line",
    code: "line",
    outcome: null,
    detail: null,
    actor: null,
    ref_type: null,
    ref_id: null,
    blocks: prose(
      "Internal Control stopped on that pack configuration error (BH-EBP-140 step 8, bridge letter and gap-period procedures, new in EBP v3). I'm continuing with the branches it does not affect.",
    ),
  },
];

const RUN_4127_FAILED: E0Run = {
  ...RUN_4127_E0,
  view: {
    ...RUN_4127_E0.view,
    run: { ...RUN_4127, id: RUN_4127_FAILED_ID },
    levels: LEVELS_4127_941.map((lv) => (lv.level === 2 ? { ...lv, waiting: 1, failed: 1 } : lv)),
  },
  items: failedItems,
};

const OCT2 = new Date(Date.UTC(2026, 9, 2, 21, 5, 0)).toISOString(); // 4:05 PM CT

const RUN_4127_DONE: E0Run = {
  ...RUN_4127_E0,
  view: {
    ...RUN_4127_E0.view,
    run: { ...RUN_4127, id: RUN_4127_DONE_ID, state: "succeeded", finished_at: OCT2 },
    allowed_actions: ["agent_run.read", "agent_run.sign_off", "run_trace.export"],
    header: { ...HEADER_4127, blocked_on: null },
    levels: LEVELS_4127_941.map((lv) => ({
      ...lv,
      done: lv.total,
      running: 0,
      blocked: 0,
      waiting: 0,
      queued: 0,
      failed: 0,
    })),
  },
  items: [
    {
      seq: 1,
      at: OCT2,
      kind: "run_card",
      session_kind: "run_card",
      code: "run.complete",
      outcome: "succeeded",
      detail: null,
      actor: null,
      ref_type: null,
      ref_id: null,
      blocks: prose(
        "Run complete · 14 of 14 workpapers drafted · 3 issues raised · 1 decision recorded",
      ),
    },
  ],
};

const item = (
  seq: number,
  at: string,
  kind: NonNullable<RunItemOut["session_kind"]>,
  fields: Partial<RunItemOut>,
): RunItemOut => ({
  seq,
  at,
  kind,
  session_kind: kind,
  code: kind,
  outcome: null,
  detail: null,
  actor: null,
  ref_type: null,
  ref_id: null,
  blocks: null,
  ...fields,
});

export const RUN_4127_IDLE_ID = stableId("agent-run:northwind-py2025-planning-4127-idle");
export const RUN_4127_PLAN_ID = stableId("agent-run:northwind-py2025-planning-4127-plan");
export const RUN_4127_ASK_ID = stableId("agent-run:northwind-py2025-planning-4127-ask");
export const RUN_CLOSE_COPPERLEAF_ID = stableId("agent-run:copperleaf-2026-08-close-run-2");

const QUEUED_LEVELS = LEVELS_4127_941.map((lv) => ({
  ...lv,
  done: 0,
  running: 0,
  blocked: 0,
  waiting: 0,
  queued: lv.total,
  failed: 0,
}));

// Frame 1, 9:20 AM: the engagement agent before its first run; "Run" in the header.
const RUN_4127_IDLE: E0Run = {
  ...RUN_4127_E0,
  view: {
    ...RUN_4127_E0.view,
    run: { ...RUN_4127, id: RUN_4127_IDLE_ID, state: "queued", started_at: sep14("9:20:00") },
    header: { ...HEADER_4127, blocked_on: null },
    levels: QUEUED_LEVELS,
  },
  items: [],
};

// Frame 2, 9:23 AM: the plan is proposed and waits for the person's go-ahead.
const RUN_4127_PLAN: E0Run = {
  ...RUN_4127_E0,
  view: {
    ...RUN_4127_E0.view,
    run: { ...RUN_4127, id: RUN_4127_PLAN_ID, state: "needs_input" },
    header: {
      ...HEADER_4127,
      blocked_on: { kind: "approval", id: null, role: null, user_id: null, needs: [] },
    },
    levels: QUEUED_LEVELS,
  },
  items: [
    item(1, sep14("9:23:00"), "user", { detail: "Run planning for Northwind." }),
    item(2, sep14("9:23:10"), "line", {
      blocks: prose(
        "Here is the run projection. I'll start with the Trial Balance, then Materiality, which needs Margaret Okonkwo's decision. Sampling waits for the census completeness tie.",
      ),
    }),
  ],
};

// Frame 5: the Sampling level asks which population eligibility testing starts from.
const RUN_4127_ASK: E0Run = {
  ...RUN_4127_E0,
  view: {
    ...RUN_4127_E0.view,
    run: { ...RUN_4127, id: RUN_4127_ASK_ID, state: "needs_input" },
    header: {
      ...HEADER_4127,
      blocked_on: { kind: "question", id: null, role: null, user_id: null, needs: [] },
    },
  },
  items: [
    item(1, sep14("9:41:00"), "question", {
      detail: "Which population should eligibility testing start from?",
      blocks: {
        version: 1,
        parts: [
          {
            kind: "options",
            options: [
              {
                key: "paygrid_census",
                title: "PayGrid payroll census (all employees paid in 2025)",
                detail:
                  "Starts from payroll so missed enrollees are found; I'll tie it to the 941s first.",
                recommended: true,
              },
              {
                key: "keystone_participants",
                title: "Keystone participant file (286 with balances)",
                detail: "Faster, but cannot find eligible employees who were never enrolled.",
              },
            ],
          },
        ],
      },
    }),
  ],
};

// Frame 8: CLS-02 Copperleaf's August close, Run 2, for Raj Malhotra: 6 of 9 complete, 3 running,
// started 18 minutes before the demo instant. Square net = gross − fees: 73,166.90 − 1,684.54.
const CLOSE_STARTED = new Date(Date.parse(DEMO_INSTANT) - 18 * 60_000).toISOString();
const CLOSE_TASKS: [string, "succeeded" | "running"][] = [
  ["Import August GL from QuickBooks Online", "succeeded"],
  ["Reconcile Front Range Bank ••4410", "succeeded"],
  ["Reconcile Amex ••1009", "succeeded"],
  ["Tie Square payouts (gross $73,166.90 − fees $1,684.54 = net $71,482.36)", "succeeded"],
  ["Amortize prepaid insurance ($700)", "succeeded"],
  ["Book depreciation ($2,140)", "succeeded"],
  ["Accrue payroll", "running"],
  ["Recognize deferred subscription revenue", "running"],
  ["Flux review August vs July", "running"],
];

const RUN_CLOSE_COPPERLEAF: E0Run = {
  ...RUN_4127_E0,
  view: {
    ...RUN_4127_E0.view,
    run: {
      ...RUN_4127,
      id: RUN_CLOSE_COPPERLEAF_ID,
      agent: "close.month_end",
      agent_label: "Copperleaf Outfitters — August 2026 close",
      started_at: CLOSE_STARTED,
      initiator_name: "Raj Malhotra",
    },
    header: { ...HEADER_4127, run_number: 2, blocked_on: null, runs_as_name: "Raj Malhotra" },
    levels: [
      { level: 1, total: 9, done: 6, running: 3, blocked: 0, waiting: 0, queued: 0, failed: 0 },
    ],
  },
  items: CLOSE_TASKS.map(([detail, outcome], i) =>
    item(i + 1, CLOSE_STARTED, "tool", { code: "close.task", detail, outcome }),
  ),
};

export const SHL13_RUNS: Record<string, E0Run> = {
  [RUN_4127_FAILED_ID]: RUN_4127_FAILED,
  [RUN_4127_DONE_ID]: RUN_4127_DONE,
  [RUN_4127_IDLE_ID]: RUN_4127_IDLE,
  [RUN_4127_PLAN_ID]: RUN_4127_PLAN,
  [RUN_4127_ASK_ID]: RUN_4127_ASK,
  [RUN_CLOSE_COPPERLEAF_ID]: RUN_CLOSE_COPPERLEAF,
};
