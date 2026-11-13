// F-07-T13 (F-07 §G1): the layered layout's properties over seeded random graphs (no new
// dependency: a small PRNG), and TPL-14a's saved positions reproduced exactly.
import { describe, expect, it } from "vitest";
import { TPL14_EDGES, TPL14_NODES, TPL14_SAVED } from "../specimens/fixtures/tpl-14";
import {
  type EdgeRoute,
  type GraphEdgeIn,
  type GraphEdgeKind,
  type GraphNodeIn,
  type GraphNodeKind,
  type LaidOutNode,
  type Layout,
  RANK_OF,
  layoutLayered,
  routeOrthogonal,
} from "./layout";

function prng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const NODE_KINDS: GraphNodeKind[] = [
  "entity",
  "partnership",
  "person",
  "trust",
  "return",
  "external",
];
const EDGE_KINDS = Object.keys(RANK_OF) as GraphEdgeKind[];

function graph(seed: number): { nodes: GraphNodeIn[]; edges: GraphEdgeIn[] } {
  const rnd = prng(seed);
  const pick = <T>(xs: readonly T[]): T => xs[Math.floor(rnd() * xs.length)] as T;
  const n = 2 + Math.floor(rnd() * 38);
  const nodes = Array.from({ length: n }, (_, i) => ({
    id: `n${String(i).padStart(2, "0")}`,
    kind: pick(NODE_KINDS),
  }));
  const m = Math.floor(rnd() * n * 2);
  const edges = Array.from({ length: m }, (_, i) => ({
    id: `e${String(i).padStart(3, "0")}`,
    from: pick(nodes).id,
    to: pick(nodes).id,
    kind: pick(EDGE_KINDS),
    label: "x".repeat(2 + Math.floor(rnd() * 34)),
  }));
  return { nodes, edges };
}

function shuffled<T>(xs: readonly T[], seed: number): T[] {
  const rnd = prng(seed);
  const out = [...xs];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rnd() * (i + 1));
    [out[i], out[j]] = [out[j] as T, out[i] as T];
  }
  return out;
}

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

const overlaps = (a: Box, b: Box): boolean =>
  a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

/** Does an axis-aligned segment pass through the box's interior? */
function crosses(a: { x: number; y: number }, b: { x: number; y: number }, box: Box): boolean {
  const [x0, x1] = [Math.min(a.x, b.x), Math.max(a.x, b.x)];
  const [y0, y1] = [Math.min(a.y, b.y), Math.max(a.y, b.y)];
  const inX = x1 > box.x && x0 < box.x + box.width;
  const inY = y1 > box.y && y0 < box.y + box.height;
  return inX && inY;
}

function check(layout: Layout, routes: EdgeRoute[], edges: readonly GraphEdgeIn[]): void {
  const nodes = layout.nodes;
  for (let i = 0; i < nodes.length; i += 1)
    for (let j = i + 1; j < nodes.length; j += 1)
      expect(
        overlaps(nodes[i] as LaidOutNode, nodes[j] as LaidOutNode),
        `${String(i)} ${String(j)}`,
      ).toBe(false);
  const ends = new Map(edges.map((e) => [e.id, new Set([e.from, e.to])]));
  for (const r of routes) {
    for (let k = 0; k + 1 < r.points.length; k += 1) {
      const [p, q] = [r.points[k], r.points[k + 1]];
      if (p === undefined || q === undefined) continue;
      expect(p.x === q.x || p.y === q.y, `${r.id} segment ${String(k)} is not orthogonal`).toBe(
        true,
      );
      for (const n of nodes) {
        if (ends.get(r.id)?.has(n.id)) continue;
        expect(crosses(p, q, n), `${r.id} crosses ${n.id}`).toBe(false);
      }
    }
  }
  for (let i = 0; i < routes.length; i += 1)
    for (let j = i + 1; j < routes.length; j += 1)
      expect(
        overlaps((routes[i] as EdgeRoute).label, (routes[j] as EdgeRoute).label),
        `pills ${String(i)} ${String(j)}`,
      ).toBe(false);
}

describe("layoutLayered and routeOrthogonal (F-07 §G1)", () => {
  it("are deterministic: the same input gives the same coordinates, whatever the input order", () => {
    for (let seed = 1; seed <= 60; seed += 1) {
      const { nodes, edges } = graph(seed);
      const a = layoutLayered(nodes, edges);
      const b = layoutLayered(shuffled(nodes, seed + 1000), shuffled(edges, seed + 2000));
      expect(b.nodes).toEqual(a.nodes);
      expect(routeOrthogonal(b, edges)).toEqual(routeOrthogonal(a, edges));
    }
  });

  it("never overlap nodes, never route an edge through a node, never overlap two pills", () => {
    for (let seed = 1; seed <= 200; seed += 1) {
      const { nodes, edges } = graph(seed);
      const layout = layoutLayered(nodes, edges);
      check(layout, routeOrthogonal(layout, edges), edges);
    }
  });

  it("puts an owned entity above its owner and a K-1's return below its partner", () => {
    const layout = layoutLayered(TPL14_NODES, TPL14_EDGES);
    const rank = new Map(layout.nodes.map((n) => [n.id, n.rank]));
    expect(rank.get("ridgeline-lp")).toBeLessThan(rank.get("jonah-feld") ?? 0);
    expect(rank.get("feld-1040")).toBeGreaterThan(rank.get("jonah-feld") ?? 0);
    expect(rank.get("pell-street-ii")).toBe(rank.get("pell-street-ventures"));
  });

  it("lets saved positions win exactly: TPL-14a's coordinates", () => {
    const layout = layoutLayered(TPL14_NODES, TPL14_EDGES, { saved: TPL14_SAVED });
    for (const n of layout.nodes) {
      expect({ id: n.id, x: n.x, y: n.y, saved: n.saved }).toEqual({
        id: n.id,
        ...TPL14_SAVED[n.id],
        saved: true,
      });
    }
    expect(layout.nodes.find((n) => n.id === "jonah-feld")).toMatchObject({ x: 836, y: 320 });
    expect(layout.nodes.find((n) => n.id === "ridgeline-lp")).toMatchObject({ x: 428, y: 150 });
  });

  it("drops an edge to a node that is not there (a walled party: no dangling edge)", () => {
    const nodes = TPL14_NODES.filter((n) => n.id !== "pell-street-ii");
    const layout = layoutLayered(nodes, TPL14_EDGES);
    const routes = routeOrthogonal(layout, TPL14_EDGES);
    expect(routes.some((r) => r.id === "ps2-lp" || r.id === "psv-ps2")).toBe(false);
    expect(layout.nodes.some((n) => n.id === "pell-street-ii")).toBe(false);
  });

  it("lays out 60 nodes inside a frame budget (16 ms, best of five)", () => {
    const { edges } = graph(7);
    const nodes = Array.from({ length: 60 }, (_, i) => ({
      id: `n${String(i).padStart(2, "0")}`,
      kind: "entity" as const,
    }));
    const wired = edges.map((e, i) => ({
      ...e,
      from: `n${String(i % 60).padStart(2, "0")}`,
      to: `n${String((i * 7 + 3) % 60).padStart(2, "0")}`,
    }));
    let best = Number.POSITIVE_INFINITY;
    for (let i = 0; i < 5; i += 1) {
      const t0 = performance.now();
      routeOrthogonal(layoutLayered(nodes, wired), wired);
      best = Math.min(best, performance.now() - t0);
    }
    expect(best).toBeLessThan(16);
  });
});
