// SPEC-033 AC-3, AC-5, AC-9 (TASK-066): the matcher's proposals for the firm (AI tag, rationale,
// verified quotes, "Suggest with AI"), and its picks for the client as "Suggested" only.
import type { FileMatchOut, InboxFileOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { InboxPanel } from "./InboxPanel";

const E = "e1";
const ITEMS = [
  { id: "i1", description: "Debt agreements", status: "open" },
  { id: "i2", description: "Lease agreements", status: "open" },
].map((i) => ({
  ...i,
  engagement_id: E,
  audit_area: "Debt",
  created_at: "2026-10-01T00:00:00Z",
})) as RequestItemOut[];

const FILE: InboxFileOut = {
  id: "f1",
  file_name: "scan0043.pdf",
  media_type: "application/pdf",
  size_bytes: 1200,
  uploaded_by: "u-c",
  uploaded_by_name: "Cara Client",
  uploaded_by_staff: false,
  note: null,
  created_at: "2026-10-09T10:00:00Z",
  suggestions: [{ request_item_id: "i1", score: 92, matched: [], source: "matcher", reasons: [] }],
};

function match(over: Partial<FileMatchOut> = {}): FileMatchOut {
  return {
    inbox_file_id: "f1",
    status: "completed",
    reason: null,
    none_fit: false,
    none_fit_rationale: null,
    proposals: [
      {
        request_item_id: "i1",
        confidence: "0.92",
        rationale: "A term loan agreement between the company and its bank.",
        quotes: [{ page: 1, sheet: null, cell: null, quote: "TERM LOAN AGREEMENT" }],
      },
    ],
    ...over,
  };
}

function panel(
  firm: boolean,
  matches: FileMatchOut[] = [match()],
  extra = {},
): { calls: { method: string; path: string }[] } {
  const api = mockApi({
    [`GET /v1/engagements/${E}/inbox`]: () => json([FILE]),
    [`GET /v1/engagements/${E}/inbox-matches`]: () => json(matches),
    ...extra,
  });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <InboxPanel
          engagementId={E}
          items={ITEMS}
          {...(firm ? { firm: { canRequestMatch: true } } : {})}
        />
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

describe("ac3 the firm's view", () => {
  it("shows each proposal with its rationale and verified quote", async () => {
    panel(true);
    const list = await screen.findByRole("list", { name: "AI suggestions" });
    expect(within(list).getByText("Debt agreements")).toBeTruthy();
    expect(within(list).getByText("92% confident")).toBeTruthy();
    expect(within(list).getByText(/A term loan agreement/)).toBeTruthy();
    expect(within(list).getByRole("button", { name: "Page 1" })).toBeTruthy();
  });

  it("says why there is no suggestion for real client data", async () => {
    panel(true, [match({ status: "failed", reason: "data_boundary", proposals: [] })]);
    expect(
      await screen.findByText("AI suggestions aren't available for real client data yet."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Suggest with AI" })).toBeNull();
  });

  it("says when none of the requests fit", async () => {
    panel(true, [
      match({ none_fit: true, none_fit_rationale: "A marketing flyer.", proposals: [] }),
    ]);
    expect(await screen.findByText("None of the requests fit")).toBeTruthy();
    expect(screen.getByText("A marketing flyer.")).toBeTruthy();
  });

  it("asks the matcher when nothing has run yet, and explains a refusal", async () => {
    const { calls } = panel(true, [], {
      [`POST /v1/engagements/${E}/inbox/f1/match`]: () =>
        json({ detail: "ai_match_unavailable" }, 409),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Suggest with AI" }));
    expect(
      await screen.findByText("AI suggestions aren't available in this environment."),
    ).toBeTruthy();
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/match"))).toBe(true);
    });
  });
});

describe("ac5 the client's view", () => {
  it("shows the pick as Suggested with no AI words and never asks for matches", async () => {
    const { calls } = panel(false);
    const suggestions = await screen.findByLabelText("Suggestions for scan0043.pdf");
    expect(within(suggestions).getByText("Suggested")).toBeTruthy();
    expect(screen.queryByText(/confident/)).toBeNull();
    expect(screen.queryByText(/term loan/i)).toBeNull();
    expect(calls.some((c) => c.path.endsWith("/inbox-matches"))).toBe(false);
  });
});
