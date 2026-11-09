// SHL-13's later frames of run #4127 (P-09-T09; handoff SHL-13 frames 6 and 7), built from the 9:41
// snapshot so every count still foots: 1 + 5 + 1 + 4 + 3 = 14 workpapers.
// Frame 6, 9:58 AM: Internal Control fails on the pack-configuration error (BH-EBP-140 step 8).
// Frame 7, Fri Oct 2, 4:05 PM: the run is complete and "Sign off run" is enabled for a person.
import type { RunItemOut } from "@abacus/api-client";
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

export const SHL13_RUNS: Record<string, E0Run> = {
  [RUN_4127_FAILED_ID]: RUN_4127_FAILED,
  [RUN_4127_DONE_ID]: RUN_4127_DONE,
};
