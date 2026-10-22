// SPEC-303 (TASK-304): the clients index and record, joined from visible engagements.
import type { EngagementSummaryOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { ClientRecord, Clients, groupClients } from "./Clients";

function eng(over: Partial<EngagementSummaryOut>): EngagementSummaryOut {
  return {
    id: "e1",
    name: "FY2025 audit",
    type: "fs_audit",
    service_line: "audit",
    status: "active",
    client_id: "c1",
    client_name: "Northwind Robotics",
    client_entity_id: "ce1",
    client_entity_name: "Northwind 401(k) Plan",
    fiscal_period_start: "2025-01-01",
    fiscal_period_end: "2025-12-31",
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const ENGAGEMENTS = [
  eng({}),
  eng({
    id: "e2",
    name: "FY2024 audit",
    status: "archived",
    fiscal_period_start: "2024-01-01",
    fiscal_period_end: "2024-12-31",
  }),
  eng({ id: "e3", client_entity_id: "ce2", client_entity_name: "Northwind Inc", name: "Review" }),
  eng({
    id: "e4",
    client_id: "c2",
    client_name: "Granite Peak",
    client_entity_id: "ce3",
    client_entity_name: "Granite Peak LLC",
    status: "archived",
  }),
];

function page(at: string) {
  mockApi({
    "GET /v1/engagements": () => json(ENGAGEMENTS),
    "GET /v1/firm/waiting/overdue": () => json([{ engagement_id: "e1", count: 3 }]),
    "GET /v1/engagements/e1": () =>
      json({
        ...ENGAGEMENTS[0],
        team: [{ user_id: "u1", display_name: "Dana Leader", role: "engagement_partner" }],
      }),
    "GET /v1/engagements/e3": () =>
      json({
        ...ENGAGEMENTS[2],
        team: [{ user_id: "u1", display_name: "Dana Leader", role: "manager" }],
      }),
  });
  renderRoutes(
    [
      { path: "/clients", component: Clients },
      { path: "/clients/$clientId", component: () => <ClientRecord clientId="c1" /> },
    ],
    { at },
  );
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SPEC-303 clients", () => {
  it("groups engagements by client and entity, newest year first (ac1)", () => {
    const [granite, northwind] = groupClients(ENGAGEMENTS, [{ engagement_id: "e1", count: 3 }]);
    expect(granite?.name).toBe("Granite Peak");
    expect(northwind?.entities.map((e) => e.name)).toEqual([
      "Northwind 401(k) Plan",
      "Northwind Inc",
    ]);
    expect(northwind?.entities[0]?.engagements.map((e) => e.id)).toEqual(["e1", "e2"]);
    expect(northwind?.active).toBe(2);
    expect(northwind?.overdue).toBe(3);
  });

  it("lists clients with active work; All shows the rest (ac2)", async () => {
    page("/clients");
    expect(await screen.findByText("Northwind Robotics")).toBeTruthy();
    expect(screen.getByText("2 entities")).toBeTruthy();
    expect(screen.queryByText("Granite Peak")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(await screen.findByText("Granite Peak")).toBeTruthy();
  });

  it("the record shows entities, engagements and the team on active work (ac3)", async () => {
    page("/clients/c1");
    expect(await screen.findByRole("heading", { name: "Northwind Robotics" })).toBeTruthy();
    expect(screen.getByText("FY2024 audit")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Northwind Inc" })).toBeTruthy();
    expect(await screen.findByText("Dana Leader")).toBeTruthy();
    expect(screen.getByText("Partner, Manager")).toBeTruthy();
  });
});
