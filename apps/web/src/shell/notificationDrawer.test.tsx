// SPEC-305 (TASK-306): the notifications drawer: tabs by kind, day groups, the engagement each
// concerns; opening one marks it read and goes to its page.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { NotificationDrawer } from "./NotificationDrawer";
import { categoryOf, dayGroup } from "./notifications";

const NOW = new Date();
const note = (id: string, kind: string, daysAgo: number, read = false) => ({
  id,
  kind,
  engagement_id: "e1",
  subject_type: "engagement",
  subject_id: "e1",
  created_at: new Date(NOW.getTime() - daysAgo * 86_400_000).toISOString(),
  read,
});

function page() {
  return mockApi({
    "GET /v1/notifications": () =>
      json({
        items: [
          note("n1", "materiality.proposed", 0),
          note("n2", "comment.mentioned", 1),
          note("n3", "evidence.uploaded", 10, true),
        ],
        unread_count: 2,
      }),
    "POST /v1/notifications/n1/read": () => json({ items: [], unread_count: 1 }),
    "GET /v1/engagements": () =>
      json([
        {
          id: "e1",
          name: "FY2025 audit",
          client_name: "Northwind",
          client_entity_name: "Northwind Inc",
          client_id: "c1",
          client_entity_id: "ce1",
          type: "fs_audit",
          service_line: "audit",
          status: "active",
          fiscal_period_start: "2025-01-01",
          fiscal_period_end: "2025-12-31",
          created_at: "2026-01-01T00:00:00Z",
        },
      ]),
  });
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SPEC-305 notifications drawer", () => {
  it("sorts kinds into tabs and days into groups (ac1, ac2)", () => {
    expect(categoryOf("risk.approval_requested")).toBe("needs_you");
    expect(categoryOf("comment.mentioned")).toBe("mentions");
    expect(categoryOf("connection.created")).toBe("client");
    expect(categoryOf("agent.digest")).toBe("updates");
    const now = new Date("2026-10-20T15:00:00");
    expect(dayGroup("2026-10-20T08:00:00", now)).toBe("Today");
    expect(dayGroup("2026-10-19T23:00:00", now)).toBe("Yesterday");
    expect(dayGroup("2026-10-16T08:00:00", now)).toBe("Earlier this week");
    expect(dayGroup("2026-10-01T08:00:00", now)).toBe("Older");
  });

  it("shows groups and the engagement; a tab narrows; opening marks read and navigates (ac2-ac4)", async () => {
    const { calls } = page();
    renderRoutes([
      { path: "/", component: () => <NotificationDrawer open onOpenChange={() => undefined} /> },
      { path: "/engagements/$engagementId/planning", component: () => <p>Planning page</p> },
    ]);
    expect(
      await screen.findByText("Materiality is waiting for your decision.", {}, { timeout: 4000 }),
    ).toBeTruthy();
    expect(screen.getByRole("region", { name: "Today" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Older" })).toBeTruthy();
    expect((await screen.findAllByText(/Northwind · FY2025 audit/)).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("tab", { name: /Mentions/ }));
    expect(screen.queryByText("Materiality is waiting for your decision.")).toBeNull();
    expect(screen.getByText("You were mentioned in a comment.")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /All/ }));
    fireEvent.click(screen.getByText("Materiality is waiting for your decision."));
    await waitFor(() => {
      expect(
        calls.some((c) => c.method === "POST" && c.path === "/v1/notifications/n1/read"),
      ).toBe(true);
    });
    expect(await screen.findByText("Planning page")).toBeTruthy();
  });
});
