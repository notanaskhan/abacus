// T-05-T38 (TASK-7628; handoff TXP-11 A–E): the workbook sheets TXP-11 reads in fixture mode, as
// the server's `GET …/workbook/sheets/{sheet}` answers them (`WorkbookSheetCellsOut`). Values are
// exact decimal strings or text, verbatim from the handoff; formulas are the engine's written-back
// text. 05 Capital before the fix (A: H8:H12 empty, J16 off 6,200), with the fix proposed (B:
// H8:H12 flagged "Proposed") and after it (B2: J13 = J15 = 6,866,200); 01 Trial Balance rows 6–18
// (C: I18 = F18+G18+H18). Synthetic only.
import type { WorkbookCellOut, WorkbookSheetCellsOut } from "@abacus/api-client";
import type { Snapshot } from "./tax-entity";

type Cell = readonly [address: string, value: string | null, formula?: string | null];

function cell([address, value, formula]: Cell, state?: WorkbookCellOut["state"]): WorkbookCellOut {
  const f = formula ?? null;
  return {
    address,
    value,
    formula: f,
    author: f === null ? "run_step" : "formula",
    state: state ?? (f === null ? "value" : "formula"),
    version: 2,
  };
}

const TEXT_05: readonly Cell[] = [
  ["A1", "Ridgeline Property Partners, LP"],
  ["A2", "05 Capital — partners' capital, tax basis · TY2025 · workbook v2"],
  [
    "A3",
    "Sources: beginning = 2024 K-1 Item L · income = 06 Schedule K · transfers = 04 Partner Txns · distributions = 01 Trial Balance acct 3200",
  ],
  ["A7", "Partner"],
  ["B7", "% 1/1–6/30"],
  ["C7", "% 7/1–12/31"],
  ["D7", "Beginning"],
  ["E7", "Contributions"],
  ["F7", "Income (rental + interest)"],
  ["G7", "Transfers"],
  ["H7", "Other increases (tax-exempt)"],
  ["I7", "Distributions"],
  ["J7", "Ending"],
  ["K7", "Item L check"],
  ["A15", "Partners' capital per Schedule L line 21 (01 Trial Balance)"],
  ["A16", "Difference"],
];

// Partner rows 8–12: A name · B % · C % · D beginning · E contributions · F income · G transfers ·
// I distributions; H (other increases) and J (ending) follow the snapshot.
const PARTNERS: readonly (readonly [
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
])[] = [
  ["Ridgeline GP LLC", "0.02", "0.02", "80000", "0", "25000", "0", "-12000"],
  ["Meera Shah", "0.38", "0.38", "2280000", "0", "475000", "0", "-228000"],
  ["Pell Street Ventures LLC", "0.35", "0.30", "2100000", "0", "406250", "-331405", "-180000"],
  ["Pell Street II LLC", "0", "0.05", "0", "0", "31250", "331405", "-30000"],
  ["Jonah Feld", "0.25", "0.25", "1500000", "250000", "312500", "0", "-150000"],
];
const H_FIXED = ["124", "2356", "2015", "155", "1550"] as const;
const J_BEFORE = ["93000", "2527000", "1994845", "332655", "1912500"] as const;
const J_AFTER = ["93124", "2529356", "1996860", "332810", "1914050"] as const;

function sheet05(snapshot: Snapshot, proposed: boolean): WorkbookCellOut[] {
  const fixed = snapshot === "afterFix";
  const out: WorkbookCellOut[] = TEXT_05.map((c) => cell(c));
  PARTNERS.forEach(([name, b, c, d, e, f, g, i], k) => {
    const row = 8 + k;
    out.push(
      cell([`A${String(row)}`, name]),
      cell([`B${String(row)}`, b]),
      cell([`C${String(row)}`, c]),
      cell([`D${String(row)}`, d]),
      cell([`E${String(row)}`, e]),
      cell([`F${String(row)}`, f]),
      cell([`G${String(row)}`, g]),
      cell([`I${String(row)}`, i]),
      cell([
        `J${String(row)}`,
        (fixed ? J_AFTER : J_BEFORE)[k] ?? "0",
        `=D${String(row)}+E${String(row)}+F${String(row)}+G${String(row)}+H${String(row)}+I${String(row)}`,
      ]),
      cell([`K${String(row)}`, "✓"]),
    );
    if (fixed || proposed) {
      out.push(cell([`H${String(row)}`, H_FIXED[k] ?? "0"], fixed ? "value" : "flagged"));
    }
  });
  out.push(
    cell(["A13", "Total"]),
    cell(["B13", "1"]),
    cell(["C13", "1"]),
    cell(["D13", "5960000", "=SUM(D8:D12)"]),
    cell(["E13", "250000", "=SUM(E8:E12)"]),
    cell(["F13", "1250000", "=SUM(F8:F12)"]),
    cell(["G13", "0", "=SUM(G8:G12)"]),
    cell(["H13", fixed ? "6200" : null, "=SUM(H8:H12)"]),
    cell(["I13", "-600000", "=SUM(I8:I12)"]),
    cell(["J13", fixed ? "6866200" : "6860000", "=SUM(J8:J12)"]),
    cell(["J15", "6866200", "='01 Trial Balance'!K21"]),
    cell(["J16", fixed ? "0" : "-6200", "=J13-J15"], fixed ? "formula" : "flagged"),
  );
  return out;
}

// 01 Trial Balance rows 6–18 (C): header, ASSETS, 1000–1650, total assets, LIABILITIES, 2000, 2050.
const SHEET_01: readonly Cell[] = [
  ["A6", "Acct"],
  ["B6", "Account"],
  ["C6", "Category"],
  ["D6", "Export"],
  ["E6", "PY"],
  ["F6", "UTB"],
  ["G6", "AJE"],
  ["H6", "RJE"],
  ["I6", "ATB"],
  ["J6", "TJE"],
  ["K6", "TTB"],
  ["A7", "ASSETS"],
  ["A16", "LIABILITIES"],
];
const TB_01: readonly (readonly [
  number,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
])[] = [
  [8, "1000", "Cash — operating", "Current Assets", "L1", "463067", "693667", "0"],
  [9, "1100", "Tenant receivables", "Current Assets", "L2a", "90200", "96000", "0"],
  [10, "1200", "Municipal bond fund", "Investments", "L5", "225600", "240000", "0"],
  [11, "1300", "Escrows & other assets", "Other Assets", "L13", "148500", "158000", "0"],
  [12, "1500", "Land", "Fixed Assets", "L11", "3600000", "3600000", "0"],
  [13, "1600", "Buildings & improvements", "Fixed Assets", "L9a", "15040000", "15752000", "0"],
  [14, "1650", "Accumulated depreciation", "Fixed Assets", "L9b", "-1891667", "-2625167", "0"],
  [17, "2000", "Accounts payable", "Current Liabilities", "L15", "-112800", "-120000", "0"],
  [18, "2050", "Accrued expenses", "Current Liabilities", "L17", "-88400", "-75500", "-18500"],
];
const ATB_01: Readonly<Record<string, string>> = { "2050": "-94000" };

function sheet01(): WorkbookCellOut[] {
  const out: WorkbookCellOut[] = SHEET_01.map((c) => cell(c));
  for (const [row, code, name, cat, line, py, utb, aje] of TB_01) {
    const atb = ATB_01[code] ?? utb;
    out.push(
      cell([`A${String(row)}`, code]),
      cell([`B${String(row)}`, name]),
      cell([`C${String(row)}`, cat]),
      cell([`D${String(row)}`, line]),
      cell([`E${String(row)}`, py]),
      cell([`F${String(row)}`, utb]),
      cell([`G${String(row)}`, aje]),
      cell([`H${String(row)}`, "0"]),
      cell([`I${String(row)}`, atb, `=F${String(row)}+G${String(row)}+H${String(row)}`]),
      cell([`J${String(row)}`, "0"]),
      cell([`K${String(row)}`, atb, `=I${String(row)}+J${String(row)}`]),
    );
  }
  out.push(
    cell(["A15", "Total assets"]),
    cell(["E15", "17675700", "=SUM(E8:E14)"]),
    cell(["F15", "17914500", "=SUM(F8:F14)"]),
    cell(["I15", "17914500", "=SUM(I8:I14)"]),
    cell(["K15", "17914500", "=SUM(K8:K14)"]),
  );
  return out;
}

/** The sheet as the server answers it for a snapshot; `proposed` is TXP-11 B (the fix awaiting
 * approval). A sheet the fixture does not carry answers no cells. */
export function sheetCells(
  snapshot: Snapshot,
  sheet: string,
  proposed = false,
): WorkbookSheetCellsOut {
  const cells = sheet === "05" ? sheet05(snapshot, proposed) : sheet === "01" ? sheet01() : [];
  return { sheet, version: 2, cells, next_range: null };
}
