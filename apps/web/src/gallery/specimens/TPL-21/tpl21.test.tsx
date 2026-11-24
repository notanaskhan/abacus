// F-08-T23 (TASK-8929; handoff TPL-21; DEC-5931): "Headers read 4-5-2-2 at 9:30 AM and 3-6-2-2
// after the 10:05 AM drop, BH-FS-430 shows Agent running 40%, and the Binder footer reads 12 of
// 21 / 10 of 21." Plus Planning collapsed "8 of 8", the owners, the four overlays without colour
// fills, and nothing on the board signs off.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TPL21_STATES, Tpl21Artboard } from ".";
import { C } from "./copy";

afterEach(cleanup);
const at = (st: string) => render(<Tpl21Artboard params={{ st } as never} />);
const counts = (): number[] =>
  [...document.querySelectorAll("[data-column-header] [data-count]")].map((c) =>
    Number(c.textContent),
  );
const cardOf = (ref: string): HTMLElement => {
  const el = document.querySelector<HTMLElement>(`[data-card="${ref}"]`);
  if (el === null) throw new Error(`no card ${ref}`);
  return el;
};

describe("TPL-21 Board · Granite Peak FY2026 audit programs", () => {
  it.each(TPL21_STATES)("TPL-21%s renders", (st) => {
    at(st);
    expect(document.querySelector(`[data-artboard="${st}"]`)).not.toBeNull();
  });

  it("a: headers 4 · 5 · 2 · 2, Planning collapsed 8 of 8, owners CH and SB", () => {
    at("a");
    expect(counts()).toEqual([4, 5, 2, 2]);
    expect(document.querySelector('[data-lane="Planning"] [data-lane-done]')?.textContent).toBe(
      "8 of 8",
    );
    const ch = [
      "BH-FS-310",
      "BH-FS-325",
      "BH-FS-340",
      "BH-FS-350",
      "BH-FS-410",
      "BH-FS-420",
      "BH-FS-430",
    ];
    for (const ref of ch)
      expect(cardOf(ref).querySelector("[data-owner]")?.textContent).toBe("CH");
    expect(cardOf("BH-FS-330").getAttribute("data-flag")).toBe("input");
    expect(cardOf("BH-FS-440").getAttribute("data-flag")).toBe("client");
    expect(cardOf("BH-FS-510").querySelector('[data-agent="running"]')).not.toBeNull();
    expect(cardOf("BH-FS-410").querySelector('[data-agent="not_run"]')).not.toBeNull();
    expect(cardOf("BH-FS-310").querySelectorAll('[data-slot="signed"]')).toHaveLength(2);
  });

  it("b: dragging BH-FS-430 previews Not started 3 and In progress 6", () => {
    at("b");
    expect(counts().slice(0, 2)).toEqual([3, 6]);
  });

  it("c: after the 10:05 AM drop, 3 · 6 · 2 · 2 and BH-FS-430 Agent running 40%", () => {
    at("c");
    expect(counts()).toEqual([3, 6, 2, 2]);
    const moved = cardOf("BH-FS-430");
    expect(
      moved.querySelector('[data-agent="running"] [data-agent-progress="40"]'),
    ).not.toBeNull();
    expect(moved.querySelector("[data-spin]")).not.toBeNull();
    expect(screen.getByText(C.dropped)).toBeTruthy();
    expect(screen.getByText(C.dockLine)).toBeTruthy();
  });

  it("d: the drop guard toast; counts unchanged", () => {
    at("d");
    expect(counts()).toEqual([4, 5, 2, 2]);
    expect(screen.getByText(C.guard)).toBeTruthy();
    expect(screen.getByText(C.openSignOff)).toBeTruthy();
  });

  it("e: the Binder footer reads Preparer 12 of 21 · Reviewer 10 of 21", () => {
    at("e");
    expect(document.querySelector("[data-binder-footer]")?.textContent).toBe(
      "Preparer 12 of 21 · Reviewer 10 of 21",
    );
    expect(document.querySelectorAll("[data-binder-row]")).toHaveLength(13);
  });

  it("f: the four overlays differ, none colour-filled", () => {
    at("f");
    const cards = [...document.querySelectorAll<HTMLElement>("[data-overlays] [data-card]")];
    expect(cards).toHaveLength(4);
    for (const c of cards) expect(c.className).not.toMatch(/bg-(amber|red|green|nested)/);
    expect(cards[0]?.getAttribute("data-flag")).toBe("input");
    expect(cards[1]?.getAttribute("data-flag")).toBe("client");
    expect(cards[2]?.querySelector("[data-spin]")).not.toBeNull();
    expect(cards[3]?.querySelector('[data-bar="sent-back"]')).not.toBeNull();
  });

  it("nothing on the board signs off, approves, releases, sends or posts", () => {
    for (const st of TPL21_STATES) {
      const { unmount } = at(st);
      for (const word of ["Sign off", "Approve", "Release", "Send", "Post"]) {
        expect(screen.queryByRole("button", { name: new RegExp(`^${word}`) })).toBeNull();
      }
      unmount();
    }
  });
});
