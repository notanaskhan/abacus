// F-05-T15: Menu and Tooltip (Radix for behaviour, tokens for the look). Escape closes a menu and
// returns focus to its trigger; a tooltip opens on focus, names its trigger and closes on Escape.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import { Menu, type MenuItem, TOOLTIP_DELAY_MS, Tooltip, TooltipProvider } from "./popover";

beforeAll(installDomShims);
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function classes(element: HTMLElement): string[] {
  return element.className.split(/\s+/);
}

function open(trigger: HTMLElement): void {
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
}

const SECTIONS = (onOpen = vi.fn(), onVoid = vi.fn()): MenuItem[][] => [
  [
    { label: "Open", onSelect: onOpen },
    { label: "Copy link", onSelect: () => undefined, hint: "To this request" },
    { label: "Archive", onSelect: () => undefined, disabled: true },
  ],
  [{ label: "Void…", onSelect: onVoid, danger: true }],
];

describe("Menu", () => {
  it("opens on ArrowDown, with the first item focused, as a named menu", () => {
    render(
      <Menu
        label="Row actions"
        trigger={<button type="button">Actions</button>}
        sections={SECTIONS()}
      />,
    );
    open(screen.getByRole("button", { name: "Actions" }));
    const menu = screen.getByRole("menu", { name: "Row actions" });
    const items = within(menu).getAllByRole("menuitem");
    expect(items.map((i) => i.textContent)).toEqual([
      "Open",
      "Copy linkTo this request",
      "Archive",
      "Void…",
    ]);
    expect(document.activeElement).toBe(items[0]);
  });

  it("closes on Escape and returns focus to the trigger", async () => {
    render(
      <Menu
        label="Row actions"
        trigger={<button type="button">Actions</button>}
        sections={SECTIONS()}
      />,
    );
    const trigger = screen.getByRole("button", { name: "Actions" });
    open(trigger);
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    await waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });

  it("moves with the arrows, skips a disabled item and selects with Enter", async () => {
    const onVoid = vi.fn();
    render(
      <Menu
        label="Row actions"
        trigger={<button type="button">Actions</button>}
        sections={SECTIONS(vi.fn(), onVoid)}
      />,
    );
    open(screen.getByRole("button", { name: "Actions" }));
    // Radix moves focus on the next tick.
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "ArrowDown" });
    await waitFor(() => {
      expect(document.activeElement?.textContent).toContain("Copy link");
    });
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "ArrowDown" });
    await waitFor(() => {
      expect(document.activeElement?.textContent).toBe("Void…");
    });
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Enter" });
    expect(onVoid).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("marks a disabled item and draws a destructive one in brick", () => {
    render(
      <Menu
        label="Row actions"
        trigger={<button type="button">Actions</button>}
        sections={SECTIONS()}
      />,
    );
    open(screen.getByRole("button", { name: "Actions" }));
    expect(screen.getByRole("menuitem", { name: "Archive" }).getAttribute("aria-disabled")).toBe(
      "true",
    );
    expect(classes(screen.getByRole("menuitem", { name: "Void…" }))).toContain("text-red-ink");
  });

  it("calls onSelect and closes on a click", () => {
    const onOpen = vi.fn();
    render(
      <Menu
        label="Row actions"
        trigger={<button type="button">Actions</button>}
        sections={SECTIONS(onOpen)}
      />,
    );
    open(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Open" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("draws the tray: nested, radius 15, a white radius-11 section, 34px rows of radius 8", () => {
    render(
      <Menu
        label="Row actions"
        trigger={<button type="button">Actions</button>}
        sections={SECTIONS()}
      />,
    );
    open(screen.getByRole("button", { name: "Actions" }));
    const menu = screen.getByRole("menu");
    expect(classes(menu)).toEqual(
      expect.arrayContaining(["bg-nested", "rounded-menu", "shadow-menu", "p-[4px]"]),
    );
    expect(menu.style.width).toBe("220px");
    const section = menu.querySelector("[role=group]");
    expect(classes(section as HTMLElement)).toEqual(
      expect.arrayContaining(["bg-card", "rounded-menu-inner", "p-[4px]"]),
    );
    expect(classes(screen.getByRole("menuitem", { name: "Open" }))).toEqual(
      expect.arrayContaining(["min-h-[34px]", "rounded-tile", "px-[10px]", "text-body"]),
    );
  });

  it("is a radio group when an item says which is checked", () => {
    const onSelect = vi.fn();
    render(
      <Menu
        label="Repeats"
        trigger={<button type="button">Repeats</button>}
        sections={[
          [
            { label: "Daily", checked: true, onSelect: () => undefined },
            { label: "Weekly", checked: false, onSelect },
          ],
        ]}
      />,
    );
    open(screen.getByRole("button", { name: "Repeats" }));
    const items = screen.getAllByRole("menuitemradio");
    expect(items.map((i) => i.getAttribute("aria-checked"))).toEqual(["true", "false"]);
    expect(items[0]?.dataset["state"]).toBe("checked");
    expect(classes(items[0] as HTMLElement)).toEqual(
      expect.arrayContaining([
        "data-[state=checked]:font-medium",
        "data-[state=checked]:bg-nav-fill",
      ]),
    );
    expect(items[0]?.querySelector("svg")?.dataset["icon"]).toBe("check");
    fireEvent.click(items[1] as HTMLElement);
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("draws an item's registry icon before its label", () => {
    render(
      <Menu
        label="View"
        trigger={<button type="button">View</button>}
        sections={[[{ label: "Grid", icon: "layout-grid", onSelect: () => undefined }]]}
      />,
    );
    open(screen.getByRole("button", { name: "View" }));
    expect(
      screen.getByRole("menuitem", { name: "Grid" }).querySelector("svg")?.dataset["icon"],
    ).toBe("layout-grid");
  });

  it("asserts that an item that opens a dialog ends with an ellipsis", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const bad: MenuItem[][] = [
      [{ label: "Rename", opensDialog: true, onSelect: () => undefined }],
    ];
    expect(() => {
      render(<Menu label="A" trigger={<button type="button">A</button>} sections={bad} />);
      open(screen.getByRole("button", { name: "A" }));
    }).toThrow(/U\+2026/);
    spy.mockRestore();
    cleanup();
    const good: MenuItem[][] = [
      [{ label: "Rename…", opensDialog: true, onSelect: () => undefined }],
    ];
    render(<Menu label="A" trigger={<button type="button">A</button>} sections={good} />);
    open(screen.getByRole("button", { name: "A" }));
    expect(screen.getByRole("menuitem", { name: "Rename…" }).getAttribute("aria-haspopup")).toBe(
      "dialog",
    );
  });

  it("holds open for a specimen and takes no focus", () => {
    render(
      <Menu
        label="Row actions"
        forceState="open"
        trigger={<button type="button">Actions</button>}
        sections={SECTIONS()}
      />,
    );
    expect(screen.getByRole("menu", { name: "Row actions" })).toBeTruthy();
    expect(document.activeElement).not.toBe(screen.getByRole("menu"));
  });

  it("plays no reveal animation under reduced motion", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({
        matches: query.includes("reduce"),
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      })),
    );
    const menu = (
      <Menu label="A" trigger={<button type="button">A</button>} sections={SECTIONS()} />
    );
    render(menu);
    open(screen.getByRole("button", { name: "A" }));
    expect(classes(screen.getByRole("menu"))).not.toContain("motion-reveal");
    cleanup();
    vi.unstubAllGlobals();
    render(menu);
    open(screen.getByRole("button", { name: "A" }));
    expect(classes(screen.getByRole("menu"))).toContain("motion-reveal");
  });

  it("draws a held menu in place with the roles and classes of a live one", () => {
    render(
      <Menu
        label="View"
        forceState="open"
        width={176}
        trigger={<button type="button">View</button>}
        sections={[
          [
            { label: "Grid", checked: true, onSelect: () => undefined },
            { label: "List", checked: false, onSelect: () => undefined },
          ],
        ]}
      />,
    );
    const trigger = screen.getByRole("button", { name: "View" });
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(trigger.getAttribute("aria-haspopup")).toBe("menu");
    const menu = screen.getByRole("menu", { name: "View" });
    expect(menu.style.width).toBe("176px");
    expect(classes(menu)).toEqual(
      expect.arrayContaining(["bg-nested", "rounded-menu", "shadow-menu"]),
    );
    expect(classes(menu)).not.toContain("motion-reveal");
    const items = screen.getAllByRole("menuitemradio");
    expect(items.map((i) => i.getAttribute("aria-checked"))).toEqual(["true", "false"]);
    expect(items[0]?.querySelector("svg")?.dataset["icon"]).toBe("check");
  });
});

describe("Tooltip", () => {
  it("opens on keyboard focus, names its trigger and is a tooltip", () => {
    render(
      <Tooltip content="Prepared by Sam Staff">
        <button type="button">Details</button>
      </Tooltip>,
    );
    expect(screen.queryByRole("tooltip")).toBeNull();
    act(() => {
      screen.getByRole("button", { name: "Details" }).focus();
    });
    const tip = screen.getByRole("tooltip");
    expect(tip.textContent).toBe("Prepared by Sam Staff");
    const describedBy = screen
      .getByRole("button", { name: "Details" })
      .getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(tip.id).toBe(describedBy);
  });

  it("closes on Escape and on blur", () => {
    render(
      <Tooltip content="Prepared by Sam Staff">
        <button type="button">Details</button>
      </Tooltip>,
    );
    const trigger = screen.getByRole("button", { name: "Details" });
    act(() => {
      trigger.focus();
    });
    expect(screen.getByRole("tooltip")).toBeTruthy();
    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
    act(() => {
      trigger.blur();
      trigger.focus();
    });
    expect(screen.getByRole("tooltip")).toBeTruthy();
    act(() => {
      trigger.blur();
    });
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("opens after 450ms of hover, not before", () => {
    vi.useFakeTimers();
    expect(TOOLTIP_DELAY_MS).toBe(450);
    render(
      <TooltipProvider>
        <Tooltip content="Go to anything" detail="Also: Open board">
          <button type="button">Go</button>
        </Tooltip>
      </TooltipProvider>,
    );
    fireEvent.pointerMove(screen.getByRole("button", { name: "Go" }));
    act(() => {
      vi.advanceTimersByTime(TOOLTIP_DELAY_MS - 1);
    });
    expect(screen.queryByRole("tooltip")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.getByRole("tooltip").textContent).toBe("Go to anythingAlso: Open board");
  });

  it("is white on the pop shadow with a 12.5 first line and an 11.5 second", () => {
    render(
      <Tooltip content="First" detail="Second" forceState="open">
        <button type="button">Go</button>
      </Tooltip>,
    );
    const first = screen.getAllByText("First")[0] as HTMLElement;
    const card = first.parentElement as HTMLElement;
    expect(classes(card)).toEqual(
      expect.arrayContaining(["bg-card", "rounded-nested", "shadow-pop", "px-[10px]", "py-[7px]"]),
    );
    expect(classes(first)).toEqual(expect.arrayContaining(["text-dense", "text-ink"]));
    expect(classes(screen.getAllByText("Second")[0] as HTMLElement)).toEqual(
      expect.arrayContaining(["text-meta", "text-ink-3"]),
    );
  });

  it("needs no provider, and shares one when there is one", () => {
    render(
      <TooltipProvider>
        <Tooltip content="A" forceState="open">
          <button type="button">One</button>
        </Tooltip>
      </TooltipProvider>,
    );
    expect(screen.getByRole("tooltip")).toBeTruthy();
  });
});
