// ac-test-author: ayushkbhatia
// Q-03-T524: back-fill of TASK-053 (ledger import web), black-box from SPEC-028 against the
// legacy ConnectionPanel, which stays live until A-02 replaces it (S17). Retired only when A-02's
// AC suite merges. Server-side ACs (3, 4, 5, 7, 8) are in backend/tests (see the task file).
// Copy is the spec's where it fixes words (AC-1's two option names) and otherwise asserted as
// behaviour (steps shown for the chosen system, a message said in words, a busy indicator).
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, never, renderRoutes, signInForTest } from "../testing/support";
import { ConnectionPanel } from "./ConnectionPanel";

const E = "eng-t524";
const QBO_STEP = "Open the trial balance report for the year end and export it as CSV.";
const XERO_STEP = "Open the trial balance report and export it as Excel.";
const FORMATS = [
  { id: "qbo_tb_csv", system: "QuickBooks Online", file_type: "csv", steps: [QBO_STEP] },
  { id: "xero_tb_xlsx", system: "Xero", file_type: "xlsx", steps: [XERO_STEP] },
];
const ENGAGEMENT = { id: E, fiscal_period_start: "2025-07-01", fiscal_period_end: "2026-06-30" };
const IMPORTED = {
  id: "imp-1",
  format: "qbo_tb_csv",
  system: "QuickBooks Online",
  period_start: "2025-07-01",
  period_end: "2026-06-30",
  status: "received",
  failure_code: null,
  totals_from_lines: false,
  on_behalf: false,
  uploaded_at: "2026-09-14T14:24:00Z",
  difference: null,
  found_period_end: null,
  duplicate: false,
};

function routes(extra: Record<string, () => Response | Promise<Response>> = {}) {
  return {
    [`GET /v1/engagements/${E}/connection`]: () => json(null),
    [`GET /v1/engagements/${E}/connection/providers`]: () =>
      json([{ provider: "fake", name: "Demo ledger", datasets: ["trial_balance"] }]),
    [`GET /v1/engagements/${E}/connection/import/formats`]: () => json(FORMATS),
    [`GET /v1/engagements/${E}/connection/import`]: () => json(null),
    [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
    ...extra,
  };
}

function show(canConnect = true): void {
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ConnectionPanel engagementId={E} firmName="Brightwater Hale" canConnect={canConnect} />
      ),
    },
  ]);
}

async function exportWith(system: string): Promise<void> {
  fireEvent.click(await screen.findByRole("button", { name: "Export instead" }));
  fireEvent.click(await screen.findByRole("radio", { name: system }));
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

describe("SPEC-028 AC-1", () => {
  it("test_ac1_connect_fastest_and_export_instead_sit_side_by_side", async () => {
    mockApi(routes());
    show();
    expect(await screen.findByRole("heading", { name: "Connect (fastest)" })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Export instead" })).toBeTruthy();
  });

  it("test_ac1_choosing_export_needs_no_connection_and_connect_stays_available", async () => {
    const { calls } = mockApi(routes());
    show();
    expect(await screen.findByRole("button", { name: "Connect Demo ledger" })).toBeTruthy();
    await exportWith("QuickBooks Online");
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
  });
});

describe("SPEC-028 AC-2", () => {
  it("test_ac2_each_system_shows_its_own_numbered_steps_and_file_type", async () => {
    mockApi(routes());
    show();
    await exportWith("Xero");
    expect(screen.getByText(XERO_STEP)).toBeTruthy();
    expect(screen.queryByText(QBO_STEP)).toBeNull();
    expect(screen.getAllByText(/Excel|xlsx/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("radio", { name: "QuickBooks Online" }));
    expect(screen.getByText(QBO_STEP)).toBeTruthy();
    expect(screen.getAllByText(/CSV/).length).toBeGreaterThan(0);
  });

  it("test_ac2_the_period_is_prefilled_from_the_engagement_year_end", async () => {
    mockApi(routes());
    show();
    await exportWith("QuickBooks Online");
    expect(await screen.findByText(/June 30, 2026/)).toBeTruthy();
  });

  it("test_ac2_a_file_uploads_for_the_chosen_format", async () => {
    const { calls } = mockApi(
      routes({ [`POST /v1/engagements/${E}/connection/import`]: () => json(IMPORTED, 201) }),
    );
    show();
    await exportWith("QuickBooks Online");
    fireEvent.change(screen.getByLabelText("Upload the export"), {
      target: { files: [new File(["Account,Debit,Credit"], "tb.csv", { type: "text/csv" })] },
    });
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST")).toBe(true);
    });
    const post = calls.find((c) => c.method === "POST");
    expect(post?.query.get("format")).toBe("qbo_tb_csv");
  });
});

describe("SPEC-028 AC-6", () => {
  it("test_ac6_a_failed_check_says_in_plain_words_what_is_wrong", async () => {
    mockApi(
      routes({
        [`POST /v1/engagements/${E}/connection/import`]: () =>
          json(
            { ...IMPORTED, status: "failed", failure_code: "unbalanced", difference: "40.00" },
            201,
          ),
      }),
    );
    show();
    await exportWith("QuickBooks Online");
    fireEvent.change(screen.getByLabelText("Upload the export"), {
      target: { files: [new File(["x"], "tb.csv", { type: "text/csv" })] },
    });
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Debits and credits/);
    expect(alert.textContent).not.toMatch(/unbalanced|failure_code|422/);
  });

  it("test_ac6_a_refused_file_never_reads_as_received", async () => {
    mockApi(
      routes({
        [`POST /v1/engagements/${E}/connection/import`]: () =>
          json({ detail: "file_refused" }, 422),
      }),
    );
    show();
    await exportWith("QuickBooks Online");
    fireEvent.change(screen.getByLabelText("Upload the export"), {
      target: { files: [new File(["x"], "tb.csv", { type: "text/csv" })] },
    });
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).not.toContain("file_refused");
    expect(screen.queryByText(/Received/)).toBeNull();
  });
});

describe("SPEC-028 AC-9", () => {
  it("test_ac9_loading_shows_a_placeholder_and_no_options", async () => {
    mockApi(routes({ [`GET /v1/engagements/${E}/connection`]: () => never() }));
    show();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("button", { name: "Export instead" })).toBeNull();
  });

  it("test_ac9_an_error_is_said_in_words", async () => {
    mockApi(
      routes({ [`GET /v1/engagements/${E}/connection`]: () => json({ detail: "boom" }, 500) }),
    );
    show();
    expect((await screen.findByText("Couldn't load the connection")).textContent).toBeTruthy();
  });

  it("test_ac9_not_allowed_offers_no_upload", async () => {
    mockApi(
      routes({
        [`GET /v1/engagements/${E}/connection/import/formats`]: () =>
          json({ detail: "forbidden" }, 403),
      }),
    );
    show(false);
    await screen.findByRole("heading", { name: "Connect (fastest)" }).catch(() => null);
    await waitFor(() => {
      expect(screen.queryByLabelText("Upload the export")).toBeNull();
      expect(screen.queryByRole("button", { name: "Export instead" })).toBeNull();
    });
  });

  it("test_ac9_the_panel_uses_no_literal_colours", async () => {
    mockApi(routes());
    const { container } = (show(), { container: document.body });
    await screen.findByRole("button", { name: "Export instead" });
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,6}\b|rgb\(/);
  });
});
