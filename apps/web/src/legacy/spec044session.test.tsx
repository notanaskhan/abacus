// SPEC-044 (TASK-109): the agent session shows the plan, a person proceeds, and adopts the
// agent's proposals.
import type { AssessmentOut, FlowOut, ItemOut, ProcedureOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { AgentSession } from "./AgentSession";

const BASE = "/v1/engagements/e1/procedures/p1";
const PLAN = {
  plan: [
    { key: "population", text: "Build the journal entry population" },
    { key: "select", text: "Select entries" },
  ],
  approved_by_name: null,
  approved_at: null,
};
const PROCEDURE = {
  id: "p1",
  definition: "journal_entry_testing",
  definition_version: 1,
  status: "selected",
  parameters: {},
  population: {
    gl_snapshot_id: "g",
    entry_count: 1,
    line_count: 2,
    total_debit: "1",
    total_credit: "1",
    tied: true,
  },
  selection: { id: "s1", item_count: 2, by_rule: {}, seed: 1, created_at: "2026-10-20T00:00:00Z" },
} as ProcedureOut;
const ITEMS = [
  {
    id: "i1",
    position: 0,
    posted_on: "2026-12-30",
    kind: "JE",
    reference: "JE-1",
    counterparty: "",
    accounts: [],
    amount: "1.00",
    descriptions: [],
    rules: [],
    support_requested: true,
  },
  {
    id: "i2",
    position: 1,
    posted_on: "2026-12-31",
    kind: "JE",
    reference: "JE-2",
    counterparty: "",
    accounts: [],
    amount: "2.00",
    descriptions: [],
    rules: [],
    support_requested: true,
  },
] as ItemOut[];
const ASSESSMENTS = [
  {
    selected_item_id: "i1",
    verdict: "explained",
    rationale: "ok",
    citations: [],
    created_at: "2026-10-20T00:00:00Z",
  },
  {
    selected_item_id: "i2",
    verdict: "unclear",
    rationale: "?",
    citations: [],
    created_at: "2026-10-20T00:00:00Z",
  },
] as unknown as AssessmentOut[];
const FLOW = {
  approval: { approved_by: "u-m", name: "Mo", approved_at: "2026-10-20T00:00:00Z", note: null },
  steps: [],
  exceptions: 0,
  needs_input: 2,
  passed: 0,
  rows: [],
} as FlowOut;

function panel(session = PLAN, extra = {}) {
  const api = mockApi({ [`GET ${BASE}/session`]: () => json(session), ...extra });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <AgentSession
          engagementId="e1"
          procedure={PROCEDURE}
          flow={FLOW}
          items={ITEMS}
          assessments={ASSESSMENTS}
          role="staff"
        />
      ),
    },
  ]);
  return api;
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("SPEC-044 the agent session", () => {
  it("shows the plan and lets a person proceed (ac1, ac2)", async () => {
    const { calls } = panel(PLAN, {
      [`POST ${BASE}/session/approve-plan`]: () => json({ ...PLAN, approved_by_name: "Sam" }, 201),
    });
    expect(await screen.findByText("Build the journal entry population")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Proceed with plan" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/session/approve-plan"))).toBe(true);
    });
  });

  it("reports the agent's reading and offers to adopt the clear ones (ac4)", async () => {
    const { calls } = panel(
      { ...PLAN, approved_by_name: "Sam", approved_at: "2026-10-20T00:00:00Z" } as never,
      { [`POST ${BASE}/adopt`]: () => json({ adopted: 1 }, 201) },
    );
    expect(await screen.findByText(/1 explained, 0 not explained, 1 unclear/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Adopt 1 results" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/adopt"))).toBe(true);
    });
  });
});
