// SPEC-312 phase 2-3 (TASK-324): the server reads and reconciles a statement's transactions;
// the reviewer excludes with reasons, types missing balances, and approves only when reconciled.
import type { StatementOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { decisionsBody, StatementReview } from "./StatementReview";

const BASE = "/v1/engagements/e1/request-items/i1/uploads/v1/statement";
const IDS = { engagementId: "e1", itemId: "i1", versionId: "v1" };
const line = (position: number, description: string, value: string) => ({
  position,
  posted_on: "2026-12-02",
  description,
  amount: value,
  page: 1,
  excluded: false,
  exclusion_reason: null,
});
const DRAFT: StatementOut = {
  status: "draft",
  format: "pdf_text",
  account_kind: "credit_card",
  issuer: "Example Card Services",
  last4: "4471",
  period_start: "2026-11-22",
  period_end: "2026-12-21",
  opening: "1250.00",
  closing: "1234.57",
  opening_source: "printed",
  closing_source: "printed",
  printed_opening: true,
  printed_closing: true,
  signs_inferred: false,
  signs_flipped: false,
  truncated: false,
  lines: [
    line(1, "PAYMENT THANK YOU", "-1250.00"),
    line(2, "RETURN OFFICE SUPPLY", "-24.99"),
    line(3, "CLOUD HOSTING INC", "1234.57"),
  ],
  reconciliation: {
    opening: "1250.00",
    lines_total: "-40.42",
    expected_closing: "1209.58",
    closing: "1234.57",
    difference: "24.99",
    reconciled: false,
  },
  approved_by_name: null,
  approved_at: null,
};
const FIXED: StatementOut = {
  ...DRAFT,
  lines: DRAFT.lines.map((l) =>
    l.position === 2 ? { ...l, excluded: true, exclusion_reason: "Counted twice" } : l,
  ),
  reconciliation: {
    ...DRAFT.reconciliation,
    lines_total: "-15.43",
    expected_closing: "1234.57",
    difference: "0.00",
    reconciled: true,
  },
};

function page(routes: Record<string, () => Response>, canApprove = true) {
  const api = mockApi(routes);
  renderRoutes([
    { path: "/", component: () => <StatementReview ids={IDS} canApprove={canApprove} /> },
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

describe("SPEC-312 statement review", () => {
  it("builds decisions only when reasons and balances are complete (ac6)", () => {
    expect(decisionsBody(new Map([[2, " Counted twice "]]), false, "", "1,234.57")).toEqual({
      excluded: [{ position: 2, reason: "Counted twice" }],
      flip_signs: false,
      closing: "1234.57",
    });
    expect(decisionsBody(new Map([[2, ""]]), false, "", "")).toBeNull();
    expect(decisionsBody(new Map(), false, "12x", "")).toBeNull();
  });

  it("excludes a line with a reason, reconciles on the server, then approves (ac6, ac7)", async () => {
    const { calls } = page({
      [`GET ${BASE}`]: () => json(DRAFT),
      [`POST ${BASE}/preview`]: () => json(FIXED),
      [`POST ${BASE}/approve`]: () =>
        json(
          {
            ...FIXED,
            status: "approved",
            approved_by_name: "Pat Person",
            approved_at: "2026-12-22T10:00:00Z",
          },
          201,
        ),
    });
    expect(await screen.findByText("Off 24.99")).toBeTruthy();
    const approve = screen.getByRole("button", { name: "Approve transactions" });
    expect(approve.hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByLabelText("Include line 2"));
    fireEvent.change(screen.getByLabelText("Why line 2 is excluded"), {
      target: { value: "Counted twice" },
    });
    expect(await screen.findByText("Reconciled")).toBeTruthy();
    expect(calls.find((c) => c.path.endsWith("/preview"))?.body).toEqual({
      excluded: [{ position: 2, reason: "Counted twice" }],
      flip_signs: false,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Approve transactions" }).hasAttribute("disabled"),
      ).toBe(false);
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve transactions" }));
    expect(
      await screen.findByText(/Approved by Pat Person on 2026-12-22 · 2 transactions/),
    ).toBeTruthy();
  });

  it("asks for balances an export doesn't print, and offers the sign flip", async () => {
    page({
      [`GET ${BASE}`]: () =>
        json({
          ...DRAFT,
          format: "csv",
          printed_opening: false,
          printed_closing: false,
          opening: null,
          closing: null,
          signs_inferred: true,
          reconciliation: {
            ...DRAFT.reconciliation,
            opening: null,
            closing: null,
            expected_closing: null,
            difference: null,
          },
        }),
    });
    expect(await screen.findByText("Needs balances")).toBeTruthy();
    expect(screen.getByLabelText("Opening balance")).toBeTruthy();
    expect(screen.getByText(/flip the signs/)).toBeTruthy();
  });

  it("says when a file has no transactions", async () => {
    page({ [`GET ${BASE}`]: () => json({ detail: "no_transactions" }, 409) });
    expect(await screen.findByText("No statement transactions found in this file.")).toBeTruthy();
  });
});
