import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DataGrid } from "./data-grid";
import type { TableColumn, TableRow } from "./types";

// F-05-T27 acceptance: "The ledger grammar renders 30px rows with cents, the arrow and Enter
// keyboard model and role=grid, and no code path sums a column in the browser."

afterEach(cleanup);

const COLUMNS: TableColumn[] = [
  { key: "date", header: "Date", type: "text", width: 76 },
  { key: "item", header: "Item", type: "label" },
  { key: "ref", header: "Reference", type: "text", width: 176 },
  { key: "amount", header: "Amount", width: 132 },
];

// The bank-rec shape (C-01 spec 02): outstanding items, then the server's total.
const ROWS: TableRow[] = [
  { id: "g1", kind: "group", label: "Outstanding checks", cells: {} },
  {
    id: "r1",
    label: "Check 1042",
    indent: 1,
    cells: { date: { value: "Aug 28" }, ref: { value: "1042" }, amount: { value: "-810" } },
  },
  {
    id: "r2",
    label: "Check 1043",
    indent: 1,
    cells: { date: { value: "Aug 29" }, ref: { value: "1043" }, amount: { value: "-1234.5" } },
  },
  {
    id: "r3",
    label: "Deposit in transit",
    cells: { date: { value: "Aug 31" }, amount: { value: "2500" } },
  },
  {
    id: "t1",
    kind: "total",
    label: "Adjusted bank balance",
    // Deliberately not the sum of the items above: the grid must print the server's figure.
    cells: { amount: { value: "48210.07" } },
  },
];

function grid(props: Partial<Parameters<typeof DataGrid>[0]> = {}) {
  render(<DataGrid label="Bank reconciliation" columns={COLUMNS} rows={ROWS} {...props} />);
  return screen.getByRole("grid", { name: "Bank reconciliation" });
}

describe("ledger grammar", () => {
  it("is a grid of rows and cells", () => {
    const g = grid();
    expect(g.getAttribute("data-grammar")).toBe("ledger");
    expect(
      within(g)
        .getAllByRole("columnheader")
        .map((c) => c.textContent),
    ).toEqual(["Date", "Item", "Reference", "Amount"]);
    expect(within(g).getAllByRole("row")).toHaveLength(ROWS.length + 1);
    expect(within(g).getAllByRole("gridcell").length).toBeGreaterThan(0);
  });

  it("draws 30px rows and a 30px header, with no zebra", () => {
    const g = grid();
    for (const cell of within(g).getAllByRole("gridcell")) {
      expect(cell.className).toContain("h-[30px]");
    }
    expect(within(g).getAllByRole("columnheader")[0]?.className).toContain("h-[30px]");
    const rows = within(g)
      .getAllByRole("row")
      .filter((r) => r.getAttribute("data-kind") === "item");
    expect(new Set(rows.map((r) => r.className)).size).toBe(1);
  });

  it("prints money with $ and cents; negatives red in parentheses", () => {
    const g = grid();
    const money = [...g.querySelectorAll("[data-money]")].map((m) => m.textContent);
    expect(money).toEqual(["($810.00)", "($1,234.50)", "$2,500.00", "$48,210.07"]);
    const negative = [...g.querySelectorAll("[data-money]")][0];
    expect(negative?.className).toContain("text-negative");
  });

  it("indents labels by the ledger's 18px step", () => {
    const g = grid();
    const cell = within(g).getByText("Check 1042");
    expect(cell.style.paddingLeft).toBe("30px");
  });

  it("prints the server's total and adds nothing up", () => {
    const g = grid();
    const total = within(g)
      .getAllByRole("row")
      .find((r) => r.getAttribute("data-kind") === "total");
    expect(total?.textContent).toContain("$48,210.07");
    expect(total?.className).toContain("font-medium");
  });
});

describe("statement grammar", () => {
  it("prints whole dollars with no $, a dash for zero, 26px cells and uppercase bands", () => {
    render(
      <DataGrid
        label="Schedule L"
        grammar="statement"
        columns={[
          { key: "line", header: "Ridgeline Property Partners, LP", entity: true },
          { key: "tax", header: "Tax" },
        ]}
        rows={[
          { id: "a", kind: "group", label: "Assets", cells: {} },
          { id: "c", label: "Cash", indent: 1, cells: { tax: { value: "412880.40" } } },
          {
            id: "d",
            label: "Accumulated depreciation",
            indent: 1,
            cells: { tax: { value: "-1486212" } },
          },
          { id: "z", label: "Other", indent: 1, cells: { tax: { value: "0" } } },
          { id: "g", kind: "grand", label: "Total assets", cells: { tax: { value: "9000000" } } },
        ]}
      />,
    );
    const g = screen.getByRole("grid", { name: "Schedule L" });
    expect([...g.querySelectorAll("[data-money]")].map((m) => m.textContent)).toEqual([
      "412,880",
      "(1,486,212)",
      "—",
      "9,000,000",
    ]);
    expect(within(g).getAllByRole("gridcell")[0]?.className).toContain("h-[26px]");
    expect(within(g).getByRole("rowheader", { name: "Assets" }).className).toContain("uppercase");
    const grand = within(g)
      .getAllByRole("row")
      .find((r) => r.getAttribute("data-kind") === "grand");
    expect(grand?.className).toContain("border-double");
  });
});

describe("keyboard model", () => {
  it("↓ and ↑ move the selection over items and totals, clamped, skipping group bands", () => {
    const onSelect = vi.fn();
    const g = grid({ onSelect });
    g.focus();
    fireEvent.keyDown(g, { key: "ArrowDown" });
    expect(onSelect).toHaveBeenLastCalledWith("r1", ROWS[1]);
    fireEvent.keyDown(g, { key: "ArrowUp" });
    expect(onSelect).toHaveBeenLastCalledWith("r1", ROWS[1]);
    for (let i = 0; i < 10; i += 1) fireEvent.keyDown(g, { key: "ArrowDown" });
    expect(onSelect).toHaveBeenLastCalledWith("t1", ROWS[4]);
    const selected = within(g)
      .getAllByRole("row")
      .filter((r) => r.getAttribute("aria-selected") === "true");
    expect(selected.map((r) => r.textContent)).toEqual([
      expect.stringContaining("Adjusted bank balance"),
    ]);
    expect(g.getAttribute("aria-activedescendant")).toBe(selected[0]?.id);
  });

  it("Home and End jump; Enter opens the selected row", () => {
    const onOpen = vi.fn();
    const g = grid({ onOpen });
    fireEvent.keyDown(g, { key: "End" });
    fireEvent.keyDown(g, { key: "Enter" });
    expect(onOpen).toHaveBeenLastCalledWith(ROWS[4]);
    fireEvent.keyDown(g, { key: "Home" });
    fireEvent.keyDown(g, { key: "Enter" });
    expect(onOpen).toHaveBeenLastCalledWith(ROWS[1]);
  });

  it("a double click opens; a click selects", () => {
    const onOpen = vi.fn();
    const onSelect = vi.fn();
    const g = grid({ onOpen, onSelect });
    const row = within(g).getByText("Deposit in transit").closest("tr");
    if (row === null) throw new Error("row");
    fireEvent.click(row);
    expect(onSelect).toHaveBeenLastCalledWith("r3", ROWS[3]);
    fireEvent.doubleClick(row);
    expect(onOpen).toHaveBeenLastCalledWith(ROWS[3]);
  });

  it("ignores keys while a button inside has focus", () => {
    const onSelect = vi.fn();
    render(
      <DataGrid
        label="With a control"
        columns={[
          { key: "item", header: "Item", type: "label" },
          { key: "note", header: "Note", type: "text" },
        ]}
        rows={[{ id: "a", label: "A", cells: { note: { value: "x" } } }]}
        onSelect={onSelect}
      />,
    );
    const g = screen.getByRole("grid", { name: "With a control" });
    const button = document.createElement("button");
    g.querySelector("td")?.appendChild(button);
    fireEvent.keyDown(button, { key: "ArrowDown" });
    expect(onSelect).not.toHaveBeenCalled();
  });
});

describe("tickmarks", () => {
  it("pins the tick and names it", () => {
    render(
      <DataGrid
        label="Evidence"
        columns={[
          { key: "item", header: "Fund", type: "label" },
          { key: "eoy", header: "End of year", tick: true },
        ]}
        rows={[
          { id: "a", label: "Vanguard 500", cells: { eoy: { value: "1200", tick: "MS" } } },
          { id: "b", label: "Stable value", cells: { eoy: { value: "800", tick: "check" } } },
          { id: "c", label: "Bond index", cells: { eoy: { value: "400", tick: "PY" } } },
        ]}
      />,
    );
    const ms = screen.getByRole("img", { name: "Matched to source" });
    expect(ms.className).toContain("bg-green");
    expect(ms.className).toContain("right-[10px]");
    expect(screen.getByRole("img", { name: "Agreed" }).textContent).toBe("");
    expect(screen.getByRole("img", { name: "Agreed to prior year" }).textContent).toBe("PY");
    expect(screen.getAllByRole("columnheader")[1]?.style.paddingRight).toBe("62px");
  });
});

describe("server totals only (ADR-050)", () => {
  it("no source in the data engine adds up a column", () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    for (const file of readdirSync(dir)) {
      if (!/\.tsx?$/.test(file) || file.includes(".test.")) continue;
      const source = readFileSync(join(dir, file), "utf8");
      expect(source, file).not.toMatch(/\.reduce\(/);
      expect(source, file).not.toMatch(/\bsum\w*\s*[(=]/i);
      expect(source, file).not.toMatch(/\+=\s*(Number|parse)/);
    }
  });
});
