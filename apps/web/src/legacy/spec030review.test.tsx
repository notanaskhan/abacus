// SPEC-030 AC-6, AC-10 (TASK-059): the firm's AI review panel: flags with verified quotes,
// links to the preview page, "Review now", the data boundary message and the states.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, never, renderRoutes, signInForTest } from "../testing/support";
import { AIReviewPanel } from "./AIReviewPanel";

const E = "e1";
const URL_ = `/v1/engagements/${E}/evidence-versions/v1/review`;

const panel = (onOpenPage = vi.fn(), canRequest = true): void => {
  renderRoutes([
    {
      path: "/",
      component: () => (
        <AIReviewPanel
          engagementId={E}
          versionId="v1"
          canRequest={canRequest}
          onOpenPage={onOpenPage}
        />
      ),
    },
  ]);
};

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

describe("ac6 flags", () => {
  it("shows each flag with its quotes, and a quote opens its preview page", async () => {
    const open = vi.fn();
    mockApi({
      [`GET ${URL_}`]: () =>
        json({
          status: "completed",
          reason: null,
          flags: [
            {
              category: "draft",
              confidence: "0.92",
              rationale: "The first page is marked DRAFT.",
              quotes: [
                { page: 1, sheet: null, cell: null, quote: "DRAFT - NOT FOR DISTRIBUTION" },
              ],
            },
          ],
        }),
    });
    panel(open);
    expect(await screen.findByText("Looks like a draft")).toBeTruthy();
    expect(screen.getByText("92% confident")).toBeTruthy();
    expect(screen.getByText("The first page is marked DRAFT.")).toBeTruthy();
    expect(screen.getByText("DRAFT - NOT FOR DISTRIBUTION")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Page 1" }));
    expect(open).toHaveBeenCalledWith(1);
  });

  it("says no concerns, and starts a review on request", async () => {
    const { calls } = mockApi({
      [`GET ${URL_}`]: () => json({ status: "completed", reason: null, flags: [] }),
      [`POST ${URL_}`]: () => json({ evidence_version_id: "v1" }, 202),
    });
    panel();
    expect(await screen.findByText("No concerns")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Review now" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST")).toBe(true);
    });
  });

  it("says when AI review isn't available in this environment", async () => {
    mockApi({
      [`GET ${URL_}`]: () => json({ status: "none", reason: null, flags: [] }),
      [`POST ${URL_}`]: () => json({ detail: "ai_review_unavailable" }, 409),
    });
    panel();
    fireEvent.click(await screen.findByRole("button", { name: "Review now" }));
    expect(await screen.findByText("AI review isn't available in this environment.")).toBeTruthy();
  });

  it("explains the data boundary and offers no retry for it", async () => {
    mockApi({
      [`GET ${URL_}`]: () => json({ status: "failed", reason: "data_boundary", flags: [] }),
    });
    panel();
    expect(
      await screen.findByText("AI review isn't available for real client data yet."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Review now" })).toBeNull();
  });
});

describe("ac10 states", () => {
  it("shows loading, not reviewed yet, and not-allowed", async () => {
    mockApi({ [`GET ${URL_}`]: () => never() });
    panel();
    await waitFor(() => {
      expect(document.querySelector(".animate-pulse")).not.toBeNull();
    });
    cleanup();
    mockApi({ [`GET ${URL_}`]: () => json({ status: "none", reason: null, flags: [] }) });
    panel(vi.fn(), false);
    expect(await screen.findByText("Not reviewed yet.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Review now" })).toBeNull();
    cleanup();
    mockApi({ [`GET ${URL_}`]: () => json({ detail: "forbidden" }, 403) });
    panel();
    expect(await screen.findByText("You can't see this file's AI review.")).toBeTruthy();
  });
});
