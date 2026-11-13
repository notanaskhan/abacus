// F-07-T14 (F-07 §G1, G3, G4; T14a, T14b): the canvas draws the layout, traces a hovered node's
// edges only, and is reachable, selectable, openable and movable by keyboard. Tier D geometry is
// the parity harness's (F-07-T22); here the 180 × 56 boxes and the intents.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TPL14_EDGES, TPL14_FACES, TPL14_NODES, TPL14_SAVED } from "../specimens/fixtures/tpl-14";
import { GraphCanvas, type GraphCanvasNode, NUDGE, safeLine } from "./canvas";

afterEach(cleanup);

const NODES: GraphCanvasNode[] = TPL14_NODES.map(
  (n) => ({ ...n, ...TPL14_FACES[n.id] }) as GraphCanvasNode,
);

function draw(props: Partial<Parameters<typeof GraphCanvas>[0]> = {}) {
  return render(
    <GraphCanvas
      nodes={NODES}
      edges={TPL14_EDGES}
      saved={TPL14_SAVED}
      selectedId="jonah-feld"
      {...props}
    />,
  );
}

const node = (name: RegExp) => screen.getByRole("button", { name });
const dark = (container: HTMLElement) =>
  [...container.querySelectorAll("[data-edge][data-dark]")]
    .map((e) => e.getAttribute("data-edge"))
    .sort();

describe("GraphCanvas (T14a, T14b)", () => {
  it("draws every node at its saved 180 × 56 box, Jonah Feld selected", () => {
    draw();
    const jonah = node(/^Jonah Feld, LP/);
    expect(jonah.style.left).toBe("836px");
    expect(jonah.style.top).toBe("320px");
    expect(jonah.style.width).toBe("180px");
    expect(jonah.style.height).toBe("56px");
    expect(jonah.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getAllByRole("button", { pressed: false }).length).toBeGreaterThanOrEqual(9);
  });

  it("darkens only the hovered node's edges (T14b)", () => {
    const { container } = draw();
    expect(dark(container)).toEqual([]);
    fireEvent.mouseEnter(node(/^Pell Street Ventures LLC/));
    expect(dark(container)).toEqual(["psv-lp", "psv-ps2"]);
    fireEvent.mouseLeave(node(/^Pell Street Ventures LLC/));
    expect(dark(container)).toEqual([]);
  });

  it("styles edges by kind: only draft K-1 flows are amber", () => {
    const { container } = draw();
    const amber = [...container.querySelectorAll("[data-edge] path.stroke-amber")].map((p) =>
      p.parentElement?.getAttribute("data-edge"),
    );
    expect(amber.sort()).toEqual(["feld-k1", "shah-k1"]);
    expect(
      container.querySelector('[data-edge="psv-ps2"] path')?.getAttribute("stroke-dasharray"),
    ).toBe("4 3");
    expect(screen.getAllByText("Draft K-1 · pre-release")).toHaveLength(2);
  });

  it("moves focus with arrows, selects with Enter, opens with Shift+Enter", () => {
    const onSelect = vi.fn();
    const onOpenRecord = vi.fn();
    draw({ onSelect, onOpenRecord });
    const jonah = node(/^Jonah Feld, LP/);
    expect(jonah.tabIndex).toBe(0);
    act(() => {
      jonah.focus();
    });
    fireEvent.keyDown(jonah, { key: "ArrowLeft" });
    expect(document.activeElement).toBe(node(/^Pell Street II LLC/));
    fireEvent.keyDown(document.activeElement as Element, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("pell-street-ii");
    fireEvent.keyDown(document.activeElement as Element, { key: "Enter", shiftKey: true });
    expect(onOpenRecord).toHaveBeenCalledWith("pell-street-ii");
    fireEvent.keyDown(document.activeElement as Element, { key: "ArrowDown" });
    expect(document.activeElement?.getAttribute("data-node")).toMatch(
      /claire-feld|feld-1040|shah-1040/,
    );
  });

  it("nudges the focused node 8 px with Alt+arrow and emits the move", () => {
    const onLayoutChange = vi.fn();
    draw({ onLayoutChange });
    const jonah = node(/^Jonah Feld, LP/);
    fireEvent.keyDown(jonah, { key: "ArrowRight", altKey: true });
    expect(onLayoutChange).toHaveBeenLastCalledWith({ "jonah-feld": { x: 836 + NUDGE, y: 320 } });
    expect(node(/^Jonah Feld, LP/).style.left).toBe(`${String(836 + NUDGE)}px`);
  });

  it("zooms by keyboard-reachable buttons between 50 % and 200 %", () => {
    draw();
    expect(screen.getByText("100%")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(screen.getByText("110%")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Fit" }));
    expect(screen.getByText("100%")).toBeTruthy();
  });

  it("draws no placeholder, count or edge for a walled party (DEC-43)", () => {
    const { container } = render(
      <GraphCanvas
        nodes={NODES.filter((n) => n.id !== "pell-street-ii")}
        edges={TPL14_EDGES}
        saved={TPL14_SAVED}
      />,
    );
    expect(screen.queryByRole("button", { name: /Pell Street II/ })).toBeNull();
    expect(container.querySelector('[data-edge="ps2-lp"], [data-edge="psv-ps2"]')).toBeNull();
    expect(container.textContent).not.toMatch(/hidden|walled|\d+ more/i);
  });

  it("never draws a node line that still holds a full TIN", () => {
    expect(safeLine("LP · •••-••-4417")).toBe("LP · •••-••-4417");
    expect(safeLine("LP · 123-45-4417")).toBe("");
    expect(safeLine("GP · 12-3450291")).toBe("");
  });
});
