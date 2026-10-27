// POR-16 · Connections (A-02-T18). One test per artboard on its fixture scenario (a–g), the 390
// layout, and the row's acceptance: "POR-16a–g render from their scenarios, Continue stays
// disabled until the toggle is on, and no write scope or vendor logo appears." The live swap and
// the OAuth round trip are A-02-T28's; the server half is A-02-T16's
// (backend/tests/integration/backfill/test_a02t16_entity_connections.py). Playwright is not run.
import { Toaster } from "@abacus/ui";
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { connectionsHandlers } from "../../fixtures/handlers/connections";
import { portalHandlers } from "../../fixtures/handlers/portal";
import { POR16_CLOCKS } from "../../fixtures/seed/connections";
import { renderRoutes } from "../../testing/support";
import { PortalConnections, glyphOf, safeSignIn } from ".";
import { ARTBOARD, type Por16State, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
  authorised: string[];
}

function show(state: Por16State, options: { mobile?: boolean } = {}): Seen {
  const seen: Seen = { calls: [], authorised: [] };
  const scenario = scenarios[state];
  const clock = scenario.clock ?? POR16_CLOCKS.a;
  // Fresh handlers per test: a disconnect or a retry changes the fixture's own state.
  const fresh = { ...portalHandlers({ clock }), ...connectionsHandlers(state, { clock }) };
  const handlers = Object.fromEntries(
    Object.entries(fresh).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const board = ARTBOARD[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <>
          <PortalConnections
            mobile={options.mobile === true}
            {...(board.sheet === undefined ? {} : { sheet: board.sheet })}
            {...(board.dialog === undefined ? {} : { dialog: board.dialog })}
            onAuthorise={(url) => {
              seen.authorised.push(url);
            }}
          />
          <Toaster />
        </>
      ),
    },
  ]);
  return seen;
}

async function card(name: string): Promise<HTMLElement> {
  // `hidden`: behind an open sheet or dialog the page is inert to assistive technology.
  return screen.findByRole("listitem", { name, hidden: true });
}

// Never the product, a posting scope or copy (DF-19), or a password field.
const BANNED = [/Accrued/, /post entries/i, /post approved/i, /posts only/i, /accept entries/i];

function avoid(): void {
  const text = document.body.textContent;
  for (const word of BANNED) expect(text).not.toMatch(word);
  expect(document.querySelector('input[type="password"]')).toBeNull();
  // Lucide glyph tiles only: no vendor logo image anywhere on the page.
  expect(document.querySelectorAll("[data-connection] img")).toHaveLength(0);
}

describe("POR-16 artboards", () => {
  it("defines a to g, all Tess Moreno's", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
    for (const s of STATES) expect(scenarios[s].persona).toBe("tess-moreno");
  });

  it("POR-16a default: six cards with registry status words and their detail lines", async () => {
    show("a");
    const qbo = await card("QuickBooks Online");
    expect(within(qbo).getByText("Connected")).toBeTruthy();
    expect(
      within(qbo).getByText("Connected by Tess Moreno · Mar 4, 2026 · last sync 9:15 AM"),
    ).toBeTruthy();
    expect(within(qbo).getByText("Read ledger")).toBeTruthy();
    const bank = await card("Front Range Bank ••4410");
    expect(within(bank).getByText("Bank feed · daily · last sync 6:02 AM")).toBeTruthy();
    expect(within(bank).getByText("Read transactions and statements")).toBeTruthy();
    const amex = await card("American Express ••1009");
    expect(within(amex).getByText("Needs reauth")).toBeTruthy();
    expect(
      within(amex).getByText(
        "American Express asks you to sign in again every 90 days. Brightwater Hale asked on Sep 10.",
      ),
    ).toBeTruthy();
    expect(within(amex).getByRole("button", { name: "Reconnect" })).toBeTruthy();
    const square = await card("Square");
    expect(
      within(square).getByText("Payouts and fees · read only · last sync 6:00 AM"),
    ).toBeTruthy();
    for (const name of ["Shopify", "Payroll provider"]) {
      expect(within(await card(name)).getByText("Not connected")).toBeTruthy();
    }
    expect(
      screen.getByText(
        "Brightwater Hale reads the books you connect. Nothing in your accounting system changes.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(/what Brightwater Hale already received stays in your client file/),
    ).toBeTruthy();
    avoid();
  });

  it("puts Export instead beside every ledger card (ADR-108)", async () => {
    show("a");
    const qbo = await card("QuickBooks Online");
    expect(within(qbo).getByRole("button", { name: "Export instead" })).toBeTruthy();
    for (const name of ["Front Range Bank ••4410", "Square", "Shopify"]) {
      expect(
        within(await card(name)).queryByRole("button", { name: "Export instead" }),
      ).toBeNull();
    }
  });

  it("POR-16b consent sheet: Continue stays disabled until the authorization toggle is on", async () => {
    const seen = show("b");
    const sheet = await screen.findByRole("dialog", { name: "Reconnect American Express" });
    expect(
      within(sheet).getByText("Read statements and transactions for card ••1009"),
    ).toBeTruthy();
    expect(within(sheet).getByText("Make payments or change your account")).toBeTruthy();
    const go = within(sheet).getByRole("button", { name: "Continue to American Express" });
    expect((go as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(go);
    expect(seen.calls.filter((c) => c.method === "POST")).toHaveLength(0);
    const toggle = within(sheet).getByRole("switch");
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect((go as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(go);
    await waitFor(() => {
      expect(seen.authorised).toHaveLength(1);
    });
    const start = seen.calls.find((c) => c.method === "POST");
    expect(start?.path).toMatch(/\/connections\/american_express\/start$/);
    expect(start?.body).toMatchObject({ consent_version: 1, authorized: true });
    // Back from the provider's site (c): the card is connecting.
    expect(
      await within(await card("American Express ••1009")).findByText("Connecting…"),
    ).toBeTruthy();
    avoid();
  });

  it("POR-16c connecting: the Amex card shows the spinner and Connecting…", async () => {
    show("c");
    const amex = await card("American Express ••1009");
    expect(within(amex).getAllByText(/Connecting/).length).toBeGreaterThan(0);
    expect(within(amex).queryByRole("button", { name: "Reconnect" })).toBeNull();
    avoid();
  });

  it("POR-16d reconnected: reconnected by Tess Moreno · Sep 14, 9:31 AM", async () => {
    show("d");
    const amex = await card("American Express ••1009");
    expect(within(amex).getByText("Connected")).toBeTruthy();
    expect(within(amex).getByText("reconnected by Tess Moreno · Sep 14, 9:31 AM")).toBeTruthy();
    avoid();
  });

  it("POR-16e first QuickBooks connect: the read-only disclosure and no write scope (DF-19)", async () => {
    show("e");
    const sheet = await screen.findByRole("dialog", { name: "Connect QuickBooks Online" });
    expect(within(sheet).getByText("Brightwater Hale will read your ledger")).toBeTruthy();
    const go = within(sheet).getByRole("button", { name: "Continue to QuickBooks Online" });
    expect((go as HTMLButtonElement).disabled).toBe(true);
    const qbo = await card("QuickBooks Online");
    expect(within(qbo).getByRole("button", { name: "Connect", hidden: true })).toBeTruthy();
    expect(within(qbo).getByRole("button", { name: "Export instead", hidden: true })).toBeTruthy();
    const scopes = [...document.querySelectorAll<HTMLElement>("[data-scope]")].map(
      (el) => el.dataset.scope,
    );
    expect(scopes.every((s) => s?.endsWith(".read"))).toBe(true);
    avoid();
  });

  it("POR-16f disconnect confirm: the dialog keeps what was received and disconnects", async () => {
    const seen = show("f");
    const dialog = await screen.findByRole("dialog", { name: "Disconnect QuickBooks Online?" });
    expect(
      within(dialog).getByText(
        "Brightwater Hale won’t be able to read your books. What it already received stays in your client file.",
      ),
    ).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Disconnect" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/disconnect"))).toBe(true);
    });
    const call = seen.calls.find((c) => c.path.endsWith("/disconnect"));
    expect(call?.body).toEqual({ seen_version: 1 });
    avoid();
  });

  it("POR-16g sync error: Needs attention, Last sync failed Sep 13 · Try again runs one retry", async () => {
    const seen = show("g");
    const square = await card("Square");
    expect(within(square).getByText("Needs attention")).toBeTruthy();
    expect(within(square).getByText(/Last sync failed Sep 13/)).toBeTruthy();
    const again = within(square).getByRole("button", { name: "Try again: Square" });
    fireEvent.click(again);
    await waitFor(() => {
      expect(seen.calls.filter((c) => c.path.endsWith("/retry"))).toHaveLength(1);
    });
    fireEvent.click(again); // a second click while it runs sends nothing more
    expect(seen.calls.filter((c) => c.path.endsWith("/retry"))).toHaveLength(1);
    avoid();
  });

  it("opens the details drawer with the scopes and who connected it", async () => {
    show("a");
    const qbo = await card("QuickBooks Online");
    fireEvent.click(within(qbo).getByRole("button", { name: "Details: QuickBooks Online" }));
    const drawer = await screen.findByRole("dialog", { name: "QuickBooks Online" });
    expect(await within(drawer).findByText("Read ledger")).toBeTruthy();
    expect(within(drawer).getByText("Connected by Tess Moreno · Mar 4, 2026")).toBeTruthy();
  });

  it("POR-16 at 390: status under the name, actions as full-width 44px buttons", async () => {
    show("a", { mobile: true });
    const amex = await card("American Express ••1009");
    const reconnect = within(amex).getByRole("button", { name: "Reconnect" });
    expect(reconnect.className).toMatch(/h-\[44px\]/);
    expect(reconnect.className).toMatch(/w-full/);
    avoid();
  });

  it("draws Lucide glyph tiles only, by the catalogue's glyph name", () => {
    expect(glyphOf("BookOpen")).toBe("book-open");
    expect(glyphOf("CreditCard")).toBe("credit-card");
    expect(glyphOf("landmark")).toBe("landmark");
    expect(glyphOf("SomeVendorLogo")).toBe("store");
  });

  it("sends the browser only to an HTTPS sign-in or this app's own origin", () => {
    expect(safeSignIn("https://appcenter.example.test/connect?state=x")).toBe(true);
    expect(safeSignIn("/connect/callback?fixture=quickbooks_online")).toBe(true);
    expect(safeSignIn("javascript:alert(1)")).toBe(false);
    expect(safeSignIn("http://evil.example.test/")).toBe(false);
  });
});
