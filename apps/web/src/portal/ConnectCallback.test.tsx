// A-02-T33 (DEC-3902): the provider's return page in the portal entry. On the connect host it
// sends the browser to the host the API stored for the state, with the provider's query
// unchanged; on that host it completes with the portal session and returns to Connections.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as bff from "../app-core/auth/bff";
import { json, mockApi } from "../testing/support";
import { PortalConnectCallback, handBackUrl } from "./ConnectCallback";

const CONNECT = "connect.example.test";
const FIRM = "acme.example.test";

function at(hostname: string, search: string): { assign: ReturnType<typeof vi.fn> } {
  const assign = vi.fn();
  vi.stubGlobal("location", {
    assign,
    replace: vi.fn(),
    hostname,
    search,
    pathname: "/client/connect/callback",
    origin: `https://${hostname}`,
    href: `https://${hostname}/client/connect/callback${search}`,
  });
  return { assign };
}

function page(signedIn = true): { leave: ReturnType<typeof vi.fn> } {
  const leave = vi.fn();
  render(<PortalConnectCallback leave={leave} ensureSession={() => Promise.resolve(signedIn)} />);
  return { leave };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("on the connect host", () => {
  it("sends the browser to the stored host with the provider's query unchanged", async () => {
    const search = "?state=s1&code=c1&realmId=r9";
    at(CONNECT, search);
    const { calls } = mockApi({
      "POST /v1/connections/handoff": () => json({ origin_host: FIRM }),
    });
    const { leave } = page();
    await waitFor(() => {
      expect(leave).toHaveBeenCalledWith(`https://${FIRM}/client/connect/callback${search}`);
    });
    expect(calls.find((c) => c.path === "/v1/connections/handoff")?.body).toEqual({
      state: "s1",
    });
    expect(calls.some((c) => c.path === "/v1/connections/complete")).toBe(false);
  });

  it("never takes the host from a tampered query", async () => {
    const search = "?state=s1&code=c1&origin_host=evil.example&redirect=https://evil.example";
    at(CONNECT, search);
    mockApi({ "POST /v1/connections/handoff": () => json({ origin_host: FIRM }) });
    const { leave } = page();
    await waitFor(() => {
      expect(leave).toHaveBeenCalledTimes(1);
    });
    expect(new URL(String(leave.mock.calls[0]?.[0])).host).toBe(FIRM);
  });

  it("shows one neutral error for a state the API refuses, and goes nowhere", async () => {
    at(CONNECT, "?state=spent&code=c1");
    mockApi({ "POST /v1/connections/handoff": () => json({ detail: "not found" }, 404) });
    const { leave } = page();
    expect(await screen.findByText(/expired or was already used/)).toBeTruthy();
    expect(leave).not.toHaveBeenCalled();
  });

  it("refuses an answer that is not a host name", () => {
    for (const bad of ["evil.example/x", "user@evil.example", "evil.example:8443", "", "EVIL"]) {
      expect(handBackUrl(bad, "?state=s1")).toBeNull();
    }
    expect(handBackUrl(FIRM, "?state=s1")).toBe(
      `https://${FIRM}/client/connect/callback?state=s1`,
    );
  });
});

describe("on the host the flow began on", () => {
  it("completes with the portal session and returns to the entity's Connections", async () => {
    const { assign } = at(FIRM, "?state=s1&code=c1&realmId=r9");
    const { calls } = mockApi({
      "POST /v1/connections/handoff": () => json({ origin_host: FIRM }),
      "POST /v1/connections/complete": () =>
        json({ engagement_id: "g1", client_entity_id: "e1", reconnected: false }, 201),
    });
    const { leave } = page();
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith("/connections?entity=e1");
    });
    expect(calls.find((c) => c.path === "/v1/connections/complete")?.body).toEqual({
      state: "s1",
      code: "c1~r9",
    });
    expect(leave).not.toHaveBeenCalled();
  });

  it("explains a refused completion in plain words", async () => {
    at(FIRM, "?state=s1&code=c1");
    mockApi({
      "POST /v1/connections/handoff": () => json({ origin_host: FIRM }),
      "POST /v1/connections/complete": () => json({ detail: "invalid_state" }, 409),
    });
    page();
    expect(await screen.findByText(/expired or was already used/)).toBeTruthy();
  });

  it("signs in without the code in any URL, then completes from this tab's storage", async () => {
    at(FIRM, "?state=s1&code=c1");
    const signIn = vi.spyOn(bff, "goToSignIn").mockImplementation(() => undefined);
    const { calls } = mockApi({
      "POST /v1/connections/handoff": () => json({ origin_host: FIRM }),
      "POST /v1/connections/complete": () =>
        json({ engagement_id: "g1", client_entity_id: "e1", reconnected: false }, 201),
    });
    page(false);
    await waitFor(() => {
      expect(signIn).toHaveBeenCalledWith("/client/connect/callback");
    });
    expect(calls.some((c) => c.path === "/v1/connections/complete")).toBe(false);
    cleanup();
    const { assign } = at(FIRM, "");
    page(true);
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith("/connections?entity=e1");
    });
    expect(calls.find((c) => c.path === "/v1/connections/complete")?.body).toEqual({
      state: "s1",
      code: "c1",
    });
    expect(sessionStorage.length).toBe(0);
  });
});
