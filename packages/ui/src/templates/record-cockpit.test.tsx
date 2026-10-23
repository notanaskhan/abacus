import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { RecordCockpitSpecimen } from "../specimens/record";
import { installDomShims } from "../test-dom";
import { DOCK_VIEWS, type RecordCockpitProps, RecordCockpit } from "./record-cockpit";

// F-05-T40 acceptance: "T2a to T2e render with data-driven sub-lines plus discs, never colour
// alone, and toggling the dock flexes the canvas between 696 and 1036." jsdom has no layout, so
// the widths are read from the tokens the frame is built on (and measured in the browser by the
// Tier D spec, apps/web/e2e/visual/tier-d.spec.ts).

beforeAll(installDomShims);
afterEach(cleanup);

const BASE: RecordCockpitProps = {
  toolbar: { nav: [{ label: "Audits" }], firm: "Brightwater Hale", active: "Audits" },
  record: {
    title: "Northwind Robotics 401(k) Plan",
    context: "PY2025 EBP Audit",
    state: "Planning",
  },
  rail: <div data-testid="rail" />,
  canvas: { title: "Trial Balance", children: <p>body</p> },
  dock: { view: "Agent", children: <p>thread</p> },
};

function px(css: string, name: string): number {
  const m = new RegExp(`--${name}:\\s*(\\d+)px`).exec(css);
  if (m?.[1] === undefined) throw new Error(`no --${name}`);
  return Number(m[1]);
}

describe("T2 RecordCockpit", () => {
  it("the canvas is 696 beside the dock and 1036 without it, from the frame's tokens", () => {
    const css = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "..", "root.css"),
      "utf8",
    );
    const inner = px(css, "app-w") - 2 * px(css, "edge-app");
    const rail = px(css, "rail-w");
    const gap = px(css, "gutter-pane");
    const dock = px(css, "dock-w");
    expect(rail).toBe(330);
    expect(dock).toBe(330);
    expect(inner - rail - gap - gap - dock).toBe(696);
    expect(inner - rail - gap).toBe(1036);
    // The frame uses exactly those tokens: a fixed rail and dock, a canvas that takes the rest.
    const { container } = render(<RecordCockpit {...BASE} />);
    expect(container.querySelector('[data-cockpit="rail"]')?.className).toContain("w-(--rail-w)");
    expect(container.querySelector('[data-cockpit="dock"]')?.className).toContain("w-(--dock-w)");
    expect(container.querySelector('[data-cockpit="canvas"]')?.className).toContain(
      "flex-[1_1_0%]",
    );
  });

  it("the layout chip in the record bar shows and hides the dock", () => {
    const onDockOpenChange = vi.fn();
    const { container } = render(<RecordCockpit {...BASE} onDockOpenChange={onDockOpenChange} />);
    expect(container.querySelector('[data-cockpit="dock"]')).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Layout" }));
    expect(container.querySelector('[data-cockpit="dock"]')).toBeNull();
    expect(onDockOpenChange).toHaveBeenLastCalledWith(false);
    fireEvent.click(screen.getByRole("button", { name: "Layout" }));
    expect(container.querySelector('[data-cockpit="dock"]')).not.toBeNull();
    expect(onDockOpenChange).toHaveBeenLastCalledWith(true);
  });

  it("with no dock the canvas runs to the edge and the chip does nothing", () => {
    const noDock: RecordCockpitProps = { ...BASE };
    delete noDock.dock;
    const { container } = render(<RecordCockpit {...noDock} />);
    expect(container.querySelector('[data-cockpit="dock"]')).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Layout" }));
    expect(container.querySelector('[data-cockpit="dock"]')).toBeNull();
  });

  it("the dock switches Agent, Viewer and Notes; one view is a title", () => {
    const onView = vi.fn();
    render(<RecordCockpit {...BASE} dock={{ view: "Agent", onView }} />);
    const tabs = screen.getByRole("tablist", { name: "Dock" });
    expect(
      within(tabs)
        .getAllByRole("tab")
        .map((t) => t.textContent),
    ).toEqual([...DOCK_VIEWS]);
    fireEvent.click(within(tabs).getByRole("tab", { name: "Viewer" }));
    expect(onView).toHaveBeenCalledWith("Viewer");
    cleanup();
    render(<RecordCockpit {...BASE} dock={{ view: "Notes", views: ["Notes"] }} />);
    expect(screen.queryByRole("tablist", { name: "Dock" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Notes" })).toBeTruthy();
  });

  it("a running dock shows the live dot and says so in words; idle shows its Run action", () => {
    render(
      <RecordCockpit
        {...BASE}
        dock={{ view: "Agent", live: true, action: <button type="button">Run</button> }}
      />,
    );
    expect(screen.getByText("Run in progress")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Run" })).toBeTruthy();
  });

  it("the canvas title is left-aligned; controls and footer show only when ready", () => {
    const canvas = {
      title: "Risk Assessment",
      controls: <span>controls</span>,
      footer: <span>footer</span>,
    };
    const { rerender } = render(<RecordCockpit {...BASE} canvas={canvas} />);
    expect(
      screen.getByRole("heading", { name: "Risk Assessment" }).getAttribute("data-title"),
    ).toBe("left");
    expect(screen.getByText("controls")).toBeTruthy();
    expect(screen.getByText("footer")).toBeTruthy();
    rerender(
      <RecordCockpit
        {...BASE}
        canvas={{
          ...canvas,
          state: { kind: "empty" },
          empty: { title: "Risk Assessment hasn’t started" },
        }}
      />,
    );
    expect(screen.getByText("Risk Assessment hasn’t started")).toBeTruthy();
    expect(screen.queryByText("controls")).toBeNull();
    expect(screen.queryByText("footer")).toBeNull();
  });
});

describe("T2a to T2e specimens", () => {
  it("renders the five artboards with every rail phase as words plus a disc", () => {
    const { container } = render(<RecordCockpitSpecimen />);
    for (const id of ["t2a", "t2b", "t2c", "t2d", "t2e"]) {
      const board = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
      expect(board, id).not.toBeNull();
      const rows = board?.querySelectorAll<HTMLElement>('[data-rail-row="phase"]') ?? [];
      expect(rows.length, id).toBeGreaterThan(0);
      for (const row of rows) {
        const disc = row.querySelector('[role="img"]');
        expect(disc?.getAttribute("aria-label"), `${id} ${row.textContent}`).toBeTruthy();
      }
    }
  });

  it("states move with the data: T2c blocked in amber words, T2d failed, T2e no dock", () => {
    const { container } = render(<RecordCockpitSpecimen />);
    const board = (id: string): HTMLElement =>
      container.querySelector<HTMLElement>(`[data-artboard="${id}"]`) as HTMLElement;
    const mat = board("t2c").querySelector('[data-phase="mat"]') as HTMLElement;
    expect(mat.getAttribute("data-disc")).toBe("warn");
    expect(within(mat).getByText("Blocked on a partner decision").className).toContain(
      "text-amber-ink",
    );
    const ic = board("t2d").querySelector('[data-phase="ic"]') as HTMLElement;
    expect(ic.getAttribute("data-disc")).toBe("fail");
    expect(within(ic).getByText("Failed — see run")).toBeTruthy();
    expect(board("t2a").querySelector('[data-cockpit="dock"]')).not.toBeNull();
    expect(within(board("t2a")).getByRole("button", { name: "Run" })).toBeTruthy();
    expect(within(board("t2b")).getByText("Run in progress")).toBeTruthy();
    expect(board("t2e").querySelector('[data-cockpit="dock"]')).toBeNull();
    expect(within(board("t2e")).getByText("Risk Assessment hasn’t started")).toBeTruthy();
  });

  it("agent words go through AgentText and Sign off is a HumanAction", () => {
    const { container } = render(<RecordCockpitSpecimen />);
    const docks = container.querySelectorAll('[data-cockpit="dock"]');
    for (const dock of docks) {
      expect(dock.querySelector('[data-actor="agent"]'), dock.textContent).not.toBeNull();
    }
    for (const button of screen.getAllByRole("button", { name: /^Sign off/ })) {
      expect(button.getAttribute("data-human-verb")).toBe("Sign off");
    }
  });
});
