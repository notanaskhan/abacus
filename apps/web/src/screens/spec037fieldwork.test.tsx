// SPEC-037 AC-4, AC-5, AC-7 (TASK-084): the Fieldwork tab: materiality, starting and selecting,
// a result per entry, sign-off, and the not-allowed and error states.
import type { ItemOut, ProcedureOut, WorkpaperOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Fieldwork } from "./Fieldwork";

const E = "e1";
const P = "p1";
const BASE = `/v1/engagements/${E}`;
const ME = { user_id: "u-s", display_name: "Sam", memberships: [], active_tenant_id: "t1" };
const PROCEDURE: ProcedureOut = {
  id: P,
  definition: "journal_entry_testing",
  definition_version: 1,
  status: "selected",
  parameters: {},
  population: {
    gl_snapshot_id: "g1",
    entry_count: 380036,
    line_count: 760072,
    total_debit: "100.00",
    total_credit: "100.00",
    tied: true,
  },
  selection: {
    id: "s1",
    item_count: 1,
    by_rule: { near_year_end: 1 },
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
  amount: "43210.09",
  descriptions: ["Year-end adjust"],
  rules: ["near_year_end", "keywords"],
};
const DRAFT: WorkpaperOut = {
  status: "draft",
  entries: 1,
  with_result: 1,
  exceptions: 0,
  conclusion: "No issues.",
  versions: [],
};

function tab(role: string, extra = {}) {
  const api = mockApi({
    "GET /v1/me": () => json(ME),
    [`GET ${BASE}/team`]: () => json([{ user_id: "u-s", display_name: "Sam", role }]),
    [`GET ${BASE}/materiality`]: () =>
      json({
        overall: "500000.00",
        performance: "375000.00",
        trivial: "25000.00",
        benchmark: "1% of revenue",
        set_by: "u-p",
        set_at: "2026-10-19T09:00:00Z",
      }),
    [`GET ${BASE}/procedures`]: () => json([PROCEDURE]),
    [`GET ${BASE}/procedures/${P}`]: () => json(PROCEDURE),
    [`GET ${BASE}/procedures/${P}/items`]: () => json([ITEM]),
    [`GET ${BASE}/procedures/${P}/workpaper`]: () => json(DRAFT),
    [`GET ${BASE}/evidence-versions`]: () => json([]),
    [`GET ${BASE}/procedures/${P}/assessments`]: () => json([]),
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

describe("ac1 ac2 the selection", () => {
  it("shows the tie-out and why each entry was chosen", async () => {
    tab("staff");
    expect(await screen.findByText(/380,036 journal entries/)).toBeTruthy();
    expect(screen.getByText(/agree to the general ledger/)).toBeTruthy();
    expect(await screen.findByText("Near year end, Flagged words")).toBeTruthy();
    expect(screen.getByText("43,210.09")).toBeTruthy();
  });
});

describe("ac4 results", () => {
  it("records an exception with its note", async () => {
    const { calls } = tab("staff", {
      [`PUT ${BASE}/procedures/${P}/items/i1/result`]: () => json({ ok: true }),
    });
    fireEvent.change(await screen.findByLabelText("Result for TE-YE"), {
      target: { value: "exception" },
    });
    fireEvent.change(screen.getByLabelText("Note"), { target: { value: "No approval" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        result: "exception",
        note: "No approval",
        evidence_version_ids: [],
        relates_to_year: null, // SPEC-038 (TASK-087): asked only for the search
      });
    });
  });

  it("asks the client for support", async () => {
    const { calls } = tab("staff", {
      [`POST ${BASE}/procedures/${P}/items/i1/request-support`]: () =>
        json({ request_item_id: "r1" }, 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Ask the client for support" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/request-support"))).toBe(true);
    });
  });
});

describe("ac5 sign-off", () => {
  it("lets the preparer sign as ready", async () => {
    const { calls } = tab("staff", {
      [`POST ${BASE}/procedures/${P}/workpaper/sign-ready`]: () =>
        json({ ...DRAFT, status: "ready" }, 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Sign off as preparer" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/sign-ready"))).toBe(true);
    });
  });

  it("explains why a reviewer can't sign their own work", async () => {
    tab("manager", {
      [`GET ${BASE}/procedures/${P}/workpaper`]: () => json({ ...DRAFT, status: "ready" }),
      [`POST ${BASE}/procedures/${P}/workpaper/sign-reviewed`]: () =>
        json({ detail: "reviewer_is_preparer" }, 409),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Sign off as reviewer" }));
    expect(await screen.findByText(/can't be the person who signed it as ready/)).toBeTruthy();
  });
});

describe("ac7 states", () => {
  it("offers to start when nothing has started", async () => {
    tab("senior", { [`GET ${BASE}/procedures`]: () => json([]) });
    // journal entry testing and the search for unrecorded liabilities (TASK-087) each offer Start
    expect((await screen.findAllByRole("button", { name: "Start" })).length).toBe(2);
  });

  it("says fieldwork is for the engagement team when refused", async () => {
    tab("staff", { [`GET ${BASE}/procedures`]: () => json({ detail: "forbidden" }, 403) });
    expect(await screen.findByText(/for the engagement team/)).toBeTruthy();
  });

  it("asks for materiality when it isn't set", async () => {
    tab("staff", { [`GET ${BASE}/materiality`]: () => json(null) });
    expect(await screen.findByText(/Not set yet/)).toBeTruthy();
  });
});

describe("task-085 the entry assessor", () => {
  it("shows the AI proposal beside the entry, tagged, with its citations", async () => {
    tab("staff", {
      [`GET ${BASE}/procedures/${P}/assessments`]: () =>
        json([
          {
            selected_item_id: "i1",
            verdict: "explained",
            rationale: "The memo shows the accrual and the CFO's approval.",
            citations: [
              {
                document: "D1",
                claim: "amount",
                page: 1,
                quote: "$43,210.09",
                verified: true,
                amount_matches: true,
              },
            ],
            created_at: "2026-10-19T12:00:00Z",
          },
        ]),
    });
    expect(await screen.findByText("Agent suggests: the support explains it")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Why" }));
    expect(screen.getByText(/CFO's approval/)).toBeTruthy();
    expect(screen.getByLabelText<HTMLSelectElement>("Result for TE-YE").value).toBe("");
  });

  it("starts assessments and says the team still decides", async () => {
    const { calls } = tab("staff", {
      [`POST ${BASE}/procedures/${P}/assess`]: () => json({ items: ["i1"] }, 202),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Assess with agent" }));
    expect(await screen.findByText(/your team still records every result/)).toBeTruthy();
    expect(calls.some((c) => c.path.endsWith("/assess"))).toBe(true);
  });

  it("explains when AI assessment isn't available", async () => {
    tab("staff", {
      [`POST ${BASE}/procedures/${P}/assess`]: () =>
        json({ detail: "ai_assessor_unavailable" }, 409),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Assess with agent" }));
    expect(await screen.findByText("AI assessment isn't available here.")).toBeTruthy();
  });
});
