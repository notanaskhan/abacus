// SPEC-317 (TASK-460): the engagement dashboard shows the server's gates, tiles and next steps.
import type { DashboardOut } from "@abacus/api-client";
import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { EngagementDashboard, nextTab } from "./EngagementDashboard";

const DASH: DashboardOut = {
  gates: [
    { gate: "G1", met: true, blockers: [] },
    { gate: "G5", met: false, blockers: ["unsigned:C-100:L2"] },
  ],
  tiles: [
    {
      key: "papers_complete",
      label: "Working papers signed off",
      value: 12,
      total: 21,
      attention: false,
    },
    { key: "requests_overdue", label: "Requests overdue", value: 3, total: null, attention: true },
  ],
  next_up: [
    {
      kind: "review",
      label: "Cash lead schedule",
      target_type: "workpaper",
      target_id: "w1",
      code: "C-100",
    },
    {
      kind: "chase_request",
      label: "Bank confirmation",
      target_type: "request_item",
      target_id: "r1",
      code: null,
    },
  ],
};

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("SPEC-317 engagement dashboard", () => {
  it("routes next steps to where the work lives (ac2)", () => {
    expect(nextTab(DASH.next_up[0] as DashboardOut["next_up"][number])).toBe("paper");
    expect(nextTab(DASH.next_up[1] as DashboardOut["next_up"][number])).toBe(
      "/engagements/$engagementId/requests",
    );
    expect(
      nextTab({
        kind: "prepare",
        label: "x",
        target_type: "mapping_set",
        target_id: "m",
        code: null,
      }),
    ).toBe("/engagements/$engagementId/trial-balance");
  });

  it("shows gates, tiles with totals and attention, and next steps (ac1, ac2)", async () => {
    mockApi({ "GET /v1/engagements/e1/dashboard": () => json(DASH) });
    renderRoutes([{ path: "/", component: () => <EngagementDashboard engagementId="e1" /> }]);
    expect(await screen.findByText("G5 · Review complete")).toBeTruthy();
    expect(screen.getByText("of 21", { exact: false })).toBeTruthy();
    const overdue = screen.getByText("Requests overdue").closest("a");
    expect(overdue?.getAttribute("data-attention")).toBe("true");
    expect(screen.getByText("Review and sign")).toBeTruthy();
    expect(screen.getByText("C-100")).toBeTruthy();
  });

  it("says when nothing waits", async () => {
    mockApi({ "GET /v1/engagements/e1/dashboard": () => json({ ...DASH, next_up: [] }) });
    renderRoutes([{ path: "/", component: () => <EngagementDashboard engagementId="e1" /> }]);
    expect(await screen.findByText("Nothing waits on you right now.")).toBeTruthy();
  });
});
