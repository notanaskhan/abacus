// SPEC-034 AC-1, AC-5, AC-9 (TASK-070): the general ledger upload section, its statuses and its
// plain-words failure messages.
import type { GlImportOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { GlExport } from "./GlExport";
import { glFailureMessage, glStatusMessage } from "./glMessages";

const E = "e1";
const BASE = `/v1/engagements/${E}/connection/import/gl`;
const FORMATS = [
  {
    id: "qbo_gl_csv",
    system: "QuickBooks Online",
    file_type: "csv",
    steps: ["Open General Ledger.", "Upload the CSV file here."],
  },
  {
    id: "xero_gl_xlsx",
    system: "Xero",
    file_type: "xlsx",
    steps: ["Open General Ledger Detail.", "Upload the Excel file here."],
  },
];

function gl(over: Partial<GlImportOut> = {}): GlImportOut {
  return {
    id: "g1",
    format: "qbo_gl_csv",
    status: "reconciled",
    line_count: 18412,
    created_at: "2026-10-14T10:00:00Z",
    ...over,
  };
}

function panel(
  latest: GlImportOut | null,
  extra = {},
): { calls: { method: string; path: string }[] } {
  const api = mockApi({
    [`GET ${BASE}/formats`]: () => json(FORMATS),
    [`GET ${BASE}`]: () => json(latest),
    ...extra,
  });
  renderRoutes([{ path: "/", component: () => <GlExport engagementId={E} /> }]);
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

describe("ac5 statuses and messages", () => {
  it.each([
    [gl({ status: "processing" }), "Checking your general ledger…"],
    [gl({ status: "waiting_for_tb" }), /Waiting for your trial balance/],
    [gl(), "Received: 18,412 transactions, reconciled to your trial balance."],
  ])("words the status", (given, expected) => {
    const text = glStatusMessage(given, "QuickBooks Online").text;
    if (typeof expected === "string") expect(text).toBe(expected);
    else expect(text).toMatch(expected);
  });

  it.each([
    [
      gl({
        status: "failed",
        failure_code: "roll_forward",
        accounts: [{ code: "4000", difference: "0.01" }],
      }),
      "These accounts don't agree with your trial balance: 4000 (off by $0.01).",
    ],
    [
      gl({ status: "failed", failure_code: "period_mismatch", months: ["2026-03"] }),
      "Your export doesn't cover the whole year: March 2026 has no transactions.",
    ],
    [
      gl({
        status: "failed",
        failure_code: "unbalanced",
        accounts: [{ code: "", difference: "10.00" }],
      }),
      "Debits and credits in your export differ by $10.00.",
    ],
    [gl({ status: "failed", failure_code: "looks_like_xero" }), "This looks like a Xero export"],
  ])("words the failure %#", (given, starts) => {
    expect(glFailureMessage(given, "QuickBooks Online").startsWith(starts)).toBe(true);
  });
});

describe("ac1 ac9 the section", () => {
  it("shows the latest status and the system's steps", async () => {
    panel(gl());
    expect(await screen.findByText(/reconciled to your trial balance/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Xero"));
    expect(screen.getByText("Open General Ledger Detail.")).toBeTruthy();
    expect(screen.getByText(/up to 50 MB/)).toBeTruthy();
  });

  it("shows nothing when general ledger import isn't on", async () => {
    mockApi({
      [`GET ${BASE}/formats`]: () => json({ detail: "ledger_import_off" }, 409),
      [`GET ${BASE}`]: () => json(null),
    });
    const { container } = renderRoutes([
      { path: "/", component: () => <GlExport engagementId={E} /> },
    ]);
    await waitFor(() => {
      expect(container.querySelector("section")).toBeNull();
    });
  });

  it("refuses a file over 50 MB before sending it", async () => {
    const { calls } = panel(null);
    fireEvent.click(await screen.findByLabelText("QuickBooks Online"));
    const big = new File(["x"], "gl.csv");
    Object.defineProperty(big, "size", { value: 51 * 1024 * 1024 });
    fireEvent.change(screen.getByLabelText("Upload the general ledger"), {
      target: { files: [big] },
    });
    expect(await screen.findByText(/over 50 MB/)).toBeTruthy();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("uploads the file for the chosen system", async () => {
    const { calls } = panel(null, {
      [`POST ${BASE}`]: () => json(gl({ status: "processing" }), 202),
    });
    fireEvent.click(await screen.findByLabelText("QuickBooks Online"));
    fireEvent.change(screen.getByLabelText("Upload the general ledger"), {
      target: { files: [new File(["a,b"], "gl.csv")] },
    });
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path === BASE)).toBe(true);
    });
  });
});
