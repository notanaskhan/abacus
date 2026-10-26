import { cleanup, fireEvent, render, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { TooltipProvider } from "../components/popover";
import { Tpl08Board } from "../specimens/tpl08";
import { flat, tpl08Messages, unmatched, waitingBySender } from "../specimens/tpl08-data";
import { installDomShims } from "../test-dom";

// F-05-T58: "Waiting rows total 23 (19 visible plus 4), the 2024 1095-C is flagged 2024 vs 2025,
// and the empty filter offers Clear filters." Plus TPL-08a to TPL-08e: the four dot states, the
// thread with the older message recessed, the row-hover File…, the unmatched sender, the filed
// thread and the agent that files nothing on its own.

beforeAll(installDomShims);
afterEach(cleanup);

function board(id: string): HTMLElement {
  const { container } = render(
    <TooltipProvider>
      <Tpl08Board id={id} />
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

describe("TPL-08 acceptance", () => {
  it("TPL-08 acceptance: waiting rows total 23 (19 visible plus 4)", () => {
    const by = waitingBySender(tpl08Messages(false));
    // The blueprint's split (01 §9): Feld 2, Shah 1, Stein 3, Collins 2, Kowal 2, Iyer 4,
    // Copperleaf 3, Northwind 2 = 19 on the rows above the fold, and 4 others below it.
    const named = [
      "claire.feld@gmail.com",
      "meera.shah@shahadvisory.com",
      "harold.stein@outlook.com",
      "wren.collins@icloud.com",
      "irene.kowal@gmail.com",
      "priyanka.iyer@gmail.com",
      "ben.ashby@copperleafcoffee.com",
      "dana.kowalski@northwindrobotics.com",
    ];
    expect(named.map((s) => by[s])).toEqual([2, 1, 3, 2, 2, 4, 3, 2]);
    const visible = named.reduce((n, s) => n + (by[s] ?? 0), 0);
    const total = Object.values(by).reduce((n, v) => n + v, 0);
    expect([visible, total - visible, total]).toEqual([19, 4, 23]);
    expect(unmatched(tpl08Messages(false))).toHaveLength(4);
    // The rail draws the 23 as amber dots on the attachments' rows.
    const a = board("tpl-08a");
    expect(a.querySelectorAll('[data-inbox-row][data-state="wait"]').length).toBeGreaterThan(0);
  });

  it("TPL-08 acceptance: the 2024 1095-C is flagged 2024 vs 2025 before filing", () => {
    const a = board("tpl-08a");
    const att = q(a, '[data-attachment="Feld_1095C_2024.pdf"]');
    expect(q(att, "[data-attachment-tag]").textContent).toBe("2024 ≠ 2025");
    expect(q(att, "[data-attachment-tag]").className).toContain("bg-red-tint");
    expect(q(att, '[data-dot="wait"]')).toBeTruthy();
    expect(
      q(a, '[data-attachment="Feld_1095C_2025.pdf"]').querySelector("[data-attachment-tag]"),
    ).toBeNull();
    // Nothing is filed silently: the agent's note waits for a decision and offers only Review.
    const note = q(a, "[data-agent-note]");
    expect(note.textContent).toContain("Both are waiting for your decision.");
    expect(
      within(note)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["Review"]);
  });

  it("TPL-08 acceptance: the empty filter offers Clear filters", () => {
    const e = board("tpl-08e");
    expect(e.querySelectorAll("[data-inbox-row]")).toHaveLength(0);
    expect(e.textContent).toContain("No messages match these filters");
    fireEvent.click(within(e).getByRole("button", { name: /Clear filters/ }));
    expect(e.querySelectorAll("[data-inbox-row]").length).toBeGreaterThan(10);
  });
});

describe("TPL-08 artboards", () => {
  it("TPL-08a Default: the Feld thread open, four dot states, the older message recessed", () => {
    const a = board("tpl-08a");
    const feld = q(a, '[data-inbox-row="feld"]');
    expect(feld.getAttribute("aria-current")).toBe("true");
    expect(feld.getAttribute("aria-expanded")).toBe("true");
    expect(q(a, '[data-inbox-row="feld-a"]').getAttribute("data-state")).toBe("wait");
    expect(q(a, '[data-inbox-row="feld-b"]').getAttribute("data-state")).toBe("filed");
    for (const dot of ["new", "wait", "filed", "ignored"]) {
      expect(a.querySelector(`[data-inbox-list] [data-dot="${dot}"]`), dot).not.toBeNull();
    }
    expect(q(a, '[data-inbox-row="varga"]').className).toContain("text-ink-3");
    const msgs = a.querySelectorAll("[data-reading=message] [data-message]");
    expect(msgs).toHaveLength(2);
    expect(msgs[0]?.className).not.toContain("bg-nested");
    expect(msgs[1]?.className).toContain("bg-nested");
    expect(msgs[0]?.textContent).toContain("September 14, 2026 9:12 AM");
    expect(q(a, '[data-client-chip="matched"]').textContent).toContain("Jonah & Claire Feld");
    expect(q(a, "[data-reading-context]").textContent).toBe("TY2025 Form 1040 · Kevin Osei");
    expect(q(a, '[data-attachment="Claire_Feld_2025_W2_MercerHill.pdf"]').textContent).toContain(
      "Filed to 2025 Binder › Income › W-2s",
    );
    expect(within(a).getByRole("button", { name: "Reply" })).toBeTruthy();
  });

  it("TPL-08b Row hover: a waiting row shows File… at the right", () => {
    const b = board("tpl-08b");
    const row = q(b, '[data-inbox-row="shah"]').closest("li");
    expect(row?.getAttribute("data-force")).toBe("hover");
    const file = q(row as HTMLElement, "[data-row-file]");
    expect(file.className).toContain("opacity-100");
    expect(within(file).getByRole("button").textContent).toBe("File…");
    // Only waiting rows offer it.
    expect(q(b, '[data-inbox-row="sound"]').closest("li")?.querySelector("[data-row-file]")).toBe(
      null,
    );
    fireEvent.click(within(file).getByRole("button"));
    expect(q(b, '[data-inbox-row="shah"]').getAttribute("aria-current")).toBe("true");
  });

  it("TPL-08c Unmatched sender: Match client… in amber ink and the agent's closest match", () => {
    const c = board("tpl-08c");
    expect(c.textContent).toContain("Invoice SE-1187");
    const chip = q(c, '[data-client-chip="unmatched"]');
    expect(chip.textContent).toContain("Match client…");
    expect(chip.className).toContain("text-amber-ink");
    expect(q(c, "[data-agent-note]").textContent).toContain("(check #2285, $3,200.00, Aug 18)");
    expect(
      q(c, '[data-attachment="SoundElectric_INV-SE-1187.pdf"] [data-dot="new"]'),
    ).toBeTruthy();
  });

  it("TPL-08d Filed: 2025 filed to Health & Medical, 2024 ignored as the wrong year", () => {
    const d = board("tpl-08d");
    expect(q(d, '[data-inbox-row="feld"]').getAttribute("data-state")).toBe("filed");
    expect(q(d, '[data-inbox-row="feld-a"]').getAttribute("data-state")).toBe("filed");
    const y25 = q(d, '[data-attachment="Feld_1095C_2025.pdf"]');
    expect(q(y25, "[data-attachment-result]").textContent).toContain(
      "Filed to 2025 Binder › Health & Medical",
    );
    const y24 = q(d, '[data-attachment="Feld_1095C_2024.pdf"]');
    expect(q(y24, "[data-attachment-result]").textContent).toBe("Ignored · wrong year");
    expect(q(y24, '[data-dot="ignored"]')).toBeTruthy();
    expect(d.querySelector("[data-agent-note]")).toBeNull();
    expect(within(d).getByRole("button", { name: "Move…" })).toBeTruthy();
  });

  it("TPL-08e Filter empty: the Client chip reads Ridgeline and the rail is empty", () => {
    const e = board("tpl-08e");
    expect(e.textContent).toContain("Ridgeline Property Partners, LP");
    expect(e.querySelector("[data-reading=header]")).toBeNull();
  });

  it("the data: every message is the File Kit's w0 inbox, no kit sample names", () => {
    const all = flat(tpl08Messages(false));
    expect(all).toHaveLength(20);
    expect(all.map((m) => m.subject)).toContain("Invoice SE-1187");
    expect(JSON.stringify(all)).not.toMatch(/Elena Ruiz|Ridgeview Partners/);
  });
});
