// SPEC-316 (TASK-345): FS groupings imported and published; the trial balance mapped by rules
// and edits; the draft statements as the server computed them.
import type { FsStatementsOut, GroupingVersionOut, MappingOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { GroupingSets, problemWord } from "./GroupingSets";
import { TbMapping, TbStatements } from "./TbMapping";

const BASE = "/v1/engagements/e1/trial-balances/tb1";
const PATH = { path: { engagement_id: "e1", tb_id: "tb1" } };
const VERSION: GroupingVersionOut = {
  id: "gv1",
  set_key: "bh-fs",
  set_name: "BH FS groupings",
  version: 2,
  status: "published",
  problems: [],
  created_at: "2026-10-21T10:00:00Z",
  published_at: "2026-10-21T11:00:00Z",
};
const MAPPING: MappingOut = {
  mapping_set_id: "ms1",
  version: VERSION,
  groupings: [
    {
      id: "g1",
      key: "cash",
      label: "Cash and equivalents",
      class: "assets",
      lines: [
        { id: "f1", key: "cash", label: "Cash", normal_balance: "debit", grouping_key: "cash" },
      ],
    },
  ],
  accounts: [
    {
      account_code: "1000",
      account_name: "Cash - operating",
      eoy: "29754445.22",
      final: null,
      boy: null,
      fs_line_id: "f1",
      method: "number_range",
      edited_by: null,
      edited_at: null,
    },
    {
      account_code: "9999",
      account_name: "Suspense",
      eoy: "0.00",
      final: null,
      boy: null,
      fs_line_id: null,
      method: null,
      edited_by: null,
      edited_at: null,
    },
  ],
  mapped: 1,
  unmapped: 1,
  manual: 0,
  content_hash: "a".repeat(64),
  published_versions: [],
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

describe("SPEC-316 FS groupings and mapping", () => {
  it("words import problems by row (ac1)", () => {
    expect(problemWord({ row: 4, code: "class_invalid", detail: "asset" })).toBe(
      "Row 4: Class must be assets, liabilities, equity, revenue or expenses (asset)",
    );
    expect(
      problemWord({ row: 0, code: "overlapping_range", detail: "1000-1099 and 1050-1060" }),
    ).toBe("Account ranges overlap (1000-1099 and 1050-1060)");
  });

  it("imports a CSV as a draft and publishes a clean draft (ac1, ac2)", async () => {
    const draft = { ...VERSION, status: "draft" as const, published_at: null };
    const { calls } = mockApi({
      "GET /v1/grouping-sets": () => json([draft]),
      "POST /v1/grouping-sets/imports": () => json([draft], 201),
      "POST /v1/grouping-sets/versions/gv1/publish": () => json([VERSION], 201),
    });
    renderRoutes([{ path: "/", component: () => <GroupingSets /> }]);
    fireEvent.change(await screen.findByLabelText("Key"), { target: { value: "bh-fs" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "BH FS groupings" } });
    fireEvent.change(screen.getByLabelText("CSV"), { target: { value: "grouping_key,…" } });
    fireEvent.click(screen.getByRole("button", { name: "Import as a draft" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/imports"))?.body).toEqual({
        key: "bh-fs",
        name: "BH FS groupings",
        csv: "grouping_key,…",
      });
    });
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    expect(await screen.findByText("Published")).toBeTruthy();
  });

  it("shows rule and unmapped accounts and maps one (ac3, ac4)", async () => {
    const { calls } = mockApi({
      [`GET ${BASE}/mapping`]: () => json(MAPPING),
      [`PUT ${BASE}/mapping/accounts`]: () =>
        json({ ...MAPPING, unmapped: 0, mapped: 2, manual: 1 }),
    });
    renderRoutes([
      { path: "/", component: () => <TbMapping path={PATH} role="senior" unit="cents" /> },
    ]);
    expect(await screen.findByText("1 unmapped")).toBeTruthy();
    expect(screen.getByText("Account range")).toBeTruthy();
    const preparerSign = screen.getByRole("button", { name: "Sign as preparer" });
    expect(preparerSign.hasAttribute("disabled")).toBe(true); // every account mapped first
    fireEvent.change(screen.getByLabelText("FS line for 9999"), { target: { value: "f1" } });
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        accounts: [{ account_code: "9999", fs_line_id: "f1" }],
      });
    });
    expect(await screen.findByText("All mapped")).toBeTruthy();
  });

  it("offers published groupings before the mapping starts (ac3)", async () => {
    const { calls } = mockApi({
      [`GET ${BASE}/mapping`]: () =>
        json({
          ...MAPPING,
          mapping_set_id: null,
          version: null,
          groupings: [],
          accounts: [],
          published_versions: [VERSION],
        }),
      [`POST ${BASE}/mapping`]: () => json(MAPPING, 201),
    });
    renderRoutes([
      { path: "/", component: () => <TbMapping path={PATH} role="manager" unit="cents" /> },
    ]);
    fireEvent.change(await screen.findByLabelText("FS groupings"), { target: { value: "gv1" } });
    fireEvent.click(screen.getByRole("button", { name: "Map with these groupings" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "POST")?.body).toEqual({
        grouping_set_version_id: "gv1",
      });
    });
  });

  it("shows the statements and the balance check (ac6)", async () => {
    const statements: FsStatementsOut = {
      layer: "unadjusted",
      groups: [
        {
          key: "cash",
          label: "Cash and equivalents",
          class: "assets",
          lines: [{ key: "cash", label: "Cash", cy: "500.00", py: null }],
          cy: "500.00",
          py: null,
        },
        {
          key: "equity",
          label: "Equity",
          class: "equity",
          lines: [{ key: "re", label: "Retained earnings", cy: "320.00", py: null }],
          cy: "320.00",
          py: null,
        },
      ],
      totals: {
        assets: "500.00",
        liabilities: "0.00",
        equity: "320.00",
        revenue: "400.00",
        expenses: "220.00",
      },
      py_totals: null,
      net_income: "180.00",
      py_net_income: null,
      difference: "0.00",
      balanced: true,
      unmapped: 0,
    };
    mockApi({ [`GET ${BASE}/statements`]: () => json(statements) });
    renderRoutes([
      { path: "/", component: () => <TbStatements path={PATH} layer="unadjusted" unit="cents" /> },
    ]);
    expect(await screen.findByText("Balance sheet balances")).toBeTruthy();
    expect(screen.getByText("Total assets")).toBeTruthy();
    expect(screen.getAllByText("180.00").length).toBeGreaterThan(0);
  });
});
