import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { pbcGroups } from "../specimens/workpaper-data";
import { installDomShims } from "../test-dom";
import type { CitationView } from "../tracing/types";
import { ScheduleBar, SectionBand } from "./bands";
import { SourceDocGroup, SourceDocRow } from "./source-docs";
import type { SourceDoc, WorkpaperTab } from "./types";
import { REVEAL_AFTER_EXPAND_MS, WorkpaperPane, workpaperCell } from "./workpaper";

// F-05-T50: "Dark section bands and schedule bars match the Workpaper kit and source-doc rows open
// the viewer through a callback." The band is one native button with no buttons inside, its label
// reads SECTION n — TITLE, sections read band → caption → rows → schedule → table → after-rows,
// a citation lights its exact cell and row, expands a collapsed section first, and collapsing or
// switching tabs closes it. Source-document rows say their state in words and call onOpen.

beforeAll(installDomShims);
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const SHEET = "wp-test";

const CITES: CitationView[] = [
  {
    n: 1,
    title: "AP-10: Audit Program for General Planning Procedures",
    quote: "Determine whether the plan uses a service organization.",
    loc: "BH Audit Methodology · EBP v3 · page 14",
    match: workpaperCell(SHEET, "keystone", "org"),
  },
  {
    n: 2,
    title: "Complementary controls memo",
    quote: "Each control maps to a sponsor control.",
    loc: "Section 2",
    match: workpaperCell(SHEET, "cuec-1", "map"),
  },
];

const TABS: WorkpaperTab[] = [
  {
    label: "Service Organizations",
    sheet: SHEET,
    sections: [
      {
        id: "s1",
        n: 1,
        title: "Service organizations",
        sign: "Prepared · Accrued Agent",
        caption: "Determines whether the plan uses a service organization.",
        rows: [{ key: "Procedure performed", text: "AP-10 step 4.", cites: [1, 2] }],
        schedule: "Schedule 1100.04-A · SOC 1 report coverage",
        table: {
          columns: [
            { key: "org", header: "Service organization", type: "label" },
            { key: "rel", header: "Relevant", type: "text" },
          ],
          rows: [
            {
              id: "keystone",
              label: "Keystone Retirement Services",
              cells: { rel: { value: "Yes" } },
            },
            {
              id: "harborline",
              label: "Harborline Trust Company",
              cells: { rel: { value: "Yes" } },
            },
          ],
        },
        after: [{ key: "AP-40 required", text: "Yes" }],
      },
      {
        id: "s3",
        n: 3,
        title: "Complementary user entity controls",
        collapsed: true,
        table: {
          columns: [
            { key: "ctl", header: "Control", type: "label" },
            { key: "map", header: "Sponsor control", type: "text" },
          ],
          rows: [{ id: "cuec-1", label: "Contributions", cells: { map: { value: "SC-4" } } }],
        },
      },
    ],
    citations: CITES,
    procedures: [{ ref: "AP-10 step 4", title: "General Planning Procedures" }],
  },
  {
    label: "Linkage",
    sheet: "wp-linkage",
    sections: [
      { id: "l1", n: 1, title: "Risk linkage", rows: [{ key: "Conclusion", text: "Mapped." }] },
    ],
  },
];

function band(name: RegExp): HTMLElement {
  return screen.getByRole("button", { name });
}

describe("C-02 SectionBand and ScheduleBar", () => {
  it("reads SECTION n — TITLE on espresso, as one native button with no button inside", () => {
    const toggle = vi.fn();
    render(
      <SectionBand
        number={1}
        title="Service organizations"
        sign="Prepared · Accrued Agent"
        onToggle={toggle}
      />,
    );
    const el = band(/Section 1 — Service organizations/);
    expect(el.tagName).toBe("BUTTON");
    expect(el.className).toContain("bg-espresso");
    expect(el.className).toContain("text-band-dark");
    expect(el.className).toContain("uppercase");
    expect(el.className).toContain("h-[30px]");
    expect(el.className).not.toMatch(/rounded-(?!none)/);
    expect(el.getAttribute("aria-expanded")).toBe("true");
    expect(el.querySelector("button")).toBeNull();
    expect(within(el).getByText("Prepared · Accrued Agent")).toBeTruthy();
    fireEvent.click(el);
    expect(toggle).toHaveBeenCalledWith(false);
  });

  it("collapsed turns the chevron; static draws a plain bar with no chevron; forced states hold", () => {
    render(
      <>
        <SectionBand number={3} title="Complementary user entity controls" collapsed />
        <SectionBand number={2} title="SOC 1 reports" collapsible={false} />
        <SectionBand number={4} title="Hover" forceState="hover" />
      </>,
    );
    const closed = band(/Section 3/);
    expect(closed.getAttribute("aria-expanded")).toBe("false");
    expect(closed.querySelector("svg:last-child")?.getAttribute("class")).toContain("-rotate-90");
    const bar = screen.getByText("Section 2 — SOC 1 reports").closest("[data-workpaper=band]");
    expect(bar?.tagName).toBe("DIV");
    expect(bar?.querySelector("svg")).toBeNull();
    expect(band(/Section 4/).dataset.force).toBe("hover");
  });

  it("the schedule bar is a 28 espresso title bar", () => {
    render(<ScheduleBar title="Schedule 1100.04-A · SOC 1 report coverage" />);
    const bar = screen.getByText("Schedule 1100.04-A · SOC 1 report coverage").parentElement;
    expect(bar?.className).toContain("h-[28px]");
    expect(bar?.className).toContain("bg-espresso");
    expect(bar?.className).toContain("text-on-dark");
  });
});

describe("C-02 WorkpaperPane", () => {
  it("reads band, caption, rows, schedule, table and after-rows in order", () => {
    render(<WorkpaperPane title="Service Organizations & SOC 1" tabs={TABS} />);
    const section = screen.getByRole("region", { name: "Service organizations" });
    const parts = [...section.querySelectorAll("[data-workpaper], table")].map(
      (el) => el.getAttribute("data-workpaper") ?? el.tagName.toLowerCase(),
    );
    expect(parts).toEqual(["band", "body", "caption", "kv", "schedule", "table", "kv"]);
    const after = section.querySelectorAll("[data-workpaper=kv]")[1]?.firstElementChild;
    expect(after?.className).toContain("hairline-t");
    // Every table cell answers to its workpaper-cell locator.
    const cell = within(section).getByText("Keystone Retirement Services");
    expect(cell.getAttribute("data-match")).toBe(workpaperCell(SHEET, "keystone", "org"));
  });

  it("collapses a section: aria-expanded, inert, and back", () => {
    render(<WorkpaperPane tabs={TABS} />);
    const toggle = band(/Section 1 — Service organizations/);
    const body = document.getElementById(toggle.getAttribute("aria-controls") ?? "");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(body?.hasAttribute("inert")).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(body?.hasAttribute("inert")).toBe(false);
  });

  it("a pinned citation lights its exact cell and its row; collapsing the section closes it", () => {
    render(<WorkpaperPane tabs={TABS} />);
    fireEvent.click(screen.getByRole("button", { name: /Citation 1:/ }));
    const cell = screen.getByText("Keystone Retirement Services");
    expect(cell.hasAttribute("data-lit")).toBe(true);
    expect(cell.closest("tr")?.hasAttribute("data-lit")).toBe(true);
    expect(screen.getByText("Harborline Trust Company").hasAttribute("data-lit")).toBe(false);
    fireEvent.click(band(/Section 1 — Service organizations/));
    expect(cell.hasAttribute("data-lit")).toBe(false);
  });

  it("a citation into a collapsed section expands it first, then reveals the cell after 380ms", () => {
    vi.useFakeTimers();
    render(<WorkpaperPane tabs={TABS} />);
    const closed = band(/Section 3/);
    expect(closed.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: /Citation 2:/ }));
    expect(closed.getAttribute("aria-expanded")).toBe("true");
    const cell = screen.getByText("SC-4");
    expect(cell.hasAttribute("data-lit")).toBe(true);
    act(() => {
      vi.advanceTimersByTime(REVEAL_AFTER_EXPAND_MS);
    });
    expect(closed.getAttribute("aria-expanded")).toBe("true");
  });

  it("switching tabs renders that tab and closes any open citation", () => {
    const onTab = vi.fn();
    render(<WorkpaperPane tabs={TABS} onTab={onTab} />);
    fireEvent.click(screen.getByRole("button", { name: /Citation 1:/ }));
    expect(screen.getByText("Keystone Retirement Services").hasAttribute("data-lit")).toBe(true);
    fireEvent.click(screen.getByRole("tab", { name: "Linkage" }));
    expect(onTab).toHaveBeenCalledWith("Linkage");
    expect(band(/Section 1 — Risk linkage/)).toBeTruthy();
    expect(screen.queryByText("Keystone Retirement Services")).toBeNull();
  });

  it("chrome draws the title, the small tabs and the ghost buttons; chrome={false} drops them", () => {
    const { unmount } = render(
      <WorkpaperPane title="Service Organizations & SOC 1" tabs={TABS} />,
    );
    expect(screen.getByRole("heading", { name: "Service Organizations & SOC 1" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open in Excel" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Citations (2)" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Procedures (1)" })).toBeTruthy();
    unmount();
    render(<WorkpaperPane tabs={TABS} chrome={false} />);
    expect(screen.queryByRole("heading")).toBeNull();
    expect(screen.queryByRole("tablist")).toBeNull();
    const pane = document.querySelector("[data-workpaper=pane]");
    expect(pane?.className).not.toContain("shadow-e2");
    expect(screen.getByRole("button", { name: "Citations (2)" })).toBeTruthy();
  });
});

describe("C-15 SourceDocGroup and SourceDocRow", () => {
  const DOCS: SourceDoc[] = [
    {
      id: "a",
      title: "Plan document & amendments",
      status: "received",
      path: "initial-input/a.pdf",
    },
    { id: "b", title: "Certified trust report (full year, signed)", status: "review" },
    { id: "c", title: "W-3 Form", status: "requested" },
  ];

  it("a row opens the viewer through onOpen and says its state in words", () => {
    const onOpen = vi.fn();
    render(
      <SourceDocGroup title="Plan documents" received={1} total={3}>
        {DOCS.map((d) => (
          <SourceDocRow key={d.id} doc={d} onOpen={onOpen} />
        ))}
      </SourceDocGroup>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Plan document & amendments/ }));
    expect(onOpen).toHaveBeenCalledWith(DOCS[0]);
    expect(
      screen.getByRole("button", { name: /Plan document & amendments.*Received/ }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Certified trust report.*Uploaded – needs review/ }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /W-3 Form.*Requested/ })).toBeTruthy();
    // A missing document is never red.
    const requested = document.querySelector("[data-status=requested]");
    expect(requested?.innerHTML).not.toMatch(/red/);
  });

  it("the band says received of total and collapses its rows", () => {
    const onToggle = vi.fn();
    render(
      <SourceDocGroup title="Plan documents" received={3} total={5} onToggle={onToggle}>
        <SourceDocRow doc={DOCS[0] as SourceDoc} />
      </SourceDocGroup>,
    );
    const toggle = screen.getByRole("button", { name: /Plan documents.*3 of 5/ });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(toggle);
    expect(onToggle).toHaveBeenCalledWith(false);
    expect(screen.queryByRole("button", { name: /Plan document & amendments/ })).toBeNull();
  });

  it("selected marks the open document; compact draws the C-15 geometry", () => {
    render(
      <>
        <SourceDocRow doc={DOCS[0] as SourceDoc} selected />
        <SourceDocRow doc={DOCS[2] as SourceDoc} size="compact" />
      </>,
    );
    const [open, compact] = screen.getAllByRole("button");
    expect(open?.getAttribute("aria-current")).toBe("true");
    expect(open?.className).toContain("min-h-[52px]");
    expect(compact?.className).toContain("min-h-[40px]");
    cleanup();
    // AUD-02's cockpit rows: min 44, padding 8 12 9.
    render(<SourceDocRow doc={DOCS[0] as SourceDoc} tight />);
    expect(screen.getByRole("button").className).toContain(
      "min-h-[44px] px-[12px] pt-[8px] pb-[9px]",
    );
    expect(compact?.className).toContain("pl-[34px]");
  });

  it("the specimen's PBC list is 11 of 24 received (3 + 4 + 3 + 1)", () => {
    const groups = pbcGroups();
    expect(groups.map((g) => [g.title, g.received, g.total])).toEqual([
      ["Plan documents", 3, 5],
      ["Trust / Recordkeeper Reports", 4, 6],
      ["Census & Payroll", 3, 7],
      ["Form 5500 & SOC 1", 1, 4],
      ["Cash", 0, 1],
      ["Compliance & other", 0, 1],
    ]);
  });
});
