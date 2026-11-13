// F-07-T12 (F-07 §F; TPL-13): the fixtures foot, and every artboard renders with its risk taken
// from the data. "Sep 15 = 8 × 1065 + 3 × 1120-S + 2 envelopes = 13 and Copperleaf is the only
// overdue item, and all seven artboards render with risk taken from data."
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TPL13_BOARDS, Tpl13Specimen } from "./tpl13";
import { TPL13_CHIPS, TPL13_DENVER, TPL13_ITEMS, TPL13_POSTPONED } from "./tpl13-data";

afterEach(cleanup);

const on = (date: string) => TPL13_ITEMS.filter((i) => i.chip.date === date);

describe("TPL-13 fixtures foot (blueprint §9.3, §9.5, §9.7)", () => {
  it("Sep 15 = 8 × 1065 + 3 × 1120-S + 2 envelopes = 13", () => {
    const sep15 = on("2026-09-15");
    const count = (k: string) => sep15.filter((i) => i.kind === k).length;
    expect([count("1065"), count("1120-S"), count("envelope")]).toEqual([8, 3, 2]);
    expect(sep15).toHaveLength(13);
  });

  it("Copperleaf's August close is the only overdue item", () => {
    expect(TPL13_CHIPS.filter((c) => c.tier === "overdue").map((c) => c.label)).toEqual([
      "Copperleaf · August close",
    ]);
  });

  it("Denver keeps exactly the seven items TPL-13d names", () => {
    expect(TPL13_DENVER.map((c) => c.label)).toEqual([
      "Copperleaf · August close",
      "Hollis Creek Veterinary · 1120-S",
      "Pinecrest Pediatrics · 1120-S",
      "Granite Peak · Engagement letter",
      "Whitley · CP2000 response",
      "Quintero · CP501 response",
      "Copperleaf · CO DOR notice",
    ]);
  });

  it("Calloway Trust's 1041 is postponed to Nov 2 and nothing else moves", () => {
    const moved = TPL13_POSTPONED.filter((c) => c.postponedTo !== undefined);
    expect(moved.map((c) => [c.label, c.postponedTo])).toEqual([
      ["Calloway Trust · Form 1041", "2026-11-02"],
    ]);
  });

  it("names no client the blueprint leaves unnamed", () => {
    const open = TPL13_CHIPS.filter((c) => c.id.startsWith("open-1065"));
    expect(open).toHaveLength(2);
    for (const c of open) expect(c.client).toBe("open row in TAX-01");
  });
});

describe("TPL-13 artboards", () => {
  it("renders all seven, Labor Day marked and today circled", () => {
    render(<Tpl13Specimen />);
    for (const b of TPL13_BOARDS)
      expect(document.querySelector(`[data-tpl13="${b.id}"]`)).not.toBeNull();
    expect(TPL13_BOARDS.map((b) => b.id)).toEqual(["a", "a2", "b", "c", "d", "e", "f"]);
    expect(screen.getAllByText("Labor Day").length).toBeGreaterThan(0);
  });

  it("a shows the Ridgeline rule; a2 the Sep 15 header; f the empty state", () => {
    render(<Tpl13Specimen />);
    const a = document.querySelector('[data-tpl13="a"]') as HTMLElement;
    expect(within(a).getByText(/15th day of the 3rd month/)).toBeTruthy();
    expect(within(a).getByText("In review · Partner")).toBeTruthy();
    const a2 = document.querySelector('[data-tpl13="a2"]') as HTMLElement;
    expect(within(a2).getByText(/Sep 15 · 13 items: 11 extended returns/)).toBeTruthy();
    const f = document.querySelector('[data-tpl13="f"]') as HTMLElement;
    expect(within(f).getByText("No deadlines match these filters.")).toBeTruthy();
    expect(within(f).getByRole("button", { name: "Clear filters" })).toBeTruthy();
  });

  it("e shows the postponed pill", () => {
    render(<Tpl13Specimen />);
    const e = document.querySelector('[data-tpl13="e"]') as HTMLElement;
    expect(within(e).getAllByText("Postponed → Nov 2").length).toBeGreaterThan(0);
  });
});
