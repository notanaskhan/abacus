// I-01-T18 · HOME-02's evidence fixtures foot to the screen contract's Figures (AC7.7): the basis
// columns and their difference, the calc card, and c's capital rollforward.
import { describe, expect, it } from "vitest";
import { BASIS_ROWS } from "./seed/approvals";
import {
  BASIS_FOOTING,
  BASIS_SUMMARY,
  CAPITAL_SUMMARY,
  ENDING,
  ROLLFORWARD,
} from "./seed/approvals-evidence";

const texts = (rows: NonNullable<typeof BASIS_SUMMARY.table>["rows"], col: number): string[] =>
  rows.map((r) => r.cells[col]?.text ?? "");

describe("HOME-02 evidence fixtures foot (I-01-T18)", () => {
  it("a: the basis table's columns foot to 01 §9.8", () => {
    expect(BASIS_FOOTING).toEqual({
      taxCapital: 6_866_200,
      liabilityShare: 11_048_300,
      outsideBasis: 17_943_095,
      insideShare: 17_914_500,
    });
    expect(BASIS_FOOTING.outsideBasis - BASIS_FOOTING.insideShare).toBe(28_595);
    const total = BASIS_SUMMARY.table?.rows.at(-1);
    expect(total?.cells.map((c) => c.text)).toEqual([
      "TOTAL",
      "6,866,200",
      "11,048,300",
      "17,943,095",
      "17,914,500",
      "28,595",
    ]);
  });

  it("a: outside = tax capital + §752 share on the four reconciled rows; Pell Street II is 28,595 off", () => {
    for (const r of BASIS_ROWS) {
      if (r.partner === "Pell Street II LLC") {
        expect(r.taxCapital + r.liabilityShare).toBe(885_225);
        expect(r.outsideBasis - r.insideShare).toBe(28_595);
      } else {
        expect(r.taxCapital + r.liabilityShare).toBe(r.outsideBasis);
      }
    }
    const rows = BASIS_SUMMARY.table?.rows ?? [];
    expect(rows.filter((r) => r.lit === true).map((r) => r.cells[0]?.text)).toEqual([
      "Pell Street II LLC",
    ]);
    expect(texts(rows.slice(0, 5), 5)).toEqual([
      "Reconciled",
      "Reconciled",
      "Reconciled",
      "off 28,595",
      "Reconciled",
    ]);
  });

  it("a: the calc card reads 360,000 − 331,405 = 28,595 and the outside basis sentence", () => {
    expect(BASIS_SUMMARY.calc?.lines.map((l) => l.value)).toEqual([
      "360,000",
      "331,405",
      "28,595",
    ]);
    expect(BASIS_SUMMARY.calc?.lines[1]?.label).toBe("− Capital transferred (5/35 × 2,319,835)");
    expect(BASIS_SUMMARY.calc?.note).toBe(
      "Pell Street II outside basis 913,820 = 360,000 + 31,250 income + 155 tax-exempt − 30,000 distributions + 552,415 liabilities.",
    );
    expect(2_100_000 + 218_750 + 1_085).toBe(2_319_835);
  });

  it("c: 5,960,000 + 250,000 + 1,250,000 − 600,000 = 6,860,000; Schedule L 6,866,200 is off 6,200", () => {
    expect(ENDING).toBe(6_860_000);
    expect(ROLLFORWARD.scheduleL - ENDING).toBe(6_200);
    expect(CAPITAL_SUMMARY.tally?.map((t) => ("value" in t ? t.value : ""))).toEqual([
      "6,860,000",
      "6,866,200",
    ]);
    expect(CAPITAL_SUMMARY.aside?.text).toBe("off 6,200");
    expect(texts(CAPITAL_SUMMARY.table?.rows ?? [], 1)).toEqual([
      "5,960,000",
      "250,000",
      "1,250,000",
      "(600,000)",
      "6,860,000",
      "6,866,200",
      "off 6,200",
    ]);
  });
});
