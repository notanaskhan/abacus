import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { TooltipProvider } from "../components/popover";
import { InboxDot } from "../inbox/inbox-kit";
import { T8Board } from "../specimens/t8";
import { installDomShims } from "../test-dom";

// F-05-T56: "T8a to T8e render the four dot states exactly, ignored rows go ink-3, and Match client
// appears as an amber-ink chip." Plus the frame (filter bar, 392 rail, reading pane), the filed
// thumbnail, the agent's filing note, the thread, File… and the empty filter.

beforeAll(installDomShims);
afterEach(cleanup);

function board(id: string): HTMLElement {
  const { container } = render(
    <TooltipProvider>
      <T8Board id={id} />
    </TooltipProvider>,
  );
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no board ${id}`);
  return el;
}

const q = (el: HTMLElement, sel: string): HTMLElement => {
  const found = el.querySelector<HTMLElement>(sel);
  if (found === null) throw new Error(`no ${sel}`);
  return found;
};

const rows = (el: HTMLElement): string[] =>
  [...el.querySelectorAll("[data-inbox-row]")].map(
    (r) => `${r.getAttribute("data-inbox-row") ?? ""}:${r.getAttribute("data-state") ?? ""}`,
  );

describe("T8 InboxLayout", () => {
  it("draws the four dot states exactly: 16 ring, 16 amber, 15 olive ✓, 15 gray ✕", () => {
    const { container } = render(
      <>
        <InboxDot state="new" />
        <InboxDot state="wait" />
        <InboxDot state="filed" />
        <InboxDot state="ignored" />
      </>,
    );
    const dot = (s: string): HTMLElement => q(container, `[data-dot="${s}"]`);
    expect(dot("new").className).toMatch(/size-\[16px\].*inset-ring-\[1\.5px\].*inset-ring-ink-4/);
    expect(dot("new").className).not.toMatch(/\bbg-/);
    expect(dot("wait").className).toMatch(/size-\[16px\].*bg-amber/);
    expect(dot("wait").querySelector("svg")).toBeNull();
    expect(dot("filed").className).toMatch(/size-\[15px\].*bg-green/);
    expect(dot("filed").querySelector("svg")).not.toBeNull();
    expect(dot("ignored").className).toMatch(/size-\[15px\].*bg-ink-4/);
    expect(dot("ignored").querySelector("svg")).not.toBeNull();
    expect(
      ["new", "wait", "filed", "ignored"].map((s) => dot(s).getAttribute("aria-label")),
    ).toEqual(["Not filed", "Waiting to be filed", "Filed", "Ignored"]);
  });

  it("T8a Waiting: the rail on the inbox preset; ignored hidden; the Feld 1099 waits", () => {
    const a = board("t8a");
    expect(q(a, "[data-split]").getAttribute("data-split")).toBe("inbox");
    expect(rows(a)).toEqual([
      "pay:new",
      "brk:wait",
      "aug:new",
      "tb:wait",
      "harbor:filed",
      "cap:new",
      "rcpt:new",
    ]);
    expect(q(a, '[data-inbox-row="brk"]').getAttribute("aria-current")).toBe("true");
    expect(q(a, '[data-client-chip="matched"]').textContent).toContain("Jonah & Claire Feld");
    const note = q(a, "[data-agent-note]");
    expect(note.textContent).toContain(
      "Accrued Agent filed 2 of 3 attachments to 2025 Binder · Income",
    );
    expect(note.querySelector('[data-actor="agent"]')).not.toBeNull();
    // INV-1: the agent's note offers Review only.
    expect(
      within(note)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["Review"]);
    const thumbs = [...a.querySelectorAll("[data-attachment] [data-dot]")].map((d) =>
      d.getAttribute("data-dot"),
    );
    expect(thumbs).toEqual(["wait", "filed", "filed"]);
    expect(within(a).getByRole("button", { name: "File…" })).toBeTruthy();
  });

  it("T8b Filed: the Harborline row reads Filed to …, its thumbnail carries the check, Move…", () => {
    const b = board("t8b");
    const row = q(b, '[data-inbox-row="harbor"]');
    expect(row.textContent).toContain(
      "Filed to Northwind 401(k) PY2025 › Investments › Trust statements",
    );
    expect(q(b, '[data-attachment] [data-dot="filed"]')).toBeTruthy();
    expect(within(b).getByRole("button", { name: "Move…" })).toBeTruthy();
    expect(q(b, "[data-agent-note]").textContent).toContain(
      "All 1 attachment is filed to Northwind 401(k) PY2025 · Investments",
    );
    expect(within(q(b, "[data-agent-note]")).queryByRole("button")).toBeNull();
  });

  it("T8c Ignored: show ignored is on and the newsletter row reads ink-3 at 400", () => {
    const c = board("t8c");
    expect(
      within(c).getByRole("button", { name: "Show ignored" }).getAttribute("aria-pressed"),
    ).toBe("true");
    const row = q(c, '[data-inbox-row="news"]');
    expect(row.getAttribute("data-state")).toBe("ignored");
    expect(row.className).toContain("text-ink-3");
    const subject = row.querySelector(".text-section");
    expect(subject?.className).toContain("font-normal");
    expect(subject?.className).toContain("text-ink-3");
    expect(q(c, '[data-inbox-row="brk"]').querySelector(".text-section")?.className).toContain(
      "font-medium",
    );
    expect(within(c).queryByRole("button", { name: "File…" })).toBeNull();
    expect(within(c).getByRole("button", { name: "Reply" })).toBeTruthy();
  });

  it("T8d Unmatched sender: the chip reads Match client… in amber ink", () => {
    const d = board("t8d");
    const chip = q(d, '[data-client-chip="unmatched"]');
    expect(chip.textContent).toContain("Match client…");
    expect(chip.className).toContain("text-amber-ink");
    expect(d.textContent).toContain("From Paycrest Payroll <soc.reports@…>");
  });

  it("T8e Empty filter: Ridgeline and Waiting to be filed match nothing; Clear filters restores", () => {
    const e = board("t8e");
    expect(e.querySelectorAll("[data-inbox-row]")).toHaveLength(0);
    const chips = [...e.querySelectorAll('[data-active="true"]')].map((c) => c.textContent);
    expect(chips.join(" ")).toContain("Ridgeline Property Partners, LP");
    expect(chips.join(" ")).toContain("Waiting to be filed");
    expect(e.textContent).toContain("No messages match these filters");
    expect(e.textContent).toContain(
      "Widen the date range or clear a filter to see more of the inbox.",
    );
    act(() => {
      fireEvent.click(within(e).getByRole("button", { name: "Clear filters →" }));
    });
    expect(e.querySelectorAll("[data-inbox-row]")).toHaveLength(7);
  });

  it("the Copperleaf thread opens its replies indented 34, newest first", () => {
    const a = board("t8a");
    const parent = q(a, '[data-inbox-row="aug"]');
    expect(parent.getAttribute("aria-expanded")).toBe("false");
    act(() => {
      fireEvent.click(parent);
    });
    expect(rows(a).slice(2, 5)).toEqual(["aug:new", "aug-2:ignored", "aug-1:filed"]);
    expect(q(a, '[data-inbox-row="aug-2"]').className).toContain("pl-[34px]");
    expect(q(a, '[data-inbox-row="aug-2"]').className).toContain("text-ink-3");
  });

  it("File… files the message where the agent suggests, and the row turns filed", async () => {
    board("t8a");
    const file = screen.getByRole("button", { name: "File…" });
    file.focus();
    fireEvent.keyDown(file, { key: "ArrowDown" });
    const item = await screen.findByRole("menuitem", { name: "2025 Binder › Income › 1099-DIV" });
    fireEvent.click(item);
    await waitFor(() => {
      expect(document.querySelector('[data-inbox-row="brk"]')?.getAttribute("data-state")).toBe(
        "filed",
      );
    });
    expect(document.body.textContent).toContain("Filed to 2025 Binder › Income › 1099-DIV");
  });
});
