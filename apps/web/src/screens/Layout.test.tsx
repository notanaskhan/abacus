import type { MeOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest, stubLocation } from "../testing/support";
import { Layout } from "./Layout";

const ROUTES = [{ path: "/", component: () => <p>Page body</p> }];

function me(over: Partial<MeOut> = {}): MeOut {
  return {
    user_id: "u1",
    display_name: "Dana Leader",
    email: "dana@dev.abacus.local",
    active_tenant_id: "t1",
    memberships: [{ tenant_id: "t1", firm_name: "Dev firm", firm_role: "practice_leader" }],
    ...over,
  };
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac1 Layout, signed out", () => {
  it("shows the splash and redirects to sign-in without calling the API", async () => {
    const { assign } = stubLocation("/engagements/e1");
    const { calls } = mockApi({});
    renderRoutes(ROUTES, { root: Layout });
    expect((await screen.findByRole("heading", { name: "Abacus" })).textContent).toBe("Abacus");
    expect(screen.getByText("Redirecting to sign-in…")).toBeTruthy();
    await waitFor(() => {
      expect(assign).toHaveBeenCalledOnce();
    });
    expect(String(assign.mock.calls[0]?.[0])).toContain("/authorize?");
    expect(calls).toHaveLength(0);
    expect(screen.queryByText("Page body")).toBeNull();
  });
});

describe("ac1 Layout, signed in", () => {
  beforeEach(async () => {
    await signInForTest();
  });

  it("shows who is signed in and the firm name, with the page below", async () => {
    mockApi({ "GET /v1/me": () => json(me()) });
    renderRoutes(ROUTES, { root: Layout });
    expect(await screen.findByText(/Dana Leader · Dev firm/)).toBeTruthy();
    expect(screen.getByText("Page body")).toBeTruthy();
  });

  it("sends the bearer token and no tenant header when the server picked the firm", async () => {
    const { calls } = mockApi({ "GET /v1/me": () => json(me()) });
    renderRoutes(ROUTES, { root: Layout });
    await screen.findByText(/Dev firm/);
    const first = calls[0];
    expect(first?.headers.get("Authorization")).toBe("Bearer tok");
    expect(first?.headers.get("X-Abacus-Tenant")).toBeNull();
  });

  const SEVERAL = me({
    active_tenant_id: null,
    memberships: [
      { tenant_id: "t1", firm_name: "Alpha LLP", firm_role: null },
      { tenant_id: "t2", firm_name: "Beta & Co", firm_role: null },
    ],
  });

  it("asks the user to choose a firm when there are several and none is active", async () => {
    const { calls } = mockApi({ "GET /v1/me": () => json(SEVERAL) });
    renderRoutes(ROUTES, { root: Layout });
    expect(await screen.findByText("Choose a firm")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Alpha LLP" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Beta & Co" })).toBeTruthy();
    expect(screen.queryByText("Page body")).toBeNull();
    expect(calls[0]?.headers.get("X-Abacus-Tenant")).toBeNull();
  });

  it("sends the chosen firm as X-Abacus-Tenant on later requests", async () => {
    const { calls } = mockApi({ "GET /v1/me": () => json(SEVERAL) });
    renderRoutes(ROUTES, { root: Layout });
    fireEvent.click(await screen.findByRole("button", { name: "Beta & Co" }));
    await waitFor(() => {
      expect(calls.some((c) => c.headers.get("X-Abacus-Tenant") === "t2")).toBe(true);
    });
    expect(calls.some((c) => c.headers.get("X-Abacus-Tenant") === "t1")).toBe(false);
  });

  it("shows the app for the chosen firm after the choice", async () => {
    // Like the real /v1/me, which names an active firm only when the user has exactly one.
    mockApi({ "GET /v1/me": () => json(SEVERAL) });
    renderRoutes(ROUTES, { root: Layout });
    fireEvent.click(await screen.findByRole("button", { name: "Beta & Co" }));
    expect(await screen.findByText(/Dana Leader · Beta & Co/)).toBeTruthy();
    expect(screen.getByText("Page body")).toBeTruthy();
    expect(screen.queryByText("Choose a firm")).toBeNull();
  });

  it("shows an alert with Retry when the account can't be loaded", async () => {
    let attempts = 0;
    mockApi({
      "GET /v1/me": () => {
        attempts += 1;
        return attempts === 1 ? json({ detail: "Down" }, 500) : json(me());
      },
    });
    renderRoutes(ROUTES, { root: Layout });
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Couldn't load your account");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/Dev firm/)).toBeTruthy();
  });
});
