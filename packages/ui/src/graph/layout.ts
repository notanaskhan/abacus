// T14 graph layout (F-07-T13; F-07 §G1; TPL-14). Pure functions, no DOM, no dependency (DEC-16:
// no dagre). `layoutLayered` places nodes on a layered grid; `routeOrthogonal` draws each edge as
// axis-aligned segments with one label pill. Same input, same output: every choice is ordered by
// rank, then position, then id.
//
// Ranks come from the relationship kind: an owned entity sits one layer above its owner, a K-1
// flow or a role points one layer down, a transfer, spouse or taxpayer link stays on its layer.
// Cycles are broken by a depth-first pass in id order. Within a layer, nodes are ordered by
// barycentric sweeps (down, then up, four times) with a stable tie-break (previous order, id).
//
// Geometry: nodes are 180 × 56 on a grid (gap 28 between columns, at least 114 between layers, the
// TPL-14 spacing). Horizontal edge runs live in the gaps between layers, one lane per run, so two
// label pills never share a lane; an edge spanning more than one layer drops through a column
// gutter, which no node occupies. Hence, without saved positions, no edge passes through a node
// box and no two pills overlap. Saved positions (the user's layout, TPL-14's spec coordinates) win
// exactly: a saved node is placed where it was saved, and the router then works from the boxes.

export type GraphNodeKind = "entity" | "partnership" | "person" | "trust" | "return" | "external";

export type GraphEdgeKind =
  | "ownership"
  | "transfer"
  | "k1_draft"
  | "k1_released"
  | "role"
  | "spouse"
  | "taxpayer"
  | "beneficiary";

export interface GraphNodeIn {
  id: string;
  kind: GraphNodeKind;
}

export interface GraphEdgeIn {
  id: string;
  from: string;
  to: string;
  kind: GraphEdgeKind;
  label: string;
}

export interface Point {
  x: number;
  y: number;
}

export interface LayoutOptions {
  nodeWidth?: number;
  nodeHeight?: number;
  /** Horizontal space between neighbouring nodes in a layer. */
  columnGap?: number;
  /** The least vertical space between two layers; more when the lanes need it. */
  rankGap?: number;
  /** The top-left of the first layer's first node. */
  origin?: Point;
  /** Saved top-left positions by node id; they win exactly. */
  saved?: Readonly<Record<string, Point>>;
}

export interface LaidOutNode {
  id: string;
  kind: GraphNodeKind;
  x: number;
  y: number;
  width: number;
  height: number;
  rank: number;
  order: number;
  saved: boolean;
}

export interface Layout {
  nodes: LaidOutNode[];
  /** Top y of each layer's row. */
  rankTop: number[];
  /** The y range of the gap below each layer: lanes run inside it. */
  gaps: { top: number; bottom: number; lanes: number }[];
  options: Required<Omit<LayoutOptions, "saved">>;
  width: number;
  height: number;
}

export interface LabelPill {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface EdgeRoute {
  id: string;
  kind: GraphEdgeKind;
  /** Corner points, first on the source box, last on the target box. */
  points: Point[];
  label: LabelPill;
}

export const NODE_WIDTH = 180;
export const NODE_HEIGHT = 56;
export const COLUMN_GAP = 28;
export const RANK_GAP = 114;
export const LANE = 22;
export const PILL_HEIGHT = 18;
const LANE_MARGIN = 12;
const ORIGIN: Point = { x: 24, y: 24 };

/** Which way the target sits from the source: up a layer, down a layer, or the same layer. */
export const RANK_OF: Readonly<Record<GraphEdgeKind, -1 | 0 | 1>> = {
  ownership: -1,
  transfer: 0,
  k1_draft: 1,
  k1_released: 1,
  role: 1,
  spouse: 0,
  taxpayer: 1,
  beneficiary: 1,
};

const KIND_ORDER: Readonly<Record<GraphNodeKind, number>> = {
  partnership: 0,
  entity: 1,
  trust: 2,
  person: 3,
  external: 4,
  return: 5,
};

const byId = (a: { id: string }, b: { id: string }): number =>
  a.id < b.id ? -1 : a.id > b.id ? 1 : 0;

/** Pill width for a label at 11.5 px: an estimate on the conservative side (no DOM here). */
export function pillWidth(label: string): number {
  return Math.ceil(label.length * 6.4) + 16;
}

function ranks(nodes: readonly GraphNodeIn[], edges: readonly GraphEdgeIn[]): Map<string, number> {
  const ids = new Set(nodes.map((n) => n.id));
  // Downward arcs: a → b means b sits at least one layer below a.
  const down = new Map<string, string[]>();
  for (const n of nodes) down.set(n.id, []);
  for (const e of [...edges].sort(byId)) {
    if (!ids.has(e.from) || !ids.has(e.to) || e.from === e.to) continue;
    const dir = RANK_OF[e.kind];
    if (dir === 1) down.get(e.from)?.push(e.to);
    if (dir === -1) down.get(e.to)?.push(e.from);
  }
  for (const list of down.values()) list.sort();
  // Break cycles: keep the arcs a depth-first pass in id order takes forward.
  const state = new Map<string, 0 | 1 | 2>();
  const kept = new Map<string, string[]>();
  const visit = (id: string): void => {
    state.set(id, 1);
    const out: string[] = [];
    for (const next of down.get(id) ?? []) {
      const s = state.get(next) ?? 0;
      if (s === 1) continue; // a back arc: dropped
      out.push(next);
      if (s === 0) visit(next);
    }
    kept.set(id, out);
    state.set(id, 2);
  };
  for (const n of [...nodes].sort(byId)) if ((state.get(n.id) ?? 0) === 0) visit(n.id);
  // Longest path from the sources, in a topological order.
  const indegree = new Map<string, number>();
  for (const n of nodes) indegree.set(n.id, 0);
  for (const list of kept.values())
    for (const t of list) indegree.set(t, (indegree.get(t) ?? 0) + 1);
  const queue = [...nodes]
    .filter((n) => indegree.get(n.id) === 0)
    .map((n) => n.id)
    .sort();
  const rank = new Map<string, number>(nodes.map((n) => [n.id, 0]));
  const vertical = new Set<string>();
  for (const [from, list] of kept)
    if (list.length > 0) {
      vertical.add(from);
      for (const t of list) vertical.add(t);
    }
  while (queue.length > 0) {
    const id = queue.shift() as string;
    for (const t of kept.get(id) ?? []) {
      rank.set(t, Math.max(rank.get(t) ?? 0, (rank.get(id) ?? 0) + 1));
      indegree.set(t, (indegree.get(t) ?? 0) - 1);
      if (indegree.get(t) === 0) {
        queue.push(t);
        queue.sort();
      }
    }
  }
  // A node held only by same-layer links joins its lowest-ranked such neighbour's layer.
  const same = edges.filter((e) => RANK_OF[e.kind] === 0 && ids.has(e.from) && ids.has(e.to));
  for (let pass = 0; pass < nodes.length; pass += 1) {
    let changed = false;
    for (const n of [...nodes].sort(byId)) {
      if (vertical.has(n.id)) continue;
      const near = same
        .filter((e) => e.from === n.id || e.to === n.id)
        .map((e) => (e.from === n.id ? e.to : e.from))
        .filter((m) => m !== n.id);
      if (near.length === 0) continue;
      const r = Math.min(...near.map((m) => rank.get(m) ?? 0));
      if (r !== rank.get(n.id)) {
        rank.set(n.id, r);
        changed = true;
      }
    }
    if (!changed) break;
  }
  // Compact: no empty layers.
  const used = [...new Set(rank.values())].sort((a, b) => a - b);
  const dense = new Map(used.map((r, i) => [r, i]));
  for (const [id, r] of rank) rank.set(id, dense.get(r) ?? 0);
  return rank;
}

function orderLayers(
  nodes: readonly GraphNodeIn[],
  edges: readonly GraphEdgeIn[],
  rank: ReadonlyMap<string, number>,
): string[][] {
  const depth = Math.max(0, ...rank.values()) + 1;
  const layers: string[][] = Array.from({ length: depth }, () => []);
  const sorted = [...nodes].sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || byId(a, b));
  for (const n of sorted) layers[rank.get(n.id) ?? 0]?.push(n.id);
  const neighbours = new Map<string, string[]>(nodes.map((n) => [n.id, []]));
  for (const e of edges) {
    if (!neighbours.has(e.from) || !neighbours.has(e.to) || e.from === e.to) continue;
    neighbours.get(e.from)?.push(e.to);
    neighbours.get(e.to)?.push(e.from);
  }
  const position = new Map<string, number>();
  const index = (): void => {
    for (const layer of layers) layer.forEach((id, i) => position.set(id, i));
  };
  index();
  const sweep = (r: number, toward: number): void => {
    const layer = layers[r];
    if (layer === undefined) return;
    const scored = layer.map((id) => {
      const near = (neighbours.get(id) ?? []).filter((m) => rank.get(m) === toward);
      const bc =
        near.length === 0
          ? (position.get(id) ?? 0)
          : near.reduce((s, m) => s + (position.get(m) ?? 0), 0) / near.length;
      return { id, bc, was: position.get(id) ?? 0 };
    });
    scored.sort((a, b) => a.bc - b.bc || a.was - b.was || (a.id < b.id ? -1 : 1));
    layers[r] = scored.map((s) => s.id);
    index();
  };
  for (let i = 0; i < 4; i += 1) {
    for (let r = 1; r < depth; r += 1) sweep(r, r - 1);
    for (let r = depth - 2; r >= 0; r -= 1) sweep(r, r + 1);
  }
  return layers;
}

/** The layered layout (file header). */
export function layoutLayered(
  nodes: readonly GraphNodeIn[],
  edges: readonly GraphEdgeIn[],
  options: LayoutOptions = {},
): Layout {
  const opts = {
    nodeWidth: options.nodeWidth ?? NODE_WIDTH,
    nodeHeight: options.nodeHeight ?? NODE_HEIGHT,
    columnGap: options.columnGap ?? COLUMN_GAP,
    rankGap: options.rankGap ?? RANK_GAP,
    origin: options.origin ?? ORIGIN,
  };
  const saved = options.saved ?? {};
  const rank = ranks(nodes, edges);
  const layers = orderLayers(nodes, edges, rank);
  const order = new Map<string, number>();
  layers.forEach((layer) => { layer.forEach((id, i) => order.set(id, i)); });
  const known = new Set(nodes.map((n) => n.id));
  // Lanes each gap needs: one per horizontal run that sits in it (see routeOrthogonal).
  const lanes = Array.from({ length: layers.length }, () => 0);
  for (const e of edges) {
    if (!known.has(e.from) || !known.has(e.to) || e.from === e.to) continue;
    const [a, b] = [rank.get(e.from) ?? 0, rank.get(e.to) ?? 0];
    const top = Math.min(a, b);
    const bottom = Math.max(a, b);
    if (top === bottom) lanes[top] = (lanes[top] ?? 0) + 1;
    else {
      lanes[top] = (lanes[top] ?? 0) + 1;
      if (bottom - top > 1) lanes[bottom - 1] = (lanes[bottom - 1] ?? 0) + 1;
    }
  }
  const rankTop: number[] = [];
  const gaps: Layout["gaps"] = [];
  let y = opts.origin.y;
  for (let r = 0; r < layers.length; r += 1) {
    rankTop.push(y);
    const need = Math.max(opts.rankGap, 2 * LANE_MARGIN + (lanes[r] ?? 0) * LANE);
    gaps.push({
      top: y + opts.nodeHeight,
      bottom: y + opts.nodeHeight + need,
      lanes: lanes[r] ?? 0,
    });
    y += opts.nodeHeight + need;
  }
  const kindOf = new Map(nodes.map((n) => [n.id, n.kind]));
  const laid: LaidOutNode[] = [];
  for (const [r, layer] of layers.entries()) {
    for (const [i, id] of layer.entries()) {
      const at = saved[id];
      laid.push({
        id,
        kind: kindOf.get(id) ?? "entity",
        x: at?.x ?? opts.origin.x + i * (opts.nodeWidth + opts.columnGap),
        y: at?.y ?? rankTop[r] ?? opts.origin.y,
        width: opts.nodeWidth,
        height: opts.nodeHeight,
        rank: r,
        order: i,
        saved: at !== undefined,
      });
    }
  }
  laid.sort((a, b) => a.rank - b.rank || a.order - b.order);
  const width = Math.max(0, ...laid.map((n) => n.x + n.width)) + opts.origin.x;
  const height = Math.max(y, ...laid.map((n) => n.y + n.height + LANE_MARGIN));
  return { nodes: laid, rankTop, gaps, options: opts, width, height };
}

/** Orthogonal routes and label pills for the layout's edges (file header). */
export function routeOrthogonal(layout: Layout, edges: readonly GraphEdgeIn[]): EdgeRoute[] {
  const { nodeWidth, columnGap, origin } = layout.options;
  const node = new Map(layout.nodes.map((n) => [n.id, n]));
  const nextLane = layout.gaps.map(() => 0);
  const laneY = (gap: number): number => {
    const g = layout.gaps[gap];
    const lane = nextLane[gap] ?? 0;
    nextLane[gap] = lane + 1;
    return (g?.top ?? 0) + LANE_MARGIN + lane * LANE + LANE / 2;
  };
  // The gutter (between two columns) nearest to x: no node sits in a gutter on an unsaved grid.
  const gutter = (x: number): number => {
    const step = nodeWidth + columnGap;
    const k = Math.round((x - origin.x + columnGap / 2) / step);
    return origin.x + k * step - columnGap / 2;
  };
  const out: EdgeRoute[] = [];
  const ordered = [...edges].sort((a, b) => {
    const ra = Math.min(node.get(a.from)?.rank ?? 0, node.get(a.to)?.rank ?? 0);
    const rb = Math.min(node.get(b.from)?.rank ?? 0, node.get(b.to)?.rank ?? 0);
    return ra - rb || byId(a, b);
  });
  for (const e of ordered) {
    const s = node.get(e.from);
    const t = node.get(e.to);
    if (s === undefined || t === undefined || s.id === t.id) continue; // walled: absent (DEC-43)
    const upper = s.rank <= t.rank ? s : t;
    const lower = upper === s ? t : s;
    const cx = (n: LaidOutNode): number => n.x + n.width / 2;
    let points: Point[];
    let runY: number;
    let runFrom: number;
    let runTo: number;
    if (upper.rank === lower.rank) {
      runY = laneY(upper.rank);
      points = [
        { x: cx(s), y: s.y + s.height },
        { x: cx(s), y: runY },
        { x: cx(t), y: runY },
        { x: cx(t), y: t.y + t.height },
      ];
      [runFrom, runTo] = [cx(s), cx(t)];
    } else if (lower.rank - upper.rank === 1) {
      runY = laneY(upper.rank);
      const a = { x: cx(upper), y: upper.y + upper.height };
      const b = { x: cx(lower), y: lower.y };
      const path = [a, { x: a.x, y: runY }, { x: b.x, y: runY }, b];
      points = upper === s ? path : [...path].reverse();
      [runFrom, runTo] = [a.x, b.x];
    } else {
      runY = laneY(upper.rank);
      const g = gutter(cx(lower));
      const second = laneY(lower.rank - 1);
      const a = { x: cx(upper), y: upper.y + upper.height };
      const b = { x: cx(lower), y: lower.y };
      const path = [
        a,
        { x: a.x, y: runY },
        { x: g, y: runY },
        { x: g, y: second },
        { x: b.x, y: second },
        b,
      ];
      points = upper === s ? path : [...path].reverse();
      [runFrom, runTo] = [a.x, g];
    }
    const width = pillWidth(e.label);
    out.push({
      id: e.id,
      kind: e.kind,
      points,
      label: {
        x: (runFrom + runTo) / 2 - width / 2,
        y: runY - PILL_HEIGHT / 2,
        width,
        height: PILL_HEIGHT,
      },
    });
  }
  return out;
}
