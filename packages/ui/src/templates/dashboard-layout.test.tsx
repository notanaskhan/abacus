import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { PRACTICE_VIEWS, T11Specimen, Tpl11Specimen } from "../specimens/dashboard";
import { RETURNS_BY_OFFICE } from "../specimens/seed-figures";
import { installDomShims } from "../test-dom";

// F-05-T46 acceptance: "Role variants, the quiet day and Office Denver recompute from fixtures
// with every count tying to blueprint section 9.5 and KPI type at 22px or less." Plus Home offers
// no decide action: a queue row is a link to where the decision is made (F-05 F8, INV-1).

beforeAll(installDomShims);
afterEach(cleanup);

function board(container: HTMLElement, id: string): HTMLElement {
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no artboard ${id}`);
  return el;
}

const tiles = (el: HTMLElement): string[] =>
  [...el.querySelectorAll("[data-tile]")].map((t) => t.getAttribute("aria-label") ?? "");

const queueTitles = (el: HTMLElement): string[] =>
  [...el.querySelectorAll("a[data-queue-row]")].map(
    (a) => a.querySelector(".font-medium")?.textContent ?? "",
  );

describe("blueprint §9.5 footings", () => {
  const all = PRACTICE_VIEWS.all;
  it("all offices: Prepared 17 · In review 15 · Issues 11 · Ready 7, audits 27, closes 11 of 22, notices 9 with 2 new", () => {
    expect(all.tax).toEqual([17, 15, 11, 7]);
    expect(all.audits.reduce((a, b) => a + b, 0)).toBe(all.auditsTotal);
    expect(all.auditsTotal).toBe(27);
    expect(all.closes).toEqual({ inProgress: 11, total: 22 });
    expect(all.notices).toEqual({ open: 9, isNew: 2 });
  });

  it("Denver: its share of each, and 64 of the 224 returns (98 + 64 + 62)", () => {
    const den = PRACTICE_VIEWS.Denver;
    expect(den.audits.reduce((a, b) => a + b, 0)).toBe(den.auditsTotal);
    for (const [i, n] of den.tax.entries()) expect(n).toBeLessThanOrEqual(all.tax[i] ?? 0);
    expect(den.closes.total).toBeLessThanOrEqual(all.closes.total);
    expect(den.caption).toBe(`Denver · ${String(RETURNS_BY_OFFICE.Denver)} returns`);
    expect(Object.values(RETURNS_BY_OFFICE).reduce((a, b) => a + b, 0)).toBe(224);
  });
});

describe("TPL-11", () => {
  it("TPL-11a: Margaret's tiles and her four items, each a link with no decide control", () => {
    const a = board(render(<Tpl11Specimen />).container, "tpl-11a");
    expect(tiles(a)).toEqual([
      "17 Prepared",
      "15 In review",
      "11 Issues",
      "7 Ready",
      "Audits & assurance · 27",
      "11 In progress of 22 · August 2026",
      "9 2 New Notices open",
    ]);
    expect(queueTitles(a)).toHaveLength(4);
    expect(a.textContent).toContain("Tax returns · TY2025 · 79 open");
    expect(a.textContent).toContain("3 running");
    expect(within(a).queryAllByRole("button", { name: /^(Approve|Decide|Sign off)/ })).toEqual([]);
    expect(a.textContent).toContain("Proposed v1 by Accrued Agent");
  });

  it("TPL-11b to d: the tax partner, the staff member's My returns and the admin's tiles", () => {
    const { container } = render(<Tpl11Specimen />);
    expect(queueTitles(board(container, "tpl-11b"))[1]).toBe(
      "Release K-1s — Ridgeline (5 recipients)",
    );
    const c = board(container, "tpl-11c");
    expect(within(c).getByRole("heading", { name: "My returns" })).toBeTruthy();
    expect(tiles(board(container, "tpl-11d")).slice(4)).toEqual([
      "17 Signatures out",
      "23 Inbox waiting",
      "4 Portal invites pending",
    ]);
  });

  it("TPL-11e: nothing waiting on you", () => {
    const e = board(render(<Tpl11Specimen />).container, "tpl-11e");
    expect(e.textContent).toContain("Nothing waiting on you.");
    expect(queueTitles(e)).toEqual([]);
  });

  it("TPL-11f: Denver recomputes the tiles, the caption and the deadlines, and the chip is amber", () => {
    const f = board(render(<Tpl11Specimen />).container, "tpl-11f");
    expect(tiles(f).slice(0, 4)).toEqual(["5 Prepared", "4 In review", "3 Issues", "2 Ready"]);
    expect(f.querySelector('[data-dashboard="caption"]')?.textContent).toBe("Denver · 64 returns");
    expect(tiles(f)[4]).toBe("Audits & assurance · 9");
    const deadlines = [...f.querySelectorAll("li[data-deadline]")].map((li) => li.textContent);
    expect(deadlines.map((t) => t.slice(0, 6))).toEqual(["Sep 16", "Sep 23", "Sep 28"]);
    const chip = within(f).getByRole("button", { name: /Office/ });
    expect(chip.className).toContain("amber");
  });
});

describe("T11", () => {
  it("role variants: partner, manager, staff and admin each have their own queue", () => {
    const { container } = render(<T11Specimen />);
    expect(queueTitles(board(container, "t11a"))).toHaveLength(5);
    expect(queueTitles(board(container, "t11b"))[0]).toBe(
      "Tell Accrued Agent which composite 1099 the Feld return uses",
    );
    expect(queueTitles(board(container, "t11c"))).toHaveLength(3);
    expect(queueTitles(board(container, "t11d"))).toHaveLength(4);
  });

  it("T11e: the quiet day; T11f: skeletons and a busy tile row", () => {
    const { container } = render(<T11Specimen />);
    expect(board(container, "t11e").textContent).toContain("Nothing waiting on you.");
    const f = board(container, "t11f");
    expect(f.querySelector('[data-dashboard="tiles"]')?.getAttribute("aria-busy")).toBe("true");
    expect(f.querySelectorAll("[data-tile]")).toHaveLength(0);
  });

  it("the Office chip filters the queue and the deadlines from each row's office", () => {
    installDomShims();
    const b = board(render(<T11Specimen />).container, "t11b");
    fireEvent.pointerDown(within(b).getByRole("button", { name: /Office/ }), { button: 0 });
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Denver" }));
    expect(queueTitles(b)).toEqual(["Approve the Whitley document reminder"]);
    expect(b.textContent).toContain("Granite Peak Outdoor Supply");
    expect(b.textContent).not.toContain("Calloway Family Trust");
  });
});

describe("KPI type stays at 22px or less", () => {
  it("tile numbers use the dashboard role, which theme.css sets at 20px", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const theme = readFileSync(join(here, "..", "theme.css"), "utf8");
    const size = /--text-dashboard:\s*(\d+(?:\.\d+)?)px/.exec(theme)?.[1];
    expect(Number(size)).toBeLessThanOrEqual(22);
    const { container } = render(<Tpl11Specimen />);
    for (const tile of container.querySelectorAll("[data-tile='single'] > span:first-child"))
      expect(tile.className).toContain("text-dashboard");
  });
});
