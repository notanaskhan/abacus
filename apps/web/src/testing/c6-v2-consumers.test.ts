// P-10-T11 (SPEC-647): the frontend half of C6 v2's consumers. These fixtures compile only while
// the generated client still has every field SHL-13, WB-01, WB-03 and WB-09 read.
import type { RunPlanOut, RunQuestionOut, RunV2Out, SessionSnapshotOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";

type Reads<T, K extends keyof T> = Required<Pick<T, K>>;

const running = {
  id: "r1",
  run_number: 4127,
  title: "Plan testing",
  state: "awaiting_plan_approval",
  blocked_on: null,
  session_id: null,
  signed_off_at: null,
  allowed_actions: [],
} satisfies Partial<
  Reads<
    RunV2Out,
    | "id"
    | "run_number"
    | "title"
    | "state"
    | "blocked_on"
    | "session_id"
    | "signed_off_at"
    | "allowed_actions"
  >
>;

const plan = { id: "p1", version: 1, steps: [] } satisfies Partial<
  Reads<RunPlanOut, "id" | "version" | "steps">
>;

const question = { id: "q1", prompt: "Which population?", options: [] } satisfies Partial<
  Reads<RunQuestionOut, "id" | "prompt" | "options">
>;

const session = { id: "s1", title: "Northwind", locked: false, items: [] } satisfies Partial<
  Reads<SessionSnapshotOut, "id" | "title" | "locked" | "items">
>;

describe("C6 v2 consumers (P-10-T11)", () => {
  it("SHL-13 states read the run, the plan and the question", () => {
    expect(running.run_number).toBe(4127);
    expect(plan.steps).toEqual([]);
    expect(question.options).toEqual([]);
  });

  it("WB-01 reads the session's items", () => {
    expect(session.items).toEqual([]);
  });
});
