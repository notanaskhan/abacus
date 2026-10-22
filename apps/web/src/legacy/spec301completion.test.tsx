// SPEC-301 (TASK-302): severity (the partner concludes), proposed entries balanced before they're
// sent, and the representation list with what still lacks one.
import type { AdjustmentOut, FindingOut, RepresentationListOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Findings } from "./Findings";

const BASE = "/v1/engagements/e1";
const FINDING: FindingOut = {
  id: "f1",
  title: "Payroll changes not approved",
  description: null,
  procedure_id: null,
  item_id: null,
  raised_by_name: "Sam Staff",
  raised_at: "2026-10-20T10:00:00Z",
  misstatement: null,
  deficiency: {
    status: "proposed",
    proposed: "significant_deficiency",
    proposed_by_name: "Mo Manager",
    concluded: null,
    concluded_by_name: null,
    concluded_at: null,
    conclusion_rationale: null,
    communicated_on: null,
    communicated_to: null,
  },
};
const ENTRY: AdjustmentOut = {
  id: "a1",
  ref: "AJE-1",
  kind: "aje",
  description: "Accrue December invoices",
  finding_id: null,
  lines: [
    { account_code: "5000", debit: "68400.00", credit: "0.00" },
    { account_code: "2000", debit: "0.00", credit: "68400.00" },
  ],
  total: "68400.00",
  status: "approved",
  raised_by_name: "Sue Senior",
  raised_at: "2026-10-20T10:00:00Z",
  approved_by_name: "Mo Manager",
  response_note: null,
};
const REPS: RepresentationListOut = {
  items: [],
  passed: ["AJE-3"],
  gaps: [{ kind: "adjustment", id: "a3", label: "AJE-3" }],
};

function page(role: string, extra = {}) {
  const api = mockApi({
    [`GET ${BASE}/findings`]: () => json([FINDING]),
    [`GET ${BASE}/findings/summary`]: () =>
      json({
        materiality_set: false,
        overall: null,
        performance: null,
        trivial: null,
        by_kind: [],
        total: "0",
        position: "unknown",
      }),
    [`GET ${BASE}/adjustments`]: () => json([ENTRY]),
    [`GET ${BASE}/representations`]: () => json(REPS),
    [`GET ${BASE}/graph`]: () => json({ areas: [], gaps: { unmapped_accounts: [] } }),
    [`GET ${BASE}/team`]: () => json([{ user_id: "u1", display_name: "Pat", role }]),
    "GET /v1/me": () =>
      json({ user_id: "u1", display_name: "Pat", memberships: [], active_tenant_id: "t1" }),
    ...extra,
  });
  renderRoutes([{ path: "/", component: () => <Findings engagementId="e1" /> }]);
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

describe("SPEC-301 completion", () => {
  it("the partner concludes severity with a rationale; a manager can't (ac2)", async () => {
    const { calls } = page("engagement_partner", {
      [`POST ${BASE}/findings/f1/severity/conclude`]: () => json([FINDING], 201),
    });
    expect(await screen.findByText("Significant deficiency · proposed")).toBeTruthy();
    fireEvent.click(screen.getByText("Payroll changes not approved"));
    const conclude = await screen.findByRole("button", { name: "Conclude severity" });
    expect(conclude.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Severity rationale"), {
      target: { value: "No compensating review" },
    });
    fireEvent.click(conclude);
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/severity/conclude"))?.body).toEqual({
        severity: "significant_deficiency",
        rationale: "No compensating review",
      });
    });
  });

  it("a manager proposes but doesn't conclude (ac1)", async () => {
    page("manager");
    fireEvent.click(await screen.findByText("Payroll changes not approved"));
    expect(await screen.findByRole("button", { name: "Propose severity" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Conclude severity" })).toBeNull();
  });

  it("records the client's answer on an approved entry (ac5, ac6)", async () => {
    const { calls } = page("manager", {
      [`POST ${BASE}/adjustments/a1/client-answer`]: () =>
        json([{ ...ENTRY, status: "client_declined" }], 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Proposed entries" }));
    expect(await screen.findByText("Accrue December invoices")).toBeTruthy();
    expect(screen.getByText("Dr 5000 68,400.00 · Cr 2000 68,400.00")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Declined · pass" }));
    expect(await screen.findByText("Passed")).toBeTruthy();
    expect(calls.find((c) => c.path.endsWith("/client-answer"))?.body).toEqual({
      accepted: false,
    });
  });

  it("only sends a balanced entry (ac4)", async () => {
    const { calls } = page("senior", {
      [`POST ${BASE}/adjustments`]: () => json([ENTRY], 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Proposed entries" }));
    fireEvent.click(await screen.findByRole("button", { name: "Propose entry" }));
    fireEvent.change(screen.getByLabelText("Entry description"), { target: { value: "Accrual" } });
    fireEvent.change(screen.getByLabelText("Line 1 account"), { target: { value: "5000" } });
    fireEvent.change(screen.getByLabelText("Line 1 debit"), { target: { value: "100" } });
    fireEvent.change(screen.getByLabelText("Line 2 account"), { target: { value: "2000" } });
    fireEvent.change(screen.getByLabelText("Line 2 credit"), { target: { value: "90" } });
    const buttons = screen.getAllByRole("button", { name: "Propose entry" });
    const send = buttons[buttons.length - 1] as HTMLElement;
    expect(send.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Line 2 credit"), { target: { value: "100" } });
    expect(screen.getByText("Balanced · 100.00")).toBeTruthy();
    fireEvent.click(send);
    await waitFor(() => {
      expect(
        calls.find((c) => c.method === "POST" && c.path.endsWith("/adjustments"))?.body,
      ).toMatchObject({ kind: "aje", description: "Accrual" });
    });
  });

  it("lists passed entries without a representation and links a new one (ac7, ac8)", async () => {
    const { calls } = page("manager", {
      [`POST ${BASE}/representations`]: () => json({ ...REPS, gaps: [] }, 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Representations" }));
    fireEvent.click(await screen.findByRole("button", { name: "Passed entry AJE-3" }));
    expect(screen.getByText(/including passed entries AJE-3/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("New representation"), {
      target: { value: "We agree AJE-3 is immaterial." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add representation" }));
    await waitFor(() => {
      expect(
        calls.find((c) => c.method === "POST" && c.path.endsWith("/representations"))?.body,
      ).toEqual({
        body: "We agree AJE-3 is immaterial.",
        adjustment_id: "a3",
      });
    });
  });
});
