// SPEC-311 (TASK-322): the summary of uncorrected misstatements, as the server computed it.
import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { UncorrectedSummary } from "./Uncorrected";

function page(body: unknown) {
  mockApi({ "GET /v1/engagements/e1/uncorrected-misstatements": () => json(body) });
  renderRoutes([{ path: "/", component: () => <UncorrectedSummary engagementId="e1" /> }]);
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

describe("SPEC-311 uncorrected misstatements", () => {
  it("lists passed entries with the aggregate and where it falls (ac4)", async () => {
    page({
      entries: [
        {
          id: "a3",
          ref: "AJE-3",
          description: "Late remittance accrual",
          amount: "18400.00",
          accounts: ["2100", "6100"],
        },
      ],
      aggregate: "18400.00",
      overall: "252200.00",
      performance: "189200.00",
      trivial: "12600.00",
      materiality_decided: true,
      band: "below_performance",
      headroom: "233800.00",
    });
    expect(await screen.findByText("AJE-3")).toBeTruthy();
    expect(screen.getAllByText("18,400.00")).toHaveLength(2);
    expect(screen.getByText("Below performance materiality")).toBeTruthy();
    expect(screen.getByText("233,800.00")).toBeTruthy();
  });

  it("says when materiality isn't set", async () => {
    page({
      entries: [],
      aggregate: "0.00",
      overall: null,
      performance: null,
      trivial: null,
      materiality_decided: false,
      band: null,
      headroom: null,
    });
    expect(await screen.findByText(/Materiality isn't set yet/)).toBeTruthy();
    expect(screen.getByText(/No passed entries/)).toBeTruthy();
  });
});
