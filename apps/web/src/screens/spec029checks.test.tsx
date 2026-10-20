// SPEC-029 AC-5, AC-10, AC-11, AC-13 (TASK-057): plain-words problems for the client with
// Replace file, every check for the firm, the document kind control and the Board's filter.
import type { CheckOut, EvidenceVersionOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { boardRows } from "../board/join";
import { applyFilters } from "../board/filters";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { ClientUploadChecks, FirmChecksPanel } from "./CheckResults";
import { checkName, crossCheckMessage, problemMessage } from "./checkMessages";
import { DocumentKindSelect } from "./DocumentKindSelect";

const E = "e1";
const IDS = { engagementId: E, itemId: "i1", versionId: "v1" };
const CHECKS = `/v1/engagements/${E}/request-items/i1/uploads/v1/checks`;

const check = (over: Partial<CheckOut>): CheckOut => ({
  code: "wrong_period",
  outcome: "passed",
  audience: "client",
  document_kind: "bank_statement",
  reason: null,
  expected_date: null,
  found_date: null,
  amount: null,
  difference: null,
  account_code: null,
  ref_item_id: null,
  ...over,
});

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac10 messages", () => {
  it.each([
    [
      check({ outcome: "problem", found_date: "2026-11-30", expected_date: "2026-12-31" }),
      "This statement ends on November 30, 2026; we need one that includes December 31, 2026.",
    ],
    [
      check({
        outcome: "problem",
        document_kind: "ar_aging",
        found_date: "2026-11-30",
        expected_date: "2026-12-31",
      }),
      "This aging is as of November 30, 2026; we need it as of December 31, 2026.",
    ],
    [
      check({ code: "wrong_entity", outcome: "problem" }),
      "This looks like it's for a different company.",
    ],
    [
      check({ code: "totals_dont_add_up", outcome: "problem", difference: "-124.50" }),
      "The balances on this statement don't add up (off by $124.50). Please check it's the complete statement.",
    ],
    [
      check({ code: "unreadable", outcome: "problem", reason: "scanned" }),
      "This looks like a scanned copy, so we can't read it. Please upload the statement you download from your bank's website.",
    ],
    [
      check({ code: "duplicate", outcome: "problem" }),
      "This file is already uploaded elsewhere in this audit.",
    ],
  ])("has a fixed message for each problem", (given, expected) => {
    expect(problemMessage(given)).toBe(expected);
  });

  it("has no message for a check that passed", () => {
    expect(problemMessage(check({}))).toBeNull();
  });

  it("puts a cross-check in the firm's words", () => {
    expect(
      crossCheckMessage(
        check({
          code: "ledger_cross_check",
          outcome: "problem",
          audience: "firm",
          difference: "124.50",
          account_code: "1000",
        }),
      ),
    ).toBe("Closing balance is $124.50 more than account 1000 in the trial balance.");
    expect(
      crossCheckMessage(
        check({
          code: "ledger_cross_check",
          outcome: "not_applicable",
          reason: "account_unclear",
        }),
      ),
    ).toMatch(/Couldn't tell which cash account/);
    expect(checkName("totals_dont_add_up")).toBe("Totals add up");
  });
});

describe("ac10 client results", () => {
  const client = (uploadedAt: string): void => {
    renderRoutes([
      {
        path: "/",
        component: () => (
          <ClientUploadChecks
            ids={IDS}
            uploadedAt={uploadedAt}
            replace={<span>Replace file</span>}
          />
        ),
      },
    ]);
  };

  it("says checking while the file is fresh, then shows problems with Replace file", async () => {
    let calls = 0;
    mockApi({
      [`GET ${CHECKS}`]: () => {
        calls += 1;
        return json(calls === 1 ? [] : [check({ code: "wrong_entity", outcome: "problem" })]);
      },
    });
    client(new Date().toISOString());
    expect(await screen.findByText("Checking…")).toBeTruthy();
    expect(
      await screen.findByText(
        "This looks like it's for a different company.",
        {},
        { timeout: 5000 },
      ),
    ).toBeTruthy();
    expect(screen.getByText("Replace file")).toBeTruthy();
  });

  it("says no problems found when every check passed", async () => {
    mockApi({ [`GET ${CHECKS}`]: () => json([check({}), check({ code: "duplicate" })]) });
    client("2026-01-01T00:00:00Z");
    expect(await screen.findByText("No problems found")).toBeTruthy();
  });
});

describe("ac11 firm panel", () => {
  it("lists every check, firm-only ones marked, with why one wasn't checked", async () => {
    mockApi({
      [`GET ${CHECKS}`]: () =>
        json([
          check({ outcome: "problem", found_date: "2026-11-30", expected_date: "2026-12-31" }),
          check({ code: "totals_dont_add_up", outcome: "not_applicable", reason: "not_printed" }),
          check({
            code: "ledger_cross_check",
            outcome: "problem",
            audience: "firm",
            difference: "-10.00",
            account_code: "1000",
          }),
        ]),
    });
    renderRoutes([{ path: "/", component: () => <FirmChecksPanel ids={IDS} /> }]);
    expect(await screen.findByText("Right period")).toBeTruthy();
    expect(screen.getByText("not every balance is printed")).toBeTruthy();
    expect(screen.getByText("firm only")).toBeTruthy();
    expect(
      screen.getByText("Closing balance is $10.00 less than account 1000 in the trial balance."),
    ).toBeTruthy();
  });

  it("shows the empty, error and not-allowed states", async () => {
    mockApi({ [`GET ${CHECKS}`]: () => json([]) });
    renderRoutes([{ path: "/", component: () => <FirmChecksPanel ids={IDS} /> }]);
    expect(await screen.findByText("Not checked yet.")).toBeTruthy();
    cleanup();
    mockApi({ [`GET ${CHECKS}`]: () => json({ detail: "forbidden" }, 403) });
    renderRoutes([{ path: "/", component: () => <FirmChecksPanel ids={IDS} /> }]);
    expect(await screen.findByText("You can't see this file's checks.")).toBeTruthy();
  });
});

describe("ac5 document kind", () => {
  it("sets an override, and returns the item to the rules", async () => {
    const { calls } = mockApi({
      [`PUT /v1/engagements/${E}/request-items/i1/document-kind`]: () => json({}),
    });
    const item = {
      id: "i1",
      engagement_id: E,
      document_kind: "bank_statement",
      document_kind_source: "rule",
    } as RequestItemOut;
    renderRoutes([
      { path: "/", component: () => <DocumentKindSelect engagementId={E} item={item} /> },
    ]);
    const select = await screen.findByRole("combobox");
    expect(screen.getByRole("option", { name: "Use the rules (Bank statement)" })).toBeTruthy();
    fireEvent.change(select, { target: { value: "ar_aging" } });
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ document_kind: "ar_aging" });
    });
    fireEvent.change(select, { target: { value: "rules" } });
    await waitFor(() => {
      expect(calls.filter((c) => c.method === "PUT").at(-1)?.body).toEqual({ clear: true });
    });
  });
});

describe("ac11 board filter", () => {
  it("filters to items whose latest version has problems", () => {
    const items = [
      {
        id: "a",
        status: "uploaded",
        audit_area: "Cash",
        description: "A",
        evidence_version_id: "va",
      },
      {
        id: "b",
        status: "uploaded",
        audit_area: "Cash",
        description: "B",
        evidence_version_id: "vb",
      },
    ] as RequestItemOut[];
    const versions = [
      { id: "va", method: "uploaded", problems: 2 },
      { id: "vb", method: "uploaded", problems: 0 },
    ] as EvidenceVersionOut[];
    const rows = applyFilters(boardRows(items, versions, []), { source: "problems" });
    expect(rows.map((r) => r.item.id)).toEqual(["a"]);
  });
});
