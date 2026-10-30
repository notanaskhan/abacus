import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SplitLayout } from "./split-layout";
import {
  SPLIT,
  SPLIT_PRESETS,
  clampWidth,
  dragTarget,
  roomFor,
  splitStorageKey,
} from "./split-presets";

// F-05-T29 acceptance: "Preset widths match chapter 04 section 3.11, gutters clamp between 280px
// and 60 percent, and the third column becomes a drawer at 1280px or less."

function narrowWindow(narrow: boolean): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: (query: string) => ({
      matches: narrow && query.includes("max-width: 1280px"),
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      onchange: null,
      dispatchEvent: () => false,
    }),
  });
}

beforeEach(() => {
  narrowWindow(false);
  window.localStorage.clear();
});
afterEach(cleanup);

describe("presets (plan 04 §3.11)", () => {
  it("carries the chapter's widths, twelve presets", () => {
    const widths = Object.fromEntries(
      Object.entries(SPLIT_PRESETS).map(([name, p]) => [name, p.panes.map((pane) => pane.width)]),
    );
    expect(widths).toEqual({
      audit: [330, 536, 490],
      "audit-chat": [330, 696, 330],
      taxReview: [214, 571, 571],
      review: [452, 452, 452],
      "issues-individual": [546, 433, 377],
      "close-review": [790, 576],
      "issues-entity": [470, 896],
      document: [470, 896],
      workbench: [358, 998],
      agents: [320, 1036],
      library: [358, 998],
      inbox: [392, 964],
      portal: [336, 1020],
    });
  });

  it("only the four three-column presets the plan names turn into a drawer", () => {
    const drawers = Object.entries(SPLIT_PRESETS)
      .filter(([, p]) => "drawer" in p && p.drawer)
      .map(([name]) => name);
    expect(drawers).toEqual(["audit", "audit-chat", "taxReview", "issues-individual"]);
  });
});

describe("clamping", () => {
  const panes = SPLIT_PRESETS.audit.panes;

  it("holds a pane between 280 and 60% of the row", () => {
    expect(clampWidth(100, 1400, panes, {}, 0)).toBe(280);
    // Two panes, the second flex (280 floor): 60% of 2400 binds before the room left.
    const workbench = SPLIT_PRESETS.workbench.panes;
    expect(clampWidth(5000, 2400, workbench, {}, 0)).toBe(Math.round(2400 * SPLIT.maxPaneRatio));
  });

  it("never lets a pane run past the room the others leave", () => {
    // 1376 inner, two gutters (20) and the other panes at 536 + 490: 330 left.
    expect(roomFor(1376, panes, {}, 0)).toBe(330);
    expect(clampWidth(600, 1376, panes, {}, 0)).toBe(330);
  });

  it("starts the floor at the design width when that is under 280", () => {
    expect(clampWidth(100, 1400, SPLIT_PRESETS.taxReview.panes, {}, 0)).toBe(214);
  });

  it("resizes the fixed neighbour; between two flex panes, the left one", () => {
    expect(dragTarget(0, panes, {})).toEqual({ target: 0, sign: 1 });
    const tax = SPLIT_PRESETS.taxReview.panes;
    expect(dragTarget(0, tax, {})).toEqual({ target: 0, sign: 1 });
    expect(dragTarget(1, tax, {})).toEqual({ target: 1, sign: 1 });
    expect(dragTarget(0, SPLIT_PRESETS.portal.panes, {})).toEqual({ target: 0, sign: 1 });
  });
});

function layout(preset: keyof typeof SPLIT_PRESETS = "audit", props = {}) {
  return render(
    <SplitLayout preset={preset} height={600} drawerTitle="Evidence" {...props}>
      <section>Rail</section>
      <section>Workpaper</section>
      <section>Evidence</section>
    </SplitLayout>,
  );
}

describe("gutters", () => {
  it("are focusable vertical separators, one between each pair of panes", () => {
    layout();
    const gutters = screen.getAllByRole("separator");
    expect(gutters).toHaveLength(2);
    expect(gutters[0]?.getAttribute("aria-orientation")).toBe("vertical");
    expect(gutters[0]?.tabIndex).toBe(0);
  });

  it("move 16px with the arrow keys, and Enter resets", () => {
    const { container } = layout();
    const gutter = screen.getAllByRole("separator")[0];
    if (gutter === undefined) throw new Error("gutter");
    const first = (): string | undefined =>
      container.querySelector<HTMLElement>('[data-split-pane="0"]')?.style.width;
    expect(first()).toBe("330px");
    fireEvent.keyDown(gutter, { key: "ArrowRight" });
    expect(first()).toBe("346px");
    fireEvent.keyDown(gutter, { key: "ArrowLeft" });
    fireEvent.keyDown(gutter, { key: "ArrowLeft" });
    expect(first()).toBe("314px");
    fireEvent.keyDown(gutter, { key: "Enter" });
    expect(first()).toBe("330px");
  });

  it("a double click resets too", () => {
    const { container } = layout();
    const gutter = screen.getAllByRole("separator")[0];
    if (gutter === undefined) throw new Error("gutter");
    fireEvent.keyDown(gutter, { key: "ArrowRight" });
    fireEvent.doubleClick(gutter);
    expect(container.querySelector<HTMLElement>('[data-split-pane="0"]')?.style.width).toBe(
      "330px",
    );
  });

  it("the library preset draws no gutters", () => {
    layout("library");
    expect(screen.queryAllByRole("separator")).toHaveLength(0);
  });
});

describe("persistence (guarded localStorage)", () => {
  it("saves per preset, reloads, and removes the key once reset", () => {
    const first = layout();
    const gutter = screen.getAllByRole("separator")[0];
    if (gutter === undefined) throw new Error("gutter");
    fireEvent.keyDown(gutter, { key: "ArrowRight" });
    expect(window.localStorage.getItem(splitStorageKey("audit"))).toBe('{"0":346}');
    first.unmount();
    const { container } = layout();
    expect(container.querySelector<HTMLElement>('[data-split-pane="0"]')?.style.width).toBe(
      "346px",
    );
    const again = screen.getAllByRole("separator")[0];
    if (again === undefined) throw new Error("gutter");
    fireEvent.keyDown(again, { key: "Enter" });
    expect(window.localStorage.getItem(splitStorageKey("audit"))).toBeNull();
  });

  it("survives storage that throws or holds junk", () => {
    window.localStorage.setItem(splitStorageKey("audit"), "{not json");
    const { container } = layout();
    expect(container.querySelector<HTMLElement>('[data-split-pane="0"]')?.style.width).toBe(
      "330px",
    );
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    try {
      const gutter = screen.getAllByRole("separator")[0];
      if (gutter === undefined) throw new Error("gutter");
      expect(() => {
        fireEvent.keyDown(gutter, { key: "ArrowRight" });
      }).not.toThrow();
      expect(container.querySelector<HTMLElement>('[data-split-pane="0"]')?.style.width).toBe(
        "346px",
      );
    } finally {
      spy.mockRestore();
    }
  });
});

describe("narrow (≤ 1280)", () => {
  it("shows two columns and puts the third in a drawer", () => {
    narrowWindow(true);
    const { container } = layout("audit", { drawerOpen: true });
    expect(container.querySelector('[data-split="audit"]')?.getAttribute("data-narrow")).toBe(
      "true",
    );
    expect(container.querySelectorAll("[data-split-pane]")).toHaveLength(2);
    expect(screen.getByRole("dialog", { name: "Evidence" }).textContent).toContain("Evidence");
  });

  it("keeps three columns for a preset with no drawer", () => {
    narrowWindow(true);
    const { container } = layout("review");
    expect(container.querySelectorAll("[data-split-pane]")).toHaveLength(3);
  });

  it("keeps three columns above 1280", () => {
    const { container } = layout("audit");
    expect(container.querySelectorAll("[data-split-pane]")).toHaveLength(3);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("closes the drawer when asked", () => {
    narrowWindow(true);
    let open = true;
    const view = layout("taxReview", {
      drawerOpen: open,
      onDrawerOpenChange: (next: boolean) => {
        open = next;
      },
    });
    act(() => {
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    });
    expect(open).toBe(false);
    view.unmount();
  });
});
