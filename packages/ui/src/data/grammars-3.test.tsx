import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "../components/popover";
import { LOAD_ROWS } from "../specimens/data-3";
import { FELD_LEADSHEETS, LEADSHEET_COLUMNS, feldBox, leadsheetMatch } from "../specimens/feld-t3";
import { installDomShims } from "../test-dom";
import { MatchScope } from "../tracing/match";
import { createMatchStore, matchIdOf } from "../tracing/match-store";
import type { CitationPayload } from "../tracing/types";
import { DataGrid } from "./data-grid";
import { EvidenceTable } from "./evidence";
import { FieldBlock, type FieldItem } from "./fields";
import { GridTable, citedCells, columnLetter } from "./grid";
import { VIRTUAL_THRESHOLD } from "./row-window";

// F-05-T52: "The grid grammar shows column letters, 34px row numbers and cited cells, and 1,000
// fixture rows keep INP at 200 ms or less with sticky bands." The INP budget itself is measured in
// the browser (e2e/components.spec.ts); here: the grid's letters, numbers, rules, citations,
// comments, header row, keys and resize; the leadsheet grammar; the field rows; and the
// virtualiser rendering a window of 1,000 rows with every row's place kept.

beforeAll(installDomShims);
afterEach(cleanup);

const wrap = (node: ReactNode) => render(<TooltipProvider>{node}</TooltipProvider>);

const COLUMNS = [
  { key: "a", width: 72 },
  { key: "b", width: 300 },
  { key: "c", width: 120, align: "right" as const },
];
const ROWS = [
  { id: "h", cells: { a: "Account", b: "Name", c: "Debit" } },
  { id: "1110", cells: { a: "1110", b: "KRS 500 Index Fund", c: "6,120,450.00" } },
  { id: "1120", cells: { a: "1120", b: "KRS Target 2035 Fund", c: "2,384,910.00" } },
  { id: "1300", cells: { a: "1300", b: "Notes receivable from participants", c: "312,400.00" } },
];

describe("grid grammar", () => {
  it("draws column letters, a 34px row-number column and hairs right and bottom", () => {
    wrap(<GridTable label="Trial balance.xlsx" columns={COLUMNS} rows={ROWS} />);
    const grid = screen.getByRole("grid", { name: "Trial balance.xlsx" });
    const heads = within(grid).getAllByRole("columnheader");
    expect(heads.map((h) => h.textContent)).toEqual(["", "A", "B", "C"]);
    expect(heads[1]?.className).toContain("h-[26px]");
    expect(grid.querySelector("col")?.getAttribute("style")).toContain("width: 34px");
    const numbers = within(grid)
      .getAllByRole("rowheader")
      .map((n) => n.textContent);
    expect(numbers).toEqual(["1", "2", "3", "4"]);
    const cell = within(grid).getByText("KRS 500 Index Fund");
    expect(cell.className).toContain("border-r-[0.5px]");
    expect(cell.className).toContain("border-b-[0.5px]");
    expect(cell.className).toContain("h-[27px]");
    expect(grid.getAttribute("style")).toContain(`width: ${String(34 + 72 + 300 + 120)}px`);
  });

  it("letters run A … Z, AA; a citation names a cell, a sheet cell or a range", () => {
    expect([0, 25, 26, 27, 51, 52].map(columnLetter)).toEqual(["A", "Z", "AA", "AB", "AZ", "BA"]);
    expect(citedCells("B4")).toEqual([[1, 4]]);
    expect(citedCells("Investments!B4")).toEqual([[1, 4]]);
    expect(citedCells("D6:D7")).toEqual([
      [3, 6],
      [3, 7],
    ]);
    expect(citedCells("not a ref")).toEqual([]);
  });

  it("lights a cited cell and its row; the header row is espresso and never selectable", () => {
    const onSelect = vi.fn();
    wrap(
      <GridTable
        label="TB"
        columns={COLUMNS}
        rows={ROWS}
        headerRow
        cite="C4"
        onSelect={onSelect}
      />,
    );
    const cited = screen.getByText("312,400.00");
    expect(cited.hasAttribute("data-cited")).toBe(true);
    expect(cited.className).toContain("bg-match-bg-2");
    expect(cited.className).toContain("text-match-ink");
    expect(cited.closest("tr")?.className).toContain("bg-match-bg");
    const head = screen.getByText("Account").closest("tr");
    expect(head?.className).toContain("bg-espresso");
    expect(head?.hasAttribute("aria-selected")).toBe(false);
    fireEvent.click(screen.getByText("Account"));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("with a source, every cell carries its sheet-cell match id and lights live", () => {
    const store = createMatchStore<CitationPayload>();
    const id = matchIdOf({ kind: "sheet_cell", file: "TB.xlsx", sheet: "TB", cell: "B3" });
    wrap(
      <MatchScope store={store}>
        <GridTable label="TB" source="TB.xlsx" sheet="TB" columns={COLUMNS} rows={ROWS} />
      </MatchScope>,
    );
    const cell = screen.getByText("KRS Target 2035 Fund");
    expect(cell.getAttribute("data-match")).toBe(id);
    act(() => {
      store.togglePin(id, null);
    });
    expect(cell.hasAttribute("data-lit")).toBe(true);
    expect(cell.closest("tr")?.hasAttribute("data-lit")).toBe(true);
  });

  it("a comment puts an amber corner on its cell and says who wrote it", () => {
    wrap(
      <GridTable
        label="TB"
        columns={COLUMNS}
        rows={ROWS}
        comments={{ C4: { by: "Hannah Leclerc", text: "Agrees to the roll-forward." } }}
      />,
    );
    const cell = screen.getByText("312,400.00").closest("td");
    expect(cell?.querySelector("[data-corner]")).not.toBeNull();
    expect(cell?.textContent).toContain("Comment by Hannah Leclerc: Agrees to the roll-forward.");
  });

  it("↑ ↓ Home End select rows, Enter opens, and ← → resize a column in 16px steps", () => {
    const onOpen = vi.fn();
    wrap(<GridTable label="TB" columns={COLUMNS} rows={ROWS} headerRow onOpen={onOpen} />);
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    expect(
      screen.getByText("KRS 500 Index Fund").closest("tr")?.getAttribute("aria-selected"),
    ).toBe("true");
    fireEvent.keyDown(grid, { key: "End" });
    fireEvent.keyDown(grid, { key: "Enter" });
    expect(onOpen).toHaveBeenCalledWith(ROWS[3]);
    const handle = screen.getByRole("separator", { name: "Resize column B" });
    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(handle.getAttribute("aria-valuenow")).toBe("316");
    for (let i = 0; i < 30; i++) fireEvent.keyDown(handle, { key: "ArrowLeft" });
    expect(handle.getAttribute("aria-valuenow")).toBe("40");
  });
});

describe("leadsheet grammar", () => {
  it("has no visible column header, a 52 line-number column in ink-3 and totals at 500", () => {
    render(
      <EvidenceTable
        label="Feld leadsheet"
        grammar="leadsheet"
        blocks={FELD_LEADSHEETS.map((b) => ({ ...b, columns: LEADSHEET_COLUMNS }))}
      />,
    );
    const income = screen.getByRole("grid", { name: "Feld leadsheet: Income" });
    expect(income.querySelector("thead")?.className).toContain("sr-only");
    const line = within(income).getByText("1a");
    expect(line.className).toContain("text-ink-3");
    expect(line.getAttribute("style")).toContain("padding-right: 0px");
    expect(line.getAttribute("style")).toContain("width: 52px");
    const total = within(income).getByText("Total income").closest("tr");
    expect(total?.className).toContain("font-medium");
    expect(within(income).getByText("149,929")).toBeTruthy();
    const row = within(income).getByText("Taxable interest").closest("td");
    expect(row?.className).toContain("py-[9px]");
  });

  it("a line matched to the open document lights as a row", () => {
    const store = createMatchStore<CitationPayload>();
    render(
      <MatchScope store={store}>
        <EvidenceTable
          label="Feld leadsheet"
          grammar="leadsheet"
          blocks={FELD_LEADSHEETS.map((b) => ({ ...b, columns: LEADSHEET_COLUMNS }))}
          rowMatch={leadsheetMatch}
        />
      </MatchScope>,
    );
    act(() => {
      store.togglePin(feldBox("1099:div-1a"), null);
    });
    expect(screen.getByText("Ordinary dividends").closest("tr")?.hasAttribute("data-lit")).toBe(
      true,
    );
    expect(screen.getByText("Taxable interest").closest("tr")?.hasAttribute("data-lit")).toBe(
      false,
    );
  });
});

describe("field rows", () => {
  const box = feldBox("1099:div-1a");
  const ROW: FieldItem = {
    id: "ws-3b",
    label: "Line 3b · Ordinary dividends",
    value: "4182",
    format: "whole",
    match: box,
    source: "2025 Composite 1099 — Brokerage.pdf · page 1 · 1099-DIV box 1a",
  };

  it("a mismatch reads in red ink with the Flag on", () => {
    render(<FieldBlock title="Interest and dividends" rows={[{ ...ROW, mismatch: true }]} />);
    const value = document.querySelector("[data-field-value]");
    expect(value?.className).toContain("text-red-ink");
    expect(value?.textContent).toBe("4,182");
    const flag = screen.getByRole("button", { name: "Flag Line 3b · Ordinary dividends" });
    expect(flag.getAttribute("aria-pressed")).toBe("true");
  });

  it("Flag toggles and reports; the active match lights the value box and the label", () => {
    const onFlag = vi.fn();
    const store = createMatchStore<CitationPayload>();
    render(
      <MatchScope store={store}>
        <FieldBlock title="Interest and dividends" meta="2025" rows={[ROW]} onFlag={onFlag} />
      </MatchScope>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Flag Line 3b · Ordinary dividends" }));
    expect(onFlag).toHaveBeenCalledWith(ROW, true);
    act(() => {
      store.togglePin(box, null);
    });
    const row = document.querySelector('[data-field="ws-3b"]');
    expect(row?.hasAttribute("data-matched")).toBe(true);
    expect(row?.querySelector("[data-field-value]")?.className).toContain("bg-match-bg");
    expect(within(row as HTMLElement).getByText(ROW.label).className).toContain("font-medium");
  });

  it("Info opens the source note", () => {
    render(<FieldBlock title="Interest and dividends" rows={[ROW]} />);
    fireEvent.click(screen.getByRole("button", { name: "Info for Line 3b · Ordinary dividends" }));
    expect(
      screen.getByRole("dialog", { name: "Source of Line 3b · Ordinary dividends" }),
    ).toBeTruthy();
    expect(screen.getByText(ROW.source ?? "")).toBeTruthy();
  });
});

describe("virtualisation", () => {
  // jsdom lays nothing out: the scroll viewport reports its 420px so the window has a size.
  beforeAll(() => {
    Object.defineProperty(HTMLElement.prototype, "clientHeight", {
      configurable: true,
      get(this: HTMLElement) {
        return this.hasAttribute("data-virtual") ? 420 : 0;
      },
    });
  });
  afterAll(() => {
    Reflect.deleteProperty(HTMLElement.prototype, "clientHeight");
  });

  it("1,000 fixture rows render a window, keep every row's index, and stick header and bands", () => {
    expect(LOAD_ROWS.length).toBe(1000);
    expect(LOAD_ROWS.length).toBeGreaterThanOrEqual(VIRTUAL_THRESHOLD);
    render(
      <DataGrid
        label="1,000 rows"
        columns={[
          { key: "item", header: "Account", type: "label" },
          { key: "debit", header: "Debit" },
          { key: "credit", header: "Credit" },
        ]}
        rows={LOAD_ROWS}
        maxHeight={420}
      />,
    );
    const grid = screen.getByRole("grid", { name: "1,000 rows" });
    expect(grid.getAttribute("aria-rowcount")).toBe("1001");
    const rendered = grid.querySelectorAll("tbody tr[data-index]");
    expect(rendered.length).toBeGreaterThan(0);
    expect(rendered.length).toBeLessThan(80);
    expect(grid.closest("[data-virtual]")?.getAttribute("style")).toContain("max-height: 420px");
    expect(within(grid).getAllByRole("columnheader")[0]?.className).toContain("sticky");
    const band = within(grid).getByText("Batch 1").closest("th");
    expect(band?.className).toContain("sticky");
    expect(band?.getAttribute("style")).toContain("top: 30px");
  });

  it("a table under 200 rows does not virtualise and sticks nothing", () => {
    render(
      <DataGrid
        label="small"
        columns={[{ key: "item", header: "Item" }]}
        rows={LOAD_ROWS.slice(0, 50)}
      />,
    );
    const grid = screen.getByRole("grid", { name: "small" });
    expect(grid.closest("[data-virtual]")).toBeNull();
    expect(grid.querySelectorAll("tbody tr").length).toBe(50);
    expect(within(grid).getAllByRole("columnheader")[0]?.className).not.toContain("sticky");
  });
});
