// SPEC-309 (TASK-320): the trial balance of record. Adopting from the empty state, the server's
// figures and balance shown as sent, the newer-version banner, annotations and leadsheets.
import type { SnapshotOut, TrialBalanceDetailOut, TrialBalanceOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { amount, wholeDollars } from "./amounts";
import { sourceWord, TrialBalance } from "./TrialBalance";

const BASE = "/v1/engagements/e1/trial-balances";
const SNAP: SnapshotOut = {
  id: "s1",
  period_start: "2026-01-01",
  period_end: "2026-12-31",
  source: "import_netsuite_tb_csv",
  pulled_at: "2026-09-11T15:02:00Z",
  line_count: 3,
  total_debit: "168600.00",
  total_credit: "168600.00",
  lines_changed: null,
  net_change: null,
};
const PRIOR: SnapshotOut = {
  ...SNAP,
  id: "s0",
  period_start: "2025-01-01",
  period_end: "2025-12-31",
};
const TB: TrialBalanceOut = {
  id: "tb1",
  label: "standard",
  period_start: "2026-01-01",
  period_end: "2026-12-31",
  display_unit: "cents",
  current_version_no: 1,
};
const VERSION = {
  version_no: 1,
  snapshot_id: "s1",
  prior_snapshot_id: "s0",
  adopted_by_name: "Simone Baptiste",
  reason: null,
  adopted_at: "2026-09-11T15:05:00Z",
  source: "import_netsuite_tb_csv",
  pulled_at: "2026-09-11T15:02:00Z",
};
const DETAIL: TrialBalanceDetailOut = {
  trial_balance: TB,
  version: VERSION,
  versions: [VERSION],
  lines: [
    {
      account_code: "1000",
      account_name: "Cash",
      boy: "100000.00",
      debit: "120000.00",
      credit: "0.00",
      eoy: "120000.00",
      change: "20000.00",
      area: "Cash",
      wp_ref: "C-100",
    },
    {
      account_code: "2000",
      account_name: "Payables",
      boy: "-60000.00",
      debit: "0.00",
      credit: "68600.00",
      eoy: "-68600.00",
      change: "-8600.00",
      area: null,
      wp_ref: null,
    },
  ],
  eoy: { debit: "168600.00", credit: "168600.00", difference: "0.00", balanced: true },
  boy: { debit: "100000.00", credit: "100000.00", difference: "0.00", balanced: true },
};

function page(role: string, routes: Record<string, () => Response>) {
  const api = mockApi({
    [`GET /v1/engagements/e1/team`]: () => json([{ user_id: "u1", display_name: "Pat", role }]),
    "GET /v1/me": () =>
      json({ user_id: "u1", display_name: "Pat", memberships: [], active_tenant_id: "t1" }),
    ...routes,
  });
  renderRoutes([{ path: "/", component: () => <TrialBalance engagementId="e1" /> }]);
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

describe("SPEC-309 trial balance", () => {
  it("formats exact amounts and names sources (ac2)", () => {
    expect(amount("-68600.00")).toBe("(68,600.00)");
    expect(amount(null)).toBe("—");
    expect(wholeDollars("86000000.50")).toBe("86,000,001");
    expect(wholeDollars("-0.40")).toBe("0");
    expect(sourceWord("import_qbo_tb_csv")).toBe("a QuickBooks export");
  });

  it("adopts a snapshot with a prior year from the empty state (ac1)", async () => {
    const { calls } = page("senior", {
      [`GET ${BASE}`]: () => json({ trial_balances: [], snapshots: [SNAP, PRIOR] }),
      [`POST ${BASE}`]: () => json(DETAIL, 201),
    });
    fireEvent.click(await screen.findByText("2026-01-01 – 2026-12-31"));
    fireEvent.change(screen.getByLabelText("Prior-year trial balance"), {
      target: { value: "s0" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Use this trial balance" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "POST")?.body).toEqual({
        snapshot_id: "s1",
        label: "standard",
        prior_snapshot_id: "s0",
      });
    });
  });

  it("shows the server's lines, totals and balance, and the newer version (ac2, ac7)", async () => {
    page("staff", {
      [`GET ${BASE}`]: () => json({ trial_balances: [TB], snapshots: [SNAP] }),
      [`GET ${BASE}/tb1`]: () => json(DETAIL),
      [`GET ${BASE}/tb1/candidates`]: () =>
        json([{ ...SNAP, id: "s2", pulled_at: "2026-09-14T14:15:00Z", lines_changed: 3 }]),
    });
    expect(await screen.findByText("Balanced")).toBeTruthy();
    expect(screen.getByText("(68,600.00)")).toBeTruthy();
    expect(screen.getAllByText("168,600.00")).toHaveLength(2);
    expect(screen.getByText(/Adopted by Simone Baptiste from a NetSuite export/)).toBeTruthy();
    expect(await screen.findByText(/3 lines changed/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Use v2…" })).toBeTruthy();
  });

  it("sets an area and WP ref on selected accounts (ac6)", async () => {
    const { calls } = page("senior", {
      [`GET ${BASE}`]: () => json({ trial_balances: [TB], snapshots: [SNAP] }),
      [`GET ${BASE}/tb1`]: () => json(DETAIL),
      [`GET ${BASE}/tb1/candidates`]: () => json([]),
      [`POST ${BASE}/tb1/annotations`]: () => json(DETAIL, 201),
    });
    fireEvent.click(await screen.findByLabelText("Select 2000"));
    fireEvent.click(screen.getByRole("button", { name: "Set area and WP ref" }));
    fireEvent.change(screen.getByPlaceholderText("Cash"), { target: { value: "Payables" } });
    fireEvent.change(screen.getByPlaceholderText("C-100"), { target: { value: "l-100" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/annotations"))?.body).toEqual({
        accounts: [{ account_code: "2000", area: "Payables", wp_ref: "L-100" }],
      });
    });
  });

  it("shows leadsheets with Unassigned (ac5)", async () => {
    page("reviewer", {
      [`GET ${BASE}`]: () => json({ trial_balances: [TB], snapshots: [SNAP] }),
      [`GET ${BASE}/tb1`]: () => json(DETAIL),
      [`GET ${BASE}/tb1/candidates`]: () => json([]),
      [`GET ${BASE}/tb1/leadsheets`]: () =>
        json([
          {
            area: "Unassigned",
            rows: [
              {
                account_code: "2000",
                account_name: "Payables",
                py: "-60000.00",
                cy: "-68600.00",
                change: "-8600.00",
                change_pct: "-14.3",
              },
            ],
            py: "-60000.00",
            cy: "-68600.00",
            change: "-8600.00",
            change_pct: "-14.3",
          },
        ]),
    });
    expect(screen.queryByRole("button", { name: "Set area and WP ref" })).toBeNull();
    fireEvent.click(await screen.findByRole("button", { name: "Leadsheets" }));
    expect(await screen.findByText("Total unassigned")).toBeTruthy();
    expect(screen.getAllByText("-14.3 %")).toHaveLength(2);
  });
});
