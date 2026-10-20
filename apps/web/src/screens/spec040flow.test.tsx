// SPEC-040 (TASK-100): the sample is approved before testing, support goes as one request, and
// each row carries preparer and reviewer slots signed in bulk.
import type { FlowOut, ItemOut, ProcedureOut, WorkpaperOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Fieldwork } from "./Fieldwork";

const E = "e1";
const P = "p1";
const BASE = `/v1/engagements/${E}`;
const PROCEDURE: ProcedureOut = {
  id: P,
  definition: "journal_entry_testing",
  definition_version: 1,
  status: "selected",
  parameters: {},
  population: {
    gl_snapshot_id: "g1",
    entry_count: 10,
    line_count: 20,
    total_debit: "100.00",
    total_credit: "100.00",
    tied: true,
  },
  selection: {
    id: "s1",
    item_count: 1,
    by_rule: { random: 1 },
    seed: 7,
    created_at: "2026-10-19T10:00:00Z",
  },
};
const ITEM: ItemOut = {
  id: "i1",
  position: 0,
  posted_on: "2026-12-30",
  kind: "Journal Entry",
  reference: "TE-YE",
  counterparty: "",
  accounts: ["1000"],
  amount: "100.00",
  descriptions: [],
  rules: ["random"],
  result: "supported",
};
const DRAFT: WorkpaperOut = {
  status: "draft",
  entries: 1,
  with_result: 1,
  exceptions: 0,
  conclusion: "",
  versions: [],
};
const STEPS = [
  { key: "population", label: "Population tied", state: "done" },
  { key: "selected", label: "Selected", state: "done" },
  { key: "approved", label: "Approved", state: "current" },
] as const;

function flow(over: Partial<FlowOut> = {}): FlowOut {
  return {
    approval: null,
    steps: [...STEPS],
    exceptions: 0,
    needs_input: 0,
    passed: 1,
    rows: [{ item_id: "i1", prepared: null, reviewed: null }],
    ...over,
  };
}

function tab(role: string, current: FlowOut, extra = {}) {
  const api = mockApi({
    "GET /v1/me": () =>
      json({ user_id: "u-1", display_name: "Pat", memberships: [], active_tenant_id: "t1" }),
    [`GET ${BASE}/team`]: () => json([{ user_id: "u-1", display_name: "Pat", role }]),
    [`GET ${BASE}/materiality`]: () => json(null),
    [`GET ${BASE}/procedures`]: () => json([PROCEDURE]),
    [`GET ${BASE}/procedures/${P}`]: () => json(PROCEDURE),
    [`GET ${BASE}/procedures/${P}/items`]: () => json([ITEM]),
    [`GET ${BASE}/procedures/${P}/workpaper`]: () => json(DRAFT),
    [`GET ${BASE}/evidence-versions`]: () => json([]),
    [`GET ${BASE}/procedures/${P}/assessments`]: () => json([]),
    [`GET ${BASE}/procedures/${P}/flow`]: () => json(current),
    ...extra,
  });
  renderRoutes([{ path: "/", component: () => <Fieldwork engagementId={E} /> }]);
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

describe("ac1 ac3 approval", () => {
  it("lets a manager approve the sample", async () => {
    const { calls } = tab("manager", flow(), {
      [`POST ${BASE}/procedures/${P}/approve`]: () => json(flow(), 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Approve sample" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/approve"))).toBe(true);
    });
  });

  it("tells staff the sample waits for approval and keeps testing closed", async () => {
    tab("staff", flow());
    expect(await screen.findByText("Waiting for approval")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Approve sample" })).toBeNull();
    const support = await screen.findByRole("button", { name: "Request support for the sample" });
    expect(support.hasAttribute("disabled")).toBe(true);
  });

  it("shows who approved it", async () => {
    tab(
      "staff",
      flow({
        approval: {
          approved_by: "u-m",
          name: "Mo Manager",
          approved_at: "2026-10-20T09:00:00Z",
          note: null,
        },
      }),
    );
    expect(await screen.findByText("Sample approved")).toBeTruthy();
    expect(screen.getByText(/by Mo Manager/)).toBeTruthy();
  });
});

describe("ac11 ac12 steps, triage and row slots", () => {
  it("shows the steps and the triage counts", async () => {
    tab("staff", flow());
    const steps = await screen.findByRole("list", { name: "Steps" });
    expect(steps.textContent).toContain("Approved");
    expect(await screen.findByLabelText("Triage")).toBeTruthy();
    expect(screen.getByText("Passed 1")).toBeTruthy();
  });

  it("marks a sign-off on an older result as changed", async () => {
    tab(
      "senior",
      flow({
        rows: [
          {
            item_id: "i1",
            prepared: {
              signed_by: "u-2",
              name: "Sam Staff",
              initials: "SS",
              signed_at: "2026-10-20T10:00:00Z",
              stale: true,
            },
            reviewed: null,
          },
        ],
      }),
    );
    expect(
      await screen.findByLabelText("Prepared by Sam Staff · changed after sign-off"),
    ).toBeTruthy();
    expect(screen.getByLabelText("Reviewer: not signed")).toBeTruthy();
  });

  it("signs selected rows as preparer in one go (ac9)", async () => {
    const approved = flow({
      approval: {
        approved_by: "u-m",
        name: "Mo",
        approved_at: "2026-10-20T09:00:00Z",
        note: null,
      },
    });
    const { calls } = tab("staff", approved, {
      [`POST ${BASE}/procedures/${P}/items/sign-prepared`]: () => json({ rows: 1 }, 201),
    });
    fireEvent.click(await screen.findByRole("checkbox", { name: "Select TE-YE" }));
    fireEvent.click(await screen.findByRole("button", { name: "Sign 1 as preparer" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/items/sign-prepared"))?.body).toEqual({
        item_ids: ["i1"],
      });
    });
  });
});
