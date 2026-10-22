// TASK-104 (the plan's DEC-74): follow-ups are drafted per contact and sent by a person after
// reading the exact email.
import type { DraftOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { FollowUps } from "./FollowUps";

const BASE = "/v1/engagements/e1/follow-ups";
const DRAFT: DraftOut = {
  id: "r1",
  recipient_user_id: "u-c",
  recipient_name: "Casey Client",
  items: [
    { request_item_id: "i1", description: "Bank statements" },
    { request_item_id: "i2", description: "Payroll register" },
  ],
  created_at: "2026-10-20T09:00:00Z",
};

function pane(extra = {}) {
  const api = mockApi({ [`GET ${BASE}`]: () => json([DRAFT]), ...extra });
  renderRoutes([{ path: "/", component: () => <FollowUps engagementId="e1" /> }]);
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

describe("follow-ups", () => {
  it("lists drafts per contact and drafts more on request", async () => {
    const { calls } = pane({ [`POST ${BASE}/draft`]: () => json({ drafted: 0 }, 201) });
    expect(await screen.findByText("Casey Client")).toBeTruthy();
    expect(screen.getByText(/and 1 more/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Draft follow-ups for overdue items" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/follow-ups/draft"))).toBe(
        true,
      );
    });
  });

  it("shows the exact email before sending, and dismisses", async () => {
    const { calls } = pane({
      [`POST ${BASE}/r1/preview`]: () =>
        json({ subject: "Dev firm is still waiting for 2 items", body: "- Bank statements" }),
      [`POST ${BASE}/r1/dismiss`]: () => json({ id: "r1" }),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Review and send" }));
    expect(await screen.findByText("Dev firm is still waiting for 2 items")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/r1/dismiss"))).toBe(true);
    });
  });
});
