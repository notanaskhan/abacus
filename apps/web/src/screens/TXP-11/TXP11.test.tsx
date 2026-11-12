// T-05-T38 (TASK-7628; docs/screens/TXP-11.md; handoff TXP-11 A–E): "After the seeded fix H8:H12
// read 124, 2,356, 2,015, 155 and 1,550, J13 = J15 = 6,866,200, and the tab's amber dot clears."
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { sheetCells } from "../../fixtures/seed/tax-entity-sheets";
import { COPY } from "./copy";
import { TXP11, display, gridCells } from ".";

afterEach(cleanup);

describe("TXP-11 Workpaper", () => {
  it("A: H12 selected and empty with its expected formula; J16 off by (6,200)", () => {
    const cells = gridCells("05", sheetCells("run2", "05"), { H12: COPY.expectedH12 });
    expect(cells.H12?.display ?? "").toBe("");
    expect(cells.H12?.expected).toBe(COPY.expectedH12);
    expect(cells.J13?.display).toBe("6,860,000");
    expect(cells.J15?.display).toBe("6,866,200");
    expect(cells.J16?.display).toBe("(6,200)");
    expect(cells.B8?.display).toBe("2%");
    expect(cells.B11?.display).toBe("—");
    render(
      <TXP11
        sheet="05 Capital"
        data={sheetCells("run2", "05")}
        selected="H12"
        cited={["H8:H12", "J13", "J15"]}
        openIssue
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText(COPY.linkedIssue)).toBeTruthy();
    expect(screen.getAllByText("Jonah Feld").length).toBeGreaterThan(0);
  });

  it("B: the fix's cells read Proposed until approved", () => {
    const cells = gridCells("05", sheetCells("run2", "05", true));
    for (const a of ["H8", "H9", "H10", "H11", "H12"]) expect(cells[a]?.proposed).toBe(true);
  });

  it("B2: after the fix H8:H12, J13 = J15 = 6,866,200 and no open issue", () => {
    const cells = gridCells("05", sheetCells("afterFix", "05"));
    expect(["H8", "H9", "H10", "H11", "H12"].map((a) => cells[a]?.display)).toEqual([
      "124",
      "2,356",
      "2,015",
      "155",
      "1,550",
    ]);
    expect(cells.J13?.display).toBe("6,866,200");
    expect(cells.J15?.display).toBe("6,866,200");
    expect(cells.H12?.proposed).toBeUndefined();
    const { container } = render(
      <TXP11
        sheet="05 Capital"
        data={sheetCells("afterFix", "05")}
        selected="J13"
        onSelect={vi.fn()}
      />,
    );
    expect(container.textContent).not.toContain(COPY.linkedIssue);
  });

  it("C: 01 Trial Balance, I18 = F18+G18+H18 reads (94,000)", () => {
    const data = sheetCells("run2", "01");
    const i18 = data.cells.find((c) => c.address === "I18");
    expect(i18?.formula).toBe("=F18+G18+H18");
    expect(display("01", i18!)).toBe("(94,000)");
    expect(gridCells("01", data).K18?.formula).toBe("=I18+J18");
  });

  it("E: a 409 reads the conflict line with Reload", () => {
    render(
      <TXP11
        sheet="05 Capital"
        data={sheetCells("run2", "05")}
        selected="H12"
        conflict
        onSelect={vi.fn()}
        onCommit={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert").textContent).toContain(COPY.conflict);
    expect(screen.getByText(COPY.reload)).toBeTruthy();
  });
});
