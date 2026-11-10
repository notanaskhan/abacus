// N-04-T10 (DEC-2956): the notices fixtures foot as the handoff and N-04-T04's goldens state them,
// and they compile against the generated client (a renamed field fails `tsc`, not a screen). The
// Whitley CP2000 for TY2024: 1,870 + 1,250 = 3,120; 22% × 3,120 = 686.40; + 66.61 = 753.01.
import type { AnalysisOut, IntakeOut, NoticeOut, ResponseOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { santosIntake } from "./seed/notice-intake";
import { not02Analysis, not02Notice } from "./seed/not02";
import { not03Response } from "./seed/not03";

const cents = (value: string | null | undefined): number => {
  if (value == null) throw new Error("a figure the fixture should carry is missing");
  return Math.round(Number(value) * 100);
};

const analysis: AnalysisOut = not02Analysis("a");
const notice: NoticeOut = not02Notice("a");
const response: ResponseOut = not03Response("a");
const intakes: IntakeOut[] = (["b", "c", "d", "duplicate", "manual", "no_client"] as const).map(
  (v) => santosIntake(v),
);

const rowOf = (key: string): AnalysisOut["rows"][number] => {
  const found = analysis.rows.find((r) => r.key === key);
  if (found === undefined) throw new Error(key);
  return found;
};

describe("N-04 Whitley fixture figures", () => {
  it("NOT-02: the two late 1099-INTs are the 3,120 the taxable lines move by", () => {
    const late = analysis.information_returns.filter((i) => i.issued_after_filing);
    expect(late.reduce((sum, i) => sum + cents(i.amount), 0)).toBe(312_000);
    expect(cents(rowOf("taxable_interest").difference)).toBe(312_000);
    expect(cents(rowOf("taxable_income").difference)).toBe(312_000);
    expect(cents(rowOf("taxable_income").irs) - cents(rowOf("taxable_income").as_filed)).toBe(
      312_000,
    );
  });

  it("NOT-02: 22% × 3,120 = 686.40 is the tax change, and the bracket check agrees", () => {
    expect(Math.round(312_000 * 0.22)).toBe(68_640);
    expect(cents(rowOf("tax").difference)).toBe(68_640);
    expect(cents(rowOf("tax").irs) - cents(rowOf("tax").as_filed)).toBe(68_640);
    expect(analysis.checks?.bracket_check?.agrees).toBe(true);
    expect(cents(analysis.checks?.bracket_check?.expected)).toBe(68_640);
  });

  it("NOT-02 and NOT-03: 686.40 + 66.61 = 753.01, the same on both screens", () => {
    expect(cents(rowOf("tax").difference) + cents(rowOf("interest").difference)).toBe(75_301);
    expect(cents(rowOf("total_due").difference)).toBe(75_301);
    const paid = response.payment?.amounts;
    expect(cents(paid?.tax)).toBe(68_640);
    expect(cents(paid?.interest)).toBe(6_661);
    expect(cents(paid?.total)).toBe(75_301);
  });

  it("no fixture carries a whole TIN: the last four only", () => {
    expect(notice.taxpayer_tin?.last4).toMatch(/^\d{4}$/u);
    const all = JSON.stringify([notice, analysis, response, intakes]);
    expect(all).not.toMatch(/\b\d{3}-\d{2}-\d{4}\b/u);
    expect(all).not.toMatch(/\b\d{9}\b/u);
  });
});
