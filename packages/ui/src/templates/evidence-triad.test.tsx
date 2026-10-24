import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "../components/popover";
import { feldBox } from "../specimens/feld-t3";
import { T3Board } from "../specimens/t3";
import { installDomShims } from "../test-dom";
import { TriadFooter } from "./evidence-triad";

// F-05-T53: "T3b shows the ink check micro-pill (never green), T3d shows the red-ink mismatch with
// Flag, and Approve Document is a HumanAction." Plus the presets' panes, the flagged and loading
// states, and a worksheet field lighting with its box on the page in one MatchScope.

beforeAll(installDomShims);
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function board(id: string): HTMLElement {
  const { container } = render(
    <TooltipProvider>
      <T3Board id={id} />
    </TooltipProvider>,
  );
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no board ${id}`);
  return el;
}

const docRow = (el: HTMLElement, id: string): HTMLElement => {
  const row = el.querySelector<HTMLElement>(`[data-triad-doc="${id}"]`);
  if (row === null) throw new Error(`no doc ${id}`);
  return row;
};

describe("T3 EvidenceTriad", () => {
  it("T3a Prepare: tree 214 · viewer 571 · sheet 571; the 1099's check is neutral with no count", () => {
    const a = board("t3a");
    expect(a.querySelector("[data-triad]")?.getAttribute("data-triad")).toBe("prepare");
    expect(a.querySelector("[data-split]")?.getAttribute("data-split")).toBe("taxReview");
    expect(a.querySelectorAll("[data-split-pane]")).toHaveLength(3);
    const check = docRow(a, "c1099").querySelector('[data-state="unapproved"]');
    expect(check?.getAttribute("aria-label")).toBe("Not approved");
    expect(check?.textContent).toBe("");
    expect(docRow(a, "w2").querySelector('[data-state="approved"]')).not.toBeNull();
  });

  it("T3b Review: 452 × 3 on Leadsheets; the approved 1099 shows ✓ 1 in ink, never green", () => {
    const b = board("t3b");
    expect(b.querySelector("[data-split]")?.getAttribute("data-split")).toBe("review");
    expect(
      within(b)
        .getByRole("tab", { name: /Leadsheets/ })
        .getAttribute("aria-selected"),
    ).toBe("true");
    const pill = docRow(b, "c1099").querySelector<HTMLElement>('[data-state="approved"]');
    expect(pill?.textContent).toContain("1");
    const html = pill?.outerHTML ?? "";
    expect(html).not.toMatch(/\bbg-green|\btext-green/);
    expect(pill?.querySelector("svg")?.getAttribute("class")).toContain("text-ink");
    expect(within(b).getByRole("button", { name: "Approved" })).toHaveProperty("disabled", true);
  });

  it("T3c Prepare · flagged: the 1099 shows ⚑ 1 in amber", () => {
    const flag = docRow(board("t3c"), "c1099").querySelector<HTMLElement>("[data-flags]");
    expect(flag?.getAttribute("data-flags")).toBe("1");
    expect(flag?.className).toContain("bg-amber-tint");
    expect(flag?.textContent).toContain("1");
  });

  it("T3d Two-pane: the sheet beside a 490 viewer; Line 3b reads 4,182 in red ink with the Flag on", () => {
    const d = board("t3d");
    expect(d.querySelector("[data-split]")?.getAttribute("data-split")).toBe("two");
    expect(d.querySelectorAll("[data-split-pane]")).toHaveLength(2);
    expect(d.querySelector('[data-triad-pane="tree"]')).toBeNull();
    const row = d.querySelector<HTMLElement>('[data-field="ws-3b"]');
    const value = row?.querySelector("[data-field-value]");
    expect(value?.textContent).toBe("4,182");
    expect(value?.className).toContain("text-red-ink");
    const flag = within(row as HTMLElement).getByRole("button", {
      name: "Flag Line 3b · Ordinary dividends",
    });
    expect(flag.getAttribute("aria-pressed")).toBe("true");
  });

  it("T3e Review · loading pages: the viewer draws skeleton pages", () => {
    const viewer = board("t3e").querySelector('[data-triad-pane="viewer"]');
    expect(viewer?.querySelector('[data-loading], [aria-busy="true"]')).not.toBeNull();
  });

  it("Approve Document is a HumanAction: it approves, and an agent actor draws none", () => {
    const a = board("t3a");
    const approve = within(a).getByRole("button", { name: "Approve Document" });
    expect(approve.getAttribute("data-human-verb")).toBe("Approve");
    fireEvent.click(approve);
    expect(docRow(a, "c1099").querySelector('[data-state="approved"]')).not.toBeNull();
    cleanup();
    render(<TriadFooter actor={{ kind: "agent" }} approved={false} />);
    expect(screen.queryByRole("button", { name: /Approve/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Issue…" })).toBeTruthy();
  });

  it("Issue… raises a flag on the open document", () => {
    const a = board("t3a");
    fireEvent.click(within(a).getByRole("button", { name: "Issue…" }));
    expect(docRow(a, "c1099").querySelector("[data-flags]")?.getAttribute("data-flags")).toBe("1");
  });

  it("hovering a worksheet field lights its box on the page and the field together", () => {
    vi.useFakeTimers();
    const a = board("t3a");
    const row = a.querySelector<HTMLElement>('[data-field="ws-3b"]');
    fireEvent.pointerEnter(row as HTMLElement);
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(row?.hasAttribute("data-matched")).toBe(true);
    const region = a.querySelector(
      `[data-triad-pane="viewer"] [data-match="${feldBox("1099:div-1a")}"]`,
    );
    expect(region?.hasAttribute("data-lit")).toBe(true);
  });

  it("a requested document has no file: Requested, and nothing to approve", () => {
    const a = board("t3a");
    const row = docRow(a, "ptax");
    expect(row.textContent).toContain("Requested");
    fireEvent.click(row);
    expect(within(a).getByRole("button", { name: "Approve Document" })).toHaveProperty(
      "disabled",
      true,
    );
  });
});
