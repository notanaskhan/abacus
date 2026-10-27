import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { AGENT_TONES, IconTile } from "../agent/agent-card";
import { TooltipProvider } from "../components/popover";
import { T5Board } from "../specimens/t5";
import {
  AGENTS,
  INTEGRATIONS,
  agentCategories,
  connectCategories,
  visibleAgents,
} from "../specimens/t5-data";
import { installDomShims } from "../test-dom";

// F-05-T59: "The library shows 28 agents (Audit 3/1/1) and Connect shows 9 of 53 (9+38+6) with
// monogram tiles and no vendor logos or brand colours." Plus one test per artboard, T5a to T5f and
// TPL-05a to TPL-05e, and the live parts: My Agents, Notify me, Enable and Disconnect.

beforeAll(installDomShims);
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function board(id: string): HTMLElement {
  const { container } = render(
    <TooltipProvider>
      <T5Board id={id} />
    </TooltipProvider>,
  );
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no board ${id}`);
  return el;
}

const cards = (el: HTMLElement): HTMLElement[] => [
  ...el.querySelectorAll<HTMLElement>("[data-catalog-card]"),
];
const names = (el: HTMLElement): string[] =>
  cards(el).map((c) => c.getAttribute("aria-label") ?? "");
const empty = (el: HTMLElement): HTMLElement => {
  const e = el.querySelector<HTMLElement>("[data-empty]");
  if (e === null) throw new Error("no empty state");
  return e;
};
const badges = (el: HTMLElement, code: string): number =>
  el.querySelectorAll(`[data-badge="${code}"]`).length;
const counts = (el: HTMLElement): string[] =>
  [...el.querySelectorAll('[role="option"]')].map(
    (o) =>
      `${o.querySelector("span span")?.textContent ?? ""} ${o.querySelector("[data-count]")?.textContent ?? ""}`,
  );

const CONNECTED = [
  "CCH Axcess Tax",
  "CCH Axcess Practice",
  "QuickBooks Online",
  "NetSuite",
  "Sage Intacct",
  "Xero",
  "Box",
  "Microsoft 365",
  "DocuSign",
];

const BANNED = /^(Approve|Sign off|Release|Send|Post|Decide)\b/;

describe("F-05-T59 acceptance", () => {
  it("F-05-T59 acceptance: the library shows 28 agents (Audit 3/1/1)", () => {
    const a = board("tpl-05a");
    expect(cards(a)).toHaveLength(28);
    expect(counts(a)).toEqual([
      "All Categories 28",
      "Tax Preparation 4",
      "Tax Review 5",
      "Tax Research 2",
      "Client Service 4",
      "Firm Operations 5",
      "Audit 5",
      "Accounting & Close 3",
    ]);
    const audit = AGENTS.filter((x) => x.cat === "audit");
    expect(
      ["installed", "available", "coming_soon"].map(
        (s) => audit.filter((x) => x.status === s).length,
      ),
    ).toEqual([3, 1, 1]);
    const sum = agentCategories(AGENTS, "Library")
      .slice(1)
      .reduce((n, c) => n + (c.count ?? 0), 0);
    expect(sum).toBe(28);
  });

  it("F-05-T59 acceptance: Connect shows 9 of 53 (9+38+6) with monogram tiles and no vendor logos or brand colours", () => {
    const e = board("tpl-05e");
    expect(cards(e)).toHaveLength(53);
    expect([badges(e, "connected"), badges(e, "available"), badges(e, "coming_soon")]).toEqual([
      9, 38, 6,
    ]);
    expect(
      cards(e)
        .filter((c) => c.querySelector('[data-badge="connected"]') !== null)
        .map((c) => c.getAttribute("aria-label")),
    ).toEqual(CONNECTED.map((n) => `${n}, Connected`));
    // Monogram tiles only: no image, no logo, and every tile fill is a category token.
    expect(e.querySelectorAll("img, image, [data-logo]")).toHaveLength(0);
    const tiles = [...e.querySelectorAll("[data-catalog-card] [data-glyph='vendor-tile']")];
    expect(tiles).toHaveLength(53);
    for (const t of tiles) {
      const fill = t.querySelector("rect")?.getAttribute("class") ?? "";
      expect(fill).toMatch(/^fill-(green|espresso|clay|amber|red)$/);
      expect(t.getAttribute("data-monogram")).toMatch(/^[A-Z0-9]{1,2}$/);
      expect(t.innerHTML).not.toMatch(/#[0-9a-f]{3,6}|rgb/i);
    }
    expect(counts(e).map((c) => c.split(" ").pop())).toEqual([
      "53",
      "8",
      "5",
      "8",
      "13",
      "8",
      "12",
      "3",
      "3",
      "5",
    ]);
  });

  it("TPL-05e acceptance: CCH Axcess Practice is card 2, Firm connection · added by Felix Andersen", () => {
    const second = cards(board("tpl-05e"))[1];
    if (second === undefined) throw new Error("no card 2");
    expect(second.getAttribute("aria-label")).toBe("CCH Axcess Practice, Connected");
    expect(second.querySelector("[data-scope]")?.textContent).toBe(
      "Firm connection · added by Felix Andersen",
    );
    expect(second.querySelector("[data-tags]")?.textContent).toBe("Practice Management");
    expect(within(second).getByRole("button", { name: "Disconnect" })).toBeTruthy();
  });
});

describe("T5 artboards", () => {
  it("T5a Agents · Library: 28 cards, the sub-row's Library on, tiles in category tones", () => {
    const a = board("t5a");
    expect(names(a).slice(0, 9)).toEqual([
      "Return Review Packet, Installed",
      "Prior-Year & Return Version Check, Available",
      "K-1 Reconciliation Workpaper, Installed",
      "Missing Document Chaser, Installed",
      "Source-Cited Tax Research Memo, Available",
      "Season Progress Reporter, Installed",
      "EBP Audit Workpapers, Installed",
      "Bank Reconciliation, Installed",
      "Workflow Status Reconciliation, Coming soon",
    ]);
    expect(cards(a)).toHaveLength(28);
    expect(a.querySelector('[data-catalog="sub-row"] [aria-selected="true"]')?.textContent).toBe(
      "Library",
    );
    expect(a.querySelector('[data-icon-tile="review"]')?.className).toMatch(/\bbg-green\b/);
    expect(a.querySelector('[data-icon-tile="operations"]')?.className).toMatch(/\bbg-red\b/);
  });

  it("T5b Filtered by category: Audit selected, 3 installed, 1 available, 1 coming soon", () => {
    const b = board("t5b");
    expect(b.querySelector('[role="option"][aria-selected="true"]')?.textContent).toContain(
      "Audit",
    );
    expect(names(b)).toEqual([
      "EBP Audit Workpapers, Installed",
      "Trial Balance Tie-Out, Installed",
      "Sample Selection & Item Requests, Installed",
      "Internal Control Exceptions Grader, Available",
      "Fraud Brainstorm Minutes, Coming soon",
    ]);
  });

  it("T5c Search, no results: “Form 941” shows the empty state; Clear search brings 28 back", () => {
    const c = board("t5c");
    expect(cards(c)).toHaveLength(0);
    expect(within(c).getByText("No agents match ‘Form 941’.")).toBeTruthy();
    fireEvent.click(within(empty(c)).getByRole("button", { name: "Clear search" }));
    expect(cards(c)).toHaveLength(28);
  });

  it("T5d Loading: six skeleton cards hold the grid, each a tile and three bars", () => {
    const d = board("t5d");
    const grid = d.querySelector("[data-catalog-grid]");
    expect(grid?.getAttribute("aria-busy")).toBe("true");
    const sk = d.querySelectorAll("[data-catalog-skeleton]");
    expect(sk).toHaveLength(6);
    expect(sk[0]?.children).toHaveLength(4);
  });

  it("T5e Connect · Integrations: 53 tiles 212 tall, the well pads 14, search at the right", () => {
    const e = board("t5e");
    expect(cards(e)).toHaveLength(53);
    expect(cards(e)[0]?.className).toMatch(/h-\[212px\]/);
    expect(e.querySelector('[data-catalog="well"]')?.className).toMatch(/\bp-\[14px\]/);
    expect(e.querySelector('[data-catalog="sub-row"]')).toBeNull();
    expect(within(e).getByRole("searchbox", { name: "Search integrations" })).toBeTruthy();
  });

  it("T5f Connect · filtered: Tax Software is 1 connected, 6 available and 1 coming soon", () => {
    const f = board("t5f");
    expect(cards(f)).toHaveLength(8);
    expect([badges(f, "connected"), badges(f, "available"), badges(f, "coming_soon")]).toEqual([
      1, 6, 1,
    ]);
  });
});

describe("TPL-05 artboards", () => {
  it("TPL-05a Default: About card, categories, and Notify me on the coming-soon card", () => {
    const a = board("tpl-05a");
    expect(a.querySelector('[data-record="about-card"]')?.textContent).toContain(
      "Explore agents published by Accrued.",
    );
    const soon = cards(a).find((c) => c.getAttribute("aria-label")?.endsWith("Coming soon"));
    if (soon === undefined) throw new Error("no coming-soon card");
    const notify = within(soon).getByRole("button", { name: "Notify me" });
    fireEvent.click(notify);
    expect(
      within(soon).getByRole("button", { name: "Notifying you" }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(soon.className).not.toMatch(/hover:shadow-e3/);
  });

  it("TPL-05b Filtered · Audit: five audit agents", () => {
    expect(cards(board("tpl-05b"))).toHaveLength(5);
  });

  it("TPL-05c Search, no results: “payroll tax” yields the EmptyState with Clear search", () => {
    const c = board("tpl-05c");
    expect(within(c).getByText("No agents match ‘payroll tax’.")).toBeTruthy();
    expect(within(empty(c)).getByRole("button", { name: "Clear search" })).toBeTruthy();
  });

  it("TPL-05d Loading: six skeleton cards", () => {
    expect(board("tpl-05d").querySelectorAll("[data-catalog-skeleton]")).toHaveLength(6);
  });

  it("TPL-05e Connect · WB-10: the Integrations About card and the nine connected first", () => {
    const e = board("tpl-05e");
    expect(e.querySelector('[data-record="about-card"]')?.textContent).toContain(
      "Firm connections are shared; personal connections act as you.",
    );
    expect(names(e).slice(0, 2)).toEqual([
      "CCH Axcess Tax, Connected",
      "CCH Axcess Practice, Connected",
    ]);
  });
});

describe("T5 live parts", () => {
  it("My Agents shows installed agents only, and the counts follow the view", () => {
    const a = board("t5a");
    fireEvent.click(within(a).getByRole("tab", { name: "My Agents" }));
    const installed = AGENTS.filter((x) => x.status === "installed").length;
    expect(cards(a)).toHaveLength(installed);
    expect(counts(a)[0]).toBe(`All Categories ${String(installed)}`);
  });

  it("CategoryList: ↓ moves the selection and filters the grid", () => {
    const a = board("t5a");
    const all = a.querySelector<HTMLElement>('[role="option"][aria-selected="true"]');
    if (all === null) throw new Error("no selected row");
    fireEvent.keyDown(all, { key: "ArrowDown" });
    expect(a.querySelector('[role="option"][aria-selected="true"]')?.textContent).toContain(
      "Tax Preparation",
    );
    expect(cards(a)).toHaveLength(4);
  });

  it("the status filter keeps the category and its counts", () => {
    const shown = visibleAgents(AGENTS, {
      view: "Library",
      cat: "audit",
      status: "installed",
      q: "",
    });
    expect(shown).toHaveLength(3);
    expect(connectCategories(INTEGRATIONS)[0]?.count).toBe(53);
  });

  it("Enable shows Connecting…, then Connected as added by the viewer", () => {
    vi.useFakeTimers();
    const e = board("t5e");
    const ultra = cards(e).find((c) => c.getAttribute("aria-label") === "UltraTax CS, Available");
    if (ultra === undefined) throw new Error("no UltraTax CS");
    fireEvent.click(within(ultra).getByRole("button", { name: "Enable" }));
    expect(ultra.querySelector('[data-badge="connecting"]')?.textContent).toContain("Connecting");
    act(() => {
      vi.advanceTimersByTime(1600);
    });
    expect(ultra.querySelector('[data-badge="connected"]')).not.toBeNull();
    expect(ultra.querySelector("[data-scope]")?.textContent).toBe(
      "Firm connection · added by Hannah Leclerc",
    );
  });

  it("Disconnect asks first, then the tile is Available", () => {
    const e = board("t5e");
    const box = cards(e).find((c) => c.getAttribute("aria-label") === "Box, Connected");
    if (box === undefined) throw new Error("no Box");
    fireEvent.click(within(box).getByRole("button", { name: "Disconnect" }));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog.textContent).toContain("Disconnect Box?");
    expect(dialog.textContent).toContain(
      "Agents stop reading from Box for everyone at Brightwater Hale. Anything already filed in Accrued stays where it is.",
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Disconnect" }));
    expect(box.getAttribute("aria-label")).toBe("Box, Available");
  });

  it("no card offers Approve, Sign off, Release, Send, Post or Decide", () => {
    for (const id of ["t5a", "t5e"]) {
      const el = board(id);
      for (const b of within(el).queryAllByRole("button")) {
        expect(b.textContent.trim()).not.toMatch(BANNED);
      }
      cleanup();
    }
  });

  it("IconTile draws its tone as a token fill and a white glyph", () => {
    const { container } = render(
      <>
        {(Object.keys(AGENT_TONES) as (keyof typeof AGENT_TONES)[]).map((t) => (
          <IconTile key={t} tone={t} />
        ))}
      </>,
    );
    const tiles = [...container.querySelectorAll("[data-icon-tile]")];
    expect(tiles).toHaveLength(7);
    for (const t of tiles) {
      expect(t.className).toMatch(/\bbg-(green|espresso|amber|clay|red)\b/);
      expect(t.className).toMatch(/\btext-on-dark\b/);
      expect(t.className).toMatch(/size-\[34px\]/);
    }
  });
});
