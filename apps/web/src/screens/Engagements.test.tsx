import type { EngagementSummaryOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, never, renderRoutes, signInForTest } from "../testing/support";
import { Engagements } from "./Engagements";

const ROUTES = [
  { path: "/", component: Engagements },
  { path: "/engagements/$engagementId", component: () => <p>Board page</p> },
];

function engagement(id: string, name: string): EngagementSummaryOut {
  return {
    id,
    name,
    client_name: "Acme",
    client_entity_name: "Acme Holdings",
    fiscal_period_start: "2025-01-01",
    fiscal_period_end: "2025-12-31",
    status: "active",
    type: "audit",
    created_at: "2025-01-02T00:00:00Z",
  };
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

describe("ac18 Engagements screen", () => {
  it("shows a busy skeleton while loading", async () => {
    mockApi({ "GET /v1/engagements": never });
    const { container } = renderRoutes(ROUTES);
    await waitFor(() => {
      expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
    });
    expect(screen.queryByText("No engagements yet")).toBeNull();
  });

  it("shows the empty state with a create button", async () => {
    mockApi({ "GET /v1/engagements": () => json([]) });
    renderRoutes(ROUTES);
    expect(await screen.findByText("No engagements yet")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /new engagement/i }).length).toBeGreaterThan(0);
  });

  it("shows an error alert with Retry, and Retry reloads", async () => {
    let attempts = 0;
    const { calls } = mockApi({
      "GET /v1/engagements": () => {
        attempts += 1;
        return attempts === 1
          ? json({ detail: "The database is down" }, 500)
          : json([engagement("e1", "FY25 audit")]);
      },
    });
    renderRoutes(ROUTES);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Couldn't load engagements");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("FY25 audit")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(calls.filter((c) => c.path === "/v1/engagements")).toHaveLength(2);
  });

  it("lists engagements with client, period, status and a link to each board", async () => {
    mockApi({
      "GET /v1/engagements": () =>
        json([engagement("e1", "FY25 audit"), engagement("e2", "FY24")]),
    });
    renderRoutes(ROUTES);
    const link = await screen.findByRole("link", { name: "FY25 audit" });
    expect(link.getAttribute("href")).toBe("/engagements/e1");
    expect(screen.getByRole("link", { name: "FY24" }).getAttribute("href")).toBe(
      "/engagements/e2",
    );
    expect(screen.getAllByText(/Acme/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/2025-01-01/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("active").length).toBe(2);
  });

  it("creates an engagement with the five fields and refreshes the list", async () => {
    let created = false;
    const { calls } = mockApi({
      "GET /v1/engagements": () => json(created ? [engagement("e9", "New audit")] : []),
      "POST /v1/engagements": () => {
        created = true;
        return json(
          {
            ...engagement("e9", "New audit"),
            team: [],
          },
          201,
        );
      },
    });
    renderRoutes(ROUTES);
    await screen.findByText("No engagements yet");

    fireEvent.click(screen.getAllByRole("button", { name: /new engagement/i })[0] as HTMLElement);
    const fill = (label: string, value: string): void => {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    };
    fill("Engagement name", "New audit");
    fill("Client", "Acme");
    fill("Client entity", "Acme Holdings");
    fill("Fiscal year start", "2025-01-01");
    fill("Fiscal year end", "2025-12-31");
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));

    expect(await screen.findByRole("link", { name: "New audit" })).toBeTruthy();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.path).toBe("/v1/engagements");
    expect(post?.body).toEqual({
      name: "New audit",
      client_name: "Acme",
      client_entity_name: "Acme Holdings",
      fiscal_period_start: "2025-01-01",
      fiscal_period_end: "2025-12-31",
      type: "audit", // SPEC-024: the default engagement type
    });
    expect(calls.filter((c) => c.method === "GET" && c.path === "/v1/engagements")).toHaveLength(
      2,
    );
  });

  it("shows an error in the dialog when creation fails, and keeps the dialog open", async () => {
    mockApi({
      "GET /v1/engagements": () => json([]),
      "POST /v1/engagements": () => json({ detail: "Not allowed" }, 403),
    });
    renderRoutes(ROUTES);
    await screen.findByText("No engagements yet");
    fireEvent.click(screen.getAllByRole("button", { name: /new engagement/i })[0] as HTMLElement);
    for (const [label, value] of [
      ["Engagement name", "X"],
      ["Client", "Y"],
      ["Client entity", "Z"],
      ["Fiscal year start", "2025-01-01"],
      ["Fiscal year end", "2025-12-31"],
    ] as const) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));
    const alert = await screen.findByText("Couldn't create the engagement");
    expect(alert).toBeTruthy();
    expect(screen.getByLabelText("Engagement name")).toBeTruthy();
  });
});
