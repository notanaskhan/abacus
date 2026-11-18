// F-08-T03 (DEC-5618): the TPL-23 and TPL-24 footings as tests (F-08 G1).
import { describe, expect, it } from "vitest";
import { AP_LEADSHEET } from "./granite-peak-fy2026-ap-leadsheet";
import { RESPONSIVENESS } from "./insights-responsiveness-2026-10-01";

const sum = (xs: number[]): number => xs.reduce((n, x) => n + x, 0);

describe("wave-5 insights and add-in slices", () => {
  it("TPL-23: 2,804 + 1,432 + 214 = 4,450 due; 63% on time; 576 open", () => {
    const { onTime, late, pastDue } = RESPONSIVENESS.due;
    const due = onTime + late + pastDue;
    expect(due).toBe(4450);
    expect(Math.round((onTime / due) * 1000) / 10).toBe(63.0);
    expect(pastDue + RESPONSIVENESS.openNotDue).toBe(576);
    expect(Math.round((pastDue / due) * 1000) / 10).toBe(4.8);
  });

  it("TPL-23: past due by age 78 + 46 + 44 + 34 + 12 = 214; quarters foot to 4,450 and 2,804", () => {
    expect(sum(RESPONSIVENESS.pastDueByAge.map((b) => b.count))).toBe(RESPONSIVENESS.due.pastDue);
    expect(sum(RESPONSIVENESS.quarters.map((q) => q.due))).toBe(4450);
    expect(sum(RESPONSIVENESS.quarters.map((q) => q.onTime))).toBe(RESPONSIVENESS.due.onTime);
  });

  it("TPL-23: lowest on-time rates 22 · 31 · 36 · 48 · 57 in order", () => {
    expect(RESPONSIVENESS.lowest.map((c) => c.onTimePct)).toEqual([22, 31, 36, 48, 57]);
    const granite = RESPONSIVENESS.lowest.find((c) => c.client.startsWith("Granite Peak"));
    expect([granite?.requests, granite?.pastDue, granite?.onTimePct]).toEqual([65, 3, 48]);
  });

  it("TPL-24: 3,962,400 + 217,600 = 4,180,000 and 3,128,600 + 181,400 = 3,310,000", () => {
    expect(sum(AP_LEADSHEET.rows.map((r) => r.current))).toBe(4180000);
    expect(sum(AP_LEADSHEET.rows.map((r) => r.prior))).toBe(3310000);
    expect(AP_LEADSHEET.links).toEqual([
      { cell: "D14", evidence: "AP aging 6/30/2026.xlsx", page: 1 },
    ]);
  });

  it("TPL-24f: exactly two Word incoming changes", () => {
    expect(AP_LEADSHEET.wordIncoming.length).toBe(2);
  });
});
