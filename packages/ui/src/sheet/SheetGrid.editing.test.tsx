// F-08-T06 (TASK-8745; DEC-5735): editing and the keyboard grid model under role="grid" — Enter or
// F2 enters edit, Esc cancels, Tab or Enter commits through onCellEdit with the row's version;
// arrows, Home/End and PageUp/PageDown move a roving focus; locked rows refuse typing, paste,
// fill and Delete/Backspace with the T18 tooltip; a 409/412 rejection shows "Changed by … — reload".
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LOCKED_TOOLTIP, SheetGrid } from "./SheetGrid";
import type { SheetCellEdit, SheetGridColumn, SheetGridRow, SheetSection } from "./types";

const COLUMNS: SheetGridColumn[] = [
  { key: "key", type: "text", label: "Key", width: 96, frozen: true },
  { key: "vendor", type: "text", label: "Vendor", width: 200 },
  { key: "amount", type: "currency", label: "Amount", width: 110 },
  {
    key: "status",
    type: "single_select",
    label: "Status",
    width: 120,
    options: [
      { value: "open", label: "Open" },
      { value: "cleared", label: "Cleared" },
    ],
  },
  { key: "conclusion", type: "agent", label: "Conclusion", width: 180, agent: { name: "Tester" } },
];
const SECTIONS: SheetSection[] = [{ key: "a", title: "Disbursements", count: 3 }];

function row(key: string, locked = false): SheetGridRow {
  return {
    key,
    sectionKey: "a",
    locked,
    version: 4,
    cells: {
      key: { value: key, state: "human" },
      vendor: { value: "Front Range Supply", state: "human" },
      amount: { value: "68,400", state: "human" },
      status: { value: "Open", state: "human" },
      conclusion: { value: "Properly excluded", state: "suggested" },
    },
  };
}

function grid(
  onCellEdit?: (e: SheetCellEdit) => Promise<void>,
  rows = [row("D-01"), row("D-02", true), row("D-03")],
) {
  return render(
    <SheetGrid
      columns={COLUMNS}
      sections={SECTIONS}
      rows={rows}
      status={{ rows: 3, exceptions: 0, view: "All rows" }}
      label="BH-FS-430"
      {...(onCellEdit === undefined ? {} : { onCellEdit })}
    />,
  );
}

function cell(rowKey: string, colKey: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(
    `[data-row-key="${rowKey}"] [data-col-key="${colKey}"]`,
  );
  if (found === null) throw new Error(`no cell ${rowKey}/${colKey}`);
  return found;
}

afterEach(cleanup); // each test renders its own grid

describe("SheetGrid editing (F-08-T06)", () => {
  it("roves focus with the arrows, Home/End and PageUp/PageDown, one cell tabbable", () => {
    grid();
    const first = cell("D-01", "key");
    expect(first.tabIndex).toBe(0);
    expect(cell("D-01", "vendor").tabIndex).toBe(-1);
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(document.activeElement).toBe(cell("D-01", "vendor"));
    fireEvent.keyDown(document.activeElement as Element, { key: "ArrowDown" });
    expect(document.activeElement).toBe(cell("D-02", "vendor"));
    fireEvent.keyDown(document.activeElement as Element, { key: "End" });
    expect(document.activeElement).toBe(cell("D-02", "conclusion"));
    fireEvent.keyDown(document.activeElement as Element, { key: "Home" });
    expect(document.activeElement).toBe(cell("D-02", "key"));
    fireEvent.keyDown(document.activeElement as Element, { key: "PageDown" });
    expect(document.activeElement).toBe(cell("D-03", "key"));
    fireEvent.keyDown(document.activeElement as Element, { key: "PageUp" });
    expect(document.activeElement).toBe(cell("D-01", "key"));
  });

  it("Enter or F2 edits, Esc cancels, Enter commits with the row's version", async () => {
    const onCellEdit = vi.fn<(edit: SheetCellEdit) => Promise<void>>(() => Promise.resolve());
    grid(onCellEdit);
    const vendor = cell("D-01", "vendor");
    vendor.focus();
    fireEvent.keyDown(vendor, { key: "F2" });
    const input = screen.getByRole("textbox", { name: "Vendor" });
    fireEvent.change(input, { target: { value: "Front Range Supply Co." } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onCellEdit).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox", { name: "Vendor" })).toBeNull();
    fireEvent.keyDown(cell("D-01", "vendor"), { key: "Enter" });
    const again = screen.getByRole("textbox", { name: "Vendor" });
    fireEvent.change(again, { target: { value: "Front Range Supply Co." } });
    await act(async () => {
      fireEvent.keyDown(again, { key: "Enter" });
      await Promise.resolve();
    });
    expect(onCellEdit).toHaveBeenCalledWith({
      rowKey: "D-01",
      colKey: "vendor",
      value: "Front Range Supply Co.",
      version: 4,
    });
  });

  it("Tab commits and moves right; a select edits from its options", async () => {
    const onCellEdit = vi.fn<(edit: SheetCellEdit) => Promise<void>>(() => Promise.resolve());
    grid(onCellEdit);
    const amount = cell("D-01", "amount");
    amount.focus();
    fireEvent.keyDown(amount, { key: "Enter" });
    const input = screen.getByRole("textbox", { name: "Amount" });
    fireEvent.change(input, { target: { value: "68,900" } });
    await act(async () => {
      fireEvent.keyDown(input, { key: "Tab" });
      await Promise.resolve();
    });
    expect(onCellEdit).toHaveBeenCalledWith(
      expect.objectContaining({ colKey: "amount", value: "68,900" }),
    );
    expect(document.activeElement).toBe(cell("D-01", "status"));
    fireEvent.keyDown(cell("D-01", "status"), { key: "Enter" });
    const select = screen.getByRole("combobox", { name: "Status" });
    await act(async () => {
      fireEvent.change(select, { target: { value: "cleared" } });
      await Promise.resolve();
    });
    expect(onCellEdit).toHaveBeenLastCalledWith(
      expect.objectContaining({ colKey: "status", value: "cleared" }),
    );
  });

  it("locked rows refuse typing, paste, Delete and Backspace, with the tooltip", () => {
    const onCellEdit = vi.fn<(edit: SheetCellEdit) => Promise<void>>(() => Promise.resolve());
    grid(onCellEdit);
    const locked = cell("D-02", "vendor");
    expect(locked.getAttribute("aria-readonly")).toBe("true");
    expect(locked.getAttribute("title")).toBe(LOCKED_TOOLTIP);
    expect(LOCKED_TOOLTIP).toBe(
      "Signed-off rows are locked. Sign-offs are removed only from the sign-off modal.",
    );
    locked.focus();
    for (const key of ["Enter", "F2", "Delete", "Backspace", "x"]) {
      fireEvent.keyDown(locked, { key });
    }
    fireEvent.keyDown(locked, { key: "d", ctrlKey: true }); // fill down
    fireEvent.paste(locked, { clipboardData: { getData: () => "pasted" } });
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(onCellEdit).not.toHaveBeenCalled();
    expect(screen.getByTestId("sheet-announcements").textContent).toBe(LOCKED_TOOLTIP);
  });

  it("agent cells are not edited here; Delete clears an unlocked editable cell", async () => {
    const onCellEdit = vi.fn<(edit: SheetCellEdit) => Promise<void>>(() => Promise.resolve());
    grid(onCellEdit);
    const agent = cell("D-01", "conclusion");
    agent.focus();
    fireEvent.keyDown(agent, { key: "Enter" });
    expect(screen.queryByRole("textbox")).toBeNull();
    const vendor = cell("D-03", "vendor");
    vendor.focus();
    await act(async () => {
      fireEvent.keyDown(vendor, { key: "Delete" });
      await Promise.resolve();
    });
    expect(onCellEdit).toHaveBeenCalledWith(
      expect.objectContaining({ rowKey: "D-03", colKey: "vendor", value: "" }),
    );
  });

  it("a 409 or 412 rejection shows Changed by <name> — reload", async () => {
    const onCellEdit = vi.fn<(edit: SheetCellEdit) => Promise<void>>(() =>
      Promise.reject(
        Object.assign(new Error("conflict"), { status: 409, changedBy: "Hannah Leclerc" }),
      ),
    );
    grid(onCellEdit);
    const vendor = cell("D-01", "vendor");
    vendor.focus();
    fireEvent.keyDown(vendor, { key: "Enter" });
    const input = screen.getByRole("textbox", { name: "Vendor" });
    fireEvent.change(input, { target: { value: "x" } });
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" });
      await Promise.resolve();
    });
    expect(screen.getByRole("alert").textContent).toContain("Changed by Hannah Leclerc — reload");
  });

  it("Ctrl or Cmd+D fills an unlocked cell from the cell above", async () => {
    const onCellEdit = vi.fn<(edit: SheetCellEdit) => Promise<void>>(() => Promise.resolve());
    const above = row("D-01");
    const below = {
      ...row("D-03"),
      cells: { ...row("D-03").cells, amount: { value: "", state: "human" as const } },
    };
    grid(onCellEdit, [above, below]);
    const target = cell("D-03", "amount");
    target.focus();
    await act(async () => {
      fireEvent.keyDown(target, { key: "d", metaKey: true });
      await Promise.resolve();
    });
    expect(onCellEdit).toHaveBeenCalledWith({
      rowKey: "D-03",
      colKey: "amount",
      value: "68,400",
      version: 4,
    });
  });
});
