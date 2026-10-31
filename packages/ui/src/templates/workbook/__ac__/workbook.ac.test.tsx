// ac-test-author: notanaskhan (ADR-078 independent suite, built in the S21 solo lane)
// F-06-T21 (TASK-2607; SPEC-400 AC-26 to AC-32; F-06.md §3 F5 Stories 5.1 to 5.7; ADR-050): the T6
// WorkbookLayout and CalcTree acceptance tests, written from the stories and the public props in
// `types.ts` only. The row's acceptance: "Tests prove the table never sums, SignOffSlots never
// signs, reduced motion removes the 45 ms stagger, and the calc tree is operable by keyboard."
// Reduced motion (`document.getAnimations()`) needs a browser: apps/web/e2e/specimens/
// f06-workbook.ac.spec.ts.

import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { MATCH_LIGHT_MS, matchIdOf } from "../../../tracing";
import { installDomShims } from "../../../test-dom";
import type { TableColumn, TableRow } from "../../../data/types";
import {
  type CalcStep,
  type GridPayload,
  type WorkbookCopy,
  WorkbookLayout,
  type WorkbookLayoutProps,
  type WorkbookVM,
} from "../index";

const HERE = dirname(fileURLToPath(import.meta.url));

beforeAll(installDomShims);
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const wait = (ms: number): void => {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
};

const COPY: WorkbookCopy = {
  openInExcel: "Open in Excel",
  download: "Download",
  signOff: "Sign off…",
  views: "Capital accounts view",
  scroller: "Partners",
  signOffChips: {
    label: "Sign-offs",
    changedAfter: "Changed after sign-off",
    open: (name, level) => `${name}, ${level}: open sign-off`,
    reviewed: (initials) => `Reviewed · ${initials}`,
  },
};

const VIEWS = [
  { value: "movement", label: "By movement" },
  { value: "partner", label: "By partner" },
] as const;

const COLUMNS: readonly TableColumn[] = [
  { key: "label", header: "Tax-exempt income", type: "label" },
  { key: "amount", header: "Amount" },
];

// Story 5.3: the tax-exempt column of TPL-06b. The server's total row is deliberately not the sum
// of the items (124 + 2,356 + 2,015 + 155 + 1,550 = 6,200): the kit must print the server's.
const ITEMS: readonly TableRow[] = [
  { id: "r1", label: "Calder Family Trust", cells: { amount: { value: "124.00" } } },
  { id: "r2", label: "Juniper Holdings", cells: { amount: { value: "2356.00" } } },
  { id: "r3", label: "Oakmont Fund II", cells: { amount: { value: "2015.00" } } },
  { id: "r4", label: "Ridge GP, LLC", tag: "GP", cells: { amount: { value: "155.00" } } },
  { id: "r5", label: "Ellery Partners", tag: "LP", cells: { amount: { value: "1550.00" } } },
  { id: "neg", label: "Distributions", cells: { amount: { value: "-148500.00" } } },
  { id: "zero", label: "Contributions", cells: { amount: { value: "0.00" } } },
  { id: "total", kind: "total", label: "Total", cells: { amount: { value: "9999.00" } } },
];

const workbook = (overrides: Partial<WorkbookVM> = {}): WorkbookVM => ({
  views: VIEWS,
  view: "movement",
  title: "Ridgeline Property Partners, LP · Capital accounts",
  tally: [
    { label: "Capital foots", tally: "tie" },
    { label: "Ending capital", value: "6,866,200" },
  ],
  panes: [
    { kind: "statement", table: { label: "Tax-exempt income", columns: COLUMNS, rows: ITEMS } },
  ],
  ...overrides,
});

const TOOLBAR: WorkbookLayoutProps["toolbar"] = {
  nav: [{ label: "Home" }, { label: "Tax" }],
  active: "Tax",
  firm: "Brightwater Hale",
};

function mount(props: Partial<WorkbookLayoutProps> = {}): ReturnType<typeof render> {
  return render(
    <WorkbookLayout
      workbook={workbook()}
      copy={COPY}
      toolbar={TOOLBAR}
      record={<div>Ridgeline Property Partners, LP</div>}
      {...props}
    />,
  );
}

describe("Story 5.3 (AC-28): the browser never sums", () => {
  it("test_ac28_a_total_the_rows_disagree_with_renders_the_servers_total_verbatim", () => {
    mount();
    const table = screen.getByRole("grid", { name: "Tax-exempt income" });
    const total = within(table).getByText("Total").closest("tr");
    expect(total).not.toBeNull();
    expect(within(total as HTMLElement).getByText("9,999")).toBeTruthy();
    expect(within(table).queryByText("6,200")).toBeNull();
    expect(within(table).queryByText("(140,300)")).toBeNull(); // the rows with the negative
  });

  it("test_ac28_negatives_in_parentheses_zero_as_a_dash_and_no_dollar_sign", () => {
    mount();
    const table = screen.getByRole("grid", { name: "Tax-exempt income" });
    expect(within(table).getByText("(148,500)")).toBeTruthy();
    const zero = within(table).getByText("Contributions").closest("tr") as HTMLElement;
    expect(within(zero).getByText("—")).toBeTruthy();
    expect(table.textContent).not.toContain("$");
    expect(table.textContent).not.toContain("-148,500");
  });

  it("test_ac26_a_statement_pane_is_a_keyboard_grid_with_its_row_count", () => {
    mount();
    const grid = screen.getByRole("grid", { name: "Tax-exempt income" });
    expect(grid.tabIndex).toBe(0);
    expect(grid.getAttribute("aria-rowcount")).toBe(String(ITEMS.length + 1));
  });

  it("test_ac28_tally_values_are_the_servers_words_and_figures", () => {
    mount();
    const strip = screen.getByRole("list", { name: "Checks" });
    expect(within(strip).getByText("6,866,200")).toBeTruthy();
    expect(within(strip).getByText("tie")).toBeTruthy();
  });

  it("test_ac28_the_calc_tree_prints_each_steps_server_value_and_never_its_childrens_sum", () => {
    const tree: CalcStep[] = [
      {
        ref: "end",
        depth: 0,
        op: "",
        label: "Ending capital",
        value: "1,000",
        src: "Capital!H12",
      },
      { ref: "beg", depth: 1, op: "+", label: "Beginning", value: "938,561", src: "Capital!H3" },
      { ref: "inc", depth: 1, op: "+", label: "Income", value: "41,250", src: "Capital!H6" },
      {
        ref: "dis",
        depth: 1,
        op: "−",
        label: "Distributions",
        value: "(148,500)",
        src: "Capital!H9",
      },
    ];
    mount({
      workbook: workbook({ panes: [{ kind: "calc", tree, title: "Calder Family Trust" }] }),
    });
    const root = screen.getByRole("tree");
    expect(within(root).getByText("1,000")).toBeTruthy();
    expect(within(root).queryByText("831,311")).toBeNull(); // 938,561 + 41,250 − 148,500
  });

  it("test_ac28_no_code_path_in_the_kit_or_the_calc_tree_parses_or_adds_numbers", () => {
    const here = join(HERE, "..");
    for (const file of [join(here, "WorkbookLayout.tsx"), join(here, "../../data/CalcTree.tsx")]) {
      const source = readFileSync(file, "utf8");
      for (const idiom of [/\.reduce\(/, /parseFloat\(/, /parseInt\(/, /\bNumber\(/, /BigInt\(/]) {
        expect(source, `${file} ${String(idiom)}`).not.toMatch(idiom);
      }
    }
  });
});

describe("Story 5.2 (AC-27): off by 6,200, linked to its cause; variance words", () => {
  it("test_ac27_the_off_pill_reads_off_6200_and_its_issue_link_calls_back_with_the_issue", () => {
    const onOpenIssue = vi.fn();
    mount({
      workbook: workbook({
        tally: [
          { label: "Capital foots", tally: "off", vars: { amount: "6,200" }, issue: "2" },
          { label: "M-2 ties", tally: "tie" },
        ],
      }),
      onOpenIssue,
    });
    const strip = screen.getByRole("list", { name: "Checks" });
    expect(within(strip).getByText("off 6,200")).toBeTruthy();
    fireEvent.click(within(strip).getByRole("button", { name: /Issue 2/ }));
    expect(onOpenIssue).toHaveBeenCalledWith("2");
  });

  it("test_ac27_each_of_the_five_variance_states_says_itself_in_words_with_an_icon", () => {
    const columns: TableColumn[] = [
      { key: "label", header: "Account", type: "label" },
      { key: "change", header: "Change", type: "variance" },
    ];
    const row = (id: string, variance: object): TableRow => ({
      id,
      label: id,
      cells: { change: { value: null, variance: { value: "6200.00", ...variance } } },
    });
    const onExplain = vi.fn();
    mount({
      workbook: workbook({
        panes: [
          {
            kind: "statement",
            table: {
              label: "By movement",
              columns,
              rows: [
                row("within", { value: "12.00", threshold: "500.00" }),
                row("unexplained", { threshold: "500.00" }),
                row("explained", { explained: { text: "Timing", by: "Olivia Brandt" } }),
                row("exception", { exception: { issue: "9" } }),
                row("posted", { posted: true }),
              ],
            },
          },
        ],
      }),
      onExplain,
    });
    const table = screen.getByRole("grid", { name: "By movement" });
    const cellOf = (id: string): HTMLElement =>
      within(table).getByText(id, { selector: "th, td, span, div" }).closest("tr") as HTMLElement;
    expect(within(cellOf("within")).getByText("Within threshold")).toBeTruthy();
    expect(within(cellOf("unexplained")).getByText("Unexplained")).toBeTruthy();
    expect(within(cellOf("explained")).getByText("Explained")).toBeTruthy();
    expect(within(cellOf("exception")).getByText("Exception")).toBeTruthy();
    expect(within(cellOf("posted")).getByText("Ties once posted")).toBeTruthy();
    // Never colour alone: an icon beside the words ("Ties once posted" is its own pill).
    for (const id of ["unexplained", "explained", "exception"]) {
      expect(cellOf(id).querySelector("svg"), id).not.toBeNull();
    }
    fireEvent.click(within(cellOf("unexplained")).getByRole("button", { name: /Explain/ }));
    expect(onExplain).toHaveBeenCalledTimes(1);
    expect(onExplain.mock.calls[0]?.[1]).toBe("change");
  });
});

describe("Story 5.4 (AC-29): building is a proposal in progress", () => {
  it("test_ac29_building_reads_pending_shows_the_running_row_and_enables_no_sign_off", () => {
    const onOpenSignOff = vi.fn();
    mount({
      workbook: workbook({
        building: { label: "Workbook agent is running" },
        tally: [
          { label: "Capital foots", tally: "pending" },
          { label: "M-2 ties", tally: "pending" },
        ],
      }),
      signOff: {
        actor: { kind: "human", name: "Samuel Ito" },
        target: "schedule:m2",
        level: "L2",
      },
      onOpenSignOff,
    });
    expect(screen.getAllByText("Workbook agent is running").length).toBeGreaterThan(0);
    const strip = screen.getByRole("list", { name: "Checks" });
    expect(within(strip).getAllByText("Pending")).toHaveLength(2);
    const signOff = screen.queryByRole("button", { name: "Sign off…" });
    expect(signOff === null || signOff.hasAttribute("disabled")).toBe(true);
    // No value renders as final while the agent builds: the payload's figures are not shown.
    expect(screen.queryByText("9,999")).toBeNull();
    expect(onOpenSignOff).not.toHaveBeenCalled();
  });
});

describe("Story 5.5 (AC-30): the control bar's sign-off opens the dialog and never signs", () => {
  it("test_ac30_sign_off_calls_on_open_sign_off_and_nothing_else", () => {
    const onOpenSignOff = vi.fn();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("the kit never calls the network");
    });
    mount({
      signOff: {
        actor: { kind: "human", name: "Samuel Ito" },
        target: "schedule:m2",
        level: "L2",
      },
      onOpenSignOff,
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign off…" }));
    expect(onOpenSignOff).toHaveBeenCalledWith("schedule:m2", "L2");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("test_ac30_the_agent_is_never_offered_a_sign_off", () => {
    mount({
      signOff: { actor: { kind: "agent" }, target: "schedule:m2", level: "L1" },
      onOpenSignOff: vi.fn(),
    });
    expect(screen.queryByRole("button", { name: "Sign off…" })).toBeNull();
  });

  it("test_ac30_signed_slots_render_as_chips_in_preparer_before_reviewer_order", () => {
    mount({
      workbook: workbook({
        signOffs: [
          { level: "L2", initials: "DR", name: "Diane Reyes" },
          { level: "L1", initials: "OB", name: "Olivia Brandt" },
        ],
      }),
      signOff: {
        actor: { kind: "human", name: "Samuel Ito" },
        target: "schedule:m2",
        level: "L2",
      },
      onOpenSignOff: vi.fn(),
    });
    const group = screen.getByRole("group", { name: "Sign-offs" });
    const text = group.textContent;
    expect(text.indexOf("OB")).toBeGreaterThanOrEqual(0);
    expect(text.indexOf("OB")).toBeLessThan(text.indexOf("DR"));
  });
});

describe("Story 5.6 (AC-31): the calculation traced to the source workbook, by keyboard", () => {
  const FILE = "Ridgeline capital accounts 2025.xlsx";
  const at = (cell: string): string =>
    matchIdOf({ kind: "sheet_cell", file: FILE, sheet: "05 Capital", cell });
  const tree: CalcStep[] = [
    {
      ref: "end",
      depth: 0,
      op: "",
      label: "Ending capital",
      value: "831,311",
      src: "05 Capital!H4",
      match: at("H4"),
    },
    {
      ref: "beg",
      depth: 1,
      op: "+",
      label: "Beginning capital",
      value: "938,561",
      src: "05 Capital!H2",
      match: at("H2"),
    },
    {
      ref: "dis",
      depth: 1,
      op: "−",
      label: "Distributions",
      value: "(148,500)",
      src: "05 Capital!H3",
      match: at("H3"),
    },
  ];
  const grid: GridPayload = {
    label: FILE,
    source: FILE,
    sheet: "05 Capital",
    columns: Array.from({ length: 8 }, (_, i) => ({ key: `c${String(i)}`, width: 80 })),
    rows: [1, 2, 3, 4].map((n) => ({
      id: `row${String(n)}`,
      cells: { c7: n === 1 ? "Capital" : `v${String(n)}` },
    })),
  };

  function traced(): void {
    mount({
      workbook: workbook({
        panes: [
          { kind: "calc", tree, title: "Calder Family Trust" },
          { kind: "grid", grid },
        ],
      }),
    });
  }

  const litCells = (): string[] =>
    Array.from(document.querySelectorAll("[data-match-kind='cell'][data-lit]")).map(
      (el) => el.getAttribute("data-match") ?? "",
    );

  it("test_ac31_the_tree_is_a_keyboard_tree_with_arrows_between_steps", () => {
    traced();
    const items = within(screen.getByRole("tree")).getAllByRole("treeitem");
    expect(items.length).toBe(3);
    items[0]?.focus();
    fireEvent.keyDown(items[0] as HTMLElement, { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    fireEvent.keyDown(items[1] as HTMLElement, { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[2]);
    fireEvent.keyDown(items[2] as HTMLElement, { key: "ArrowUp" });
    expect(document.activeElement).toBe(items[1]);
  });

  it("test_ac31_focusing_a_step_lights_its_typed_cell_within_360_ms", () => {
    traced();
    const step = within(screen.getByRole("tree"))
      .getByText("Beginning capital")
      .closest("[role='treeitem']") as HTMLElement;
    act(() => {
      step.focus();
      fireEvent.focus(step);
    });
    wait(MATCH_LIGHT_MS);
    expect(litCells()).toEqual([at("H2")]);
  });

  it("test_ac31_enter_pins_the_match_and_escape_clears_it_and_returns_focus", () => {
    traced();
    const step = within(screen.getByRole("tree"))
      .getByText("Distributions")
      .closest("[role='treeitem']") as HTMLElement;
    act(() => {
      step.focus();
      fireEvent.focus(step);
    });
    wait(MATCH_LIGHT_MS);
    fireEvent.keyDown(step, { key: "Enter" });
    const source = screen.getByRole("grid", { name: FILE });
    act(() => {
      fireEvent.blur(step);
      source.focus();
    });
    wait(MATCH_LIGHT_MS * 2);
    expect(litCells()).toEqual([at("H3")]); // pinned: leaving the step does not release it
    fireEvent.keyDown(document, { key: "Escape" });
    expect(litCells()).toEqual([]); // cleared at once (E1's contract, F-05-T42)
    expect(document.activeElement).toBe(step);
  });

  it("test_ac31_match_ids_come_from_the_typed_locator_not_the_steps_text", () => {
    traced();
    const ids = new Set(
      Array.from(document.querySelectorAll("[data-match]")).map((el) =>
        el.getAttribute("data-match"),
      ),
    );
    for (const s of tree) expect(ids.has(s.match ?? "")).toBe(true);
    expect(ids.has("05 Capital!H2")).toBe(false); // the human-readable src is never an id
  });
});

describe("Story 5.1 (AC-26): the by-partner scroller is a labelled, focusable region", () => {
  it("test_ac26_the_scroller_is_a_named_focusable_region", () => {
    const pane = (title: string) => ({
      kind: "statement" as const,
      width: 452,
      title,
      table: { label: title, columns: COLUMNS, rows: ITEMS.slice(0, 2) },
    });
    mount({
      workbook: workbook({
        view: "partner",
        panes: [pane("Calder Family Trust"), pane("Juniper Holdings"), pane("Oakmont Fund II")],
      }),
    });
    const region = screen.getByRole("region", { name: "Partners" });
    expect(region.tabIndex).toBe(0);
    expect(within(region).getAllByRole("grid")).toHaveLength(3);
  });
});

describe("Story 5.7 (AC-32): export is the consumer's", () => {
  it("test_ac32_open_in_excel_and_download_call_back_and_generate_no_file", () => {
    const onOpenInExcel = vi.fn();
    const onDownload = vi.fn();
    const created = vi.fn();
    vi.stubGlobal(
      "URL",
      Object.assign(Object.create(URL) as object, { createObjectURL: created }),
    );
    try {
      mount({ onOpenInExcel, onDownload });
      fireEvent.click(screen.getByRole("button", { name: "Open in Excel" }));
      fireEvent.click(screen.getByRole("button", { name: "Download" }));
    } finally {
      vi.unstubAllGlobals();
    }
    expect(onOpenInExcel).toHaveBeenCalledTimes(1);
    expect(onDownload).toHaveBeenCalledTimes(1);
    expect(created).not.toHaveBeenCalled();
    expect(document.querySelector("a[download]")).toBeNull();
  });
});
