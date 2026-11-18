// F-08-T05 (DEC-5619): SheetGrid core acceptance — 1,000 rows virtualised with Key frozen, glyph
// headers, hairline grid, no column letters, row numbers or zebra rows; bands and status bar.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SheetGrid } from "./SheetGrid";
import type { SheetGridColumn, SheetGridRow, SheetSection } from "./types";

const COLUMNS: SheetGridColumn[] = [
  { key: "key", type: "text", label: "Key", width: 96, frozen: true },
  { key: "vendor", type: "text", label: "Vendor", width: 200 },
  { key: "amount", type: "currency", label: "Amount", width: 110 },
  { key: "paid", type: "date", label: "Paid", width: 100 },
  {
    key: "conclusion",
    type: "agent",
    label: "Conclusion",
    width: 180,
    agent: { name: "Unrecorded liabilities tester" },
  },
];
const SECTIONS: SheetSection[] = [
  { key: "a", title: "Section A", count: 600, total: "1,000" },
  { key: "b", title: "Section B", count: 400, sub: true },
];

function rows(n: number): SheetGridRow[] {
  return Array.from({ length: n }, (_, i) => ({
    key: `ROW-${String(i + 1).padStart(4, "0")}`,
    sectionKey: i < 600 ? "a" : "b",
    locked: i === 0,
    cells: {
      key: { value: `ROW-${String(i + 1).padStart(4, "0")}`, state: "human" },
      conclusion: { value: "Properly excluded", state: "suggested" },
    },
  }));
}

describe("SheetGrid", () => {
  it("virtualises 1,000 rows with aria-rowcount and aria-rowindex kept", () => {
    render(
      <SheetGrid
        label="Sheet"
        columns={COLUMNS}
        sections={SECTIONS}
        rows={rows(1000)}
        status={{ rows: 1000, exceptions: 0, view: "Default" }}
      />,
    );
    const grid = screen.getByRole("grid", { name: "Sheet" });
    expect(grid.getAttribute("aria-rowcount")).toBe(String(1000 + 2 + 1));
    const rendered = within(grid).getAllByRole("row");
    expect(rendered.length).toBeLessThan(200);
    expect(rendered[0]?.getAttribute("aria-rowindex")).toBe("1");
  });

  it("freezes select and Key, shows glyph headers and no column letters or row numbers", () => {
    const { container } = render(
      <SheetGrid
        label="Sheet"
        columns={COLUMNS}
        sections={SECTIONS}
        rows={rows(3)}
        status={{ rows: 3, exceptions: 0, view: "Default" }}
      />,
    );
    const headers = screen.getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "",
      "Key",
      "Vendor",
      "Amount",
      "Paid",
      "Conclusion",
    ]);
    expect(headers[1]?.className).toContain("sticky");
    expect(headers[1]?.style.left).toBe("28px");
    expect(container.querySelectorAll("[data-column-type] svg").length).toBe(COLUMNS.length * 2);
    expect(container.textContent).not.toMatch(/\$/);
    expect(container.innerHTML).not.toMatch(/odd:|even:/);
  });

  it("draws the dark section band with its server total and the light sub-band", () => {
    const { container } = render(
      <SheetGrid
        label="Sheet"
        columns={COLUMNS}
        sections={SECTIONS}
        rows={rows(700)}
        status={{ rows: 700, exceptions: 1, view: "Default" }}
      />,
    );
    const band = container.querySelector('[data-band="section"]');
    expect(band?.textContent).toBe("SECTION A (600)1,000");
    expect(band?.querySelector("td")?.className).toContain("bg-espresso");
    expect(screen.getByRole("status").textContent).toBe("700 rows · 1 exception · View: Default");
  });

  it("emits agent-column intents from the header menu and performs none", () => {
    const onIntent = vi.fn();
    render(
      <SheetGrid
        label="Sheet"
        columns={COLUMNS}
        sections={SECTIONS}
        rows={rows(3)}
        status={{ rows: 3, exceptions: 0, view: "Default" }}
        onColumnIntent={onIntent}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Conclusion column menu" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Run on empty rows" }));
    expect(onIntent).toHaveBeenCalledWith("conclusion", { kind: "run_on_empty_rows" });
    fireEvent.click(screen.getByRole("button", { name: "Vendor column menu" }));
    expect(screen.queryByRole("menuitem", { name: "Edit agent column…" })).toBeNull();
  });

  it("shows a suggested agent value in ink-2 and a lock on a locked row", () => {
    render(
      <SheetGrid
        label="Sheet"
        columns={COLUMNS}
        sections={SECTIONS}
        rows={rows(2)}
        status={{ rows: 2, exceptions: 0, view: "Default" }}
      />,
    );
    const cells = screen
      .getAllByRole("gridcell")
      .filter((c) => c.getAttribute("data-state") === "suggested");
    expect(cells[0]?.className).toContain("text-ink-2");
    expect(screen.getAllByLabelText("Locked").length).toBe(1);
  });
});
