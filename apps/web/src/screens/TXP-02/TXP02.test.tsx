// T-05-T37 (TASK-7627; docs/screens/TXP-02.md; handoff TXP-02 A–F): "All nine artboards render,
// every column foots on screen to the golden values, and keyboard users reach the line picker."
// The screen shows the server's figures (the fixture stands in for it) and adds nothing.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { journalEntries, tallies, trialBalance } from "../../fixtures/seed/tax-entity";
import { COPY } from "./copy";
import { TXP02, derivation, entrySummary, tableRows, tallyItems } from ".";
import { LinePicker } from "./Overlays";

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
        entries={journalEntries()}
      />,
    );
    expect(screen.getAllByText("$17,914,500").length).toBeGreaterThan(0);
    expect(screen.getAllByText("($11,048,300)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$2,641,300").length).toBeGreaterThan(0);
    expect(screen.getAllByText("($94,000)").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "AJE-1" })).toBeTruthy();
    expect(screen.getByText(COPY.pyNote, { exact: false })).toBeTruthy();
  });

  it("A: the tally strip shows the handoff's nine cards, every figure the server's", () => {
    const items = tallyItems(tallies("run2"), false);
    expect(items.map((i) => i.label)).toEqual([
      "TTB balanced",
      "Balance sheet",
      "Capital tie",
      "Retained earnings",
      "Unmapped",
      "Gross rents",
      "Total deductions",
      "Net rental RE income",
      "Book total assets",
    ]);
    expect(items[0]).toMatchObject({ tally: "tie" });
    expect(items[1]).toMatchObject({ tally: "tie" });
    expect(items[2]).toMatchObject({ tally: "tie" });
    expect(items[3]).toMatchObject({
      tally: "tie",
      info: "Book net income $1,256,200 · closes to partners' capital",
    });
    expect(items[5]).toMatchObject({
      value: "$3,872,900",
      info: "Rental income $3,776,500 + Parking & other property income $96,400 = $3,872,900",
    });
    expect(items[7]).toMatchObject({ value: "$1,231,600" });
    expect((items[7] as { info?: string }).info).toContain("− Total deductions $2,641,300");
    expect((items[7] as { info?: string }).info).toContain(COPY.toScheduleK);
  });

  it("A: the capital tie's derivation is the roll-forward the spec names (AC-3.1)", () => {
    const capital = tallies("run2").items.find((i) => i.key === "capital_tie");
    expect(derivation(capital?.terms)).toBe(
      "Beginning capital $5,960,000 + Contributions $250,000 + Book net income $1,256,200 − Distributions $600,000",
    );
  });

  it("E: on Run 1 the balance sheet reads off by the unmapped account and the M-2 checks wait", () => {
    const items = tallyItems(tallies("run1"), false);
    expect(items[1]).toMatchObject({ tally: "off", vars: { amount: "($158,000)" } });
    expect(items[2]).toMatchObject({ tally: "pending" });
    expect(items[3]).toMatchObject({ tally: "pending" });
  });

  it("a3: the footnote names each entry from its server lines; its reference opens the drawer", () => {
    const aje = journalEntries()[0];
    if (aje === undefined) throw new Error("the fixture has AJE-1");
    expect(entrySummary(aje)).toBe(
      "Dr Real estate taxes 18,500 / Cr Accrued expenses 18,500 (December installment)",
    );
    const onOpenEntry = vi.fn();
    render(
      <TXP02
        tb={trialBalance("run2")}
        tallies={tallies("run2")}
        view="account"
        statement="full"
        entries={journalEntries()}
        onOpenEntry={onOpenEntry}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "AJE-1" }));
    expect(onOpenEntry).toHaveBeenCalledWith(aje);
  });

  it("a2: every account row carries its sheet 01 cells; by form line there are none", () => {
    const row = trialBalance("run2").rows.find((r) => r.account_code === "2050");
    expect(row?.cells).toEqual({ utb: "01!C10", aje: "01!D10", rje: "01!E10", atb: "01!F10" });
    expect(
      trialBalance("run2", "line").rows.every((r) => Object.keys(r.cells ?? {}).length === 0),
    ).toBe(true);
  });

  it("e2: keyboard users reach every line in the picker and a pick names its key", () => {
    const onPick = vi.fn();
    render(
      <LinePicker
        accountCode="1300"
        lines={[
          { key: "L5", label: "Schedule L · line 5 Tax-exempt securities" },
          { key: "L13", label: "Schedule L · line 13 Other assets" },
        ]}
        query=""
        onQuery={vi.fn()}
        onPick={onPick}
        onClose={vi.fn()}
        outcome="flagged"
      />,
    );
    const line = screen.getByRole("button", { name: "Schedule L · line 13 Other assets" });
    line.focus();
    expect(document.activeElement).toBe(line);
    fireEvent.click(line);
    expect(onPick).toHaveBeenCalledWith("L13");
    expect(screen.getByRole("status").textContent).toBe(COPY.pickerProposed);
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
    expect(screen.getAllByText(COPY.pending).length).toBe(9);
    expect(screen.getAllByText(COPY.building).length).toBeGreaterThan(0);
  });
});
