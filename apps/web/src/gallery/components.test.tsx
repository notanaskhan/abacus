// TASK-101: the shared components' behaviour: a held action commits after ten seconds unless
// undone; the table sorts and selects; every state reads one way.
import { type Column, DataTable, Toaster, UNDO_MS, statusWord, toast } from "@abacus/ui";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("toast with Undo", () => {
  it("commits after ten seconds", () => {
    vi.useFakeTimers();
    const commit = vi.fn();
    render(<Toaster />);
    act(() => {
      toast.deferred("Sent", commit);
    });
    expect(screen.getByRole("button", { name: "Undo" })).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(UNDO_MS);
    });
    expect(commit).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  });

  it("never commits when undone", () => {
    vi.useFakeTimers();
    const commit = vi.fn();
    const undone = vi.fn();
    render(<Toaster />);
    act(() => {
      toast.deferred("Sent", commit, undone);
    });
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    act(() => {
      vi.advanceTimersByTime(UNDO_MS * 2);
    });
    expect(commit).not.toHaveBeenCalled();
    expect(undone).toHaveBeenCalledOnce();
  });
});

interface Row {
  id: string;
  name: string;
  amount: number;
}
const ROWS: Row[] = [
  { id: "a", name: "Beta", amount: 2 },
  { id: "b", name: "Alpha", amount: 10 },
];
const COLUMNS: Column<Row>[] = [
  { key: "name", header: "Name", cell: (r) => r.name, sortValue: (r) => r.name },
  { key: "amount", header: "Amount", cell: (r) => String(r.amount), sortValue: (r) => r.amount },
];

describe("data table", () => {
  it("sorts by a column, then the other way", () => {
    render(<DataTable label="T" rows={ROWS} columns={COLUMNS} rowKey={(r) => r.id} />);
    const names = (): string[] =>
      within(screen.getByRole("table"))
        .getAllByRole("row")
        .slice(1)
        .map((r) => r.textContent);
    fireEvent.click(screen.getByRole("button", { name: "Name" }));
    expect(names()[0]).toContain("Alpha");
    fireEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(names()[0]).toContain("Beta");
  });

  it("selects rows and shows the bulk bar", () => {
    const changed = vi.fn();
    render(
      <DataTable
        label="T"
        rows={ROWS}
        columns={COLUMNS}
        rowKey={(r) => r.id}
        selectable
        selected={new Set(["a"])}
        onSelectedChange={changed}
        bulkActions={(ids) => <span>{`act on ${String(ids.length)}`}</span>}
      />,
    );
    expect(screen.getByText("1 selected")).toBeTruthy();
    expect(screen.getByText("act on 1")).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: "Select all" }));
    expect(changed).toHaveBeenCalledWith(new Set(["a", "b"]));
  });
});

describe("status vocabulary", () => {
  it("reads every state one way, and an unknown one as itself", () => {
    expect(statusWord("workpaper", "ready")).toEqual({ label: "Prepared", tone: "warning" });
    expect(statusWord("request", "uploaded").label).toBe("Uploaded");
    expect(statusWord("request", "mystery")).toEqual({ label: "mystery", tone: "neutral" });
  });
});
