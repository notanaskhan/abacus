// K-03-T10 (TASK-8854; C23): the SH-1 fixture half. Every SHT-01, SHT-02 and SHT-04 artboard has a
// scenario; the SheetVM adapter keeps every field; 3,698,700.00 and 31 + 8 + 1 + 0 foot.
import { describe, expect, it } from "vitest";
import { toSheetVM } from "../../domain/sheets/vm";
import { scenarios as sht01 } from "../scenarios/SHT-01";
import { scenarios as sht02 } from "../scenarios/SHT-02";
import { scenarios as sht04 } from "../scenarios/SHT-04";
import { CONCLUSIONS, rows, sheet } from "../seed/sheets-sh1";

describe("SH-1 consumer (fixtures)", () => {
  it("serves all 17 artboards", () => {
    expect(Object.keys(sht01)).toEqual(["a", "b", "c", "d", "e", "f"]);
    expect(Object.keys(sht02)).toEqual(["a", "b", "c", "d", "e", "f"]);
    expect(Object.keys(sht04)).toEqual(["a", "b", "c", "d", "e"]);
  });
  it("the bands total 3,698,700.00 and the conclusions 31 + 8 + 1 + 0 = 40", () => {
    const totals = sheet().sections.map((s) => Number((s.total ?? "0").replace(/,/gu, "")));
    expect(totals.reduce((t, n) => t + n, 0).toFixed(2)).toBe("3698700.00");
    expect(Object.values(CONCLUSIONS)).toEqual([31, 8, 1, 0]);
  });
  it("toSheetVM keeps columns, sections, rows and the status bar", () => {
    const vm = toSheetVM(sheet(), rows());
    expect(vm.columns.find((c) => c.key === "conclusion")?.agent?.name).toBe("Conclusion");
    expect(vm.columns[0]?.frozen).toBe(true);
    expect(vm.sections).toHaveLength(2);
    expect(vm.rows[0]?.cells.conclusion?.state).toBe("suggested");
    expect(vm.status.rows).toBe(40);
  });
});
