// SPEC-302 (TASK-303): ⌘K opens the palette; engagements filter on the client, request items and
// findings come from the server, and Enter goes to the chosen record.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { matches, Palette } from "./Palette";

const ENG = {
  id: "e1",
  name: "FY2025 audit",
  client_name: "Northwind Robotics",
  client_entity_name: "Northwind Robotics 401(k) Plan",
  client_id: "c1",
  client_entity_id: "ce1",
  status: "active",
  type: "fs_audit",
  service_line: "audit",
  created_at: "2026-09-01T00:00:00Z",
  fiscal_period_start: "2025-01-01",
  fiscal_period_end: "2025-12-31",
};

function page() {
  const api = mockApi({
    "GET /v1/engagements": () => json([ENG]),
    "GET /v1/firm/search/request-items": () =>
      json([
        {
          id: "i1",
          engagement_id: "e1",
          description: "Bank statements December",
          audit_area: "Cash",
          status: "requested",
        },
      ]),
    "GET /v1/firm/search/findings": () => json([]),
  });
  renderRoutes([
    {
      path: "/",
      component: () => <Palette isAdmin={false} onNotifications={() => undefined} />,
    },
    { path: "/engagements/$engagementId/items/$itemId", component: () => <p>Item page</p> },
  ]);
  return api;
}

beforeEach(async () => {
  sessionStorage.clear();
  localStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SPEC-302 command palette", () => {
  it("matches every word, ignoring case (ac1)", () => {
    expect(matches("Northwind Robotics FY2025", "north fy")).toBe(true);
    expect(matches("Northwind Robotics", "granite")).toBe(false);
  });

  it("⌘K opens it; typing finds the client and a request item; Enter opens it (ac1-ac3)", async () => {
    const { calls } = page();
    await screen.findByRole("button", { name: "Search (⌘K)" });
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const input = await screen.findByRole("combobox", { name: "Search" });
    expect(await screen.findByText("Engagements")).toBeTruthy(); // Go to
    fireEvent.change(input, { target: { value: "bank" } });
    expect(await screen.findByText("Bank statements December")).toBeTruthy();
    expect(calls.some((c) => c.path === "/v1/firm/search/request-items")).toBe(true);
    fireEvent.change(input, { target: { value: "northwind" } });
    expect((await screen.findAllByText("Northwind Robotics")).length).toBe(2); // client, engagement
    fireEvent.change(input, { target: { value: "bank" } });
    await screen.findByText("Bank statements December");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("Item page")).toBeTruthy();
  });

  it("says when nothing matches (ac1)", async () => {
    page();
    fireEvent.click(await screen.findByRole("button", { name: "Search (⌘K)" }));
    fireEvent.change(await screen.findByRole("combobox", { name: "Search" }), {
      target: { value: "zzzz" },
    });
    await waitFor(() => {
      expect(screen.getByText("Nothing matches “zzzz”.")).toBeTruthy();
    });
  });
});
