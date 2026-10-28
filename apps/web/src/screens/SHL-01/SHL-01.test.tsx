// SHL-01 · Firm app shell, toolbar and nav (P-01-T02). One test per artboard state (a–g) on its
// fixture scenario, the AC 1.1.x behaviours, and the revision's acceptance checklist.
import type { CapabilitiesOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { type ToolbarMeasure, fitToolbar } from "@abacus/ui";
import { QueryClientProvider, focusManager } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { router } from "../../router";
import { AreaLanding, areaLandingRoutes } from "../../routes/firm/areas";
import { MANIFEST, type ScreenEntry } from "../../routes/manifest";
import { AREAS, activeArea } from "../../app-core/nav-areas";
import { NAV } from "../../shell/nav";
import { POLL_MS } from "../../shell/NotificationPanel";
import { newQueryClient } from "../../testing/support";
import { SHL01, on } from ".";
import { R2_LABELS } from "./copy";
import { type Shl01State, scenarios } from "./scenarios";

const LABELS = NAV.map((n) => n.label);
const ORDER = [
  "Home",
  "Engagements",
  "Tax Returns",
  "Files",
  "Knowledge",
  "Workbench",
  "Inbox",
  "Clients",
  "Binders",
  "Notices",
  "Audits",
  "Closes",
  "Signatures",
];

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

/** Renders an artboard on its scenario; returns every request the screen made. */
function show(state: Shl01State, extra: Record<string, FixtureHandler> = {}): { paths: string[] } {
  const paths: string[] = [];
  const base = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...base.handlers, ...extra }).map(([key, handler]) => [
      key,
      ((request) => {
        paths.push(request.path);
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  const scenario: Scenario = { ...base, handlers };
  restore = installFixtureMode(scenario);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <SHL01 state={state} />
    </QueryClientProvider>,
  );
  return { paths };
}

function navOf(root: HTMLElement): HTMLElement {
  return within(root).getByRole("navigation", { name: "Modules" });
}

function itemLabels(root: HTMLElement): string[] {
  return within(navOf(root))
    .getAllByRole("button")
    .map((b) => b.textContent);
}

function lit(root: HTMLElement): string[] {
  return [...navOf(root).querySelectorAll('[aria-current="page"]')].map((b) => b.textContent);
}

function strips(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("[data-strip]")];
}

const capabilities = (flags: Record<string, boolean>): FixtureHandler => {
  const body: CapabilitiesOut = {
    capabilities: [],
    clock_mode: "frozen",
    engagement_id: null,
    entitlements: [],
    flags,
    mfa_recent_until: null,
    office_id: null,
    portal: null,
    roles: [],
    server_now: "2026-09-14T14:24:00Z",
    tz: "America/Chicago",
  };
  return () => json(body);
};

// Measured Geist widths of the 13 items at weight 500 and the controls (F-05-T18's measure).
const ITEMS = [
  60.64, 110.23, 98.42, 53.42, 93.75, 95.16, 58.92, 67.73, 71.83, 72.05, 63.92, 66.61, 91.7,
];
function measure(barWidth: number): ToolbarMeasure {
  return {
    barWidth,
    go: 67.84,
    firm: 140.58,
    firmShort: 109.64,
    homePill: 30,
    support: 92.08,
    bell: 30,
    items: ITEMS,
    more: 69.98,
  };
}
function inMore(width: number): string[] {
  return LABELS.slice(fitToolbar(measure(width), { moreFirst: true }).inline);
}

describe("SHL-01 artboards", () => {
  it("SHL-01a default: Go…, the firm pill, the 13 items, Support and the bell with its dot", async () => {
    show("a");
    const board = document.querySelector<HTMLElement>('[data-artboard="a"]');
    expect(board).not.toBeNull();
    const root = board as HTMLElement;
    expect(await within(root).findByRole("button", { name: "Brightwater Hale" })).toBeTruthy();
    expect(itemLabels(root)).toEqual(ORDER);
    expect(lit(root)).toEqual(["Home"]);
    expect(within(root).getByRole("button", { name: "Go to anything ⌘K" })).toBeTruthy();
    expect(within(root).getByRole("button", { name: "Support" })).toBeTruthy();
    expect(
      await within(root).findByRole("button", { name: "Notifications, unread" }),
    ).toBeTruthy();
    expect(root.querySelector('[data-dot="unread"]')).not.toBeNull();
  });

  it("SHL-01b: thirteen strips, each lighting the item its landing screen belongs to", async () => {
    show("b");
    await screen.findAllByRole("button", { name: "Brightwater Hale" });
    const all = strips();
    expect(all.map((s) => s.dataset.strip)).toEqual(AREAS.map((a) => a.landing));
    expect(all.map((s) => s.dataset.strip)).toEqual([
      "HOME-01",
      "ENG-01",
      "TAX-01",
      "FIL-01",
      "KNW-01",
      "WB-01",
      "INB-01",
      "CLI-01",
      "BND-01",
      "NOT-01",
      "AUD-01",
      "CLS-01",
      "SIG-01",
    ]);
    all.forEach((strip, i) => {
      expect(lit(strip)).toEqual([ORDER[i]]);
    });
  });

  it("SHL-01c: hover on Audits, focus-visible on Inbox, Go… pressed", () => {
    show("c");
    const [hover, focus, go] = strips();
    expect(
      within(navOf(hover as HTMLElement)).getByRole("button", { name: "Audits" }).dataset.force,
    ).toBe("hover");
    expect(
      within(navOf(focus as HTMLElement)).getByRole("button", { name: "Inbox" }).dataset.force,
    ).toBe("focus");
    expect(
      within(go as HTMLElement).getByRole("button", { name: "Go to anything ⌘K" }).dataset.force,
    ).toBe("pressed");
  });

  it("SHL-01d: the bell read, with no dot, when unread_count is 0", async () => {
    const { paths } = show("d");
    await waitFor(() => {
      expect(paths).toContain("/v1/notifications");
    });
    const [strip] = strips();
    expect(
      within(strip as HTMLElement).getByRole("button", { name: "Notifications" }),
    ).toBeTruthy();
    expect(document.querySelector('[data-dot="unread"]')).toBeNull();
  });

  it("SHL-01e: DF-39 with More first: Signatures at 1400, then Closes and Audits below 1280", () => {
    show("e");
    expect(strips().map((s) => s.dataset.strip)).toEqual(["1400", "1279", "1279"]);
    expect(inMore(1440)).toEqual([]);
    expect(inMore(1400)).toEqual(["Signatures"]);
    expect(inMore(1279)).toEqual(["Audits", "Closes", "Signatures"]);
    // At 1400 the full "Brightwater Hale" pill and Home stay (SHL-01a; AC 1.1.4).
    expect(fitToolbar(measure(1400), { moreFirst: true })).toMatchObject({
      firmShort: false,
      homePill: false,
    });
    expect(fitToolbar(measure(1279), { moreFirst: true })).toMatchObject({
      firmShort: false,
      homePill: false,
    });
  });

  it("SHL-01f: /settings/general lights nothing and presses the firm pill", async () => {
    show("f");
    const [strip] = strips();
    const root = strip as HTMLElement;
    expect(lit(root)).toEqual([]);
    const pill = await within(root).findByRole("button", { name: "Brightwater Hale" });
    expect(pill.dataset.pressed).toBe("true");
  });

  it("SHL-01g: the eight R2 screens light the item that owns them; nothing is added", () => {
    show("g");
    const r2 = strips().filter((s) => s.dataset.strip !== "");
    expect(r2.map((s) => s.dataset.strip)).toEqual(Object.values(R2_LABELS));
    expect(r2.map((s) => lit(s)[0])).toEqual([
      "Engagements",
      "Home",
      "Home",
      "Binders",
      "Workbench",
      "Knowledge",
      "Audits",
      "Audits",
    ]);
    for (const strip of r2) expect(itemLabels(strip)).toEqual(ORDER);
  });
});

describe("SHL-01 behaviour (P-01 AC 1.1)", () => {
  it("AC 1.1.2: the lit item comes from the manifest's navArea", () => {
    for (const [id, area] of Object.entries({
      "ENG-10": "Engagements",
      "HOME-05": "Home",
      "INS-01": "Home",
      "BND-04": "Binders",
      "WB-12": "Workbench",
      "KNW-06": "Knowledge",
      "FSP-01": "Audits",
      "ATT-01": "Audits",
    })) {
      expect((MANIFEST as Record<string, { navArea?: string }>)[id]?.navArea).toBe(area);
      expect(activeArea(on(id))).toBe(area);
    }
  });

  it("AC 1.1.2: the area table is the manifest's: landings, their paths and every routed navArea", () => {
    const entries = MANIFEST as Readonly<Record<string, ScreenEntry>>;
    for (const area of AREAS) {
      const landing = entries[area.landing];
      expect(landing?.navArea, area.landing).toBe(area.label);
      // A routed landing is reached at its manifest path; Home's is "/home" (I-01-T13), which
      // "/" redirects to.
      expect(landing?.path ?? area.path, area.landing).toBe(area.path);
      expect(area.routed, area.landing).toBe(landing?.path != null || area.path === "/");
    }
    for (const [id, entry] of Object.entries(entries)) {
      if (entry.path === null || entry.navArea === undefined) continue;
      const pathname = entry.path.replaceAll(/\$[A-Za-z]+/g, "x1");
      expect(activeArea({ pathname }), id).toBe(entry.navArea);
    }
  });

  it("AC 1.1.2: routes light their area, deep routes included", () => {
    expect(activeArea({ pathname: "/" })).toBe("Home");
    expect(activeArea({ pathname: "/engagements" })).toBe("Engagements");
    expect(activeArea({ pathname: "/engagements/e1/requests" })).toBe("Engagements");
    expect(activeArea({ pathname: "/clients/c1" })).toBe("Clients");
    expect(activeArea({ pathname: "/knowledge" })).toBe("Knowledge");
    expect(activeArea({ pathname: "/tax-returns" })).toBe("Tax Returns");
    expect(activeArea({ pathname: "/signatures" })).toBe("Signatures");
  });

  it("AC 1.1.3: every settings route lights nothing", () => {
    for (const pathname of ["/settings/general", "/settings", "/admin/methodology"]) {
      expect(activeArea({ pathname })).toBe("");
    }
  });

  it("AC 1.1.5: a planned landing has a flag-off page at the area's path, never a 404", () => {
    const planned = AREAS.filter((a) => !a.routed);
    expect(planned.map((a) => a.label)).toEqual([
      "Tax Returns",
      "Files",
      "Workbench",
      "Inbox",
      // Binders is routed by P-06-T09 (BND-01); its flag-off page is BND-01.test.tsx's.
      "Notices",
      // Audits is routed by A-01-T11 (AUD-01); its flag-off page is AUD-01.test.tsx's.
      "Closes",
      "Signatures",
    ]);
    expect(areaLandingRoutes.map((r) => r.fullPath)).toEqual(planned.map((a) => a.path));
    const paths = new Set(
      Object.values(router.routesById as unknown as Record<string, { fullPath: string }>).map(
        (r) => r.fullPath,
      ),
    );
    for (const area of AREAS) expect(paths.has(area.path), area.label).toBe(true);
    for (const area of planned) {
      render(<AreaLanding area={area} />);
      expect(screen.getByText(`${area.label} is not turned on for this firm.`)).toBeTruthy();
      cleanup();
    }
  });

  it("AC 1.1.6: the dot follows unread_count, polled every 60 s and on window focus", async () => {
    expect(POLL_MS).toBe(60_000);
    let count = 4;
    show("a", {
      "GET /v1/notifications": () => json({ items: [], unread_count: count }),
    });
    expect(await screen.findByRole("button", { name: "Notifications, unread" })).toBeTruthy();
    count = 0;
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    expect(await screen.findByRole("button", { name: "Notifications" })).toBeTruthy();
    expect(document.querySelector('[data-dot="unread"]')).toBeNull();
    focusManager.setFocused(undefined);
  });

  it("AC 1.1.7: ⌘K and Ctrl K open Go…; G H, G T, G A, G C and G W go to their areas", async () => {
    show("a");
    await screen.findByRole("button", { name: "Brightwater Hale" });
    const board = document.querySelector<HTMLElement>('[data-artboard="a"]') as HTMLElement;
    const chord = (key: string): void => {
      fireEvent.keyDown(document.body, { key: "g" });
      fireEvent.keyDown(document.body, { key });
    };
    for (const [key, label] of [
      ["t", "Tax Returns"],
      ["a", "Audits"],
      ["c", "Closes"],
      ["w", "Workbench"],
      ["h", "Home"],
    ] as const) {
      chord(key);
      await waitFor(() => {
        expect(lit(board)).toEqual([label]);
      });
    }
    expect(board.dataset.path).toBe("/home"); // I-01-T13: G H opens HOME-01
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeTruthy();
  });

  it("AC 1.1.7: ? opens Go…, and no chord fires from a text field", async () => {
    show("a");
    await screen.findByRole("button", { name: "Brightwater Hale" });
    const board = document.querySelector<HTMLElement>('[data-artboard="a"]') as HTMLElement;
    const input = document.createElement("input");
    document.body.append(input);
    fireEvent.keyDown(input, { key: "g" });
    fireEvent.keyDown(input, { key: "t" });
    fireEvent.keyDown(input, { key: "?" });
    expect(lit(board)).toEqual(["Home"]);
    expect(screen.queryByRole("dialog", { name: "Command palette" })).toBeNull();
    input.remove();
    fireEvent.keyDown(document.body, { key: "?" });
    expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeTruthy();
  });

  it("AC 1.1.8: the interim Go… lists the 13 areas and the shortcuts and sends no search", async () => {
    const { paths } = show("a");
    await screen.findByRole("button", { name: "Brightwater Hale" });
    fireEvent.click(screen.getByRole("button", { name: "Go to anything ⌘K" }));
    const dialog = await screen.findByRole("dialog", { name: "Command palette" });
    const areas = within(dialog).getByRole("group", { name: "Areas" });
    expect(
      within(areas)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([
      "HomeG H",
      "Engagements",
      "Tax ReturnsG T",
      "Files",
      "Knowledge",
      "WorkbenchG W",
      "Inbox",
      "Clients",
      "Binders",
      "Notices",
      "AuditsG A",
      "ClosesG C",
      "Signatures",
    ]);
    const keys = within(dialog).getByRole("group", { name: "Shortcuts" });
    expect(
      within(keys)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([
      "Go…⌘K",
      "HomeG H",
      "Tax ReturnsG T",
      "AuditsG A",
      "ClosesG C",
      "WorkbenchG W",
      "Help?",
    ]);
    fireEvent.change(within(dialog).getByRole("combobox", { name: "Search" }), {
      target: { value: "clo" },
    });
    expect(
      within(dialog)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["ClosesG C", "ClosesG C"]);
    fireEvent.click(within(dialog).getAllByRole("option")[0] as HTMLElement);
    const board = document.querySelector<HTMLElement>('[data-artboard="a"]') as HTMLElement;
    await waitFor(() => {
      expect(lit(board)).toEqual(["Closes"]);
    });
    expect(
      paths.every((p) => p === "/v1/me" || p === "/v1/notifications" || p.startsWith("/v1/me/")),
    ).toBe(true);
  });

  it("AC 1.1.8: Support opens the interim frame with the contact and System status", async () => {
    show("a");
    fireEvent.click(await screen.findByRole("button", { name: "Support" }));
    const drawer = await screen.findByRole("dialog", { name: "Support" });
    expect(within(drawer).getByText("Accrued Support")).toBeTruthy();
    expect(within(drawer).getByText("System status")).toBeTruthy();
  });

  it("a nav item goes to its landing: the screen's route, or the area's path", async () => {
    show("a");
    await screen.findByRole("button", { name: "Brightwater Hale" });
    const board = document.querySelector<HTMLElement>('[data-artboard="a"]') as HTMLElement;
    fireEvent.click(within(navOf(board)).getByRole("button", { name: "Clients" }));
    await waitFor(() => {
      expect(board.dataset.path).toBe("/clients");
    });
    expect(lit(board)).toEqual(["Clients"]);
    fireEvent.click(within(navOf(board)).getByRole("button", { name: "Engagements" }));
    await waitFor(() => {
      expect(board.dataset.path).toBe("/engagements");
    });
  });
});

describe("SHL-01 acceptance (revision.md)", () => {
  it("SHL-01 acceptance: the nav still reads the same 13 items in the same order; the 1400 width test and its fallbacks are unchanged", () => {
    expect(LABELS).toEqual(ORDER);
    expect(inMore(1400)).toEqual(["Signatures"]);
    expect(inMore(1279)).toEqual(["Audits", "Closes", "Signatures"]);
  });

  it("SHL-01 acceptance: frame g shows eight strips; every new area lights an existing nav item", () => {
    show("g");
    const r2 = strips().filter((s) => s.dataset.strip !== "");
    expect(r2).toHaveLength(8);
    for (const strip of r2) {
      const [item] = lit(strip);
      expect(LABELS).toContain(item);
    }
  });

  it("SHL-01 acceptance: the Go… tooltip shows the second line with the three actions (once the palette flag exists)", async () => {
    show("g", { "GET /v1/me/capabilities": capabilities({ palette: true }) });
    expect(
      await screen.findByText("Also: New to-do… · Load saved prompt… · Open board"),
    ).toBeTruthy();
    cleanup();
    restore?.();
    show("g");
    const tip = await screen.findByRole("tooltip");
    expect(tip.textContent).toBe("Go to anything ⌘K");
  });

  it("SHL-01 acceptance: the bell stays a 6px brick dot with no count", async () => {
    show("a", {
      "GET /v1/notifications": () => json({ items: [], unread_count: 12 }),
    });
    const bell = await screen.findByRole("button", { name: "Notifications, unread" });
    const dot = bell.querySelector<HTMLElement>('[data-dot="unread"]');
    expect(dot?.className).toContain("size-[6px]");
    expect(dot?.className).toContain("bg-red");
    expect(bell.textContent).toBe("");
    expect(document.body.textContent).not.toContain("12");
  });
});
