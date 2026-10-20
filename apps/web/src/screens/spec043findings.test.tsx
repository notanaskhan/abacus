// SPEC-043 (TASK-107): the findings register, the summary computed by the server, and raising
// a finding.
import type { FindingOut, SummaryOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Findings } from "./Findings";

const BASE = "/v1/engagements/e1";
const FINDING: FindingOut = {
  id: "f1",
  title: "Exception: JE-104, 12,000.00",
  description: "No approval",
  procedure_id: "p1",
  item_id: "i1",
  raised_by_name: "Sam Staff",
  raised_at: "2026-10-20T10:00:00Z",
  misstatement: {
    kind: "factual",
    amount: "-12000.00",
    account_code: "2000",
    corrected: false,
    recorded_by_name: "Mo Manager",
    recorded_at: "2026-10-20T11:00:00Z",
  },
};
const SUMMARY: SummaryOut = {
  materiality_set: true,
  overall: "150000.00",
  performance: "100000.00",
  trivial: "5000.00",
  by_kind: [
    { kind: "factual", count: 1, total: "-12000.00" },
    { kind: "judgmental", count: 0, total: "0" },
    { kind: "projected", count: 0, total: "0" },
  ],
  total: "-12000.00",
  position: "below_performance",
};

function page(role: string, extra = {}) {
  const api = mockApi({
    [`GET ${BASE}/findings`]: () => json([FINDING]),
    [`GET ${BASE}/findings/summary`]: () => json(SUMMARY),
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

describe("SPEC-043 findings", () => {
  it("shows the register and the summary against materiality (ac3, ac5)", async () => {
    page("staff");
    expect(await screen.findByText("Exception: JE-104, 12,000.00")).toBeTruthy();
    expect(screen.getAllByText("(12,000.00)").length).toBeGreaterThan(0);
    expect(screen.getByText("Below performance materiality")).toBeTruthy();
    expect(screen.getByText("Uncorrected")).toBeTruthy();
  });

  it("raises a finding by hand (ac1)", async () => {
    const { calls } = page("staff", { [`POST ${BASE}/findings`]: () => json([FINDING], 201) });
    fireEvent.click(await screen.findByRole("button", { name: "New finding" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Cut-off error" } });
    fireEvent.click(screen.getByRole("button", { name: "Raise finding" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "POST" && c.path.endsWith("/findings"))?.body).toEqual(
        {
          title: "Cut-off error",
        },
      );
    });
  });
});
