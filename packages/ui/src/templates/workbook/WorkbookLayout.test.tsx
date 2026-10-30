import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkbookLayout, type WorkbookLayoutProps } from "./WorkbookLayout";
import type { WorkbookVM } from "./types";

// F-06-T18 (SPEC-400 AC-26 to AC-29, AC-32; F-06 Stories 5.1 to 5.4, 5.7): "Both tab groups fit one
// 50 px row at 1400, T6b links off 6,200 to Issue 2 through a callback, and T6c shows Pending pills
// and skeleton rows with no sign-off control." F-06-T21 owns the independent suite.

afterEach(cleanup);

const COPY = {
  openInExcel: "Open in Excel",
  download: "Download",
  signOff: "Sign off…",
  views: "Capital accounts view",
  scroller: "Partners",
};

const TOOLBAR = {
  firm: "Brightwater Hale",
  nav: [],
  active: "Tax Returns",
} as unknown as WorkbookLayoutProps["toolbar"];

const SIGN_OFF = {
  actor: { kind: "human" as const, name: "Samuel Ito" },
  target: "capital_accounts",
  level: "reviewer",
};

const COLUMNS = [
  { key: "name", header: "Partner", type: "label" as const },
  { key: "beg", header: "Beginning", width: 120 },
  { key: "end", header: "Ending", width: 120 },
];

function vm(extra: Partial<WorkbookVM> = {}): WorkbookVM {
  return {
    views: ["By partner", "By movement", "Calculation"],
    view: "By partner",
    title: "Capital Accounts",
    tally: [
      { label: "Beginning capital", value: "1,743,482" },
      { label: "Capital foots", tally: "tie" },
      { label: "M-2 ties", tally: "off", vars: { amount: "6,200" }, issue: "2" },
    ],
    panes: [
      {
        kind: "statement",
        table: {
          label: "Capital by partner",
          columns: COLUMNS,
          rows: [
            { id: "g", kind: "group", label: "General partner", cells: {} },
            {
              id: "gp",
              label: "Ridgeline GP, LLC",
              indent: 1,
              tag: "GP",
              cells: { beg: { value: "17835" }, end: { value: "-3000" } },
            },
            {
              id: "tpc",
              kind: "grand",
              label: "Total partners’ capital",
              cells: { beg: { value: "1743482" }, end: { value: "0" } },
            },
          ],
          footnote: "Tax basis · December 31, 2025",
        },
      },
    ],
    ...extra,
  };
}

function book(workbook: WorkbookVM, extra: Partial<WorkbookLayoutProps> = {}) {
  return render(
    <WorkbookLayout
      workbook={workbook}
      copy={COPY}
      toolbar={TOOLBAR}
      record={<div data-testid="record">2025 Form 1065</div>}
      tabs={<div data-testid="groups">tabs</div>}
      frame
      height={860}
      {...extra}
    />,
  );
}

describe("WorkbookLayout (T6, F-06-T18)", () => {
  it("AC-26: both tab groups sit in one 50 px tabsbar row at x12 that never wraps", () => {
    book(vm());
    const bar = document.querySelector("[data-workbook='tabsbar']");
    expect(bar).not.toBeNull();
    expect(bar?.className).toContain("h-[50px]");
    expect(bar?.className).toContain("flex-nowrap");
    expect(bar?.className).toContain("px-[12px]");
    expect(within(bar as HTMLElement).getByTestId("groups")).toBeTruthy();
  });

  it("AC-26: control bar 44 holds the view segmented, the centred title and the two ghost exports", () => {
    const onView = vi.fn();
    const onOpenInExcel = vi.fn();
    const onDownload = vi.fn();
    book(vm(), { onView, onOpenInExcel, onDownload });
    const bar = document.querySelector("[data-workbook='control-bar']") as HTMLElement;
    expect(bar.className).toContain("h-[44px]");
    expect(within(bar).getByRole("tablist", { name: "Capital accounts view" })).toBeTruthy();
    expect(within(bar).getByText("Capital Accounts").className).toContain("absolute");
    fireEvent.click(within(bar).getByRole("tab", { name: "By movement" }));
    expect(onView).toHaveBeenCalledWith("By movement");
    // AC-32 (Story 5.7): export is the consumer's; the kit generates no file.
    fireEvent.click(within(bar).getByRole("button", { name: "Open in Excel" }));
    fireEvent.click(within(bar).getByRole("button", { name: "Download" }));
    expect(onOpenInExcel).toHaveBeenCalledTimes(1);
    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it("AC-26: the tally strip is a 52 slot over the shell's columns", () => {
    book(vm());
    const strip = document.querySelector("[data-workbook='tally']") as HTMLElement;
    expect(strip.className).toContain("h-[52px]");
    // The shell's columns pad 10 12 12 (--gutter-pane, --edge-app) around the panes.
    const cols = document.querySelector("[data-workbook='columns']") as HTMLElement;
    expect(cols.parentElement?.getAttribute("data-shell")).toBe("cols");
  });

  it("AC-27: off 6,200 links to Issue 2 through onOpenIssue", () => {
    const onOpenIssue = vi.fn();
    book(vm(), { onOpenIssue });
    const strip = screen.getByRole("list", { name: "Checks" });
    expect(within(strip).getByText("off 6,200")).toBeTruthy();
    fireEvent.click(within(strip).getByRole("button", { name: /Issue 2/ }));
    expect(onOpenIssue).toHaveBeenCalledWith("2");
  });

  it("AC-27: a variance exception's issue link reaches onOpenIssue with its issue", () => {
    const onOpenIssue = vi.fn();
    book(
      vm({
        view: "By movement",
        panes: [
          {
            kind: "statement",
            table: {
              label: "Capital by movement",
              columns: [
                { key: "name", header: "Ridgeline Property Partners, LP", entity: true },
                { key: "d", header: "Change", type: "variance", width: 220 },
              ],
              rows: [
                {
                  id: "dist",
                  label: "Distributions",
                  cells: {
                    d: {
                      value: null,
                      variance: { value: "-50000", ratio: "-0.2", exception: { issue: "2" } },
                    },
                  },
                },
              ],
            },
          },
        ],
      }),
      { onOpenIssue },
    );
    fireEvent.click(screen.getByRole("button", { name: /Issue 2/ }));
    expect(onOpenIssue).toHaveBeenCalledWith("2");
  });

  it("AC-28: statement figures render as the server sent them: negatives in parentheses, zero as —, no $", () => {
    book(vm());
    const pane = document.querySelector("[data-workbook='pane']") as HTMLElement;
    expect(within(pane).getByText("(3,000)")).toBeTruthy();
    expect(within(pane).getByText("GP")).toBeTruthy();
    expect(pane.textContent).not.toContain("$");
    expect(within(pane).getByText("Tax basis · December 31, 2025")).toBeTruthy();
  });

  it("AC-28: no code path in the workbook kit adds numbers (ADR-050)", () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    for (const file of ["WorkbookLayout.tsx", "types.ts"]) {
      const src = readFileSync(join(dir, file), "utf8");
      expect(src).not.toMatch(/\.reduce\(/);
      expect(src).not.toMatch(/parseFloat|Number\(/);
    }
  });

  it("AC-29: Building shows Pending pills, the running row and skeleton rows, and no value as final", () => {
    const onOpenSignOff = vi.fn();
    book(vm({ building: { label: "Workbook agent is running" } }), {
      onOpenSignOff,
      signOff: SIGN_OFF,
    });
    const strip = screen.getByRole("list", { name: "Checks" });
    expect(within(strip).queryByText("1,743,482")).toBeNull();
    expect(within(strip).queryByText("off 6,200")).toBeNull();
    expect(within(strip).getAllByText("Pending")).toHaveLength(3);
    expect(screen.getByText("Workbook agent is running")).toBeTruthy();
    const pane = document.querySelector("[data-workbook='pane']") as HTMLElement;
    expect(pane.getAttribute("aria-busy")).toBe("true");
    expect(within(pane).getByText("Partner")).toBeTruthy();
    expect(within(pane).queryByText("Ridgeline GP, LLC")).toBeNull();
    expect(pane.querySelectorAll("[data-workbook='skeleton-row']").length).toBe(7);
    // No sign-off control is enabled while the agent builds.
    const signOff = screen.getByRole("button", { name: "Sign off…" });
    expect(signOff).toHaveProperty("disabled", true);
    expect(signOff.getAttribute("aria-describedby")).toBeTruthy();
    fireEvent.click(signOff);
    expect(onOpenSignOff).not.toHaveBeenCalled();
  });

  it("Sign off… only opens SHL-12 through onOpenSignOff once built", () => {
    const onOpenSignOff = vi.fn();
    book(vm(), { onOpenSignOff, signOff: SIGN_OFF });
    const control = screen.getByRole("button", { name: "Sign off…" });
    expect(control.getAttribute("data-human-verb")).toBe("Sign off");
    fireEvent.click(control);
    expect(onOpenSignOff).toHaveBeenCalledWith("capital_accounts", "reviewer");
  });

  it("without onOpenSignOff there is no sign-off control at all, and an agent never gets one", () => {
    book(vm());
    expect(screen.queryByRole("button", { name: "Sign off…" })).toBeNull();
    cleanup();
    book(vm(), { onOpenSignOff: vi.fn(), signOff: { ...SIGN_OFF, actor: { kind: "agent" } } });
    expect(screen.queryByRole("button", { name: "Sign off…" })).toBeNull();
  });

  it("AC-26 (Story 5.1): sized panes sit in a labelled, focusable scroller that arrow keys move", () => {
    const pane = vm().panes[0];
    const five = Array.from({ length: 5 }, (_, i) => ({
      ...pane,
      kind: "statement" as const,
      width: 452,
      title: `Partner ${String(i + 1)}`,
    }));
    book(vm({ panes: five }));
    const scroller = screen.getByRole("region", { name: "Partners" });
    expect(scroller.getAttribute("tabindex")).toBe("0");
    expect(scroller.querySelectorAll("[data-workbook='pane']")).toHaveLength(5);
    const by = vi.fn();
    Object.defineProperty(scroller, "scrollBy", { value: by });
    fireEvent.keyDown(scroller, { key: "ArrowRight" });
    expect(by).toHaveBeenCalledWith(expect.objectContaining({ left: 462 }));
    fireEvent.keyDown(scroller, { key: "ArrowLeft" });
    expect(by).toHaveBeenLastCalledWith(expect.objectContaining({ left: -462 }));
  });

  it("T6 adopts no T18 behaviour: no editable cell, no agent column", () => {
    book(vm());
    expect(document.querySelector("[contenteditable], input, textarea")).toBeNull();
    expect(document.querySelector("[data-actor='agent']")).toBeNull();
  });
});
