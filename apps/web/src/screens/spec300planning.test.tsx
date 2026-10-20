// SPEC-300 (TASK-301): materiality proposed from a basis and decided by the partner; the risk
// register with RMM from the server and the partner's approval.
import type { MaterialityVersionOut, RiskOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Planning, previewAmounts } from "./Planning";

const BASE = "/v1/engagements/e1";
const PROPOSED: MaterialityVersionOut = {
  id: "m1",
  version: 1,
  status: "proposed",
  overall: "252200.00",
  performance: "189200.00",
  trivial: "12600.00",
  benchmark: "Net assets",
  basis_amount: "16812400.00",
  rate_pct: "1.500",
  performance_pct: "75.000",
  trivial_pct: "5.000",
  rationale: null,
  set_by_name: "Mo Manager",
  set_at: "2026-10-20T10:00:00Z",
  decided_by_name: null,
  decided_at: null,
  decision_rationale: null,
};
const RISK: RiskOut = {
  id: "r1",
  code: "R1",
  title: "Revenue recognised early",
  area: "Revenue",
  level: "assertion",
  assertions: ["cut_off"],
  inherent: "high",
  control: "maximum",
  rmm: "high",
  significant: true,
  fraud: "none",
  rationale: "Year-end incentives",
  needs_approval: true,
  approved_by_name: null,
  approved_at: null,
  recorded_by_name: "Sue Senior",
  recorded_at: "2026-10-20T10:00:00Z",
};

function page(role: string, extra = {}) {
  const api = mockApi({
    [`GET ${BASE}/materiality/versions`]: () => json([PROPOSED]),
    [`GET ${BASE}/risks`]: () => json([RISK]),
    [`GET ${BASE}/team`]: () => json([{ user_id: "u1", display_name: "Pat", role }]),
    "GET /v1/me": () =>
      json({ user_id: "u1", display_name: "Pat", memberships: [], active_tenant_id: "t1" }),
    ...extra,
  });
  renderRoutes([{ path: "/", component: () => <Planning engagementId="e1" /> }]);
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

describe("SPEC-300 planning", () => {
  it("previews the amounts the server computes (ac1)", () => {
    expect(previewAmounts(16812400, 1.5, 75, 5)).toEqual({
      overall: 252200,
      performance: 189200,
      trivial: 12600,
    });
    expect(previewAmounts(100, 1, 5, 6)).toBeNull();
  });

  it("a manager sees the proposal waiting; only the partner decides (ac2)", async () => {
    page("manager");
    expect(await screen.findByText("Waiting on the partner")).toBeTruthy();
    expect(screen.getByText("$252,200")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Decide materiality" })).toBeNull();
    expect(screen.getByText("Waiting")).toBeTruthy(); // the risk's approval
  });

  it("the partner decides with a rationale (ac2)", async () => {
    const { calls } = page("engagement_partner", {
      [`POST ${BASE}/materiality/decide`]: () => json([{ ...PROPOSED, status: "decided" }], 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Decide materiality" }));
    fireEvent.change(screen.getByLabelText("Decision rationale"), {
      target: { value: "Net assets drive users' decisions" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Decide" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/materiality/decide"))?.body).toEqual({
        rationale: "Net assets drive users' decisions",
      });
    });
  });

  it("shows the register and the partner approves a significant risk (ac5, ac6)", async () => {
    const { calls } = page("engagement_partner", {
      [`POST ${BASE}/risks/r1/approve`]: () =>
        json([{ ...RISK, needs_approval: false, approved_by_name: "Pat" }], 201),
    });
    expect(await screen.findByText("Revenue recognised early")).toBeTruthy();
    expect(screen.getByText("Significant · proposed")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("Approved · Pat")).toBeTruthy();
    expect(calls.some((c) => c.path.endsWith("/risks/r1/approve"))).toBe(true);
  });

  it("adding a significant risk needs a rationale (ac4)", async () => {
    const { calls } = page("senior", {
      [`POST ${BASE}/risks`]: () => json([RISK], 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Add risk" }));
    fireEvent.change(screen.getByLabelText("Risk title"), { target: { value: "Inventory" } });
    fireEvent.change(screen.getByLabelText("Area"), { target: { value: "Inventory" } });
    fireEvent.click(screen.getByLabelText("Significant risk (the partner approves)"));
    const buttons = screen.getAllByRole("button", { name: "Add risk" });
    const add = buttons[buttons.length - 1] as HTMLElement;
    expect(add.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Risk rationale"), { target: { value: "Obsolete" } });
    fireEvent.click(add);
    await waitFor(() => {
      expect(
        calls.find((c) => c.method === "POST" && c.path.endsWith("/risks"))?.body,
      ).toMatchObject({ title: "Inventory", significant: true, rationale: "Obsolete" });
    });
  });
});
