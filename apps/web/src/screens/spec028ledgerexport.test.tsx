// SPEC-028 (TASK-053): connect or export, the guided steps, uploading, and plain-words results.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { ConnectionPanel } from "./ConnectionPanel";
import { importFailureMessage } from "./importMessages";

const E = "e1";
const FORMATS = [
  {
    id: "qbo_tb_csv",
    system: "QuickBooks Online",
    file_type: "csv",
    steps: [
      "In QuickBooks Online, go to Reports and open Trial Balance.",
      "Upload the CSV file here.",
    ],
  },
  {
    id: "xero_tb_xlsx",
    system: "Xero",
    file_type: "xlsx",
    steps: ["In Xero, go to Accounting, then Reports, and open Trial Balance."],
  },
];
const ENGAGEMENT = { id: E, fiscal_period_start: "2026-01-01", fiscal_period_end: "2026-12-31" };
const IMPORT = {
  id: "i1",
  format: "qbo_tb_csv",
  system: "QuickBooks Online",
  period_start: "2026-01-01",
  period_end: "2026-12-31",
  status: "received",
  failure_code: null,
  totals_from_lines: false,
  on_behalf: false,
  uploaded_at: "2026-10-12T09:00:00Z",
  difference: null,
  found_period_end: null,
  duplicate: false,
};

const panel = (canConnect: boolean): void => {
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ConnectionPanel engagementId={E} firmName="Dev firm" canConnect={canConnect} />
      ),
    },
  ]);
};

const routes = (extra: Record<string, () => Response | Promise<Response>> = {}) => ({
  [`GET /v1/engagements/${E}/connection`]: () => json(null),
  [`GET /v1/engagements/${E}/connection/providers`]: () =>
    json([{ provider: "fake", name: "Demo ledger", datasets: ["trial_balance"] }]),
  [`GET /v1/engagements/${E}/connection/import/formats`]: () => json(FORMATS),
  [`GET /v1/engagements/${E}/connection/import`]: () => json(null),
  [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
  ...extra,
});

async function chooseAndUpload(system: string, name = "tb.csv"): Promise<void> {
  fireEvent.click(await screen.findByRole("button", { name: "Export instead" }));
  fireEvent.click(await screen.findByRole("radio", { name: system }));
  const input = await screen.findByLabelText("Upload the export");
  fireEvent.change(input, { target: { files: [new File(["Debit,Credit"], name)] } });
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

describe("ac1 connect or export", () => {
  it("offers Connect (fastest) and Export instead side by side, export needing no connection", async () => {
    mockApi(routes());
    panel(true);
    expect(await screen.findByRole("heading", { name: "Connect (fastest)" })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Export instead" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Connect Demo ledger" })).toBeTruthy();
  });

  it("offers only Connect when the firm hasn't turned export on", async () => {
    mockApi(
      routes({
        [`GET /v1/engagements/${E}/connection/import/formats`]: () =>
          json({ detail: "ledger_import_off" }, 409),
      }),
    );
    panel(true);
    expect(await screen.findByRole("button", { name: "Connect Demo ledger" })).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Export instead" })).toBeNull();
    });
  });
});

describe("ac2 guided steps and upload", () => {
  it("shows the chosen system's steps and the year end, then uploads the file raw", async () => {
    const { calls } = mockApi(
      routes({ [`POST /v1/engagements/${E}/connection/import`]: () => json(IMPORT, 201) }),
    );
    panel(true);
    fireEvent.click(await screen.findByRole("button", { name: "Export instead" }));
    fireEvent.click(await screen.findByRole("radio", { name: "Xero" }));
    expect(screen.getByText(/In Xero, go to Accounting/)).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: "QuickBooks Online" }));
    expect(screen.getByText(/In QuickBooks Online, go to Reports/)).toBeTruthy();
    expect(await screen.findByText(/year ending December 31, 2026, as a CSV file/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Upload the export"), {
      target: { files: [new File(["Debit,Credit"], "tb.csv", { type: "text/csv" })] },
    });
    expect(await screen.findByText("Received. We're preparing your trial balance.")).toBeTruthy();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toBe("Debit,Credit");
    expect(post?.headers.get("Content-Type")).toBe("text/csv");
  });

  it("says when the same file was already uploaded", async () => {
    mockApi(
      routes({
        [`POST /v1/engagements/${E}/connection/import`]: () =>
          json({ ...IMPORT, duplicate: true }, 201),
      }),
    );
    panel(true);
    await chooseAndUpload("QuickBooks Online");
    expect(await screen.findByText(/already uploaded this file/)).toBeTruthy();
  });
});

describe("ac6 plain-words failures", () => {
  it("shows the unbalanced difference computed by the server", async () => {
    mockApi(
      routes({
        [`POST /v1/engagements/${E}/connection/import`]: () =>
          json(
            { ...IMPORT, status: "failed", failure_code: "unbalanced", difference: "-1250.00" },
            201,
          ),
      }),
    );
    panel(true);
    await chooseAndUpload("QuickBooks Online");
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Debits and credits differ by $1,250.00. Check the export covers every account, then upload it again.",
    );
  });

  it("names the date the export is for and the year end needed", async () => {
    mockApi(
      routes({
        [`POST /v1/engagements/${E}/connection/import`]: () =>
          json(
            {
              ...IMPORT,
              status: "failed",
              failure_code: "period_mismatch",
              found_period_end: "2026-11-30",
            },
            201,
          ),
      }),
    );
    panel(true);
    await chooseAndUpload("QuickBooks Online");
    expect((await screen.findByRole("alert")).textContent).toContain(
      "This export is as of November 30, 2026; we need December 31, 2026.",
    );
  });

  it("names both systems when the file is another system's export", async () => {
    mockApi(
      routes({
        [`POST /v1/engagements/${E}/connection/import`]: () =>
          json({ ...IMPORT, status: "failed", failure_code: "looks_like_xero" }, 201),
      }),
    );
    panel(true);
    await chooseAndUpload("QuickBooks Online");
    expect((await screen.findByRole("alert")).textContent).toContain(
      "This looks like a Xero export, but you chose QuickBooks Online.",
    );
  });

  it("explains a refused file and a refusal from the server without its code", async () => {
    mockApi(
      routes({
        [`POST /v1/engagements/${E}/connection/import`]: () =>
          json({ detail: "file_refused" }, 422),
      }),
    );
    panel(true);
    await chooseAndUpload("QuickBooks Online");
    expect((await screen.findByRole("alert")).textContent).toBe(
      "We couldn't accept this file. Please export it again from QuickBooks Online.",
    );
  });

  it.each([
    ["control_totals_mismatch", /total row doesn't match/],
    ["unsupported_currency", /isn't in US dollars/],
    ["duplicate_account", /same account appears more than once/],
    ["empty", /no balances/],
    ["unrecognised_format", /doesn't look like a QuickBooks Online trial balance/],
    ["unreadable", /couldn't read this file/],
    ["invalid_amount", /amounts or account names couldn't be read/],
    ["payload_too_large", /over 20 MB/],
    ["empty_file", /file is empty/],
    ["already_connected", /connected, so an export isn't needed/],
    ["something_new", /couldn't read this file/],
  ])("has a fixed message for %s", (code, expected) => {
    expect(importFailureMessage({ code, system: "QuickBooks Online" })).toMatch(expected);
  });
});

describe("ac6 after an import", () => {
  it("shows the firm the latest export and the same reason, with an upload on the client's behalf", async () => {
    mockApi(
      routes({
        [`GET /v1/engagements/${E}/connection/import`]: () =>
          json({ ...IMPORT, status: "failed", failure_code: "unbalanced", difference: "10.00" }),
      }),
    );
    panel(false);
    expect(
      await screen.findByText(/QuickBooks Online · year ending December 31, 2026/),
    ).toBeTruthy();
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Debits and credits differ by $10.00.",
    );
    expect(
      await screen.findByRole("button", { name: "Upload an export for the client" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Connect/ })).toBeNull();
  });

  it("offers a newer export once the import is the connection", async () => {
    mockApi(
      routes({
        [`GET /v1/engagements/${E}/connection`]: () =>
          json({
            id: "c1",
            provider: "import",
            status: "active",
            scopes: [],
            created_by: "u-a",
            created_at: "2026-10-12T09:00:00Z",
            expires_at: null,
            last_checked_at: null,
            last_check_ok: null,
            last_pull_at: null,
          }),
        [`GET /v1/engagements/${E}/connection/import`]: () => json(IMPORT),
      }),
    );
    panel(true);
    expect(await screen.findByText("Received")).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Upload a newer export" })).toBeTruthy();
    expect(screen.getByText(/isn't updated automatically/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Check now" })).toBeNull();
  });
});

describe("ac9 states", () => {
  it("hides Export when the options can't load, keeping Connect", async () => {
    mockApi(
      routes({
        [`GET /v1/engagements/${E}/connection/import/formats`]: () => json({ detail: "x" }, 500),
      }),
    );
    panel(true);
    expect(await screen.findByRole("button", { name: "Connect Demo ledger" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Export instead" })).toBeNull();
  });
});
