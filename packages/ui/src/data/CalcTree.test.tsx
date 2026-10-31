import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MatchScope } from "../tracing/match";
import { matchIdOf } from "../tracing/match-store";
import { CalcTree, type CalcTreeStep } from "./CalcTree";
import { GridTable } from "./grid";
import { VarianceCell } from "./variance";

// F-06-T19 (F-06 Story 5.6; INV-2): "Hovering or focusing a calc step lights its Sheet!Cell in
// the grid within 360 ms, and every variance state is stated in words and icons, never colour
// alone." The light is set at once and fades in 360 ms (the MATCH classes); reduced motion cuts
// the fade, not the light.

afterEach(cleanup);

const FILE = "Ridgeline capital accounts 2025.xlsx";
const at = (cell: string): string =>
  matchIdOf({ kind: "sheet_cell", file: FILE, sheet: "Capital", cell });
const STEPS: CalcTreeStep[] = [
  {
    ref: "end",
    depth: 0,
    op: "",
    label: "Ending capital",
    value: "938,561",
    src: "Capital!H3",
    match: at("H3"),
  },
  {
    ref: "dist",
    depth: 1,
    op: "−",
    label: "Distributions",
    value: "(148,500)",
    src: "Capital!G3",
    match: at("G3"),
  },
  {
    ref: "rre",
    depth: 2,
    op: "",
    label: "Net rental real estate income",
    value: "384,120",
    src: "Form 8825 · line 21",
  },
];
const COLUMNS = ["a", "b", "c", "d", "e", "f", "g", "h"].map((key) => ({ key, width: 80 }));
const ROWS = [1, 2, 3].map((n) => ({
  id: `r${String(n)}`,
  cells: Object.fromEntries(COLUMNS.map((c) => [c.key, `${c.key}${String(n)}`])),
}));

function page(): void {
  render(
    <MatchScope>
      <CalcTree label="Ending Capital · Calder Family Trust" steps={STEPS} />
      <GridTable label={FILE} source={FILE} sheet="Capital" columns={COLUMNS} rows={ROWS} />
    </MatchScope>,
  );
}

const cellOf = (id: string): HTMLElement => {
  const found = document.querySelector<HTMLElement>(`td[data-match="${id}"]`);
  if (found === null) throw new Error(`no cell ${id}`);
  return found;
};

describe("CalcTree", () => {
  it("is a tree with one level per depth", () => {
    page();
    const tree = screen.getByRole("tree", { name: "Ending Capital · Calder Family Trust" });
    const items = within(tree).getAllByRole("treeitem");
    expect(items.map((i) => i.getAttribute("aria-level"))).toEqual(["1", "2", "3"]);
    expect(items[2]?.querySelectorAll("[data-rail]")).toHaveLength(2);
  });

  it("hovering a step lights its Sheet!Cell in the grid, fading in 360 ms", async () => {
    page();
    const step = screen.getByRole("treeitem", { name: /Ending capital/ });
    act(() => {
      fireEvent.pointerEnter(step);
    });
    // The store's 120 ms hover intent, then the 360 ms fade: lit well inside 360 ms.
    await waitFor(
      () => {
        expect(cellOf(at("H3")).hasAttribute("data-lit")).toBe(true);
      },
      { timeout: 360, interval: 10 },
    );
    expect(cellOf(at("H3")).className).toContain("duration-[360ms]");
    expect(cellOf(at("G3")).hasAttribute("data-lit")).toBe(false);
  });

  it("focus lights too; Enter pins; Escape clears and returns focus", async () => {
    page();
    const step = screen.getByRole("treeitem", { name: /Distributions/ });
    act(() => {
      step.focus();
    });
    await waitFor(
      () => {
        expect(cellOf(at("G3")).hasAttribute("data-lit")).toBe(true);
      },
      { timeout: 360, interval: 10 },
    );
    act(() => {
      fireEvent.keyDown(step, { key: "Enter" });
    });
    act(() => {
      fireEvent.blur(step);
    });
    await new Promise((r) => setTimeout(r, 200)); // past the 140 ms release: a pin holds
    expect(cellOf(at("G3")).hasAttribute("data-lit")).toBe(true);
    act(() => {
      fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
    });
    await waitFor(() => {
      expect(cellOf(at("G3")).hasAttribute("data-lit")).toBe(false);
    });
  });

  it("a step whose source is a form line lights nothing", () => {
    page();
    act(() => {
      fireEvent.pointerEnter(screen.getByRole("treeitem", { name: /Net rental/ }));
    });
    expect(document.querySelectorAll("td[data-lit]")).toHaveLength(0);
  });

  it("arrow keys move focus between steps", () => {
    page();
    const items = screen.getAllByRole("treeitem");
    act(() => {
      items[0]?.focus();
    });
    act(() => {
      fireEvent.keyDown(items[0] as HTMLElement, { key: "ArrowDown" });
    });
    expect(document.activeElement).toBe(items[1]);
  });
});

describe("VarianceCell: every state in words and an icon", () => {
  const cases = [
    { state: "unexplained", v: { value: "50000", threshold: "25000" } },
    { state: "explained", v: { value: "141242", explained: { text: "Equals 2024 ending." } } },
    { state: "exception", v: { value: "-50000", exception: { issue: "2" } } },
    { state: "within", v: { value: "-862", threshold: "25000" } },
    { state: "posted", v: { value: "152600", posted: true } },
  ] as const;

  for (const { state, v } of cases) {
    it(state, () => {
      const { container } = render(<VarianceCell variance={v} format="whole" />);
      const cell = container.querySelector(`[data-variance="${state}"]`);
      expect(cell).not.toBeNull();
      expect((cell?.textContent ?? "").length).toBeGreaterThan(0);
      if (state === "posted") expect(cell?.textContent).toContain("Ties once posted");
      else expect(cell?.querySelector(".sr-only")?.textContent).not.toBe("");
    });
  }

  it("takes an explanation slot for the note", () => {
    render(
      <VarianceCell
        variance={{ value: "141242", explained: { text: "plain" } }}
        format="whole"
        explanation={<span data-slot="">rich note</span>}
      />,
    );
    expect(screen.getByText("141,242")).toBeTruthy();
  });
});
