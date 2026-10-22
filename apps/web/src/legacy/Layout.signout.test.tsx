// A separate file from Layout.test.tsx: `signIn` is latched per page load, so each redirect
// needs its own module registry.
import type { MeOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { accessToken } from "../auth/session";
import { json, mockApi, renderRoutes, signInForTest, stubLocation } from "../testing/support";
import { Layout } from "./Layout";

const ROUTES = [{ path: "/", component: () => <p>Page body</p> }];

const ME: MeOut = {
  user_id: "u1",
  display_name: "Dana Leader",
  email: "dana@dev.abacus.local",
  active_tenant_id: "t1",
  server_now: "2026-09-14T14:24:00Z",
  clock_mode: "real",
  memberships: [{ tenant_id: "t1", firm_name: "Dev firm", firm_role: "practice_leader" }],
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

describe("ac1 Layout, sign out", () => {
  it("ends the server session, then drops the token and starts sign-in again", async () => {
    const { assign } = stubLocation();
    const { calls } = mockApi({
      "GET /v1/me": () => json(ME),
      // P-01 AC 2.1.6 (P-01-T08): the menu ends the staff session first, with the bearer token.
      "POST /v1/auth/sign-out": () => json({ ended: true }),
    });
    renderRoutes(ROUTES, { root: Layout });
    // SHL-03 (F-05-T23): Sign out is in the firm pill's menu.
    fireEvent.click(await screen.findByRole("button", { name: "Dev firm" }));
    expect(accessToken()).toBe("tok");
    fireEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
    await waitFor(() => {
      expect(accessToken()).toBeNull();
    });
    const signOut = calls.find((c) => c.method === "POST" && c.path === "/v1/auth/sign-out");
    expect(signOut?.headers.get("authorization")).toBe("Bearer tok");
    await waitFor(() => {
      expect(assign).toHaveBeenCalled();
    });
  });
});
