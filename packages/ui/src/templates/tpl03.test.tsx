import { act, cleanup, fireEvent, render, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { TooltipProvider } from "../components/popover";
import { FELD_1040_LINES, FELD_HALVARD, FELD_K1 } from "../specimens/seed-figures";
import { HALVARD_BOXES, K1_BOXES, K1_DOC, K1_FILE, Tpl03Board } from "../specimens/tpl03";
import { installDomShims } from "../test-dom";

// F-05-T54: "Box 5 lights Interest Income $4,600, the Review count moves from 37 to 36 on approve,
// and 307,900, 4,600, 1,550 and 150,000 foot in seed tests" (the footing is the app's seed test,
// apps/web/src/fixtures/specimen-figures.test.ts). Plus TPL-03a to TPL-03e: the presets, the
// Prepare preset's 1a ↔ 3b and 1b ↔ 3a, Unapprove, the flag pill, the loading pages.

beforeAll(installDomShims);
afterEach(cleanup);

function board(id: string): HTMLElement {
  const { container } = render(
    <TooltipProvider>
      <Tpl03Board id={id} />
    </TooltipProvider>,
  );
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no board ${id}`);
  return el;
}

const row = (el: HTMLElement, id: string): HTMLElement => {
  const found = el.querySelector<HTMLElement>(`[data-triad-doc="${id}"]`);
  if (found === null) throw new Error(`no doc ${id}`);
  return found;
};

const k1Row = (el: HTMLElement, id: string): HTMLElement => {
  const found = el.querySelector<HTMLElement>(`[data-k1-row="${id}"]`);
  if (found === null) throw new Error(`no K-1 row ${id}`);
  return found;
};

const reviewTab = (el: HTMLElement): string =>
  within(el).getByRole("tab", { name: /Review/ }).textContent;

describe("TPL-03 Feld 1040 review", () => {
  it("TPL-03a: box 5 and Interest Income $4,600 are lit together, and nothing else is", () => {
    const a = board("tpl-03a");
    expect(a.querySelector("[data-split]")?.getAttribute("data-split")).toBe("review");
    const lit = [...a.querySelectorAll("[data-lit][data-match]")];
    expect(lit.length).toBeGreaterThanOrEqual(2);
    for (const el of lit) expect(el.getAttribute("data-match")).toBe(K1_BOXES.box5.match);
    const interest = k1Row(a, "interest");
    expect(interest.hasAttribute("data-lit")).toBe(true);
    expect(interest.textContent).toBe("Interest Income$4,600");
    expect(interest.className).toContain("bg-match-bg");
    expect(a.textContent).toContain(K1_FILE);
    expect(row(a, "k1").getAttribute("aria-current")).toBe("true");
    expect(row(a, "k1").textContent).toContain(K1_DOC);
  });

  it("TPL-03a: the K-1 matrix draws the seed's 307,900 · 4,600 · 1,550 · 150,000 and Item L", () => {
    const a = board("tpl-03a");
    const values = (id: string): string => k1Row(a, id).textContent;
    expect(values("rental")).toContain("$307,900");
    expect(values("interest")).toContain("$4,600");
    expect(values("taxexempt")).toContain("$1,550");
    expect(values("dist")).toContain("$150,000");
    expect(values("begin")).toContain("$1,500,000");
    expect(values("ending")).toContain("$1,912,500");
    expect(values("ending")).toContain("Ridgeline M-2 is off 6,200 — Item L will change");
    expect(values("status")).toContain("Draft K-1 · pre-release");
    expect(values("gp")).toContain("—");
    expect(FELD_K1.box2).toBe("307900");
  });

  it("TPL-03a: tabs read Overview · Intake 2 · Review 37 · Issues 4 · Activity, Issues red-tint", () => {
    const a = board("tpl-03a");
    const tabs = within(a)
      .getAllByRole("tab")
      .map((t) => t.textContent);
    expect(tabs.slice(0, 5)).toEqual(["Overview", "Intake2", "Review37", "Issues4", "Activity"]);
    expect(a.textContent).toContain("Synced Sep 10");
  });

  it("approving the draft K-1 moves Review from 37 to 36, toasts, and offers Unapprove", () => {
    const a = board("tpl-03a");
    expect(reviewTab(a)).toBe("Review37");
    const approve = within(a).getByRole("button", { name: /Approve Document/ });
    expect(approve.getAttribute("data-human-verb")).toBe("Approve");
    act(() => {
      fireEvent.click(approve);
    });
    expect(reviewTab(a)).toBe("Review36");
    expect(a.textContent).toContain("Approved Ridgeline K-1 (draft) for review");
    expect(row(a, "k1").querySelector('[data-state="approved"]')?.textContent).toContain("1");
    act(() => {
      fireEvent.click(within(a).getByRole("button", { name: "Unapprove Document" }));
    });
    expect(reviewTab(a)).toBe("Review37");
  });

  it("TPL-03b Prepare: 214 · 571 · 571; box 1a lights line 3b, with the linked-figure tag", () => {
    const b = board("tpl-03b");
    expect(b.querySelector("[data-split]")?.getAttribute("data-split")).toBe("taxReview");
    expect(row(b, "halvard").getAttribute("aria-current")).toBe("true");
    const lit = [...b.querySelectorAll("[data-lit]")];
    for (const el of lit.filter((x) => x.hasAttribute("data-match")))
      expect(el.getAttribute("data-match")).toBe(HALVARD_BOXES.div1a.match);
    expect(lit.some((el) => el.textContent.includes("3b Ordinary dividends"))).toBe(true);
    expect(b.textContent).toContain("Form 1040 · Line 3b");
    expect(b.textContent).toContain("2a Tax-exempt interest");
    expect(b.textContent).toContain("6,910");
    expect(b.textContent).toContain("11,960");
    expect(b.textContent).toContain("14,820");
    // The Form 1040 lines are the seed's Halvard figures.
    expect(FELD_1040_LINES.line3b).toBe(FELD_HALVARD.ordinaryDividends);
    expect(FELD_1040_LINES.line3a).toBe(FELD_HALVARD.qualifiedDividends);
  });

  it("TPL-03c Approved: ✓ 1 in ink (never green), Review 36, Unapprove Document in the footer", () => {
    const c = board("tpl-03c");
    expect(reviewTab(c)).toBe("Review36");
    const pill = row(c, "k1").querySelector<HTMLElement>('[data-state="approved"]');
    expect(pill?.textContent).toContain("1");
    expect(pill?.outerHTML ?? "").not.toMatch(/\bbg-green|\btext-green/);
    const unapprove = within(c).getByRole("button", { name: "Unapprove Document" });
    expect(unapprove.getAttribute("data-unapprove")).toBe("");
  });

  it("TPL-03d Flagged: ⚑ 1 in amber on the K-1 row, pointing to TAX-06; the agent never approves", () => {
    const d = board("tpl-03d");
    const flag = row(d, "k1").querySelector<HTMLElement>("[data-flags]");
    expect(flag?.getAttribute("data-flags")).toBe("1");
    expect(flag?.getAttribute("title")).toBe("Opens TAX-06 · Return issues");
    expect(flag?.className).toContain("amber");
    expect(row(d, "k1").querySelector("[data-info]")).not.toBeNull();
    // The NYC worksheet carries ⓘ and no document check.
    expect(row(d, "nyc").querySelector("[data-state]")).toBeNull();
    expect(row(d, "nyc").querySelector("[data-info]")).not.toBeNull();
  });

  it("TPL-03e Loading pages: the viewer draws the gray page skeleton", () => {
    const e = board("tpl-03e");
    const viewer = e.querySelector<HTMLElement>('[data-triad-pane="viewer"]');
    expect(viewer?.querySelector('[aria-busy="true"], [data-skeleton]')).not.toBeNull();
  });

  it("the viewer bar has no Download capsule; Download is in ⋯; TINs are masked", () => {
    const a = board("tpl-03a");
    const viewer = a.querySelector<HTMLElement>('[data-triad-pane="viewer"]');
    expect(within(viewer as HTMLElement).queryByRole("button", { name: "Download" })).toBeNull();
    expect(a.textContent).not.toMatch(/\d{3}-\d{2}-\d{4}/);
  });
});
