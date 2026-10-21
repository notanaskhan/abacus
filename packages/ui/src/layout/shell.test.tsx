// F-05-T18 (C-00 Shell Kit): the Toolbar's measured nav overflow in the component (element widths
// are mocked, since jsdom has no layout), the Tier D heights (46, 42, 59, 46, and the close
// variant's 42 + 50) as the geometry tokens the parts are built on, RecordHeader, Tabsbar, Pane,
// PaneHeader, Timeline and AppShell. The same heights are asserted as computed styles in a real
// browser by apps/web/e2e/visual/tier-d.spec.ts.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import guards from "../../scope-guards.gen.json";
import { installDomShims } from "../test-dom";
import {
  AppShell,
  FooterAction,
  FooterSpacer,
  Pane,
  PaneAction,
  PaneHeader,
  PortalToolbar,
  RecordHeader,
  Tabsbar,
  Timeline,
  Toolbar,
} from "./index";

const NAV = guards.nav.map((label) => ({ label }));
const FIRM = { firm: "Brightwater Hale", firmTitle: "Brightwater Hale LLP" } as const;

// ---- Mocked layout ----------------------------------------------------------------------------

// What Geist measures on the bar (see nav-overflow.test.ts): the items at weight 500, the controls.
const ITEM_WIDTHS = [
  60.64, 110.23, 98.42, 53.42, 93.75, 95.16, 58.92, 67.73, 71.83, 72.05, 63.92, 66.61, 91.7,
];
const CONTROL_WIDTHS: Record<string, number> = {
  go: 67.84,
  firm: 140.58,
  "firm-short": 109.64,
  home: 30,
  support: 92.08,
  bell: 30,
  more: 69.98,
};

let barWidth = 1440;
const observers: (() => void)[] = [];

function widthOf(el: HTMLElement): number {
  const key = el.getAttribute("data-measure");
  if (key === null) return el.getAttribute("data-shell") === "toolbar" ? barWidth : 0;
  if (key.startsWith("item:")) return ITEM_WIDTHS[Number(key.slice(5))] ?? 0;
  return CONTROL_WIDTHS[key] ?? 0;
}

beforeEach(() => {
  installDomShims();
  observers.length = 0;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
    this: HTMLElement,
  ) {
    const width = widthOf(this);
    return {
      width,
      height: 0,
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: width,
      bottom: 0,
      toJSON: () => ({}),
    };
  });
  vi.stubGlobal(
    "ResizeObserver",
    class {
      constructor(callback: () => void) {
        observers.push(callback);
      }
      observe(): void {
        // The test calls the callback itself.
      }
      unobserve(): void {
        // See observe.
      }
      disconnect(): void {
        // See observe.
      }
    },
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function resize(width: number): void {
  barWidth = width;
  act(() => {
    for (const callback of observers) callback();
  });
}

function bar(): HTMLElement {
  return screen.getByRole("banner");
}

/** The nav's buttons by name (not the hidden measuring row, which is aria-hidden). */
function navLabels(): string[] {
  return within(screen.getByRole("navigation", { name: "Modules" }))
    .getAllByRole("button")
    .map((b) => b.textContent);
}

function renderToolbar(width: number, props: Partial<Parameters<typeof Toolbar>[0]> = {}): void {
  barWidth = width;
  render(<Toolbar nav={NAV} {...FIRM} active="Home" {...props} />);
}

// ---- Geometry ---------------------------------------------------------------------------------

describe("shell heights (Tier D: 46 / 42 / 59 / 46)", () => {
  const css = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), "..", "root.css"),
    "utf8",
  );
  const token = (name: string): string =>
    new RegExp(`--${name}:\\s*(\\d+)px`).exec(css)?.[1] ?? "missing";

  it("the geometry tokens are the plan's", () => {
    expect(token("toolbar-h")).toBe("46");
    expect(token("subbar-h")).toBe("42");
    expect(token("auditbar-h")).toBe("59");
    expect(token("pane-hd-h")).toBe("46");
    expect(token("tabs-h")).toBe("50");
    expect(token("tabs-h-compact")).toBe("44");
    expect(token("tabs-h-workbench")).toBe("60");
  });

  it("each part is built on its token", () => {
    renderToolbar(1440);
    expect(bar().className).toContain("h-(--toolbar-h)");
    cleanup();

    render(<RecordHeader title="A" />);
    expect(document.querySelector('[data-shell="record-header"]')?.className).toContain(
      "h-(--subbar-h)",
    );
    cleanup();

    render(<RecordHeader variant="audit" title="A" />);
    expect(document.querySelector('[data-shell="record-header"]')?.className).toContain(
      "h-(--auditbar-h)",
    );
    cleanup();

    render(<RecordHeader variant="close" title="A" periods={["2026-08"]} tabs={["Overview"]} />);
    expect(document.querySelector('[data-row="line"]')?.className).toContain("h-(--subbar-h)");
    expect(document.querySelector('[data-row="tabs"]')?.className).toContain("h-(--tabs-h)");
    cleanup();

    render(<RecordHeader variant="settings" title="A" />);
    expect(document.querySelector('[data-shell="record-header"]')?.className).toContain(
      "h-(--subbar-h)",
    );
    cleanup();

    render(<PaneHeader title="A" />);
    expect(document.querySelector('[data-shell="pane-header"]')?.className).toContain(
      "h-(--pane-hd-h)",
    );
  });

  it("the tabsbar is 50, 44 or 60", () => {
    for (const [size, token] of [
      ["default", "h-(--tabs-h)"],
      ["compact", "h-(--tabs-h-compact)"],
      ["workbench", "h-(--tabs-h-workbench)"],
    ] as const) {
      render(<Tabsbar size={size} label="Sections" options={["A", "B"]} />);
      expect(document.querySelector(`[data-size="${size}"]`)?.className).toContain(token);
      cleanup();
    }
  });

  it("the nav item is 32 high and the firm, Support and Go… pills 30", () => {
    renderToolbar(1440);
    const nav = within(screen.getByRole("navigation", { name: "Modules" }));
    expect(nav.getByRole("button", { name: "Engagements" }).className).toContain("h-[32px]");
    expect(screen.getByRole("button", { name: /Go to anything/ }).className).toContain("h-[30px]");
    expect(screen.getByRole("button", { name: "Brightwater Hale LLP" }).className).toContain(
      "h-[30px]",
    );
  });
});

// ---- Toolbar ----------------------------------------------------------------------------------

describe("Toolbar: DF-39 at 1440, 1400 and 1280", () => {
  it("at 1440 all 13 areas show, in the list's order, and nothing is given up", () => {
    renderToolbar(1440);
    expect(navLabels()).toEqual(guards.nav);
    expect(bar().getAttribute("data-stage")).toBe("none");
    expect(screen.getByRole("button", { name: "Brightwater Hale LLP" }).textContent).toBe(
      "Brightwater Hale",
    );
    expect(screen.queryByRole("button", { name: /^More/ })).toBeNull();
  });

  it("at 1400 the firm pill reads Brightwater (step 1), with the full name as its hint", () => {
    renderToolbar(1400);
    expect(bar().getAttribute("data-stage")).toBe("firm-short");
    const pill = screen.getByRole("button", { name: "Brightwater Hale LLP" });
    expect(pill.textContent).toBe("Brightwater");
    expect(pill.getAttribute("title")).toBe("Brightwater Hale LLP");
    expect(navLabels()).toEqual(guards.nav);
  });

  it("then Home becomes the house pill (step 2)", () => {
    renderToolbar(1360);
    expect(bar().getAttribute("data-stage")).toBe("home-pill");
    expect(navLabels()).toEqual(guards.nav.slice(1));
    const home = screen.getByRole("button", { name: "Home" });
    expect(home.getAttribute("aria-current")).toBe("page");
    expect(home.className).toContain("size-[30px]");
  });

  it("then Signatures moves into More (step 3)", () => {
    renderToolbar(1340);
    expect(bar().getAttribute("data-stage")).toBe("signatures");
    expect(navLabels()).toEqual([...guards.nav.slice(1, 12), "More"]);
  });

  it("at 1280 Signatures, Closes and Audits are in More (step 4), Notices is not", () => {
    renderToolbar(1280);
    expect(bar().getAttribute("data-stage")).toBe("signatures-closes-audits");
    expect(navLabels()).toEqual([...guards.nav.slice(1, 10), "More"]);
  });

  it("the More menu lists the rest in nav order, and the current page has the check", () => {
    const onNavigate = vi.fn();
    renderToolbar(1280, { active: "Closes", onNavigate });
    const more = screen.getByRole("button", { name: "More" });
    expect(more.getAttribute("data-current")).toBe("true");
    more.focus();
    fireEvent.keyDown(more, { key: "ArrowDown" });
    const menu = screen.getByRole("menu", { name: "More" });
    const rows = within(menu).getAllByRole("menuitemradio");
    expect(rows.map((r) => r.textContent)).toEqual(["Audits", "Closes", "Signatures"]);
    expect(rows.map((r) => r.getAttribute("aria-checked"))).toEqual(["false", "true", "false"]);
    fireEvent.click(rows[2] as HTMLElement);
    expect(onNavigate).toHaveBeenCalledWith("Signatures");
  });

  it("the More pill is quiet when the current page is on the bar", () => {
    renderToolbar(1280, { active: "Inbox" });
    expect(screen.getByRole("button", { name: "More" }).getAttribute("data-current")).toBeNull();
  });

  it("re-fits when the bar resizes: the steps come back in the other order as it widens", () => {
    renderToolbar(1280);
    expect(bar().getAttribute("data-stage")).toBe("signatures-closes-audits");
    resize(1340);
    expect(bar().getAttribute("data-stage")).toBe("signatures");
    resize(1360);
    expect(bar().getAttribute("data-stage")).toBe("home-pill");
    resize(1400);
    expect(bar().getAttribute("data-stage")).toBe("firm-short");
    resize(1440);
    expect(bar().getAttribute("data-stage")).toBe("none");
    expect(navLabels()).toEqual(guards.nav);
  });

  it("below 1280 trailing items leave one at a time, and Home stays reachable", () => {
    renderToolbar(1080);
    expect(bar().getAttribute("data-stage")).toBe("narrow");
    const labels = navLabels();
    expect(labels.at(-1)).toBe("More");
    expect(labels).toEqual([...guards.nav.slice(1, labels.length), "More"]);
    expect(screen.getByRole("button", { name: "Home" })).toBeTruthy();
  });

  it("draws every area in the app's list: it takes the items as props", () => {
    barWidth = 1500;
    render(<Toolbar nav={[{ label: "Alpha" }, { label: "Beta" }]} {...FIRM} />);
    expect(navLabels()).toEqual(["Alpha", "Beta"]);
  });

  it("holds a fallback step when a specimen names one", () => {
    renderToolbar(1500, { minFallback: "home-pill" });
    expect(bar().getAttribute("data-stage")).toBe("home-pill");
    expect(screen.getByRole("button", { name: "Home" })).toBeTruthy();
  });

  it("keeps everything with overflow none", () => {
    renderToolbar(900, { overflow: "none" });
    expect(navLabels()).toEqual(guards.nav);
  });

  it("measures before it fits: before any layout nothing is collapsed", () => {
    renderToolbar(0);
    expect(navLabels()).toEqual(guards.nav);
  });
});

describe("Toolbar: the nav never wraps and never shrinks its type", () => {
  it("every item is 13.5px (text-nav) on one line, at every width", () => {
    for (const width of [1500, 1440, 1400, 1360, 1340, 1280, 1080]) {
      renderToolbar(width);
      const nav = screen.getByRole("navigation", { name: "Modules" });
      for (const button of within(nav).getAllByRole("button")) {
        const c = button.className.split(/\s+/);
        expect(c, `${String(width)}: ${button.textContent}`).toContain("text-nav");
        expect(c).toContain("whitespace-nowrap");
        expect(c).toContain("flex-none");
        expect(c.some((x) => /^(text-(xs|sm|base)|scale-)/.test(x))).toBe(false);
      }
      expect(nav.className).not.toContain("flex-wrap");
      expect(nav.className).toContain("min-w-0");
      cleanup();
    }
  });

  it("a label holds its weight-500 width, so the active item moves nothing", () => {
    renderToolbar(1440, { active: "Files" });
    const label = within(screen.getByRole("navigation", { name: "Modules" })).getByRole("button", {
      name: "Files",
    }).firstElementChild as HTMLElement;
    expect(label.getAttribute("data-label")).toBe("Files");
    expect(label.className).toContain("after:font-medium");
    expect(label.className).toContain("after:content-[attr(data-label)]");
  });

  it("measures each item at weight 500 in a hidden row", () => {
    renderToolbar(1440);
    const row = bar().querySelector("[data-measuring]") as HTMLElement;
    expect(row.getAttribute("aria-hidden")).toBe("true");
    const items = [...row.querySelectorAll<HTMLElement>('[data-measure^="item:"]')];
    expect(items.map((i) => i.textContent)).toEqual(guards.nav);
    for (const item of items) expect(item.className).toContain("font-medium");
  });
});

describe("Toolbar: controls", () => {
  it("names the active area with aria-current, and none in the settings context", () => {
    renderToolbar(1440, { active: "Audits" });
    expect(
      within(screen.getByRole("navigation", { name: "Modules" }))
        .getAllByRole("button")
        .filter((b) => b.getAttribute("aria-current") === "page")
        .map((b) => b.textContent),
    ).toEqual(["Audits"]);
    cleanup();
    renderToolbar(1440, { active: "", firmPressed: true });
    expect(document.querySelector('[aria-current="page"]')).toBeNull();
    expect(
      screen.getByRole("button", { name: "Brightwater Hale LLP" }).getAttribute("data-pressed"),
    ).toBe("true");
  });

  it("nav items are text only: no icon, no count", () => {
    renderToolbar(1440);
    const nav = screen.getByRole("navigation", { name: "Modules" });
    expect(nav.querySelector("svg")).toBeNull();
    expect(nav.textContent).toBe(guards.nav.join(""));
  });

  it("the bell shows a dot and never a number, and says so", () => {
    renderToolbar(1440);
    const bell = screen.getByRole("button", { name: "Notifications, unread" });
    expect(bell.querySelector('[data-dot="unread"]')).not.toBeNull();
    expect(bell.textContent).toBe("");
    cleanup();
    renderToolbar(1440, { unread: false });
    expect(
      screen.getByRole("button", { name: "Notifications" }).querySelector("[data-dot]"),
    ).toBeNull();
  });

  it("calls the handlers", () => {
    const h = {
      onGo: vi.fn(),
      onNavigate: vi.fn(),
      onSupport: vi.fn(),
      onBell: vi.fn(),
      onFirm: vi.fn(),
    };
    renderToolbar(1440, h);
    fireEvent.click(screen.getByRole("button", { name: /Go to anything/ }));
    fireEvent.click(screen.getByRole("button", { name: "Inbox" }));
    fireEvent.click(screen.getByRole("button", { name: "Support" }));
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.click(screen.getByRole("button", { name: "Brightwater Hale LLP" }));
    expect(h.onGo).toHaveBeenCalledOnce();
    expect(h.onNavigate).toHaveBeenCalledWith("Inbox");
    expect(h.onSupport).toHaveBeenCalledOnce();
    expect(h.onBell).toHaveBeenCalledOnce();
    expect(h.onFirm).toHaveBeenCalledOnce();
  });

  it("carries no Accrued name or mark: the firm chrome is brand-free", () => {
    renderToolbar(1440);
    expect(bar().textContent).not.toMatch(/accrued/i);
    expect(bar().querySelector("[data-brand]")).toBeNull();
  });

  it("holds the Go… tooltip open for a specimen, with the other ways in", () => {
    renderToolbar(1440, { forceState: { goTip: true } });
    const tip = screen.getByRole("tooltip");
    expect(tip.textContent).toContain("Go to anything");
    expect(tip.textContent).toContain("⌘K");
    expect(tip.textContent).toContain("Also: New to-do… · Load saved prompt… · Open board");
  });

  it("holds a nav item hovered or focused for a specimen", () => {
    renderToolbar(1440, { forceState: { nav: { label: "Inbox", state: "focus" } } });
    expect(screen.getByRole("button", { name: "Inbox" }).getAttribute("data-force")).toBe("focus");
  });
});

// ---- RecordHeader -----------------------------------------------------------------------------

describe("RecordHeader", () => {
  it("default: Checkpoints, the sync chip, the title block centred, Assistant", () => {
    render(
      <RecordHeader
        title="2025 Form 1065"
        context="Ridgeline Property Partners, LP"
        state="Working"
        syncDate="Sep 10"
      />,
    );
    expect(screen.getByRole("button", { name: "Checkpoints" })).toBeTruthy();
    expect(screen.getByText("Synced Sep 10")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Assistant" })).toBeTruthy();
    const title = screen.getByText("2025 Form 1065");
    const centre = title.parentElement as HTMLElement;
    expect(centre.className).toContain("absolute");
    expect(centre.className).toContain("left-1/2");
    expect(centre.className).toContain("-translate-x-1/2");
    expect(title.className).toContain("font-medium");
    expect(within(centre).getByText("Ridgeline Property Partners, LP").className).toContain(
      "text-ink-2",
    );
    expect(within(centre).getByText("Working").className).toContain("bg-amber-tint");
  });

  it("splits the context on ' · ' into ink-2 runs with ink-4 separators", () => {
    render(
      <RecordHeader variant="audit" title="PY2025 Plan Audit" context="Methodology · EBP v3" />,
    );
    expect(screen.getByText("Methodology").className).toContain("text-ink-2");
    expect(screen.getByText("EBP v3").className).toContain("text-ink-2");
    const dot = screen.getByText("·");
    expect(dot.className).toContain("text-ink-4");
    expect(dot.getAttribute("aria-hidden")).toBe("true");
  });

  it("shows all seven sync states, each the same white chip", () => {
    const codes = [
      ["not_yet_exported", "Not yet exported"],
      ["ready_for_export", "Ready for export"],
      ["exporting", "Exporting…"],
      ["synced", "Synced Sep 10"],
      ["out_of_sync", "Out of sync"],
      ["import_pending_approval", "Import pending approval"],
      ["failed", "Export failed"],
    ] as const;
    for (const [code, label] of codes) {
      render(<RecordHeader title="T" sync={code} syncDate="Sep 10" />);
      const chip = screen.getByText(label).closest("[data-code]") as HTMLElement;
      expect(chip.getAttribute("data-code")).toBe(code);
      expect(chip.className).toContain("bg-card");
      expect(chip.className).not.toContain("green-tint");
      cleanup();
    }
  });

  it("hides what is switched off, and a slot replaces the cluster", () => {
    render(<RecordHeader title="T" checkpoints={false} sync={null} assistant={false} />);
    expect(screen.queryByRole("button")).toBeNull();
    cleanup();
    render(<RecordHeader title="T" left={<span>Mine</span>} right={<span>Yours</span>} />);
    expect(screen.getByText("Mine")).toBeTruthy();
    expect(screen.getByText("Yours")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Checkpoints" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Assistant" })).toBeNull();
  });

  it("Checkpoints reads as pressed while its drawer is open", () => {
    render(<RecordHeader title="T" checkpointsPressed />);
    expect(screen.getByRole("button", { name: "Checkpoints" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
  });

  it("audit: the back chip, meta, and the Auto mode switch that slides", () => {
    const onAutoMode = vi.fn();
    const onBack = vi.fn();
    render(
      <RecordHeader
        variant="audit"
        title="PY2025 Plan Audit"
        meta="Started 9:24 AM"
        onAutoMode={onAutoMode}
        onBack={onBack}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "All Audits" }));
    expect(onBack).toHaveBeenCalledOnce();
    expect(screen.getByText("Started 9:24 AM")).toBeTruthy();
    const toggle = screen.getByRole("switch", { name: "Auto mode" });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(toggle.className).toContain("h-[21px]");
    expect(toggle.className).toContain("w-[36px]");
    expect((toggle.firstElementChild as HTMLElement).className).toContain("left-[17px]");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect((toggle.firstElementChild as HTMLElement).className).toContain("left-[2px]");
    expect(onAutoMode).toHaveBeenCalledWith(false);
    expect(screen.getByRole("button", { name: "Layout" })).toBeTruthy();
  });

  it("close: the period steps back and wraps, and the tabs follow it", () => {
    const onPeriod = vi.fn<(period: string) => void>();
    const onTab = vi.fn();
    render(
      <RecordHeader
        variant="close"
        title="Copperleaf Coffee Roasters, Inc."
        periods={["2026-06", "2026-07", "2026-08"]}
        tabs={["Overview", "Intake", { label: "Review", count: 9, bad: true }]}
        activeTab="Overview"
        onPeriod={onPeriod}
        onTab={onTab}
      />,
    );
    expect(screen.getByText("Close")).toBeTruthy();
    const stepper = screen.getByTitle("Change period");
    expect(stepper.textContent).toBe("2026-08");
    fireEvent.click(stepper);
    expect(stepper.textContent).toBe("2026-07");
    fireEvent.click(stepper);
    fireEvent.click(stepper);
    expect(stepper.textContent).toBe("2026-08");
    expect(onPeriod.mock.calls.map(([period]) => period)).toEqual([
      "2026-07",
      "2026-06",
      "2026-08",
    ]);
    fireEvent.click(screen.getByRole("tab", { name: /Intake/ }));
    expect(onTab).toHaveBeenCalledWith("Intake");
    expect(screen.getByRole("button", { name: "Back" })).toBeTruthy();
    // No sync chip, Checkpoints or Assistant in this variant.
    expect(screen.queryByRole("button", { name: "Assistant" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Checkpoints" })).toBeNull();
  });

  it("settings: Back, the centred title, and a slot on the right", () => {
    const onBack = vi.fn();
    render(
      <RecordHeader
        variant="settings"
        title="Firm settings"
        context="Brightwater Hale LLP"
        onBack={onBack}
        right={<span>Unsaved changes</span>}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledOnce();
    expect(screen.getByText("Firm settings")).toBeTruthy();
    expect(screen.getByText("Unsaved changes")).toBeTruthy();
  });
});

// ---- Tabsbar ----------------------------------------------------------------------------------

describe("Tabsbar", () => {
  it("holds a centred Segmented and fires once per change", () => {
    const onChange = vi.fn();
    render(
      <Tabsbar
        label="Return"
        options={["Overview", { label: "Review", count: 38 }]}
        active="Overview"
        onChange={onChange}
      />,
    );
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(2);
    fireEvent.click(tabs[0] as HTMLElement);
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(tabs[1] as HTMLElement);
    expect(onChange).toHaveBeenCalledExactlyOnceWith("Review");
  });

  it("pins the view toggle at the right only when asked", () => {
    const onView = vi.fn();
    const { rerender } = render(<Tabsbar label="Return" options={["A", "B"]} />);
    expect(screen.queryByRole("button", { name: /View/ })).toBeNull();
    rerender(<Tabsbar label="Return" options={["A", "B"]} view={{ view: "grid", onView }} />);
    const toggle = screen.getByRole("button", { name: "View: Grid" });
    expect((toggle.parentElement as HTMLElement).className).toContain("right-(--edge-app)");
  });
});

// ---- Pane and PaneHeader ----------------------------------------------------------------------

describe("Pane and PaneHeader", () => {
  it("a pane is white, radius 12, e2, and its body scrolls", () => {
    render(<Pane title="Overview">body</Pane>);
    const pane = screen.getByRole("region", { name: "Overview" });
    expect(pane.className).toContain("pane");
    expect(pane.className).toContain("overflow-hidden");
    expect(pane.className).toContain("flex-[1_1_0%]");
    expect(screen.getByText("body").className).toContain("overflow-auto");
  });

  it("a number is a fixed width that does not flex", () => {
    render(<Pane width={330} title="Rail" />);
    const pane = screen.getByRole("region", { name: "Rail" });
    expect(pane.style.width).toBe("330px");
    expect(pane.className).toContain("flex-none");
  });

  it("a well puts the shell colour behind the body, and header false hides the header", () => {
    render(
      <Pane well header={false}>
        doc
      </Pane>,
    );
    expect(screen.getByText("doc").className).toContain("bg-shell");
    expect(document.querySelector('[data-shell="pane-header"]')).toBeNull();
  });

  it("the title is 14.5 / 500, centred by default, and left-aligned on request", () => {
    const { rerender } = render(<PaneHeader title="Sessions" />);
    const centred = screen.getByText("Sessions");
    expect(centred.className).toContain("text-pane");
    expect(centred.className).toContain("font-medium");
    expect(centred.className).toContain("-translate-x-1/2");
    rerender(<PaneHeader title="Sessions" titleAlign="left" />);
    const left = screen.getByText("Sessions");
    expect(left.className).toContain("flex-1");
    expect(left.className).not.toContain("absolute");
  });

  it("a centred title stays clear of the wider cluster: pane less twice (cluster + 16)", () => {
    // The clusters are the wrappers the header makes; give them the widths a browser would.
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(function (
      this: HTMLElement,
    ) {
      return this.textContent === "Draft" ? 190 : this.textContent === "All" ? 60 : 0;
    });
    render(
      <PaneHeader
        title="A long pane title"
        left={<PaneAction kind="meta" label="All" />}
        right={<PaneAction kind="meta" label="Draft" />}
      />,
    );
    expect(screen.getByText("A long pane title").style.maxWidth).toBe("calc(100% - 412px)");
  });

  it("with no actions the title keeps 16px each side", () => {
    render(<PaneHeader title="Overview" />);
    expect(screen.getByText("Overview").style.maxWidth).toBe("calc(100% - 32px)");
  });

  it("draws the five action kinds", () => {
    render(
      <PaneHeader
        title="T"
        left={<PaneAction kind="picker" label="All" />}
        right={
          <>
            <PaneAction kind="icon" icon="download" label="Download" />
            <PaneAction kind="round" icon="plus" label="New session…" opensDialog />
            <PaneAction icon="pencil" label="Edit" />
            <PaneAction kind="meta" label="Draft" />
          </>
        }
      />,
    );
    const download = screen.getByRole("button", { name: "Download" });
    expect(download.getAttribute("data-variant")).toBe("white");
    expect(download.className).toContain("size-[28px]");
    const round = screen.getByRole("button", { name: "New session…" });
    expect(round.getAttribute("data-variant")).toBe("dark");
    expect(round.className).toContain("size-[29px]");
    const pill = screen.getByRole("button", { name: "Edit" });
    expect(pill.getAttribute("data-size")).toBe("sm");
    expect(pill.className).toContain("h-[28px]");
    expect(screen.getByRole("button", { name: "All" }).className).toContain("h-[28px]");
    expect(screen.getByText("Draft").tagName).toBe("SPAN");
  });

  it("a label that opens a dialog ends with …", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<PaneAction label="Sign off" opensDialog />)).toThrow(/…/);
    error.mockRestore();
  });

  it("the footer: Cancel, a spacer, Save draft, Send, 30 high", () => {
    const onSend = vi.fn();
    render(
      <Pane
        title="Request documents"
        footer={
          <>
            <FooterAction kind="ghost">Cancel</FooterAction>
            <FooterSpacer />
            <FooterAction>Save draft</FooterAction>
            <FooterAction kind="primary" onClick={onSend}>
              Send
            </FooterAction>
          </>
        }
      />,
    );
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Cancel", "Save draft", "Send"]);
    expect(buttons.map((b) => b.getAttribute("data-variant"))).toEqual([
      "ghost",
      "secondary",
      "primary",
    ]);
    for (const b of buttons) expect(b.className).toContain("h-[30px]");
    fireEvent.click(buttons[2] as HTMLElement);
    expect(onSend).toHaveBeenCalledOnce();
    const kinds = ["destructive"] as const;
    cleanup();
    render(<FooterAction kind={kinds[0]}>Remove</FooterAction>);
    expect(screen.getByRole("button", { name: "Remove" }).getAttribute("data-variant")).toBe(
      "destructive",
    );
  });
});

// ---- Timeline ---------------------------------------------------------------------------------

describe("Timeline", () => {
  it("is one card: a date, a disc with a line down to the next row, then the text", () => {
    render(
      <Timeline
        label="Activity"
        events={[
          {
            id: "a",
            date: "Sep 14",
            state: "done",
            title: "Return prepared",
            detail: "Form 1065",
          },
          { id: "b", date: "Sep 12", state: "half", title: "Documents received" },
          { id: "c", date: "Sep 8", state: "wait", title: "Request sent" },
        ]}
      />,
    );
    const list = screen.getByRole("list", { name: "Activity" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]?.className).toContain("grid-cols-[76px_20px_minmax(0,1fr)]");
    expect(rows.map((r) => r.querySelector("i") !== null)).toEqual([true, true, false]);
    expect(within(rows[0] as HTMLElement).getByText("Sep 14").className).toContain("text-right");
    expect(within(rows[0] as HTMLElement).getByText("Return prepared").className).toContain(
      "font-medium",
    );
    expect(within(rows[0] as HTMLElement).getByText("Form 1065").className).toContain(
      "text-ink-2",
    );
    // A disc is always beside words: it has a name of its own.
    expect(
      within(rows[0] as HTMLElement)
        .getByRole("img")
        .getAttribute("aria-label"),
    ).toBeTruthy();
  });
});

// ---- PortalToolbar ----------------------------------------------------------------------------

const PORTAL_NAV = [
  { label: "Home", icon: "house" },
  { label: "Documents", icon: "file-text" },
  { label: "Messages", icon: "message-circle", count: 1 },
] as const;

describe("PortalToolbar", () => {
  it("shows the firm's mark and name, icon-and-word nav with a count, and the user chip", () => {
    const onNavigate = vi.fn();
    render(
      <PortalToolbar
        firm="Brightwater Hale"
        user="Jonah Feld"
        nav={PORTAL_NAV}
        active="Documents"
        onNavigate={onNavigate}
      />,
    );
    expect(screen.getByRole("img", { name: "Brightwater Hale" })).toBeTruthy();
    expect(screen.getByText("Brightwater Hale").className).toContain("text-brand");
    const nav = within(screen.getByRole("navigation", { name: "Portal" }));
    expect(nav.getByRole("button", { name: /Documents/ }).getAttribute("aria-current")).toBe(
      "page",
    );
    expect(nav.getByRole("button", { name: /Messages/ }).textContent).toContain("1");
    expect(nav.getAllByRole("button").every((b) => b.querySelector("svg") !== null)).toBe(true);
    fireEvent.click(nav.getByRole("button", { name: /Home/ }));
    expect(onNavigate).toHaveBeenCalledWith("Home");
    expect(screen.getByRole("button", { name: "Jonah Feld" })).toBeTruthy();
  });

  it("has no Go…, Support or bell, and never shows the Accrued name or mark", () => {
    render(<PortalToolbar firm="Brightwater Hale" user="Jonah Feld" nav={PORTAL_NAV} />);
    expect(screen.queryByRole("button", { name: /Go to anything/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Support" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Notifications/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/accrued/i);
    expect(document.querySelector('[data-brand="wordmark"]')).toBeNull();
  });

  it("takes the items it is given: an individual client's nav has no Approvals", () => {
    render(<PortalToolbar firm="Feld Tax" user="Jonah Feld" nav={PORTAL_NAV} />);
    expect(screen.queryByRole("button", { name: /Approvals/ })).toBeNull();
  });
});

// ---- AppShell ---------------------------------------------------------------------------------

describe("AppShell", () => {
  it("stacks the toolbar, record header, tabsbar and the body row of panes, in that order", () => {
    barWidth = 1440;
    render(
      <AppShell
        toolbar={{ nav: NAV, ...FIRM, active: "Audits" }}
        record={<RecordHeader variant="audit" title="PY2025 Plan Audit" />}
        tabs={<Tabsbar label="Audit" options={["Overview", "Issues"]} />}
      >
        <Pane width={330} title="Rail" />
        <Pane title="Main" />
      </AppShell>,
    );
    const shell = document.querySelector('[data-shell="app"]') as HTMLElement;
    expect([...shell.children].map((c) => c.getAttribute("data-shell"))).toEqual([
      "toolbar",
      "record-header",
      "tabsbar",
      "cols",
    ]);
    const cols = shell.querySelector('[data-shell="cols"]') as HTMLElement;
    expect(cols.className).toContain("gap-(--gutter-pane)");
    expect(cols.className).toContain("px-(--edge-app)");
    expect(cols.className).toContain("pt-(--gutter-pane)");
    expect(cols.className).toContain("pb-(--edge-app)");
    expect(cols.className).toContain("min-h-0");
    expect(cols.className).toContain("flex-1");
    expect(within(cols).getAllByRole("region")).toHaveLength(2);
  });

  it("fills the viewport and never scrolls as a page (panes' bodies do), firm minimum 1280", () => {
    barWidth = 1440;
    render(<AppShell toolbar={{ nav: NAV, ...FIRM }} />);
    const shell = document.querySelector('[data-shell="app"]') as HTMLElement;
    expect(shell.className).toContain("h-dvh");
    expect(shell.className).toContain("min-w-[1280px]");
    expect(shell.className).toContain("bg-shell");
  });

  it("is framed only on request: 1400 wide, radius 16, on the presentation ground", () => {
    barWidth = 1400;
    render(<AppShell frame height={860} toolbar={{ nav: NAV, ...FIRM }} />);
    const shell = document.querySelector('[data-shell="app"]') as HTMLElement;
    expect(shell.getAttribute("data-frame")).toBe("framed");
    expect(shell.className).toContain("w-(--app-w)");
    expect(shell.className).toContain("rounded-window");
    expect(shell.style.height).toBe("860px");
    const stage = document.querySelector('[data-shell="stage"]') as HTMLElement;
    expect(stage.className).toContain("bg-presentation");
    expect(stage.className).toContain("p-[40px]");
    cleanup();
    render(<AppShell embedded toolbar={{ nav: NAV, ...FIRM }} />);
    const embedded = document.querySelector('[data-shell="stage"]') as HTMLElement;
    expect(embedded.className).not.toContain("bg-presentation");
    expect(embedded.className).toContain("min-h-[600px]");
  });

  it("opens Go… on Ctrl K and Cmd K in the firm shell, and not on a bare K", () => {
    const onGo = vi.fn();
    barWidth = 1440;
    render(<AppShell toolbar={{ nav: NAV, ...FIRM, onGo }} />);
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    fireEvent.keyDown(document, { key: "K", metaKey: true });
    fireEvent.keyDown(document, { key: "k" });
    expect(onGo).toHaveBeenCalledTimes(2);
  });

  it("never opens the palette from the keyboard in the portal", () => {
    const onUser = vi.fn();
    render(
      <AppShell
        variant="portal"
        toolbar={{ firm: "Brightwater Hale", user: "Jonah Feld", nav: PORTAL_NAV, onUser }}
      />,
    );
    const prevented = !fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(prevented).toBe(false);
    expect(screen.queryByRole("button", { name: /Go to anything/ })).toBeNull();
  });

  it("draws an overlay over the shell: the command palette's slot", () => {
    barWidth = 1440;
    render(
      <AppShell toolbar={{ nav: NAV, ...FIRM }} overlay={<div role="dialog">Palette</div>} />,
    );
    const shell = document.querySelector('[data-shell="app"]') as HTMLElement;
    expect(shell.className).toContain("relative");
    expect(within(shell).getByRole("dialog").textContent).toBe("Palette");
  });

  it("portal: the portal toolbar, no firm chrome, and the footer only when the firm turns it on", () => {
    const toolbar = { firm: "Brightwater Hale", user: "Jonah Feld", nav: PORTAL_NAV };
    const { rerender } = render(<AppShell variant="portal" toolbar={toolbar} />);
    expect(document.querySelector('[data-shell="portal-toolbar"]')).not.toBeNull();
    expect(document.querySelector('[data-shell="toolbar"]')).toBeNull();
    expect(document.querySelector('[data-shell="app"]')?.className).not.toContain(
      "min-w-[1280px]",
    );
    expect(document.querySelector('[data-shell="portal-footer"]')).toBeNull();
    expect(document.body.textContent).not.toMatch(/accrued/i);
    rerender(<AppShell variant="portal" securedFooter toolbar={toolbar} />);
    const footer = document.querySelector('[data-shell="portal-footer"]') as HTMLElement;
    expect(footer.textContent).toContain("Secured by");
    expect(within(footer).getByRole("img", { name: "Accrued" })).toBeTruthy();
    expect(footer.className).toContain("h-[34px]");
  });
});
