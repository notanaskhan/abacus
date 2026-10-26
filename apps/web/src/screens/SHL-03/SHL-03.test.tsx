// SHL-03 · Firm switcher and profile menu (P-01-T08). One test per artboard (a–f) on its fixture
// scenario, then the AC 2.1.x behaviours on the live tray: capability-gated admin rows, the office
// PUT, firm switching, Escape and Sign out.
import type { RoleOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { SHELL_PERSONAS, officeIdOf } from "../../fixtures/seed/shell";
import { ADMIN_ROWS, FirmMenu, adminRows, cardLine } from "../../shell/firm/FirmMenu";
import { newQueryClient } from "../../testing/support";
import { SHL03 } from ".";
import { type Shl03State, STATES, scenarios } from "./scenarios";

const { process } = globalThis as unknown as { process: { cwd: () => string } };

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

/** Installs a state's scenario, recording every request; `extra` adds or replaces handlers. */
function install(state: Shl03State, extra: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [] };
  const base = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...base.handlers, ...extra }).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...base, handlers });
  return seen;
}

function show(state: Shl03State): Seen {
  const seen = install(state);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <SHL03 state={state} />
    </QueryClientProvider>,
  );
  return seen;
}

async function tray(): Promise<HTMLElement> {
  const menu = await screen.findByRole("menu", { name: "Firm and profile" });
  // The tray draws once /v1/me and the capabilities have answered.
  await within(menu).findByText(/@brightwaterhale\.com$/);
  return menu;
}

function adminLabels(menu: HTMLElement): string[] {
  const group = within(menu).queryByRole("group", { name: "Admin" });
  if (group === null) return [];
  return within(group)
    .getAllByRole("menuitem")
    .map((row) => row.querySelector("span")?.textContent ?? "");
}

function rowNames(menu: HTMLElement): string[] {
  return within(menu)
    .getAllByRole("menuitem")
    .map((row) => row.textContent);
}

describe("SHL-03 artboards", () => {
  it("covers a–f, each with its README viewer", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("SHL-03a admin: firm row, Grace's card, the rows, Firm settings · Users & roles · Audit log, Sign out", async () => {
    show("a");
    const menu = await tray();
    const firms = within(menu).getAllByRole("menuitemradio");
    expect(firms).toHaveLength(1);
    expect(firms[0]?.getAttribute("aria-checked")).toBe("true");
    expect(firms[0]?.textContent).toContain("US · Central Time · 46 seats");
    expect(within(menu).getByText("GH")).toBeTruthy();
    expect(within(menu).getByText("Grace Holloway")).toBeTruthy();
    expect(
      within(menu).getByText("Firm Admin · Client Service Coordinator · Chicago"),
    ).toBeTruthy();
    expect(within(menu).getByText("grace.holloway@brightwaterhale.com")).toBeTruthy();
    expect(rowNames(menu)).toEqual([
      "Your profile",
      "Default office filterAll offices",
      "Notification preferences",
      "Keyboard shortcuts⌘/",
      "Firm settings",
      "Users & roles",
      "Audit log",
      "Sign out",
    ]);
    expect(adminLabels(menu)).toEqual(["Firm settings", "Users & roles", "Audit log"]);
    expect(within(menu).getByRole("img", { name: "Accrued" })).toBeTruthy();
    // The pill reads pressed while the tray is open.
    const pill = screen.getByRole("button", { name: "Brightwater Hale" });
    expect(pill.dataset.pressed).toBe("true");
  });

  it("SHL-03b non-admin: no admin section, Chicago as the default office", async () => {
    show("b");
    const menu = await tray();
    expect(within(menu).queryByRole("group", { name: "Admin" })).toBeNull();
    expect(adminLabels(menu)).toEqual([]);
    expect(within(menu).getByText("Audit Senior Manager · Chicago")).toBeTruthy();
    expect(menu.querySelector('[data-value="office"]')?.textContent).toBe("Chicago");
  });

  it("SHL-03c partner: Firm settings, View only, and Audit log", async () => {
    show("c");
    const menu = await tray();
    expect(adminLabels(menu)).toEqual(["Firm settings", "Audit log"]);
    const settings = within(menu).getByRole("menuitem", { name: /Firm settings/ });
    expect(settings.textContent).toBe("Firm settingsView only");
    expect(within(menu).getByText("Tax Partner · New York")).toBeTruthy();
  });

  it("SHL-03d IT / Security: Security center, Developer & API, Audit log", async () => {
    show("d");
    const menu = await tray();
    expect(adminLabels(menu)).toEqual(["Security center", "Developer & API", "Audit log"]);
    expect(within(menu).getByText("IT / Security · Qualified Individual · Chicago")).toBeTruthy();
  });

  it("SHL-03e multi-firm: the training sandbox row, its pill and line", async () => {
    show("e");
    const menu = await tray();
    const firms = within(menu).getAllByRole("menuitemradio");
    expect(firms.map((f) => f.getAttribute("aria-checked"))).toEqual(["true", "false"]);
    const sandbox = firms[1] as HTMLElement;
    expect(within(sandbox).getByText("Brightwater Hale LLP — Training sandbox")).toBeTruthy();
    expect(within(sandbox).getByText("Sandbox")).toBeTruthy();
    expect(within(sandbox).getByText("Sandbox · seeded demo data only")).toBeTruthy();
  });

  it("SHL-03f office submenu: All offices ✓ · Chicago · Denver · New York", async () => {
    show("f");
    await tray();
    const sub = screen.getByRole("menu", { name: "Default office filter" });
    const items = within(sub).getAllByRole("menuitemradio");
    expect(items.map((i) => i.textContent)).toEqual([
      "All offices",
      "Chicago",
      "Denver",
      "New York",
    ]);
    expect(items.map((i) => i.getAttribute("aria-checked"))).toEqual([
      "true",
      "false",
      "false",
      "false",
    ]);
  });
});

/** The live tray as the firm layout mounts it: opened from a stand-in pill. */
function Live({
  onSwitch = () => undefined,
  onSignedOut = () => undefined,
  navigate = () => undefined,
}: {
  onSwitch?: () => void;
  onSignedOut?: () => void;
  navigate?: (path: string) => void;
}): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        aria-haspopup="menu"
        data-pressed={open}
        onClick={() => {
          setOpen((o) => !o);
        }}
      >
        Firm pill
      </button>
      <FirmMenu
        open={open}
        onOpenChange={setOpen}
        activeTenantId={null}
        navigate={navigate}
        onShortcuts={() => undefined}
        onNotificationPreferences={() => undefined}
        onSwitch={onSwitch}
        onSignedOut={onSignedOut}
      />
    </>
  );
}

function live(
  state: Shl03State,
  props: Parameters<typeof Live>[0] = {},
  extra: Record<string, FixtureHandler> = {},
): Seen {
  const seen = install(state, extra);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Live {...props} />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Firm pill" }));
  return seen;
}

describe("SHL-03 behaviour (P-01 AC 2.1)", () => {
  it("AC 2.1.2: the admin section comes only from capabilities.nav", () => {
    expect(adminRows({})).toEqual([]);
    expect(
      adminRows({ firm_settings: "read", audit_log: "read", users_roles: "none" }).map((r) => [
        r.label,
        r.viewOnly,
      ]),
    ).toEqual([
      ["Firm settings", true],
      ["Audit log", false],
    ]);
    expect(ADMIN_ROWS.map((r) => r.key)).toEqual([
      "firm_settings",
      "users_roles",
      "security_center",
      "developer_api",
      "audit_log",
    ]);
  });

  it("AC 2.1.2: the firm menu names no role code", () => {
    const source = readFileSync(
      join(process.cwd(), "src", "shell", "firm", "FirmMenu.tsx"),
      "utf8",
    );
    for (const code of [
      "firm_admin",
      "practice_leader",
      "quality_partner",
      "security_admin",
      "firm_partner",
      "firm_role",
    ]) {
      expect(source, code).not.toContain(code);
    }
  });

  it("the person card lines foot to the four handoff cards", () => {
    const roles: Record<string, RoleOut[]> = Object.fromEntries(
      SHELL_PERSONAS.map((p) => [p.slug, p.role === null ? [] : [p.role]]),
    );
    expect(cardLine(roles["grace-holloway"] ?? [], "Client Service Coordinator", "Chicago")).toBe(
      SHELL_PERSONAS[0]?.cardLine,
    );
    expect(cardLine(roles["hannah-leclerc"] ?? [], "Audit Senior Manager", "Chicago")).toBe(
      SHELL_PERSONAS[1]?.cardLine,
    );
    expect(cardLine(roles["daniel-reyes"] ?? [], "Tax Partner", "New York")).toBe(
      SHELL_PERSONAS[2]?.cardLine,
    );
    expect(cardLine(roles["felix-andersen"] ?? [], "Qualified Individual", "Chicago")).toBe(
      SHELL_PERSONAS[3]?.cardLine,
    );
  });

  it("AC 2.1.1: Escape closes the tray and the pill toggles it", async () => {
    live("a");
    await tray();
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("menu", { name: "Firm and profile" })).toBeNull();
    });
    fireEvent.click(screen.getByRole("button", { name: "Firm pill" }));
    await tray();
    fireEvent.click(screen.getByRole("button", { name: "Firm pill" }));
    expect(screen.queryByRole("menu", { name: "Firm and profile" })).toBeNull();
  });

  it("AC 2.1.1: an admin row closes the tray and goes to its page", async () => {
    const navigate = vi.fn();
    live("a", { navigate });
    const menu = await tray();
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Users & roles" }));
    expect(navigate).toHaveBeenCalledWith("/admin/people");
    expect(screen.queryByRole("menu", { name: "Firm and profile" })).toBeNull();
  });

  it("AC 2.1.3: picking Chicago PUTs the default office and the row reads Chicago", async () => {
    const seen = live("f");
    const menu = await tray();
    const row = within(menu).getByRole("menuitem", { name: "Default office filter" });
    fireEvent.keyDown(row, { key: "ArrowRight" });
    const sub = await screen.findByRole("menu", { name: "Default office filter" });
    fireEvent.click(within(sub).getByRole("menuitemradio", { name: "Chicago" }));
    await waitFor(() => {
      expect(menu.querySelector('[data-value="office"]')?.textContent).toBe("Chicago");
    });
    const put = seen.calls.find((c) => c.method === "PUT" && c.path === "/v1/me/preferences");
    expect(put?.body).toEqual({ default_office_id: officeIdOf("Chicago") });
  });

  it("AC 2.1.4: picking the sandbox sets the tenant, refetches /v1/me and toasts", async () => {
    const onSwitch = vi.fn();
    const seen = live("e", { onSwitch });
    const menu = await tray();
    const before = seen.calls.filter((c) => c.path === "/v1/me").length;
    fireEvent.click(
      within(menu).getByRole("menuitemradio", { name: /Brightwater Hale LLP — Training sandbox/ }),
    );
    expect(onSwitch).toHaveBeenCalledWith(
      expect.objectContaining({ firm_name: "Brightwater Hale LLP — Training sandbox" }),
    );
    expect(toastStore.list().map((t) => t.text)).toContain(
      "Switched to Brightwater Hale LLP — Training sandbox",
    );
    // The tray is closed; reopening reads /v1/me again from a cleared cache.
    fireEvent.click(screen.getByRole("button", { name: "Firm pill" }));
    await tray();
    expect(seen.calls.filter((c) => c.path === "/v1/me").length).toBeGreaterThan(before);
  });

  it("AC 2.1.4: picking the firm already in use changes nothing", async () => {
    const onSwitch = vi.fn();
    live("e", { onSwitch });
    const menu = await tray();
    const toasts = toastStore.list().length;
    fireEvent.click(within(menu).getAllByRole("menuitemradio")[0] as HTMLElement);
    expect(onSwitch).not.toHaveBeenCalled();
    expect(toastStore.list()).toHaveLength(toasts);
  });

  it("AC 2.1.6: Sign out ends the staff session, then hands over to the local sign-out", async () => {
    const onSignedOut = vi.fn();
    const seen = live("b", { onSignedOut });
    const menu = await tray();
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Sign out" }));
    await waitFor(() => {
      expect(onSignedOut).toHaveBeenCalledOnce();
    });
    expect(seen.calls.some((c) => c.method === "POST" && c.path === "/v1/auth/sign-out")).toBe(
      true,
    );
  });

  it("AC 2.1.5: Your profile opens a read-only drawer", async () => {
    live("a");
    const menu = await tray();
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Your profile" }));
    const drawer = await screen.findByRole("dialog", { name: "Your profile" });
    expect(within(drawer).getByText("Ask your firm admin to change these")).toBeTruthy();
    expect(within(drawer).getByText("Client Service Coordinator")).toBeTruthy();
    expect(within(drawer).getByText("Central Time")).toBeTruthy();
    expect(within(drawer).queryByRole("textbox")).toBeNull();
  });

  it("↑ ↓ move between the tray's rows", async () => {
    live("b");
    const menu = await tray();
    const rows = [...menu.querySelectorAll('[role="menuitem"],[role="menuitemradio"]')];
    expect(document.activeElement).toBe(rows[0]);
    fireEvent.keyDown(menu, { key: "ArrowDown" });
    expect(document.activeElement).toBe(rows[1]);
    fireEvent.keyDown(menu, { key: "ArrowUp" });
    fireEvent.keyDown(menu, { key: "ArrowUp" });
    expect(document.activeElement).toBe(rows[rows.length - 1]);
  });
});

// G-01 AC6.1 (the T10 follow-up): the profile drawer's annual independence self-confirmation. The
// firm's statement is firm content with no design data (DF-07), so these tests bring their own.
describe("SHL-03 annual independence confirmation (G-01 AC6.1)", () => {
  const STATEMENT = "Test statement one.\nTest statement two.\nTest statement three.";

  function annual(status: "not_yet" | "confirmed" | "declined", statement = true) {
    let current = status;
    let decidedAt: string | null = status === "not_yet" ? null : "2026-09-14T14:31:00Z";
    const handlers: Record<string, FixtureHandler> = {
      "GET /v1/me/independence/annual": () =>
        json({
          year: 2026,
          status: current,
          decided_at: decidedAt,
          statement: statement ? { body: STATEMENT, version: 3 } : null,
        }),
      "POST /v1/me/independence/annual": ({ body }) => {
        const given = body as { decision: "confirmed" | "declined"; note: string | null };
        current = given.decision;
        decidedAt = "2026-09-14T14:31:00Z";
        return json({ year: 2026, status: current, decided_at: decidedAt }, 201);
      },
    };
    return handlers;
  }

  async function profile(extra: Record<string, FixtureHandler>): Promise<[HTMLElement, Seen]> {
    const seen = live("a", {}, extra);
    const menu = await tray();
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Your profile" }));
    return [await screen.findByRole("dialog", { name: "Your profile" }), seen];
  }

  it("not yet: the row offers Confirm…, and Confirm sends the statement's version", async () => {
    const [drawer, seen] = await profile(annual("not_yet"));
    expect(
      await within(drawer).findByText("Annual independence confirmation · 2026"),
    ).toBeTruthy();
    fireEvent.click(within(drawer).getByRole("button", { name: "Confirm…" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Annual independence confirmation · 2026",
    });
    expect(within(dialog).getByText(/Test statement one\./)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));
    await waitFor(() => {
      const post = seen.calls.find(
        (c) => c.method === "POST" && c.path === "/v1/me/independence/annual",
      );
      expect(post?.body).toEqual({
        decision: "confirmed",
        year: 2026,
        statement_version: 3,
        note: null,
      });
    });
    expect(await within(drawer).findByText(/^Confirmed /)).toBeTruthy();
  });

  it("declining needs a note", async () => {
    const [drawer, seen] = await profile(annual("not_yet"));
    fireEvent.click(await within(drawer).findByRole("button", { name: "Confirm…" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Annual independence confirmation · 2026",
    });
    const decline = within(dialog).getByRole("button", { name: "Decline" });
    expect(decline.hasAttribute("disabled")).toBe(true);
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "I hold shares in a client." },
    });
    expect(decline.hasAttribute("disabled")).toBe(false);
    fireEvent.click(decline);
    await waitFor(() => {
      const post = seen.calls.find((c) => c.method === "POST");
      expect(post?.body).toMatchObject({
        decision: "declined",
        note: "I hold shares in a client.",
      });
    });
  });

  it("without a published statement nothing can be confirmed", async () => {
    const [drawer] = await profile(annual("not_yet", false));
    fireEvent.click(await within(drawer).findByRole("button", { name: "Confirm…" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Annual independence confirmation · 2026",
    });
    expect(
      within(dialog).getByText("Your firm hasn't published its independence statement yet."),
    ).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Confirm" }).hasAttribute("disabled")).toBe(
      true,
    );
  });

  it("already confirmed: the date, no Confirm…", async () => {
    const [drawer] = await profile(annual("confirmed"));
    expect(await within(drawer).findByText(/^Confirmed /)).toBeTruthy();
    expect(within(drawer).queryByRole("button", { name: "Confirm…" })).toBeNull();
  });
});
