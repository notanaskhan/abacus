import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import { AccountTree, type AccountSection } from "./account-tree";
import { DataGrid } from "./data-grid";
import { EvidenceTable } from "./evidence";
import { TallyStrip } from "./tally-strip";
import type { TableColumn, TableRow, VarianceState, VarianceValue } from "./types";
import { VARIANCE_WORD, varianceState } from "./variance";

// F-05-T43 acceptance: "The statement grammar shows whole dollars without $ and a dash for zero,
// and every variance state renders in words." Plus the evidence grammar (C-01 spec 03), the
// TallyStrip and the AccountTree (spec 02 and 06).

beforeAll(installDomShims);
afterEach(cleanup);

const cellText = (grid: HTMLElement, row: string, col: number): string =>
  within(grid)
    .getByRole("row", { name: new RegExp(row) })
    .querySelectorAll("td")[col]?.textContent ?? "";

describe("statement grammar", () => {
  it("shows whole dollars without $, and a dash for zero", () => {
    const columns: TableColumn[] = [
      { key: "line", header: "Line" },
      { key: "now", header: "2025" },
      { key: "then", header: "2024" },
    ];
    const rows: TableRow[] = [
      { id: "a", label: "Cash", cells: { now: { value: "1234567.89" }, then: { value: "0.00" } } },
      { id: "b", label: "Payables", cells: { now: { value: "-2500.40" }, then: { value: "0" } } },
    ];
    render(<DataGrid label="Statement" grammar="statement" columns={columns} rows={rows} />);
    const grid = screen.getByRole("grid", { name: "Statement" });
    expect(cellText(grid, "Cash", 1)).toBe("1,234,568");
    expect(cellText(grid, "Cash", 2)).toBe("—");
    expect(cellText(grid, "Payables", 1)).toBe("(2,500)");
    expect(cellText(grid, "Payables", 2)).toBe("—");
    expect(grid.textContent).not.toContain("$");
  });
});

describe("evidence grammar", () => {
  const columns: TableColumn[] = [
    { key: "line", header: "Description", type: "label" },
    { key: "level", header: "Level", type: "chip", width: 88 },
    { key: "end", header: "End of year", width: 180, tick: true },
  ];
  const rows: TableRow[] = [
    { id: "g", kind: "group", label: "Mutual funds", cells: {} },
    {
      id: "f",
      label: "Fund A",
      indent: 1,
      cells: { level: { value: "Level 1" }, end: { value: "100.5", tick: "MS" } },
    },
    { id: "t", kind: "total", label: "Total", cells: { end: { value: "100.5", tick: "F" } } },
  ];

  it("draws block cards on a well, th 28 and td 29, $ with cents, a fixed layout and value chips", () => {
    const { container } = render(
      <EvidenceTable
        label="Trial Balance"
        blocks={[{ id: "inv", title: "Investments", meta: "PY2025", columns, rows }]}
      />,
    );
    const frame = container.querySelector('[data-grammar="evidence"]');
    expect(frame?.className).toContain("bg-shell");
    const card = screen.getByRole("region", { name: "Investments" });
    expect(card.className).toContain("rounded-pane");
    expect(card.className).toContain("shadow-e1");
    expect(within(card).getByRole("heading", { name: "Investments" })).toBeTruthy();
    expect(within(card).getByText("PY2025")).toBeTruthy();
    const grid = screen.getByRole("grid", { name: "Trial Balance: Investments" });
    expect(grid.className).toContain("table-fixed");
    expect(grid.querySelector("th")?.className).toContain("h-[28px]");
    expect(grid.querySelector("td")?.className).toContain("h-[29px]");
    expect(cellText(grid, "Fund A", 2)).toContain("$100.50");
    expect(within(grid).getByText("Level 1").className).toContain("rounded-prop");
    expect(within(grid).getByRole("img", { name: "Matched to source" })).toBeTruthy();
  });

  it("card={false} drops the cards and the well", () => {
    const { container } = render(
      <EvidenceTable label="TB" card={false} blocks={[{ id: "b", columns, rows }]} />,
    );
    expect(container.querySelector('[data-grammar="evidence"]')?.className).not.toContain(
      "bg-shell",
    );
    expect(container.querySelector("section")?.className).not.toContain("rounded-pane");
  });
});

describe("variance cell", () => {
  const base: VarianceValue = { value: "13742.62", ratio: "0.285", threshold: "1000" };
  const cases: { state: VarianceState; v: VarianceValue }[] = [
    { state: "within", v: { value: "-999.99", threshold: "1000" } },
    { state: "unexplained", v: base },
    { state: "explained", v: { ...base, explained: { text: "Price increase", by: "Raj" } } },
    { state: "exception", v: { ...base, exception: { issue: "9" } } },
    { state: "posted", v: { ...base, posted: true, exception: { issue: "9" } } },
  ];

  it("takes posted, then exception, explained, within, unexplained; |Δ| compared exactly", () => {
    for (const { state, v } of cases) expect(varianceState(v), state).toBe(state);
    expect(varianceState({ value: "1000.00", threshold: "1000" })).toBe("within");
    expect(varianceState({ value: "-1000.01", threshold: "1000" })).toBe("unexplained");
    expect(varianceState({ value: "5" })).toBe("unexplained");
  });

  it("renders every state in words, with the action column", () => {
    const onExplain = vi.fn();
    const onIssue = vi.fn();
    const columns: TableColumn[] = [
      { key: "acct", header: "Account" },
      { key: "chg", header: "Change", type: "variance" },
    ];
    const rows: TableRow[] = cases.map(({ state, v }) => ({
      id: state,
      label: `Row ${state}`,
      cells: { chg: { value: null, variance: v } },
    }));
    render(
      <DataGrid
        label="Flux"
        columns={columns}
        rows={rows}
        onExplain={onExplain}
        onIssue={onIssue}
      />,
    );
    const grid = screen.getByRole("grid", { name: "Flux" });
    expect(within(grid).getAllByRole("columnheader")).toHaveLength(3);
    for (const { state } of cases) {
      const row = within(grid).getByRole("row", { name: new RegExp(`Row ${state}`) });
      expect(row.textContent, state).toContain(VARIANCE_WORD[state]);
      expect(row.querySelector(`[data-variance="${state}"]`), state).not.toBeNull();
    }
    const unexplained = within(grid).getByRole("row", { name: /Row unexplained/ });
    expect(unexplained.querySelectorAll("td")[1]?.className).toContain("bg-amber-tint");
    expect(unexplained.textContent).toContain("$13,742.62");
    expect(unexplained.textContent).toContain("28.5%");
    fireEvent.click(within(unexplained).getByRole("button", { name: "Explain…" }));
    expect(onExplain).toHaveBeenCalledWith(expect.objectContaining({ id: "unexplained" }), "chg");
    const exception = within(grid).getByRole("row", { name: /Row exception/ });
    fireEvent.click(within(exception).getByRole("button", { name: "Issue 9" }));
    expect(onIssue).toHaveBeenCalledWith(expect.objectContaining({ id: "exception" }));
    const explained = within(grid).getByRole("row", { name: /Row explained/ });
    expect(explained.querySelector("[data-corner]")).not.toBeNull();
    const posted = within(grid).getByRole("row", { name: /Row posted/ });
    expect(within(posted).getByText("Ties once posted")).toBeTruthy();
    expect(within(posted).queryByRole("button")).toBeNull();
    const withinRow = within(grid).getByRole("row", { name: /Row within/ });
    expect(withinRow.querySelector("td.bg-amber-tint")).toBeNull();
  });
});

describe("TallyStrip", () => {
  it("draws each check's label and its second line in words", () => {
    const onLink = vi.fn();
    render(
      <TallyStrip
        label="Checks"
        items={[
          { label: "Capital foots", tally: "tie" },
          { label: "M-1 reconciles", tally: "off", vars: { amount: "8,500" } },
          { label: "Requests", value: "11 / 24", info: "Received of requested" },
          { label: "Roll-forward", tally: "check", link: { text: "Open", onClick: onLink } },
          { label: "Trust report", tally: "pending" },
          { label: "Planning", running: "Running" },
          { label: "Signed off", signs: [{ initials: "HL", when: "Sep 14", name: "H. L." }] },
        ]}
      />,
    );
    const strip = screen.getByRole("list", { name: "Checks" });
    const cards = within(strip).getAllByRole("listitem");
    expect(cards).toHaveLength(7);
    expect(cards[0]?.className).toContain("h-[52px]");
    expect(within(strip).getByText("Capital foots").className).toContain("uppercase");
    expect(within(strip).getByText("tie")).toBeTruthy();
    expect(within(strip).getByText("off 8,500")).toBeTruthy();
    expect(within(strip).getByText("11 / 24")).toBeTruthy();
    expect(within(strip).getByRole("img", { name: "Received of requested" })).toBeTruthy();
    expect(within(strip).getByText("Pending")).toBeTruthy();
    expect(within(strip).getByText("Running")).toBeTruthy();
    expect(within(strip).getByText("HL · Sep 14")).toBeTruthy();
    fireEvent.click(within(strip).getByRole("button", { name: /Open/ }));
    expect(onLink).toHaveBeenCalledOnce();
  });
});

describe("AccountTree", () => {
  const sections: AccountSection[] = [
    {
      title: "Assets",
      accounts: [
        {
          id: "1000",
          num: "1000",
          name: "Cash",
          balance: "1500.00",
          children: [{ id: "1010", num: "1010", name: "Operating", balance: "1500.00" }],
        },
        {
          id: "1300",
          num: "1300",
          name: "Inventory",
          balance: "900.00",
          open: false,
          children: [{ id: "1310", num: "1310", name: "Green coffee", balance: "900.00" }],
        },
      ],
    },
    {
      title: "Liabilities",
      accounts: [{ id: "2000", num: "2000", name: "Allowance", balance: "-120.00" }],
    },
  ];

  it("indents 12, 30 by level, starts a closed parent closed, and prints balances", () => {
    render(<AccountTree label="Chart" sections={sections} />);
    const tree = screen.getByRole("tree", { name: "Chart" });
    expect(within(tree).getByRole("group", { name: "Assets" })).toBeTruthy();
    const cash = within(tree).getByRole("treeitem", { name: /Cash/ });
    expect(cash.getAttribute("aria-expanded")).toBe("true");
    expect(cash.style.paddingLeft).toBe("12px");
    expect(cash.className).toContain("h-[37px]");
    expect(within(tree).getByRole("treeitem", { name: /Operating/ }).style.paddingLeft).toBe(
      "30px",
    );
    expect(
      within(tree)
        .getByRole("treeitem", { name: /Inventory/ })
        .getAttribute("aria-expanded"),
    ).toBe("false");
    expect(within(tree).queryByRole("treeitem", { name: /Green coffee/ })).toBeNull();
    expect(within(tree).getByText("($120.00)")).toBeTruthy();
  });

  it("↓ ↑ move, → opens then enters, ← leaves then closes, Enter opens", () => {
    const onOpen = vi.fn();
    render(<AccountTree label="Chart" sections={sections} onOpen={onOpen} />);
    const tree = screen.getByRole("tree", { name: "Chart" });
    const sel = (): string =>
      within(tree)
        .getAllByRole("treeitem")
        .find((el) => el.getAttribute("aria-selected") === "true")?.textContent ?? "";
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    expect(sel()).toContain("Cash");
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    expect(sel()).toContain("Operating");
    fireEvent.keyDown(tree, { key: "ArrowLeft" });
    expect(sel()).toContain("Cash");
    fireEvent.keyDown(tree, { key: "ArrowLeft" });
    expect(within(tree).queryByRole("treeitem", { name: /Operating/ })).toBeNull();
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    expect(sel()).toContain("Inventory");
    fireEvent.keyDown(tree, { key: "ArrowRight" });
    expect(within(tree).getByRole("treeitem", { name: /Green coffee/ })).toBeTruthy();
    fireEvent.keyDown(tree, { key: "ArrowRight" });
    expect(sel()).toContain("Green coffee");
    fireEvent.keyDown(tree, { key: "Enter" });
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "1310" }));
    fireEvent.keyDown(tree, { key: "End" });
    expect(sel()).toContain("Allowance");
  });

  it("the chevron toggles without selecting", () => {
    const onSelect = vi.fn();
    render(<AccountTree label="Chart" sections={sections} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "Expand Inventory" }));
    expect(screen.getByRole("treeitem", { name: /Green coffee/ })).toBeTruthy();
    expect(onSelect).not.toHaveBeenCalled();
  });
});
