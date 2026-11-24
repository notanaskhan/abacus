// C-02-T35 (TASK-8922; DEC-5924): CLS-11 a, a2, c, d and d2 render from their scenarios, whose
// console, log, failures and sync events are the exported Python scenario's. Tile counts match
// the table (7 posted batches January to July, 1 proposed August, 0 open failures); posted dates
// agree with ENG-02's deliveries; reconnect is the client's step, the firm only requests it, and
// "Request reconnect…" shows the POR-20 email before anything is sent; no credential field.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
  never,
} from "../../app-core/fixture-mode";
import exported from "../../fixtures/seed/scenario.cls11-console.json";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { CLS11, type Cls11Log } from "./index";
import { CLS11_CLOSE_ID, CLS11_ENTITY_ID, type Cls11State, scenarios } from "./scenarios";

let restore: (() => void) | null = null;
interface Call {
  method: string;
  path: string;
}

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(
  state: Cls11State,
  opts: { log?: Cls11Log; reconnectOpen?: boolean } = {},
  over: Record<string, FixtureHandler> = {},
): Call[] {
  const calls: Call[] = [];
  const base: Scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...base.handlers, ...over }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...base, handlers });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <CLS11
          clientEntityId={CLS11_ENTITY_ID}
          closeId={CLS11_CLOSE_ID}
          {...(opts.log === undefined ? {} : { log: opts.log })}
          {...(opts.reconnectOpen === undefined ? {} : { reconnectOpen: opts.reconnectOpen })}
        />
      ),
    },
  ]);
  return calls;
}

function kv(label: string): HTMLElement {
  const term = screen.getByText(label, { selector: "dt" });
  const row = term.parentElement;
  if (row === null) throw new Error(`no row ${label}`);
  return row;
}

function batch(code: string): HTMLElement {
  const row = document.querySelector<HTMLElement>(`[data-batch="${code}"]`);
  if (row === null) throw new Error(`no batch ${code}`);
  return row;
}

describe("CLS-11 Ledger sync console", () => {
  it("CLS-11a default: connected under Tess Moreno's authorization, July posted, August proposed", async () => {
    show("a");
    await screen.findByText(C.title);
    const tiles = document.querySelector<HTMLElement>('[data-cls11="tiles"]');
    expect(tiles?.textContent).toContain("7");
    expect(within(tiles as HTMLElement).getByText("Jul 31")).toBeTruthy();
    expect(screen.getByText(C.tiles.resolvedCaption(1, "Aug 11"))).toBeTruthy();
    expect(within(kv(C.connection.company)).getByText("Copperleaf Coffee Roasters")).toBeTruthy();
    expect(
      within(kv(C.connection.authorizedBy)).getByText("Tess Moreno (client portal) · Mar 9, 2026"),
    ).toBeTruthy();
    expect(kv(C.connection.mode).textContent).toContain(C.connection.modeWrite);
    expect(kv(C.connection.lastSync).textContent).toContain(
      "9:02 AM · 1,214 transactions read · 0 errors",
    );
    expect(kv(C.connection.nextSync).textContent).toContain("10:02 AM (hourly)");
    expect(kv(C.connection.closingDate).textContent).toContain(
      "Jul 31, 2026 · set by Raj Malhotra, Aug 11, 2:42 PM",
    );
    expect(kv(C.connection.writeScope).textContent).toContain(C.connection.writeScopeValue);
    expect(kv(C.connection.agents).textContent).toContain(
      "Close agent · Close Planner · 1099 vendor screen",
    );
    await waitFor(() => {
      expect(document.querySelectorAll("[data-batch]")).toHaveLength(8);
    });
    expect(within(batch("2026-08-A")).getByText("$34,920.00")).toBeTruthy();
    expect(within(batch("2026-08-A")).getByText(C.log.approved(0, 5))).toBeTruthy();
    const july = batch("2026-07-A");
    expect(within(july).getByText("$31,480.00")).toBeTruthy();
    expect(within(july).getByText("Aug 11, 2:41 PM")).toBeTruthy();
    expect(within(july).getByText("QBO 47602–47607")).toBeTruthy();
    expect(within(july).getByText(C.log.resolved(1))).toBeTruthy();
    expect(within(july).getByText("Raj Malhotra")).toBeTruthy();
    const failures = document.querySelector<HTMLElement>('[data-cls11="failures"]');
    expect(failures?.textContent).toContain("Aug 11, 2:38 PM · 2026-07-A · AJE-03 Depreciation");
    expect(failures?.textContent).toContain(
      "QuickBooks Online: account 'Accumulated Depreciation' is inactive",
    );
    expect(failures?.textContent).toContain(C.log.resolvedBy("Raj Malhotra", "2:41 PM"));
  });

  it("CLS-11 acceptance: tile counts match the table and posted dates agree with ENG-02", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-batch]")).toHaveLength(8);
    });
    const posted = exported.batches.filter((b) => b.status === "posted");
    expect(exported.tiles.posted).toBe(posted.length);
    expect(exported.tiles.proposed).toBe(
      exported.batches.filter((b) => b.status === "proposed").length,
    );
    expect(exported.tiles.failed_post).toBe(0);
    expect(within(batch("2026-05-A")).getByText("Jun 10, 3:18 PM")).toBeTruthy();
    expect(within(batch("2026-06-A")).getByText("Jul 10, 11:05 AM")).toBeTruthy();
    expect(within(batch("2026-07-A")).getByText("Aug 11, 2:41 PM")).toBeTruthy();
    expect(exported.august_posted.amount).toBe("35300.00");
  });

  it("the Posted tile filters the log to posted batches", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-batch]")).toHaveLength(8);
    });
    fireEvent.click(screen.getByRole("button", { name: /Posted/ }));
    await waitFor(() => {
      expect(document.querySelectorAll("[data-batch]")).toHaveLength(7);
    });
    expect(document.querySelector('[data-batch="2026-08-A"]')).toBeNull();
  });

  it("CLS-11a2 sync events: today's syncs, then the Aug 11 failure, post and closing date", async () => {
    show("a2", { log: "events" });
    const events = await screen.findByText(C.events.closingDate("Jul 31, 2026"));
    const list = events.closest<HTMLElement>('[data-cls11="events"]') as HTMLElement;
    expect(within(list).getByText(C.events.today("Monday, September 14"))).toBeTruthy();
    expect(within(list).getByText(C.events.syncRead("1,214"))).toBeTruthy();
    expect(within(list).getByText(C.events.syncRead("1,209"))).toBeTruthy();
    expect(within(list).getByText(C.events.posted("2026-07-A", 6))).toBeTruthy();
    expect(within(list).getByText(C.events.failedPost("AJE-03"))).toBeTruthy();
    expect(within(list).getAllByText("Raj Malhotra").length).toBeGreaterThan(0);
  });

  it("CLS-11c needs attention: the 10:02 AM rate limit retrying at 10:07 AM", async () => {
    show("c");
    await screen.findByText(C.title);
    expect(screen.getAllByText("Needs attention").length).toBeGreaterThan(0);
    expect(kv(C.connection.lastSync).textContent).toContain(
      C.connection.failedRateLimit("10:02 AM", "10:07 AM"),
    );
    expect(kv(C.connection.nextSync).textContent).toContain("10:07 AM (retry)");
    expect(screen.getByRole("button", { name: C.connection.retryNow })).toBeTruthy();
  });

  it("CLS-11d needs reauth: the banner, posting paused, Sync now off", async () => {
    show("d");
    expect(await screen.findByText(C.banner.expired("Copperleaf", "Tess Moreno"))).toBeTruthy();
    expect(screen.getAllByText("Needs reauth").length).toBeGreaterThan(0);
    expect(kv(C.connection.lastSync).textContent).toContain(C.connection.failedExpired("9:02 AM"));
    expect(kv(C.connection.nextSync).textContent).toContain(C.connection.paused("Tess Moreno"));
    expect(kv(C.connection.authorizedBy).textContent).toContain(C.connection.expired);
    const sync = screen.getByRole("button", { name: C.connection.syncNow });
    expect((sync as HTMLButtonElement).disabled).toBe(true);
    await waitFor(() => {
      expect(batch("2026-08-A").textContent).toContain(
        `${C.log.approved(0, 5)} · ${C.log.postingPaused}`,
      );
    });
  });

  it("CLS-11d2 acceptance: Request reconnect shows the POR-20 preview before sending", async () => {
    const calls = show("d2", { reconnectOpen: true });
    const dialog = await screen.findByRole("dialog", { name: C.dialog.title });
    await within(dialog).findByText(
      C.dialog.toValue(["Tess Moreno"], "Copperleaf Coffee Roasters"),
    );
    expect(within(dialog).getByText(C.dialog.sendsValue)).toBeTruthy();
    expect(within(dialog).getByText(C.dialog.reconnectsInValue)).toBeTruthy();
    expect(within(dialog).getByTitle(C.dialog.preview).tagName).toBe("IFRAME");
    expect(within(dialog).getByText(/Please reconnect QuickBooks Online/)).toBeTruthy();
    expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/reconnect-requests"))).toBe(
      false,
    );
    fireEvent.click(within(dialog).getByRole("button", { name: C.dialog.send }));
    expect(await screen.findByText(C.banner.sent("Tess Moreno", "9:14 AM"))).toBeTruthy();
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([
      expect.stringMatching(/\/reconnect-requests$/),
    ]);
  });

  it("CLS-11 acceptance: the console never shows a credential field", async () => {
    show("d2", { reconnectOpen: true });
    await screen.findByRole("dialog", { name: C.dialog.title });
    expect(document.querySelector('input[type="password"]')).toBeNull();
    expect(screen.queryByLabelText(/password/i)).toBeNull();
  });

  it("Sync now pulls once and shows the spinner on Last sync", async () => {
    const calls = show("a");
    fireEvent.click(await screen.findByRole("button", { name: C.connection.syncNow }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/ledger-pull"))).toBe(true);
    });
  });

  it("loading: the console holds skeletons while the read is pending", async () => {
    show("a", {}, { "GET /v1/client-entities/{client_entity_id}/ledger-console": () => never() });
    await waitFor(() => {
      expect(document.querySelector('[data-screen="CLS-11"][aria-busy="true"]')).not.toBeNull();
    });
  });

  it("error: a failed read offers Retry", async () => {
    show(
      "a",
      {},
      {
        "GET /v1/client-entities/{client_entity_id}/ledger-console": () =>
          json({ detail: "boom" }, 500),
      },
    );
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: C.retryLoad })).toBeTruthy();
  });

  it("not allowed: a walled entity's 404 reads as the error state, never another entity", async () => {
    show(
      "a",
      {},
      {
        "GET /v1/client-entities/{client_entity_id}/ledger-console": () =>
          json({ detail: "not found" }, 404),
      },
    );
    expect(await screen.findByText(C.failedToLoad)).toBeTruthy();
    expect(screen.queryByText("Copperleaf Coffee Roasters, Inc.")).toBeNull();
  });

  it("empty: no batch matches the filters", async () => {
    show(
      "a",
      {},
      {
        "GET /v1/client-entities/{client_entity_id}/posting-batches": () =>
          json({ items: [], total: 0 }),
      },
    );
    expect(await screen.findByText(C.log.empty)).toBeTruthy();
  });

  it("the back chip opens the August 2026 close (CLS-02)", async () => {
    show("a");
    const back = await screen.findByRole("link", { name: C.back("August 2026") });
    expect(back.getAttribute("href")).toContain(CLS11_CLOSE_ID);
  });

  it("no agent-owned control approves, signs off, releases, sends or posts", async () => {
    show("a");
    await screen.findByText(C.title);
    for (const word of ["Approve", "Sign off", "Release", "Post"]) {
      expect(screen.queryByRole("button", { name: new RegExp(`^${word}`) })).toBeNull();
    }
  });
});
