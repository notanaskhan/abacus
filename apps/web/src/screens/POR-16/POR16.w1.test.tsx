// C-02-T40 (TASK-8924; DEC-5926): POR-16's posting scope once the firm holds W1 for a non-attest
// client. Row acceptance: "Tess Moreno grants and revokes the write scope with fresh MFA and sees
// 'Posted 6 journal entries · batch 2026-08-A' in the details drawer." The QBO card offers
// "Allow posting…" with the consent v2 sheet (will and won't, the authorization toggle gating the
// button); granting brings back the design's posting words; a stale second factor asks to sign
// in again; "Turn off posting…" confirms and revokes; an attest client sees read-only copy only.
// Artboards a–g (no W1 held) keep DF-19's masks: POR16.test.tsx.
import { Toaster } from "@abacus/ui";
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { type W1Fixture, connectionsHandlers } from "../../fixtures/handlers/connections";
import { portalHandlers } from "../../fixtures/handlers/portal";
import { POR16_CLOCKS, QUICKBOOKS_WRITE_CONSENT } from "../../fixtures/seed/connections";
import { renderRoutes } from "../../testing/support";
import { PortalConnections } from ".";
import { COPY } from "./copy";
import { scenarios } from "./scenarios";

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
  steppedUp: number;
}

function show(w1: W1Fixture, over: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [], steppedUp: 0 };
  const clock = POR16_CLOCKS.a;
  const fresh = {
    ...portalHandlers({ clock }),
    ...connectionsHandlers("a", { clock, w1 }),
    ...over,
  };
  const handlers = Object.fromEntries(
    Object.entries(fresh).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenarios.a, handlers });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <>
          <PortalConnections
            onStepUp={() => {
              seen.steppedUp += 1;
            }}
          />
          <Toaster />
        </>
      ),
    },
  ]);
  return seen;
}

async function qbo(): Promise<HTMLElement> {
  return screen.findByRole("listitem", { name: "QuickBooks Online", hidden: true });
}

describe("POR-16 posting scope (W1)", () => {
  it("offered: Allow posting… opens the consent v2 sheet; the toggle gates the button", async () => {
    const seen = show({ write: "offered" });
    const card = await qbo();
    expect(within(card).queryByText(COPY.postTag)).toBeNull();
    fireEvent.click(within(card).getByRole("button", { name: COPY.allowPosting }));
    const sheet = await screen.findByRole("dialog", { name: QUICKBOOKS_WRITE_CONSENT.title });
    for (const line of [...QUICKBOOKS_WRITE_CONSENT.will, ...QUICKBOOKS_WRITE_CONSENT.wont]) {
      expect(within(sheet).getByText(line)).toBeTruthy();
    }
    const allow = within(sheet).getByRole("button", {
      name: QUICKBOOKS_WRITE_CONSENT.continue_label,
    });
    expect((allow as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(sheet).getByRole("switch"));
    expect((allow as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(allow);
    expect(await within(await qbo()).findByText(COPY.postTag)).toBeTruthy();
    const posted = seen.calls.filter(
      (c) => c.method === "POST" && c.path.endsWith("/write-grants"),
    );
    expect(posted).toHaveLength(1);
    expect(posted[0]?.body).toEqual({
      capability_id: "ledger_post_journal_entries",
      consent_copy_version: "por16.qbo.post_entries.v2",
    });
    expect(screen.getByText(COPY.relationshipPosting("Brightwater Hale"))).toBeTruthy();
  });

  it("a stale second factor asks to sign in again and grants nothing", async () => {
    const seen = show(
      { write: "offered" },
      {
        "POST /v1/portal/connections/{connection_id}/write-grants": () =>
          json({ code: "mfa_required", message: "Confirm it's you to change posting." }, 409),
      },
    );
    fireEvent.click(within(await qbo()).getByRole("button", { name: COPY.allowPosting }));
    const sheet = await screen.findByRole("dialog", { name: QUICKBOOKS_WRITE_CONSENT.title });
    fireEvent.click(within(sheet).getByRole("switch"));
    fireEvent.click(
      within(sheet).getByRole("button", { name: QUICKBOOKS_WRITE_CONSENT.continue_label }),
    );
    await waitFor(() => {
      expect(seen.steppedUp).toBe(1);
    });
    expect(within(await qbo()).queryByText(COPY.postTag)).toBeNull();
  });

  it("granted: who allowed it, Turn off posting… confirms and revokes", async () => {
    const seen = show({ write: "granted" });
    const card = await qbo();
    expect(within(card).getByText(COPY.postTag)).toBeTruthy();
    expect(
      within(card).getByText(COPY.postingAllowedBy("Tess Moreno", "Mar 9, 2026")),
    ).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: COPY.turnOff }));
    const dialog = await screen.findByRole("dialog", {
      name: COPY.turnOffTitle("QuickBooks Online"),
    });
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.turnOffConfirm }));
    await waitFor(() => {
      expect(
        seen.calls.some((c) => c.method === "DELETE" && c.path.endsWith("/write-grants/current")),
      ).toBe(true);
    });
    expect(
      await within(await qbo()).findByRole("button", { name: COPY.allowPosting }),
    ).toBeTruthy();
    expect(screen.getByText(COPY.relationship("Brightwater Hale"))).toBeTruthy();
  });

  it("C-02-T40 acceptance: the drawer shows Posted 6 journal entries · batch 2026-08-A", async () => {
    show({ write: "granted", august: true });
    fireEvent.click(
      within(await qbo()).getByRole("button", { name: `${COPY.details}: QuickBooks Online` }),
    );
    const drawer = await screen.findByRole("dialog", { name: "QuickBooks Online" });
    const log = await within(drawer).findByText(COPY.writes);
    const section = log.closest("[data-writes]") as HTMLElement;
    expect(within(section).getByText(COPY.postedEntries(6, "2026-08-A"))).toBeTruthy();
    expect(within(section).getByText(COPY.postedEntries(6, "2026-07-A"))).toBeTruthy();
    expect(within(section).getByText(COPY.closingDateSet("Jul 31, 2026"))).toBeTruthy();
  });

  it("the disconnect confirm names posting once it is allowed", async () => {
    show({ write: "granted" });
    fireEvent.click(
      within(await qbo()).getByRole("button", { name: `${COPY.disconnect}: QuickBooks Online` }),
    );
    expect(await screen.findByText(COPY.disconnectBodyPosting("Brightwater Hale"))).toBeTruthy();
  });

  it("an attest client sees read-only copy: no posting control, tag or consent", async () => {
    show({ write: "read_only" });
    const card = await qbo();
    expect(within(card).queryByRole("button", { name: COPY.allowPosting })).toBeNull();
    expect(within(card).queryByText(COPY.postTag)).toBeNull();
    expect(screen.getByText(COPY.relationship("Brightwater Hale"))).toBeTruthy();
    expect(screen.queryByText(/post entries/i)).toBeNull();
  });
});
