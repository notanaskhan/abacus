// SPEC-033 AC-1, AC-6, AC-9 (TASK-064): suggestions from a file's contents, with their reasons,
// and the source and rank sent when one is followed.
import type { InboxFileOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { InboxPanel } from "./InboxPanel";
import { reasonLabel } from "./matchingMessages";

const E = "e1";
const ITEMS = [
  { id: "i1", description: "Bank statement - operating", status: "open" },
  { id: "i2", description: "Bank statement - payroll", status: "open" },
].map((i) => ({
  ...i,
  engagement_id: E,
  audit_area: "Cash",
  created_at: "2026-10-01T00:00:00Z",
})) as RequestItemOut[];

const FILE: InboxFileOut = {
  id: "f1",
  file_name: "scan0042.pdf",
  media_type: "application/pdf",
  size_bytes: 1200,
  uploaded_by: "u-c",
  uploaded_by_name: "Cara Client",
  uploaded_by_staff: false,
  note: null,
  created_at: "2026-10-09T10:00:00Z",
  suggestions: [
    {
      request_item_id: "i2",
      score: 100,
      matched: [],
      source: "content",
      reasons: [
        { code: "kind", value: "bank_statement" },
        { code: "date", value: "2026-12-31" },
        { code: "account", value: "4471" },
        { code: "holder" },
      ],
    },
    {
      request_item_id: "i1",
      score: 70,
      matched: [],
      source: "content",
      reasons: [{ code: "kind", value: "bank_statement" }],
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

describe("ac1 reasons", () => {
  it.each([
    [{ code: "kind" as const, value: "bank_statement" }, "Bank statement"],
    [{ code: "kind" as const, value: "aging" }, "Aging report"],
    [{ code: "date" as const, value: "2026-12-31" }, "Covers December 31, 2026"],
    [{ code: "account" as const, value: "4471" }, "Account ending 4471"],
    [{ code: "holder" as const }, "In the company's name"],
    [{ code: "file_name" as const, value: "bank, december" }, "File name: bank, december"],
  ])("labels %o", (reason, label) => {
    expect(reasonLabel(reason)).toBe(label);
  });

  it("shows a content suggestion with its reasons and sends its source and rank", async () => {
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}/inbox`]: () => json([FILE]),
      [`POST /v1/engagements/${E}/inbox/f1/assign`]: () =>
        json({ evidence_version_id: "v1" }, 201),
    });
    renderRoutes([{ path: "/", component: () => <InboxPanel engagementId={E} items={ITEMS} /> }]);
    const list = await screen.findByLabelText("Suggestions for scan0042.pdf");
    const first = within(list).getAllByRole("listitem")[0] as HTMLElement;
    expect(within(first).getByText("From the file's contents")).toBeTruthy();
    expect(within(first).getByText("Account ending 4471")).toBeTruthy();
    fireEvent.click(
      within(list).getByRole("button", { name: "Bank statement - operating · 70%" }),
    );
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/assign"))?.body).toEqual({
        request_item_id: "i1",
        followed_suggestion: true,
        suggestion_source: "content",
        suggestion_rank: 2,
      });
    });
  });
});
