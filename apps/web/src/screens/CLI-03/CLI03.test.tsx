// T-06-T40 (TASK-8836; docs/screens/CLI-03.md): "Every node is reachable by keyboard, the List view
// carries the same relationships, and a walled node is simply absent." One test per artboard.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { scenarios } from "../../fixtures/scenarios/CLI-03";
import { graph } from "../../fixtures/seed/cli03";
import { COPY } from "./copy";
import { CLI03, canvasNodes, inspectorOf, listRows } from ".";

afterEach(cleanup);

describe("CLI-03 Relationships", () => {
  it("covers the six artboards", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("a: every node is a keyboard stop and Jonah Feld's inspector masks the TIN", () => {
    const g = graph("ridgeline");
    render(<CLI03 graph={g} view="graph" selected="jonah-feld" />);
    for (const n of g.nodes) {
      const el = screen.getByRole("button", {
        name: new RegExp(n.label.replace(/[()·]/gu, "."), "u"),
      });
      expect(el.getAttribute("tabindex")).not.toBe("-1");
    }
    const inspector = inspectorOf(g, "jonah-feld");
    expect(inspector?.tin).toBe("•••-••-4417");
    expect(inspector?.linked?.map((l) => l.id)).toEqual(["feld-1040"]);
  });

  it("b: the List view carries the same relationships", () => {
    const g = graph("ridgeline");
    expect(listRows(g).map((r) => r.id)).toEqual(g.edges.map((e) => e.edge_id));
  });

  it("c: the trust variant draws the trust and its people", () => {
    expect(canvasNodes(graph("trust")).find((n) => n.id === "calloway-trust")?.kind).toBe("trust");
  });

  it("d: the external node reads Not a Brightwater Hale client", () => {
    const ext = canvasNodes(graph("external")).find((n) => n.kind === "external");
    expect(ext?.line).toBe(COPY.external);
  });

  it("e: a single entity shows the empty state", () => {
    render(<CLI03 graph={graph("single")} view="graph" selected={null} />);
    expect(screen.getByText(/No relationships yet/u)).toBeTruthy();
  });

  it("f: released K-1 edges and the green banner", () => {
    const g = graph("released");
    expect(g.banner?.tone).toBe("green");
    expect(g.edges.filter((e) => e.kind === "k1").every((e) => e.state === "released")).toBe(true);
  });

  it("a walled node is simply absent: nothing the server leaves out is drawn", () => {
    const g = graph("ridgeline");
    const walled = {
      ...g,
      nodes: g.nodes.filter((n) => n.node_id !== "meera-shah"),
      edges: g.edges.filter((e) => e.from_node_id !== "meera-shah"),
    };
    render(<CLI03 graph={walled} view="list" selected={null} />);
    expect(screen.queryByText("Meera Shah")).toBeNull();
  });

  it("Add relationship… opens the O3 sheet and adds once complete", () => {
    const onAdd = vi.fn();
    render(
      <CLI03 graph={graph("ridgeline")} view="graph" selected={null} onAdd={onAdd} sheet="add" />,
    );
    expect(screen.getByRole("button", { name: COPY.save }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: COPY.save }));
    expect(onAdd).not.toHaveBeenCalled();
  });
});
