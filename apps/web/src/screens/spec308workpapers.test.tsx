// SPEC-308 (TASK-319): working papers. The index with status and sign-off squares, the grid
// showing server-computed values, editing a cell, and the sign-off rail's rules.
import type { WorkingPaperOut, WorkpaperDetailOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { groupDigits } from "./amounts";
import { display, rowCount, Workpaper } from "./Workpaper";
import { Workpapers } from "./Workpapers";

const BASE = "/v1/engagements/e1";
const LEVELS = (["preparer", "reviewer", "manager", "partner", "eqr"] as const).map((name, i) => ({
  level: i + 1,
  name,
  signed_by_name: null as string | null,
  signed_at: null as string | null,
  stale: false,
}));
const WP: WorkingPaperOut = {
  id: "w1",
  code: "C-100",
  title: "Cash lead schedule",
  audit_area: "Cash",
  status: "in_progress",
  levels: LEVELS,
  cells: 3,
  citations: 0,
  created_at: "2026-10-21T10:00:00Z",
};
const CELL = {
  error: false,
  formula: false,
  tickmarks: [],
  set_by_name: "Sue Senior",
  set_at: "2026-10-21T10:00:00Z",
  text: null,
};
const DETAIL: WorkpaperDetailOut = {
  workpaper: WP,
  content_hash: "a".repeat(64),
  cells: [
    { ...CELL, cell_key: "A1", raw: "Operating account", value: null, text: "Operating account" },
    { ...CELL, cell_key: "B1", raw: "1,250.10", value: "1250.10" },
    { ...CELL, cell_key: "B2", raw: "=B1*2", value: "2500.20", formula: true },
    {
      ...CELL,
      cell_key: "B3",
      raw: "=1/0",
      value: null,
      text: "#DIV/0!",
      formula: true,
      error: true,
    },
  ],
  citations: [],
  versions: [],
};

function page(role: string, ui: "index" | "grid", extra = {}, detail = DETAIL) {
  const api = mockApi({
    [`GET ${BASE}/workpapers`]: () => json([detail.workpaper]),
    [`GET ${BASE}/workpapers/w1`]: () => json(detail),
    [`GET ${BASE}/team`]: () => json([{ user_id: "u1", display_name: "Pat Person", role }]),
    "GET /v1/me": () =>
      json({ user_id: "u1", display_name: "Pat Person", memberships: [], active_tenant_id: "t1" }),
    ...extra,
  });
  renderRoutes([
    {
      path: "/",
      component: () =>
        ui === "index" ? (
          <Workpapers engagementId="e1" />
        ) : (
          <Workpaper engagementId="e1" workpaperId="w1" />
        ),
    },
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

describe("SPEC-308 working papers", () => {
  it("formats the server's decimals exactly and sizes the grid (ac3)", () => {
    expect(groupDigits("1250.1")).toBe("1,250.10");
    expect(groupDigits("-400")).toBe("(400)");
    expect(groupDigits("1234567.891")).toBe("1,234,567.89");
    expect(display(undefined)).toBe("");
    expect(rowCount([{ cell_key: "C40" }])).toBe(45);
    expect(rowCount([])).toBe(30);
  });

  it("lists papers with status and sign-off squares (ac1)", async () => {
    page("senior", "index");
    expect(await screen.findByText("Cash lead schedule")).toBeTruthy();
    expect(screen.getByText("In progress")).toBeTruthy();
    expect(screen.getByLabelText("EP not signed")).toBeTruthy();
  });

  it("shows computed values and formula errors; edits a cell (ac3)", async () => {
    const { calls } = page("senior", "grid", {
      [`PUT ${BASE}/workpapers/w1/cells`]: () => json(DETAIL),
    });
    expect(await screen.findByText("2,500.20")).toBeTruthy();
    expect(screen.getByText("#DIV/0!")).toBeTruthy();
    fireEvent.click(screen.getByText("Operating account"));
    const bar = screen.getByLabelText("Contents of A1");
    fireEvent.change(bar, { target: { value: "Payroll account" } });
    fireEvent.keyDown(bar, { key: "Enter" });
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        cells: [{ cell_key: "A1", raw: "Payroll account", tickmarks: [] }],
      });
    });
  });

  it("only the preparer level is open until L1 signs; the partner can't prepare (ac5)", async () => {
    page("engagement_partner", "grid");
    await screen.findByText("2,500.20");
    const buttons = screen.getAllByRole("button", { name: "Sign off" });
    // the partner holds L2, L3 and L4 (not L1 or L5), all blocked until the preparer signs
    expect(buttons).toHaveLength(3);
    expect(buttons.every((b) => b.hasAttribute("disabled"))).toBe(true);
  });

  it("the preparer signs; a stale sign-off asks to sign again (ac5)", async () => {
    const stale = {
      ...DETAIL,
      workpaper: {
        ...WP,
        status: "changed_after_signoff" as const,
        levels: LEVELS.map((l) =>
          l.level === 1
            ? { ...l, signed_by_name: "Pat Person", signed_at: WP.created_at, stale: true }
            : l,
        ),
      },
    };
    const { calls } = page(
      "staff",
      "grid",
      { [`POST ${BASE}/workpapers/w1/sign-offs/prepare`]: () => json(DETAIL, 201) },
      stale,
    );
    expect(await screen.findByText("Changed after sign-off")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sign again" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/sign-offs/prepare"))).toBe(true);
    });
  });
});
