// F-08-T11 (TASK-8750; ADR-078; F-08 §3 A2): locked rows refuse every edit path. A signed-off row
// refuses typing, paste (ClipboardEvent), fill, Delete, Backspace and cut; it is aria-readonly,
// shows Lock 11 in the key cell and the exact tooltip copy. A lock follows sign-off state
// (row.locked, P-07), never presence.
import { act, cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SheetGrid } from "../SheetGrid";
import type { SheetCellEdit } from "../types";
import { LOCK_COPY, cellOf, grid, surlRow } from "./fixtures";

afterEach(cleanup);

const edits = () => vi.fn<(e: SheetCellEdit) => Promise<void>>(() => Promise.resolve());

describe("F-08-T11 locks", () => {
  it("test_ac1_locked_row_is_readonly_with_lock_11_and_the_exact_tooltip", () => {
    grid();
    for (const col of ["key", "vendor", "amount", "conclusion"]) {
      const c = cellOf("SURL-05", col);
      expect(c.getAttribute("aria-readonly")).toBe("true");
      expect(c.getAttribute("title")).toBe(LOCK_COPY);
    }
    const lock = cellOf("SURL-05", "key").querySelector('svg[aria-label="Locked"]');
    expect(lock).not.toBeNull();
    expect(lock?.getAttribute("class")).toContain("size-[11px]");
    expect(cellOf("SURL-04", "key").querySelector('svg[aria-label="Locked"]')).toBeNull();
    expect(cellOf("SURL-04", "vendor").getAttribute("aria-readonly")).not.toBe("true");
  });

  it("test_ac2_typing_enter_f2_delete_backspace_refused_on_a_locked_row", async () => {
    const onCellEdit = edits();
    grid({ onCellEdit });
    const c = cellOf("SURL-05", "vendor");
    c.focus();
    await act(async () => {
      for (const key of ["a", "Z", "1", "Enter", "F2", "Delete", "Backspace"]) {
        fireEvent.keyDown(c, { key });
      }
      await Promise.resolve();
    });
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(onCellEdit).not.toHaveBeenCalled();
    expect(cellOf("SURL-05", "vendor").textContent).toBe("Front Range Freight Co.");
    expect(screen.getByTestId("sheet-announcements").textContent).toBe(LOCK_COPY);
  });

  it("test_ac3_paste_clipboard_event_refused_on_a_locked_row", async () => {
    const onCellEdit = edits();
    grid({ onCellEdit });
    const c = cellOf("SURL-05", "amount");
    c.focus();
    await act(async () => {
      fireEvent.paste(c, { clipboardData: { getData: () => "99,999" } });
      await Promise.resolve();
    });
    expect(onCellEdit).not.toHaveBeenCalled();
    expect(cellOf("SURL-05", "amount").textContent).toBe("68,400");
    expect(screen.getByTestId("sheet-announcements").textContent).toBe(LOCK_COPY);
  });

  it("test_ac4_fill_down_into_a_locked_row_refused", async () => {
    const onCellEdit = edits();
    grid({ onCellEdit, rows: [surlRow("SURL-04", false), surlRow("SURL-05", true)] });
    const c = cellOf("SURL-05", "amount");
    c.focus();
    await act(async () => {
      fireEvent.keyDown(c, { key: "d", ctrlKey: true });
      fireEvent.keyDown(c, { key: "d", metaKey: true });
      await Promise.resolve();
    });
    expect(onCellEdit).not.toHaveBeenCalled();
    expect(screen.getByTestId("sheet-announcements").textContent).toBe(LOCK_COPY);
  });

  it("test_ac5_cut_refused_on_a_locked_row", async () => {
    const onCellEdit = edits();
    grid({ onCellEdit });
    const c = cellOf("SURL-05", "vendor");
    c.focus();
    let event: Event | undefined;
    c.addEventListener("cut", (e) => {
      event = e;
    });
    await act(async () => {
      fireEvent.cut(c, { clipboardData: { setData: () => undefined } });
      fireEvent.keyDown(c, { key: "x", ctrlKey: true });
      await Promise.resolve();
    });
    expect(onCellEdit).not.toHaveBeenCalled();
    expect(event?.defaultPrevented).toBe(true);
    expect(cellOf("SURL-05", "vendor").textContent).toBe("Front Range Freight Co.");
    expect(screen.getByTestId("sheet-announcements").textContent).toBe(LOCK_COPY);
  });

  it("test_ac6_the_lock_follows_sign_off_state_never_presence", async () => {
    // The grid takes no presence input: a row is locked only by row.locked (derived from sign-off
    // state by the consumer). An unlocked row with someone else in it still edits.
    const onCellEdit = edits();
    const { rerender, props } = grid({ onCellEdit });
    const c = cellOf("SURL-04", "vendor");
    c.focus();
    await act(async () => {
      fireEvent.keyDown(c, { key: "Delete" });
      await Promise.resolve();
    });
    expect(onCellEdit).toHaveBeenCalledWith(
      expect.objectContaining({ rowKey: "SURL-04", colKey: "vendor", value: "" }),
    );
    // Signing SURL-04 off locks it on the next render, with no other input changed.
    rerender(
      <SheetGrid
        {...props}
        onCellEdit={onCellEdit}
        rows={[surlRow("SURL-04", true), surlRow("SURL-05", true)]}
      />,
    );
    expect(cellOf("SURL-04", "vendor").getAttribute("aria-readonly")).toBe("true");
    expect(Object.keys(props)).not.toContain("presence");
  });
});
