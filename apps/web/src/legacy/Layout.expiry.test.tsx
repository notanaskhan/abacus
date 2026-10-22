// A separate file from Layout.test.tsx: `signIn` is latched per page load, so each redirect
// needs its own module registry.
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { accessToken } from "../auth/session";
import { json, mockApi, renderRoutes, signInForTest, stubLocation } from "../testing/support";
import { Layout } from "./Layout";

const ROUTES = [{ path: "/", component: () => <p>Page body</p> }];

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac1 Layout, session over", () => {
  it("sends the user back through sign-in when the API answers 401", async () => {
    const { assign } = stubLocation();
    mockApi({ "GET /v1/me": () => json({ detail: "Unauthorized" }, 401) });
    renderRoutes(ROUTES, { root: Layout });
    await waitFor(() => {
      expect(assign).toHaveBeenCalled();
    });
    expect(String(assign.mock.calls[0]?.[0])).toContain("/authorize?");
    expect(accessToken()).toBeNull();
    expect(screen.queryByText("Page body")).toBeNull();
  });
});
