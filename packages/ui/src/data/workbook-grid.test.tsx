// T-05-T12 (SPEC-651 AC-4.1, AC-4.3): WorkbookGrid's grammar and keyboard model.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  EMPTY_LABEL,
  WorkbookGrid,
  type WorkbookCell,
  formulaText,
  parseAddress,
} from "./workbook-grid";

afterEach(cleanup);

const CELLS: Record<string, WorkbookCell> = {
  H12: { display: "", expected: "='06 Schedule K'!C31 × 25% → 1,550" },
  J12: { display: "1,912,500", formula: "=SUM(D12:I12)" },
  H8: { display: "124", proposed: true },
  D12: { display: "1,500,000", comment: "2024 K-1 Item L" },
};

function Harness({
  onCommit,
  rows = 16,
}: {
  onCommit?: (a: string, v: string) => void;
  rows?: number;
}): JSX.Element {
  const [selected, setSelected] = useState("H12");
  return (
    <WorkbookGrid
      label="Ridgeline workbook"
      sheet="05 Capital"
      sheets={[{ title: "01 Trial Balance" }, { title: "05 Capital", openIssue: true }]}
      columns={10}
      rows={rows}
      cells={CELLS}
      cited={["H8:H12", "J13"]}
      selected={selected}
      onSelect={setSelected}
      {...(onCommit ? { onCommit } : {})}
    />
  );
}

describe("WorkbookGrid", () => {
  it("AC-4.1: the name box, the expected formula and the Sheet!Cell footer for an empty cell", () => {
    render(<Harness />);
    expect(screen.getByLabelText("Name box").textContent).toBe("H12");
    expect(screen.getByLabelText("Formula bar").textContent).toBe(
      `${EMPTY_LABEL} — expected ='06 Schedule K'!C31 × 25% → 1,550`,
    );
    expect(document.querySelector("[data-workbook-footer]")?.textContent).toContain(
      "05 Capital!H12",
    );
    expect(document.querySelectorAll("[data-cited='true']")).toHaveLength(6);
    expect(document.querySelector("[data-cell='H12'][aria-selected='true']")).not.toBeNull();
  });

  it("column letters, row numbers, the proposed pill, the comment corner and the issue dot", () => {
    render(<Harness />);
    expect(
      screen
        .getAllByRole("columnheader")
        .map((c) => c.textContent)
        .slice(0, 3),
    ).toEqual(["A", "B", "C"]);
    expect(screen.getAllByRole("rowheader")).toHaveLength(16);
    expect(
      document.querySelector("[data-cell='H8'][data-proposed='true']")?.textContent,
    ).toContain("Proposed");
    expect(screen.getByLabelText("Comment: 2024 K-1 Item L")).toBeTruthy();
    expect(screen.getByLabelText("Open issue")).toBeTruthy();
  });

  it("arrows move the selection; the formula bar follows", () => {
    render(<Harness />);
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowRight" });
    fireEvent.keyDown(grid, { key: "ArrowRight" });
    expect(screen.getByLabelText("Name box").textContent).toBe("J12");
    expect(screen.getByLabelText("Formula bar").textContent).toBe("=SUM(D12:I12)");
    fireEvent.keyDown(grid, { key: "ArrowUp" });
    expect(screen.getByLabelText("Name box").textContent).toBe("J11");
  });

  it("AC-4.3: F2 opens the editor, Enter commits to the host, Esc cancels", () => {
    const onCommit = vi.fn();
    render(<Harness onCommit={onCommit} />);
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "F2" });
    const editor = screen.getByLabelText("Edit 05 Capital!H12");
    fireEvent.change(editor, { target: { value: "1,550" } });
    fireEvent.keyDown(editor, { key: "Enter" });
    expect(onCommit).toHaveBeenCalledWith("H12", "1,550");
    fireEvent.keyDown(grid, { key: "Enter" });
    fireEvent.keyDown(screen.getByLabelText("Edit 05 Capital!H12"), { key: "Escape" });
    expect(screen.queryByLabelText("Edit 05 Capital!H12")).toBeNull();
    expect(onCommit).toHaveBeenCalledTimes(1);
  });

  it("virtualises above 200 rows", () => {
    render(<Harness rows={1000} />);
    // jsdom has no layout, so the window draws few or no rows; the grid caps its height (virtual).
    expect(screen.queryAllByRole("rowheader").length).toBeLessThan(1000);
    expect(screen.getByRole("grid").style.maxHeight).not.toBe("");
  });

  it("helpers", () => {
    expect(parseAddress("H12")).toEqual([7, 12]);
    expect(parseAddress("H8:H12")).toBeNull();
    expect(formulaText(undefined)).toBe(EMPTY_LABEL);
    expect(formulaText({ display: "6,200" })).toBe("6,200");
  });
});
