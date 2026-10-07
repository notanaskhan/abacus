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
  it("drops the token and starts sign-in again", async () => {
    const { assign } = stubLocation();
    mockApi({ "GET /v1/me": () => json(ME) });
    renderRoutes(ROUTES, { root: Layout });
    await screen.findByText(/Dev firm/);
    expect(accessToken()).toBe("tok");
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(accessToken()).toBeNull();
    await waitFor(() => {
      expect(assign).toHaveBeenCalled();
    });
  });
});
