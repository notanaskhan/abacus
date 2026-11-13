// I-02-T16 (TASK-7915; docs/screens/HOME-05.md; SPEC-654 §3.9): "HOME-05 c renders HOME-01
// geometry exactly, flag off removes the chip, link and bell entry, and hovering Needs-you-first
// row 2 lights Sign-off row 7."
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DANIEL_ROWS, danielToday } from "../../fixtures/seed/today";
import { readCollapsed, writeCollapsed } from "../../domain/today";
import { TodayPanel } from "../SHL-23";
import { lightRows } from ".";

afterEach(cleanup);

function must<T>(v: T | null | undefined): T {
  if (v === null || v === undefined) throw new Error("expected an element");
  return v;
}

describe("HOME-05 docked Today", () => {
  it("hovering Needs-you-first row 2 lights its HOME-01 row", () => {
    const capital = DANIEL_ROWS[1];
    const home = document.createElement("div");
    home.innerHTML = `<ul><li data-gate="${capital?.gate_id ?? ""}"></li><li data-gate="other"></li></ul>`;
    const onHighlight = vi.fn((refs: readonly string[] | null) => {
      lightRows(home, refs);
    });
    render(<TodayPanel vm={danielToday()} onHighlight={onHighlight} />);
    const row = document.querySelector(`[data-row="${capital?.gate_id ?? ""}"]`);
    fireEvent.mouseEnter(must(row));
    expect(
      home.querySelector(`[data-gate="${capital?.gate_id ?? ""}"]`)?.getAttribute("data-lit"),
    ).toBe("true");
    expect(home.querySelector('[data-gate="other"]')?.hasAttribute("data-lit")).toBe(false);
    fireEvent.mouseLeave(must(row));
    expect(home.querySelector("[data-lit]")).toBeNull();
  });

  it("the collapse preference survives in storage and fails safe without it", () => {
    writeCollapsed(true);
    expect(readCollapsed()).toBe(true);
    writeCollapsed(false);
    expect(readCollapsed()).toBe(false);
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readCollapsed()).toBe(false);
    spy.mockRestore();
  });
});
