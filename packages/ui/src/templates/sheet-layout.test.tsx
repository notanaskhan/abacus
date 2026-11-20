// F-08-T08 (TASK-8747; DEC-5737): SheetLayout T18 a-i from typed view models. A P or R slot
// calls onOpenSignOff and never signs, the agent never has a slot, and T18b scrolls a 696 px
// canvas with select and Key frozen. Tier D: toolbar 44, drawer 480, P · R 64.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SheetGridColumn, SheetGridRow, SheetSection } from "../sheet/types";
import { installDomShims } from "../test-dom";
import {
  CANVAS_COCKPIT,
  DRAWER_W,
  PR_W,
  ROW_DRAWER_TABS,
  SHEET_EMPTY,
  SheetLayout,
  type SheetLayoutProps,
  TOOLBAR_H,
} from "./sheet-layout";

installDomShims();
afterEach(cleanup);

const COLUMNS: SheetGridColumn[] = [
  { key: "key", type: "text", label: "Key", width: 96, frozen: true },
  { key: "name", type: "text", label: "Name", width: 220 },
  { key: "status", type: "single_select", label: "Status", width: 120 },
  { key: "notes", type: "agent", label: "Notes", width: 220, agent: { name: "Notes" } },
];
const SECTIONS: SheetSection[] = [
  { key: "a", title: "Section A", count: 2 },
  { key: "b", title: "Section B", count: 1 },
];

function rows(lockA = false): SheetGridRow[] {
  const r = (key: string, sectionKey: string, notes?: string): SheetGridRow => ({
    key,
    sectionKey,
    locked: lockA && sectionKey === "a",
    cells: {
      key: { value: key, state: "human" },
      name: { value: `Row ${key}`, state: "human" },
      ...(notes === undefined ? {} : { notes: { value: notes, state: "suggested" as const } }),
    },
  });
  return [r("A-1", "a", "Agrees to support"), r("A-2", "a"), r("B-1", "b")];
}

function props(over: Partial<SheetLayoutProps> = {}): SheetLayoutProps {
  return {
    variant: "full",
    view: "ready",
    toolbar: { view: "Default view", filters: 0, search: "", onSearch: vi.fn() },
    grid: {
      label: "Sheet",
      columns: COLUMNS,
      sections: SECTIONS,
      rows: rows(),
      status: { rows: 3, exceptions: 0, view: "Default" },
      viewer: { kind: "human", name: "Ana Cruz" },
    },
    onOpenSignOff: vi.fn(),
    ...over,
  };
}

describe("SheetLayout T18 (F-08-T08)", () => {
  it("a: default toolbar, P · R column of open slots, status bar", () => {
    const { container } = render(<SheetLayout {...props()} />);
    const bar = container.querySelector<HTMLElement>("[data-sheet-toolbar]");
    expect(bar?.style.height).toBe(`${String(TOOLBAR_H)}px`);
    for (const name of [
      "Default view",
      "+ View",
      "Filter · 0",
      "Columns",
      "Sign-offs",
      "Agents",
      "Comments",
    ]) {
      expect(within(bar as HTMLElement).getByRole("button", { name })).toBeTruthy();
    }
    expect(
      screen.getByRole("searchbox", { name: "Search rows" }).closest("span")?.className,
    ).toContain("w-[200px]");
    const pr = screen.getByRole("columnheader", { name: "P · R" });
    expect(pr.style.width).toBe(`${String(PR_W)}px`);
    expect(container.querySelectorAll("[data-pr-slots]").length).toBe(3);
    expect(screen.getByText("3 rows · 0 exceptions · View: Default")).toBeTruthy();
  });

  it("a: a P or R slot click opens the sign-off and never signs; the agent has no slot", () => {
    const onOpenSignOff = vi.fn();
    render(
      <SheetLayout
        {...props({
          onOpenSignOff,
          signOffs: { "A-1": { P: { level: "P", initials: "AC", name: "Ana Cruz" } } },
        })}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "R sign-off for A-1" }));
    expect(onOpenSignOff).toHaveBeenLastCalledWith(["A-1"], "R");
    fireEvent.click(screen.getByRole("button", { name: "Ana Cruz, P: open sign-off" }));
    expect(onOpenSignOff).toHaveBeenLastCalledWith(["A-1"], "P");
    expect(screen.queryByRole("button", { name: /^sign off$|approve/i })).toBeNull();
    const agentSigned = render(
      <SheetLayout
        {...props({
          signOffs: { "A-2": { P: { level: "P", initials: "AA", name: "Accrued Agent" } } },
        })}
      />,
    );
    expect(within(agentSigned.container).queryByText("AA")).toBeNull();
  });

  it("b: the cockpit holds a 696 px canvas that scrolls sideways with select and Key frozen", () => {
    const { container } = render(
      <SheetLayout {...props({ variant: "cockpit", dock: <aside>Dock</aside> })} />,
    );
    const canvas = container.querySelector<HTMLElement>("[data-canvas]");
    expect(canvas?.style.width).toBe(`${String(CANVAS_COCKPIT)}px`);
    expect(canvas?.className).toContain("overflow-x-auto");
    const [select, key] = screen.getAllByRole("columnheader");
    expect(select?.className).toContain("sticky");
    expect(key?.className).toContain("sticky");
    expect(screen.getByText("Dock")).toBeTruthy();
  });

  it("c: filtered shows Filter · 2 in amber, the filter row and Clear", () => {
    const onClearFilters = vi.fn();
    const { container } = render(
      <SheetLayout
        {...props({
          toolbar: {
            view: "Default view",
            filters: 2,
            search: "",
            onSearch: vi.fn(),
            onClearFilters,
          },
          grid: { ...props().grid, filterRow: true },
        })}
      />,
    );
    expect(screen.getByRole("button", { name: "Filter · 2" }).className).toContain(
      "text-amber-ink",
    );
    expect(container.querySelector("[data-filter-row]")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onClearFilters).toHaveBeenCalled();
  });

  it("d: the agent column's menu adds its two intents", () => {
    render(<SheetLayout {...props()} />);
    fireEvent.click(screen.getByRole("button", { name: "Notes column menu" }));
    expect(screen.getByRole("menuitem", { name: "Edit agent column…" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Run on empty rows" })).toBeTruthy();
  });

  it("e: a running agent column says so in the status bar", () => {
    render(
      <SheetLayout
        {...props({
          grid: {
            ...props().grid,
            status: { rows: 3, exceptions: 0, view: "Default", agentRunning: true },
          },
        })}
      />,
    );
    expect(screen.getByText("Agent column running")).toBeTruthy();
  });

  it("f: the O2 480 drawer shows the six tabs and hosts the open tab's slot", () => {
    const onTab = vi.fn();
    render(
      <SheetLayout
        {...props({
          drawer: {
            rowKey: "A-1",
            title: "A-1",
            tab: "Agents",
            onTab,
            onClose: vi.fn(),
            slots: { Agents: <p>Agents slot</p> },
          },
        })}
      />,
    );
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog)
        .getAllByRole("tab")
        .map((t) => t.textContent),
    ).toEqual([...ROW_DRAWER_TABS]);
    expect(within(dialog).getByText("Agents slot")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("tab", { name: "To-dos" }));
    expect(onTab).toHaveBeenCalledWith("To-dos");
    expect(DRAWER_W).toBe(480);
    const suggested = document.querySelector('[data-row-key="A-1"] [data-filled="suggested"]');
    expect(suggested?.className).toContain("text-ink-2");
  });

  it("g: locked rows show Lock 11 in the key cell", () => {
    render(<SheetLayout {...props({ grid: { ...props().grid, rows: rows(true) } })} />);
    expect(screen.getAllByLabelText("Locked").length).toBe(2);
  });

  it("h: empty shows the T18h copy and Add row, with the real header", () => {
    const onAddRow = vi.fn();
    render(<SheetLayout {...props({ view: "empty", onAddRow })} />);
    expect(screen.getByText(SHEET_EMPTY.title)).toBeTruthy();
    expect(screen.getByText(SHEET_EMPTY.body)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add row" }));
    expect(onAddRow).toHaveBeenCalled();
    expect(screen.getByRole("columnheader", { name: /Key/ })).toBeTruthy();
    expect(SHEET_EMPTY).toEqual({
      title: "No rows yet.",
      body: "Rows appear from the procedure session or when you add them.",
      action: "Add row",
    });
  });

  it("i: loading keeps the real header and draws 8 skeleton rows", () => {
    const { container } = render(<SheetLayout {...props({ view: "loading" })} />);
    expect(screen.getByRole("columnheader", { name: /Name/ })).toBeTruthy();
    const skeleton = container.querySelector('[data-skeleton="table"]');
    expect(skeleton?.children.length).toBe(8);
    expect(container.querySelectorAll("[data-row-key]").length).toBe(0);
  });
});
