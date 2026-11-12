// T-05-T37 (TASK-7627; docs/screens/TXP-02.md; handoff TXP-02 A–F): "All nine artboards render,
// every column foots on screen to the golden values, and keyboard users reach the line picker."
// The screen shows the server's figures (the fixture stands in for it) and adds nothing.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { tallies, trialBalance } from "../../fixtures/seed/tax-entity";
import { COPY } from "./copy";
import { TXP02, tableRows, tallyItems } from ".";

afterEach(cleanup);

describe("TXP-02 Financials (TB → TTB)", () => {
  it("A: 28 accounts in five sections, each with its total, and the TB total at $0", () => {
    const rows = tableRows(trialBalance("run2"));
    expect(rows.filter((r) => r.id.startsWith("acct:"))).toHaveLength(28);
    expect(rows.filter((r) => r.kind === "group").map((r) => r.label)).toEqual([
      "Assets",
      "Liabilities",
      "Equity",
      "Income",
      "Rental expenses (Form 8825)",
    ]);
    const grand = rows.at(-1);
    expect(grand?.kind).toBe("grand");
    expect(Object.values(grand?.cells ?? {}).every((c) => c?.value === "0")).toBe(true);
  });

  it("A: the golden totals read in the TB grammar ($, whole dollars, credits in parentheses)", () => {
    render(
      <TXP02
        tb={trialBalance("run2")}
        tallies={tallies("run2")}
        view="account"
        statement="full"
      />,
    );
    expect(screen.getAllByText("$17,914,500").length).toBeGreaterThan(0);
    expect(screen.getAllByText("($11,048,300)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$2,641,300").length).toBeGreaterThan(0);
    expect(screen.getAllByText("($94,000)").length).toBeGreaterThan(0);
    expect(screen.getByText(COPY.footnote)).toBeTruthy();
  });

  it("A: the tally strip shows the server's tie and figure cards", () => {
    const items = tallyItems(tallies("run2"), false);
    expect(items.map((i) => i.label)).toEqual([
      "TTB balanced",
      "Unmapped",
      "Gross rents",
      "Total deductions",
      "Net rental RE income",
      "Book total assets",
    ]);
    expect(items[0]).toMatchObject({ tally: "tie" });
    expect(items[2]).toMatchObject({ value: "$3,872,900" });
    expect(items[4]).toMatchObject({ value: "$1,231,600" });
  });

  it("B: the balance sheet keeps Schedule L lines only", () => {
    const tb = trialBalance("run2", "account", "balance_sheet");
    expect(tb.rows.every((r) => (r.form_line_key ?? "").startsWith("L"))).toBe(true);
    expect(tableRows(tb).some((r) => r.id === "total:tb_total")).toBe(false);
  });

  it("C: the income statement keeps every other mapped line", () => {
    const tb = trialBalance("run2", "account", "income_statement");
    expect(tb.rows.some((r) => r.form_line_key === "8825 Rents")).toBe(true);
    expect(tb.rows.every((r) => !(r.form_line_key ?? "L").startsWith("L"))).toBe(true);
  });

  it("D: grouped by Form 1065 line, one row per line with no account number", () => {
    const tb = trialBalance("run2", "line");
    const rents = tb.rows.find((r) => r.form_line_key === "8825 Rents");
    expect(rents?.tax_basis).toBe("-3872900");
    const rows = tableRows(tb).filter((r) => r.id.startsWith("acct:"));
    expect(rows.every((r) => r.cells.code?.value === null)).toBe(true);
  });

  it("E: an unmapped account reads Map… and the Unmapped card Check; Map… opens the picker", () => {
    const onMap = vi.fn();
    render(
      <TXP02
        tb={trialBalance("run1")}
        tallies={tallies("run1")}
        view="account"
        statement="full"
        onMap={onMap}
      />,
    );
    expect(screen.getByText(COPY.map)).toBeTruthy();
    expect(screen.getByText("Check")).toBeTruthy();
    const row = screen.getByText("Escrows & other assets").closest("[role='row']");
    expect(row).not.toBeNull();
    fireEvent.keyDown(row as Element, { key: "Enter" });
    fireEvent.doubleClick(row as Element);
    expect(onMap).toHaveBeenCalledWith("1300");
  });

  it("F: building, the tallies read Pending and the rows are skeletons", () => {
    render(<TXP02 view="account" statement="full" building />);
    expect(screen.getAllByText(COPY.pending).length).toBe(6);
    expect(screen.getAllByText(COPY.building).length).toBeGreaterThan(0);
  });
});
