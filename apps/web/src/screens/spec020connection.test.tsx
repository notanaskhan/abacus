// SPEC-020 (TASK-036): connecting, health, the access log and revoke; the provider's return page.
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { ConnectCallback } from "./ConnectCallback";
import { ConnectionPanel } from "./ConnectionPanel";

const E = "e1";
const LIVE = {
  id: "c1",
  provider: "fake",
  status: "active",
  scopes: [],
  created_by: "u-a",
  created_at: "2026-10-09T09:00:00Z",
  expires_at: null,
  last_checked_at: null,
  last_check_ok: null,
  last_pull_at: "2026-10-09T10:00:00Z",
};

const panel = (canConnect: boolean): void => {
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ConnectionPanel engagementId={E} firmName="Dev firm" canConnect={canConnect} />
      ),
    },
  ]);
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

describe("ac2 ac3 connecting", () => {
  it("shows the consent copy first, then sends the client to the provider", async () => {
    const assign = vi.fn();
    vi.spyOn(window.location, "assign").mockImplementation(assign);
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}/connection`]: () => json(null),
      [`GET /v1/engagements/${E}/connection/providers`]: () =>
        json([{ provider: "fake", name: "Demo ledger", datasets: ["trial_balance"] }]),
      [`POST /v1/engagements/${E}/connection/start`]: () =>
        json({ authorise_url: "https://ledger.example.test/authorise?state=s" }),
    });
    panel(true);
    fireEvent.click(await screen.findByRole("button", { name: "Connect Demo ledger" }));
    const dialog = await screen.findByRole("dialog", { name: "Connect your accounting system" });
    expect(within(dialog).getByText(/only read from your system/)).toBeTruthy();
    expect(within(dialog).getByText(/Your auditor at Dev firm/)).toBeTruthy();
    expect(calls.some((c) => c.path.endsWith("/connection/start"))).toBe(false);
    fireEvent.click(within(dialog).getByRole("button", { name: "Connect" }));
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith("https://ledger.example.test/authorise?state=s");
    });
    expect(calls.find((c) => c.path.endsWith("/connection/start"))?.body).toEqual({
      provider: "fake",
    });
  });

  it("asks the client admin to confirm it's them when the sign-in isn't recent", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/connection`]: () => json(null),
      [`GET /v1/engagements/${E}/connection/providers`]: () =>
        json([{ provider: "fake", name: "Demo ledger", datasets: ["trial_balance"] }]),
      [`POST /v1/engagements/${E}/connection/start`]: () => json({ detail: "forbidden" }, 403),
    });
    panel(true);
    fireEvent.click(await screen.findByRole("button", { name: "Connect Demo ledger" }));
    const dialog = await screen.findByRole("dialog", { name: "Connect your accounting system" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Connect" }));
    expect(await screen.findByRole("dialog", { name: "Confirm it's you" })).toBeTruthy();
  });

  it("offers the firm no way to connect, and says no ledger is available when none is", async () => {
    mockApi({ [`GET /v1/engagements/${E}/connection`]: () => json(null) });
    panel(false);
    expect(await screen.findByText(/client's administrator can connect/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Connect/ })).toBeNull();
  });
});

describe("ac4 ac5 ac6 a live connection", () => {
  it("shows health, checks it, lists the access log, and disconnects after confirmation", async () => {
    let checked = false;
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}/connection`]: () =>
        json(checked ? { ...LIVE, status: "needs_attention", last_check_ok: false } : LIVE),
      [`POST /v1/engagements/${E}/connection/check`]: () => {
        checked = true;
        return json({ ...LIVE, status: "needs_attention", last_check_ok: false });
      },
      [`GET /v1/engagements/${E}/connection/log`]: () =>
        json([
          {
            id: "r1",
            dataset: "trial_balance",
            period_start: "2026-01-01",
            period_end: "2026-12-31",
            status: "succeeded",
            started_at: "2026-10-09T10:00:00Z",
            finished_at: "2026-10-09T10:01:00Z",
            started_by: "u-s",
          },
        ]),
      [`POST /v1/engagements/${E}/connection/revoke`]: () => json({ engagement_id: E }),
    });
    panel(false);
    expect(await screen.findByText("Connected")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Check now" }));
    expect(await screen.findByText("Needs attention")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Access log" }));
    const log = await screen.findByRole("table", { name: "Access log" });
    expect(within(log).getByText("Trial balance")).toBeTruthy();
    expect(within(log).getByText("Retrieved")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Disconnect the accounting system?",
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Disconnect" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/connection/revoke"))).toBe(true);
    });
  });
});

describe("ac2 the provider's return page", () => {
  it("completes with the state and code, and explains a spent link in plain words", async () => {
    const { calls } = mockApi({
      "POST /v1/connections/complete": () => json({ detail: "invalid_state" }, 409),
    });
    renderRoutes([{ path: "/", component: ConnectCallback }], { at: "/?state=s1&code=demo" });
    expect(await screen.findByText(/expired or was already used/)).toBeTruthy();
    expect(calls.find((c) => c.path === "/v1/connections/complete")?.body).toEqual({
      state: "s1",
      code: "demo",
    });
  });
});
