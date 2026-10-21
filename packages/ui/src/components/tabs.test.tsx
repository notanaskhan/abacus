// F-05-T15 (C-05 Tabs kit): Segmented, SegmentedGroup, UnderlineTabs, SheetTabs and ViewToggle.
// The keyboard model is the plan's: roving tabindex, arrows that move and select and wrap,
// disabled options skipped, Home and End; the selected option switches in place; onChange fires
// once per change; an external `active` resets the selection.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import {
  DEFAULT_VIEWS,
  MAX_OPTIONS_PER_TRACK,
  Segmented,
  SegmentedGroup,
  SheetTabs,
  UnderlineTabs,
  ViewToggle,
  nextTab,
  type Opt,
} from "./tabs";

beforeAll(installDomShims);
afterEach(cleanup);

function classes(element: HTMLElement): string[] {
  return element.className.split(/\s+/);
}

const RETURN: Opt[] = [
  "Overview",
  { label: "Intake", count: 7 },
  { label: "Review", count: 38 },
  { label: "Issues", count: 16, bad: true },
  "Activity",
];

function tab(name: string | RegExp): HTMLElement {
  return screen.getByRole("tab", { name });
}

describe("nextTab", () => {
  const none = [false, false, false, false];

  it("moves with the arrows and wraps past both ends", () => {
    expect(nextTab("ArrowRight", 1, none)).toBe(2);
    expect(nextTab("ArrowRight", 3, none)).toBe(0);
    expect(nextTab("ArrowLeft", 0, none)).toBe(3);
    expect(nextTab("ArrowDown", 3, none)).toBe(0);
    expect(nextTab("ArrowUp", 0, none)).toBe(3);
  });

  it("skips disabled options in both directions and when wrapping", () => {
    const disabled = [false, true, true, false];
    expect(nextTab("ArrowRight", 0, disabled)).toBe(3);
    expect(nextTab("ArrowLeft", 3, disabled)).toBe(0);
    expect(nextTab("ArrowRight", 3, [true, false, false, true])).toBe(1);
  });

  it("jumps to the first and last enabled option with Home and End", () => {
    const disabled = [true, false, false, true];
    expect(nextTab("Home", 2, disabled)).toBe(1);
    expect(nextTab("End", 1, disabled)).toBe(2);
  });

  it("answers -1 for a key it does not own and when nothing is enabled", () => {
    expect(nextTab("a", 0, none)).toBe(-1);
    expect(nextTab("Tab", 0, none)).toBe(-1);
    expect(nextTab("ArrowRight", 0, [true, true])).toBe(-1);
    expect(nextTab("Home", 0, [true, true])).toBe(-1);
    expect(nextTab("End", 0, [])).toBe(-1);
  });
});

describe("Segmented", () => {
  it("is a tablist named by its label, with one tab per option", () => {
    render(<Segmented label="Return" options={RETURN} active="Overview" />);
    const list = screen.getByRole("tablist", { name: "Return" });
    expect(within(list).getAllByRole("tab")).toHaveLength(5);
    expect(tab(/Overview/).getAttribute("aria-selected")).toBe("true");
    expect(tab(/Activity/).getAttribute("aria-selected")).toBe("false");
  });

  it("keeps only the selected tab in the tab order (roving tabindex)", () => {
    render(<Segmented label="Return" options={RETURN} active="Review" />);
    const indexes = screen.getAllByRole("tab").map((t) => t.getAttribute("tabindex"));
    expect(indexes).toEqual(["-1", "-1", "0", "-1", "-1"]);
  });

  it("puts the first enabled tab in the tab order when none is selected", () => {
    render(<Segmented label="Return" options={["A", "B"]} />);
    expect(tab("A").getAttribute("tabindex")).toBe("0");
    expect(tab("B").getAttribute("tabindex")).toBe("-1");
  });

  it("wraps with the arrow keys: past the last option to the first, and back", () => {
    const onChange = vi.fn();
    render(<Segmented label="Return" options={RETURN} active="Activity" onChange={onChange} />);
    fireEvent.keyDown(tab(/Activity/), { key: "ArrowRight" });
    expect(tab(/Overview/).getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tab(/Overview/));
    expect(onChange).toHaveBeenLastCalledWith("Overview");
    fireEvent.keyDown(tab(/Overview/), { key: "ArrowLeft" });
    expect(tab(/Activity/).getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tab(/Activity/));
    expect(onChange).toHaveBeenLastCalledWith("Activity");
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it("moves with all four arrows, selecting as it goes", () => {
    render(<Segmented label="Return" options={RETURN} active="Overview" />);
    fireEvent.keyDown(tab(/Overview/), { key: "ArrowDown" });
    expect(tab(/Intake/).getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab(/Intake/), { key: "ArrowRight" });
    expect(tab(/Review/).getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab(/Review/), { key: "ArrowUp" });
    expect(tab(/Intake/).getAttribute("aria-selected")).toBe("true");
  });

  it("skips a disabled option and never selects it", () => {
    const onChange = vi.fn();
    render(
      <Segmented
        label="Close"
        options={["Overview", { label: "Accounts", disabled: true }, "Review"]}
        active="Overview"
        onChange={onChange}
      />,
    );
    fireEvent.keyDown(tab("Overview"), { key: "ArrowRight" });
    expect(tab("Review").getAttribute("aria-selected")).toBe("true");
    expect(onChange).toHaveBeenCalledWith("Review");
    const disabled = tab("Accounts");
    expect((disabled as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(disabled);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("jumps with Home and End", () => {
    render(<Segmented label="Return" options={RETURN} active="Review" />);
    fireEvent.keyDown(tab(/Review/), { key: "End" });
    expect(tab(/Activity/).getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab(/Activity/), { key: "Home" });
    expect(tab(/Overview/).getAttribute("aria-selected")).toBe("true");
  });

  it("ignores a key it does not own and lets Tab through", () => {
    const onChange = vi.fn();
    render(<Segmented label="Return" options={RETURN} active="Overview" onChange={onChange} />);
    expect(fireEvent.keyDown(tab(/Overview/), { key: "Tab" })).toBe(true);
    expect(fireEvent.keyDown(tab(/Overview/), { key: "x" })).toBe(true);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("fires onChange once per change, and not for the tab already selected", () => {
    const onChange = vi.fn();
    render(<Segmented label="Return" options={RETURN} active="Overview" onChange={onChange} />);
    fireEvent.click(tab(/Overview/));
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(tab(/Review/));
    fireEvent.click(tab(/Review/));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("Review");
  });

  it("resets its selection when `active` changes from outside", () => {
    const { rerender } = render(<Segmented label="Return" options={RETURN} active="Overview" />);
    fireEvent.click(tab(/Review/));
    expect(tab(/Review/).getAttribute("aria-selected")).toBe("true");
    rerender(<Segmented label="Return" options={RETURN} active="Activity" />);
    expect(tab(/Activity/).getAttribute("aria-selected")).toBe("true");
    expect(tab(/Review/).getAttribute("aria-selected")).toBe("false");
  });

  it("switches in place: the selected option is white and lifted, and nothing slides", () => {
    const { container } = render(<Segmented label="Return" options={RETURN} active="Intake" />);
    expect(classes(tab(/Intake/))).toEqual(
      expect.arrayContaining(["bg-card", "font-medium", "text-ink", "shadow-e1"]),
    );
    expect(classes(tab(/Overview/))).toEqual(
      expect.arrayContaining(["text-ink-2", "font-normal"]),
    );
    // Only the options are drawn: no indicator element, no translate or motion class.
    expect(container.querySelector("[role=tablist]")?.children).toHaveLength(5);
    expect(container.innerHTML).not.toMatch(/translate|motion-|animate-/);
  });

  it("draws a pill track of 4px padding, 2px gap on nav-fill, with 30px options", () => {
    render(<Segmented label="Return" options={RETURN} active="Intake" />);
    const track = screen.getByRole("tablist");
    expect(classes(track)).toEqual(
      expect.arrayContaining(["rounded-pill", "bg-nav-fill", "gap-[2px]", "p-[4px]"]),
    );
    expect(classes(tab(/Overview/))).toEqual(
      expect.arrayContaining(["h-[30px]", "px-[16px]", "rounded-pill", "text-tab"]),
    );
  });

  it("draws the small size: 3px track padding, 28px options", () => {
    render(<Segmented label="Pane" size="small" options={["By partner", "By movement"]} />);
    expect(classes(screen.getByRole("tablist"))).toContain("p-[3px]");
    expect(classes(tab("By partner"))).toEqual(
      expect.arrayContaining(["h-[28px]", "px-[13px]", "text-btn"]),
    );
  });

  it("tightens the right padding of an option with a count", () => {
    render(<Segmented label="Return" options={RETURN} active="Overview" />);
    expect(classes(tab(/Intake/))).toContain("pr-[10px]");
    expect(classes(tab("Overview"))).not.toContain("pr-[10px]");
  });

  it("draws a count badge, red for a bad count", () => {
    render(<Segmented label="Return" options={RETURN} active="Overview" />);
    const plain = within(tab(/Intake/)).getByText("7");
    const bad = within(tab(/Issues/)).getByText("16");
    expect(plain.dataset["tone"]).toBe("segment");
    expect(bad.dataset["tone"]).toBe("bad");
    expect(classes(bad)).toEqual(expect.arrayContaining(["bg-red-tint", "text-red-ink"]));
  });

  it("holds a forced state on one option without a pointer", () => {
    render(
      <Segmented
        label="Return"
        options={RETURN}
        active="Overview"
        forceState="hover"
        forceOn="Review"
      />,
    );
    expect(tab(/Review/).dataset["force"]).toBe("hover");
    expect(tab(/Intake/).dataset["force"]).toBeUndefined();
  });

  it("holds focus on the selected option by default, hover on the first other", () => {
    const { rerender } = render(
      <Segmented label="Return" options={RETURN} active="Overview" forceState="focus" />,
    );
    expect(tab(/Overview/).dataset["force"]).toBe("focus");
    rerender(<Segmented label="Return" options={RETURN} active="Overview" forceState="hover" />);
    expect(tab(/Intake/).dataset["force"]).toBe("hover");
  });

  it("presses to .985 on every option, and takes no animation of its own", () => {
    render(<Segmented label="Return" options={RETURN} active="Overview" />);
    expect(classes(tab(/Intake/))).toEqual(
      expect.arrayContaining(["press", "active:pressed", "data-[force=pressed]:pressed"]),
    );
  });

  it("refuses more than seven options in a track", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const eight = ["A", "B", "C", "D", "E", "F", "G", "H"];
    expect(MAX_OPTIONS_PER_TRACK).toBe(7);
    expect(() => render(<Segmented label="Too many" options={eight} />)).toThrow(/at most 7/);
    expect(() => render(<Segmented label="Seven" options={eight.slice(0, 7)} />)).not.toThrow();
    spy.mockRestore();
  });

  it("links a tab to its panel with aria-controls", () => {
    render(
      <Segmented
        label="Return"
        options={[{ label: "Overview", controls: "panel-1" }, "Intake"]}
      />,
    );
    expect(tab("Overview").getAttribute("aria-controls")).toBe("panel-1");
    expect(tab("Intake").hasAttribute("aria-controls")).toBe(false);
  });
});

describe("SegmentedGroup", () => {
  const SUB = {
    Workpaper: {
      options: ["Summary", "Financials", "Fixed Assets"],
    },
    Review: { options: ["Notes", "Sign-off"], active: "Sign-off" },
  };
  const FIRST: Opt[] = ["Agent", { label: "Issues", count: 16, bad: true }, "Workpaper", "Review"];

  it("draws two tracks 8px apart, the second only for an item with sub options", () => {
    const { container } = render(
      <SegmentedGroup label="Return" options={FIRST} active="Workpaper" sub={SUB} />,
    );
    expect(screen.getAllByRole("tablist")).toHaveLength(2);
    expect(container.firstElementChild?.className).toContain("gap-[8px]");
    expect(screen.getByRole("tablist", { name: "Return: Workpaper" })).toBeTruthy();
    expect(tab("Summary").getAttribute("aria-selected")).toBe("true");
  });

  it("hides the second track while the selected item has none", () => {
    render(<SegmentedGroup label="Return" options={FIRST} active="Agent" sub={SUB} />);
    expect(screen.getAllByRole("tablist")).toHaveLength(1);
  });

  it("follows the first track: selecting an item swaps the sub-track", () => {
    render(<SegmentedGroup label="Return" options={FIRST} active="Agent" sub={SUB} />);
    fireEvent.click(tab("Workpaper"));
    expect(screen.getByRole("tablist", { name: "Return: Workpaper" })).toBeTruthy();
    fireEvent.click(tab("Review"));
    expect(screen.queryByRole("tab", { name: "Summary" })).toBeNull();
    expect(tab("Sign-off").getAttribute("aria-selected")).toBe("true");
  });

  it("reports (item, section) from either track", () => {
    const onChange = vi.fn();
    render(
      <SegmentedGroup
        label="Return"
        options={FIRST}
        active="Agent"
        sub={SUB}
        onChange={onChange}
      />,
    );
    fireEvent.click(tab("Workpaper"));
    expect(onChange).toHaveBeenLastCalledWith("Workpaper", "Summary");
    fireEvent.click(tab("Financials"));
    expect(onChange).toHaveBeenLastCalledWith("Workpaper", "Financials");
    fireEvent.click(tab("Agent"));
    expect(onChange).toHaveBeenLastCalledWith("Agent", undefined);
    expect(onChange).toHaveBeenCalledTimes(3);
  });

  it("remembers the section of each first-track item", () => {
    const onChange = vi.fn();
    render(
      <SegmentedGroup
        label="Return"
        options={FIRST}
        active="Workpaper"
        sub={SUB}
        onChange={onChange}
      />,
    );
    fireEvent.click(tab("Fixed Assets"));
    fireEvent.click(tab("Review"));
    fireEvent.click(tab("Workpaper"));
    expect(tab("Fixed Assets").getAttribute("aria-selected")).toBe("true");
    expect(onChange).toHaveBeenLastCalledWith("Workpaper", "Fixed Assets");
  });

  it("wraps with the arrows inside each track on its own", () => {
    render(<SegmentedGroup label="Return" options={FIRST} active="Workpaper" sub={SUB} />);
    fireEvent.keyDown(tab("Fixed Assets"), { key: "ArrowRight" });
    expect(tab("Summary").getAttribute("aria-selected")).toBe("true");
    expect(tab("Workpaper").getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab("Summary"), { key: "ArrowLeft" });
    expect(tab("Fixed Assets").getAttribute("aria-selected")).toBe("true");
  });
});

describe("UnderlineTabs", () => {
  const SETTINGS = ["Firm", "Members", "Roles", "Billing", "Integrations"];

  it("is a flat tablist: 37px items, a hairline under the row, no pill", () => {
    render(<UnderlineTabs label="Settings" options={SETTINGS} active="Members" />);
    const list = screen.getByRole("tablist", { name: "Settings" });
    expect(classes(list)).toEqual(expect.arrayContaining(["hairline-b", "gap-[4px]"]));
    expect(classes(tab("Roles"))).toContain("h-[37px]");
    expect(classes(tab("Roles"))).not.toContain("rounded-pill");
  });

  it("marks the selected item with a 2px espresso underline and weight 500", () => {
    render(<UnderlineTabs label="Settings" options={SETTINGS} active="Members" />);
    expect(classes(tab("Members"))).toEqual(
      expect.arrayContaining(["font-medium", "text-ink", "after:bg-espresso", "after:h-[2px]"]),
    );
    expect(classes(tab("Roles"))).toEqual(
      expect.arrayContaining(["text-ink-2", "hover:text-ink"]),
    );
  });

  it("does not press: an underline tab has no scale", () => {
    render(<UnderlineTabs label="Settings" options={SETTINGS} active="Members" />);
    expect(classes(tab("Roles"))).not.toContain("active:pressed");
  });

  it("shares the keyboard model", () => {
    const onChange = vi.fn();
    render(
      <UnderlineTabs
        label="Settings"
        options={SETTINGS}
        active="Integrations"
        onChange={onChange}
      />,
    );
    fireEvent.keyDown(tab("Integrations"), { key: "ArrowRight" });
    expect(tab("Firm").getAttribute("aria-selected")).toBe("true");
    expect(onChange).toHaveBeenCalledWith("Firm");
  });
});

describe("SheetTabs", () => {
  const SHEETS: Opt[] = [
    { label: "Worksheets", icon: "panels-top-left" },
    { label: "Leadsheets", icon: "layers" },
    { label: "2-Year Comparison", icon: "chart-column" },
  ];

  it("draws a 14px icon before each label on 30px pills", () => {
    const { container } = render(
      <SheetTabs label="Sheets" options={SHEETS} active="Worksheets" />,
    );
    const icons = [...container.querySelectorAll("svg")].map((s) => s.dataset["icon"]);
    expect(icons).toEqual(["panels-top-left", "layers", "chart-column"]);
    expect(classes(tab("Leadsheets"))).toEqual(
      expect.arrayContaining(["h-[30px]", "rounded-pill", "px-[10px]", "text-ink-2"]),
    );
  });

  it("lifts the selected sheet onto nested with e1 and weight 500", () => {
    render(<SheetTabs label="Sheets" options={SHEETS} active="Leadsheets" />);
    expect(classes(tab("Leadsheets"))).toEqual(
      expect.arrayContaining(["bg-nested", "shadow-e1", "font-medium", "text-ink"]),
    );
  });

  it("wraps with the arrows", () => {
    render(<SheetTabs label="Sheets" options={SHEETS} active="2-Year Comparison" />);
    fireEvent.keyDown(tab("2-Year Comparison"), { key: "ArrowRight" });
    expect(tab("Worksheets").getAttribute("aria-selected")).toBe("true");
  });
});

describe("ViewToggle", () => {
  function toggle(): HTMLElement {
    return screen.getByRole("button", { name: /^View:/ });
  }

  it("is a 29px white pill on e1 named for the view", () => {
    render(<ViewToggle view="grid" />);
    expect(toggle().getAttribute("aria-label")).toBe("View: Grid");
    expect(toggle().getAttribute("title")).toBe("View: Grid");
    expect(toggle().getAttribute("aria-haspopup")).toBe("menu");
    expect(toggle().getAttribute("aria-expanded")).toBe("false");
    expect(classes(toggle())).toEqual(
      expect.arrayContaining(["h-[29px]", "rounded-pill", "bg-card", "shadow-e1", "px-[9px]"]),
    );
  });

  it("always draws layout-grid and a chevron, whatever the view", () => {
    const { container } = render(<ViewToggle view="list" />);
    const icons = [...container.querySelectorAll("svg")].map((s) => s.dataset["icon"]);
    expect(icons).toEqual(["layout-grid", "chevron-down"]);
    expect(toggle().getAttribute("aria-label")).toBe("View: List");
  });

  it("opens on ArrowDown with the first item focused, a 176px radio menu", () => {
    render(<ViewToggle view="grid" />);
    fireEvent.keyDown(toggle(), { key: "ArrowDown" });
    const menu = screen.getByRole("menu", { name: "View" });
    expect(menu.style.width).toBe("176px");
    const items = within(menu).getAllByRole("menuitemradio");
    expect(items.map((i) => i.textContent)).toEqual(["Grid", "List"]);
    expect(items[0]?.getAttribute("aria-checked")).toBe("true");
    expect(items[1]?.getAttribute("aria-checked")).toBe("false");
    expect(document.activeElement).toBe(items[0]);
  });

  it("closes on Escape and returns focus to the button", async () => {
    render(<ViewToggle view="grid" />);
    toggle().focus();
    fireEvent.keyDown(toggle(), { key: "ArrowDown" });
    const menu = screen.getByRole("menu", { name: "View" });
    fireEvent.keyDown(within(menu).getAllByRole("menuitemradio")[0] as HTMLElement, {
      key: "Escape",
    });
    expect(screen.queryByRole("menu")).toBeNull();
    await waitFor(() => {
      expect(document.activeElement).toBe(toggle());
    });
  });

  it("calls onView only when the choice changes, and renames the button", () => {
    const onView = vi.fn();
    render(<ViewToggle view="grid" onView={onView} />);
    fireEvent.keyDown(toggle(), { key: "ArrowDown" });
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Grid" }));
    expect(onView).not.toHaveBeenCalled();
    fireEvent.keyDown(toggle(), { key: "ArrowDown" });
    fireEvent.click(screen.getByRole("menuitemradio", { name: "List" }));
    expect(onView).toHaveBeenCalledTimes(1);
    expect(onView).toHaveBeenCalledWith("list");
    expect(toggle().getAttribute("aria-label")).toBe("View: List");
  });

  it("resets its view when `view` changes from outside", () => {
    const { rerender } = render(<ViewToggle view="grid" />);
    rerender(<ViewToggle view="list" />);
    expect(toggle().getAttribute("aria-label")).toBe("View: List");
  });

  it("takes its own views", () => {
    render(
      <ViewToggle
        view="board"
        views={[
          { v: "rail", label: "Rail", icon: "layout-grid" },
          { v: "board", label: "Board", icon: "list" },
        ]}
      />,
    );
    expect(toggle().getAttribute("aria-label")).toBe("View: Board");
    expect(DEFAULT_VIEWS.map((v) => v.v)).toEqual(["grid", "list"]);
  });

  it("holds the menu open for a specimen", () => {
    render(<ViewToggle view="grid" forceState="open" />);
    expect(screen.getByRole("menu", { name: "View" })).toBeTruthy();
  });
});
