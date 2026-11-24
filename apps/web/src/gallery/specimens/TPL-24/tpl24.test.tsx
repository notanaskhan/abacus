// F-08-T19 (TASK-8926; handoff TPL-24; DEC-5928): "TPL-24a to g render with D14 =SUM(D12:D13)
// linked, tickmarks 2/1/0/3/0, exactly F12-F14 changed in d, and no host brand colours or
// Microsoft marks." Plus the leadsheet's figures and the pane's intents (it never signs).
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TPL24_STATES, Tpl24Artboard } from ".";
import { C } from "./copy";

afterEach(cleanup);
const at = (st: string) => render(<Tpl24Artboard params={{ st } as never} />);
const cell = (a: string): HTMLElement => {
  const found = document.querySelector<HTMLElement>(`[data-cell="${a}"]`);
  if (found === null) throw new Error(`no cell ${a}`);
  return found;
};

// Host brand colours (Excel green, Word blue) and Microsoft's names or marks never appear.
const BRAND = /#(217346|107c41|185abd|2b579a|0078d4)|microsoft|office\.js|ms-office/i;

describe("TPL-24 add-in pane specimen", () => {
  it("a: D14 =SUM(D12:D13), linked, selected; the leadsheet foots", () => {
    at("a");
    expect(document.querySelector("[data-formula]")?.textContent).toBe("=SUM(D12:D13)");
    expect(cell("D14").getAttribute("aria-selected")).toBe("true");
    expect(cell("D14").querySelector("[data-linked]")).not.toBeNull();
    expect(document.querySelectorAll("[data-linked]")).toHaveLength(1);
    expect(cell("D12").textContent).toBe("3,962,400");
    expect(cell("D13").textContent).toBe("217,600");
    expect(cell("D14").textContent).toBe("4,180,000");
    expect(cell("C14").textContent).toBe("3,310,000");
    expect(cell("G14").textContent).toBe("870,000");
    expect([cell("H12"), cell("H13"), cell("H14")].map((c) => c.textContent)).toEqual([
      "26.7%",
      "20.0%",
      "26.3%",
    ]);
    expect(cell("D19").textContent).toBe("—");
    expect(screen.getByText(C.link.workbook(1))).toBeTruthy();
    expect(cell("D24").querySelector("[data-comment]")).not.toBeNull();
  });

  it("b: tickmarks 2 / 1 / 0 / 3 / 0, matching the glyphs in the grid", () => {
    at("b");
    const usage = ["✓", "⊕", "∧", "◊", "¢"].map(
      (m) => document.querySelector(`[data-usage="${m}"]`)?.textContent,
    );
    expect(usage).toEqual(["2", "1", "0", "3", "0"]);
    const grid = ["E12", "E13", "E14"].map((a) => cell(a).textContent).join(" ");
    expect(grid.split("✓").length - 1).toBe(2);
    expect(grid.split("⊕").length - 1).toBe(1);
    expect(grid.split("◊").length - 1).toBe(3);
  });

  it("c: the preparer signed at 2:21 PM, the reviewer awaited; D13 now linked too", () => {
    at("c");
    expect(screen.getByText(C.signOff.signedBy)).toBeTruthy();
    expect(screen.getByText(C.signOff.awaiting)).toBeTruthy();
    expect(document.querySelectorAll("[data-linked]")).toHaveLength(2);
  });

  it("d: exactly F12–F14 changed after sign-off", () => {
    at("d");
    const changed = [...document.querySelectorAll<HTMLElement>("[data-cell]")]
      .filter((c) => c.className.includes("bg-amber-tint"))
      .map((c) => c.dataset.cell);
    expect(changed).toEqual(["F12", "F13", "F14"]);
    const list = document.querySelector<HTMLElement>("[data-changes]") as HTMLElement;
    expect(
      within(list)
        .getAllByText(/^F1[234]$/)
        .map((e) => e.textContent),
    ).toEqual(["F12", "F13", "F14"]);
    // The pane only opens the sign-off (SHL-12); nothing here signs.
    expect(screen.getByRole("button", { name: C.changes.again })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Sign off$/ })).toBeNull();
  });

  it("e: offline, 2 changes waiting, last synced 2:14 PM", () => {
    at("e");
    expect(document.querySelector("[data-offline]")).not.toBeNull();
    expect(screen.getByText(C.offline.queued(2))).toBeTruthy();
    expect(screen.getByText("Last synced 2:14 PM")).toBeTruthy();
  });

  it("f: the Word host shows exactly the two incoming changes", () => {
    at("f");
    expect(document.querySelector('[data-host="word"]')).not.toBeNull();
    expect(screen.getByText(C.word.incoming(2))).toBeTruthy();
    expect(document.querySelectorAll("[data-incoming] li")).toHaveLength(2);
    expect(screen.getByRole("button", { name: C.word.update })).toBeTruthy();
  });

  it("g: signed out offers the firm's SSO", () => {
    at("g");
    expect(screen.getByRole("button", { name: C.signedOut.sso("Brightwater Hale") })).toBeTruthy();
  });

  it("no host brand colours or Microsoft marks in any state", () => {
    for (const st of TPL24_STATES) {
      const { container, unmount } = at(st);
      expect(container.innerHTML).not.toMatch(BRAND);
      expect(container.querySelector("img, svg[data-vendor]")).toBeNull();
      unmount();
    }
  });
});
