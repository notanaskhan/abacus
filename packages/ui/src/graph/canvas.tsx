// T14 GraphCanvas (F-07-T14; F-07 §G1, G3, G4; handoff T14 and TPL-14). The kit draws what L3 sends:
// nodes (180 × 56: type glyph, name, masked line; return nodes with a state pill; external nodes
// dashed), orthogonal edges by kind (ownership hairline, transfer dashed, draft K-1 dashed amber,
// released K-1 solid olive) with label pills, a hover trace (only the hovered node's edges darken,
// 200 ms, none under reduced motion), the zoom capsule with Fit, the legend, pan, and keyboard
// focus, select, open and nudge. It fetches nothing and decides nothing: select, open and layout
// changes are intents (`onSelect`, `onOpenRecord`, `onLayoutChange`; T-06 persists per user).
//
// Walls (DEC-43): a party L3 omits is simply absent, and its edges with it; there is no placeholder
// or count. A node line is server-composed and masked; a line that still holds a full TIN is not
// drawn (ADR-031, DEC-52). Firm-only: portal entries may not import `graph` (INV-4, F-07-T20).
import {
  type JSX,
  type KeyboardEvent,
  type PointerEvent,
  useCallback,
  useMemo,
  useRef,
  useState,
} from "react";
import { cn } from "../cn";
import { Pill } from "../components/pill";
import { Icon } from "../icons";
import type { IconName } from "../icons";
import type { PillVariant } from "../status";
import {
  type EdgeRoute,
  type GraphEdgeIn,
  type GraphNodeIn,
  type LaidOutNode,
  type Point,
  layoutLayered,
  routeOrthogonal,
} from "./layout";

export interface GraphCanvasNode extends GraphNodeIn {
  name: string;
  /** "LP · •••-••-4417": type and masked TIN, composed by the server. */
  line: string;
  /** Return nodes: the state pill on line 2 ("In review · Manager"). */
  state?: { label: string; variant: PillVariant } | null;
  /** Return nodes: a tag beside the state ("Waiting on K-1"). */
  tag?: string | null;
}

export interface GraphCanvasProps {
  nodes: readonly GraphCanvasNode[];
  edges: readonly GraphEdgeIn[];
  /** The viewer's saved positions; they win exactly. */
  saved?: Readonly<Record<string, Point>>;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  /** Shift+Enter or double-click: open the node's record (CLI-02, TAX-02, TXP-01). */
  onOpenRecord?: (id: string) => void;
  /** A move by keyboard nudge or drag: every moved node's new top-left. */
  onLayoutChange?: (positions: Record<string, Point>) => void;
  /** The specimen's hovered node (T14b), as if the pointer rested on it. */
  hoverId?: string | null;
  label?: string;
  className?: string;
}

export const NUDGE = 8;
export const ZOOM_MIN = 0.5;
export const ZOOM_MAX = 2;
const ZOOM_STEP = 0.1;
const FULL_TIN = /\b\d{3}-?\d{2}-?\d{4}\b|\b\d{2}-?\d{7}\b/;

const GLYPH: Readonly<Record<GraphNodeIn["kind"], IconName>> = {
  entity: "building-2",
  partnership: "landmark",
  person: "user",
  trust: "landmark",
  return: "file-text",
  external: "building-2",
};

/** A node line as drawn: masked text, or nothing when it still holds a full TIN. */
export function safeLine(line: string): string {
  return FULL_TIN.test(line) ? "" : line;
}

const EDGE_STROKE: Readonly<Record<GraphEdgeIn["kind"], string>> = {
  ownership: "stroke-stroke",
  role: "stroke-stroke",
  spouse: "stroke-stroke",
  taxpayer: "stroke-stroke",
  beneficiary: "stroke-stroke",
  transfer: "stroke-stroke",
  k1_draft: "stroke-amber",
  k1_released: "stroke-green",
};

function edgeDash(kind: GraphEdgeIn["kind"]): string | undefined {
  if (kind === "transfer") return "4 3";
  if (kind === "k1_draft") return "5 3";
  return undefined;
}

function pillFill(kind: GraphEdgeIn["kind"]): [string, string] {
  if (kind === "k1_draft") return ["fill-amber-tint", "fill-amber-ink"];
  if (kind === "k1_released") return ["fill-green-tint", "fill-green-ink"];
  return ["fill-shell", "fill-ink-2"];
}

function GraphEdge({
  route,
  label,
  dark,
  onHover,
}: {
  route: EdgeRoute;
  label: string;
  dark: boolean;
  onHover: (id: string | null) => void;
}): JSX.Element {
  const d = route.points
    .map((p, i) => `${i === 0 ? "M" : "L"}${String(p.x)} ${String(p.y)}`)
    .join(" ");
  const k1 = route.kind === "k1_draft" || route.kind === "k1_released";
  const [bg, ink] = pillFill(route.kind);
  return (
    <g
      data-edge={route.id}
      data-kind={route.kind}
      data-dark={dark ? "" : undefined}
      onMouseEnter={() => {
        onHover(route.id);
      }}
      onMouseLeave={() => {
        onHover(null);
      }}
    >
      <path
        d={d}
        fill="none"
        strokeWidth={k1 ? 1.5 : 1}
        strokeDasharray={edgeDash(route.kind)}
        className={cn(
          dark ? "stroke-ink-2" : EDGE_STROKE[route.kind],
          "motion-safe:transition-[stroke] motion-safe:duration-200",
        )}
      />
      <rect
        x={route.label.x}
        y={route.label.y}
        width={route.label.width}
        height={route.label.height}
        rx={route.label.height / 2}
        className={bg}
      />
      <text
        x={route.label.x + route.label.width / 2}
        y={route.label.y + route.label.height / 2}
        textAnchor="middle"
        dominantBaseline="central"
        className={cn("text-[11.5px]", ink)}
      >
        {label}
      </text>
    </g>
  );
}

function ZoomCapsule({
  zoom,
  onZoom,
  onFit,
}: {
  zoom: number;
  onZoom: (next: number) => void;
  onFit: () => void;
}): JSX.Element {
  const btn =
    "inline-flex h-[26px] min-w-[26px] items-center justify-center rounded-sheet text-ink-2 hover:bg-nested focus-visible:outline-[1.5px] focus-visible:outline-espresso";
  return (
    <div className="absolute bottom-[12px] left-[12px] flex items-center gap-[6px]">
      <div className="flex items-center gap-[2px] rounded-nested bg-card p-[2px] shadow-e1">
        <button
          type="button"
          aria-label="Zoom out"
          className={btn}
          disabled={zoom <= ZOOM_MIN}
          onClick={() => {
            onZoom(zoom - ZOOM_STEP);
          }}
        >
          <Icon name="minus" size={14} />
        </button>
        <span className="min-w-[40px] text-center text-[12px] text-ink-2" aria-live="polite">
          {`${String(Math.round(zoom * 100))}%`}
        </span>
        <button
          type="button"
          aria-label="Zoom in"
          className={btn}
          disabled={zoom >= ZOOM_MAX}
          onClick={() => {
            onZoom(zoom + ZOOM_STEP);
          }}
        >
          <Icon name="plus" size={14} />
        </button>
      </div>
      <button
        type="button"
        className={cn(btn, "bg-card px-[10px] text-[12px] shadow-e1")}
        onClick={onFit}
      >
        Fit
      </button>
    </div>
  );
}

function Swatch({ dash, className }: { dash?: string; className: string }): JSX.Element {
  return (
    <svg width="18" height="6" aria-hidden="true">
      <line
        x1="0"
        y1="3"
        x2="18"
        y2="3"
        strokeWidth={1.5}
        strokeDasharray={dash}
        className={className}
      />
    </svg>
  );
}

export function GraphLegend(): JSX.Element {
  return (
    <div className="absolute right-[12px] bottom-[12px] flex items-center gap-[8px] text-[11.5px] text-ink-3">
      <span className="inline-flex items-center gap-[4px]">
        <Swatch className="stroke-stroke" /> ownership
      </span>
      <span aria-hidden="true">·</span>
      <span className="inline-flex items-center gap-[4px]">
        <Swatch dash="4 3" className="stroke-stroke" /> transfer
      </span>
      <span aria-hidden="true">·</span>
      <span className="inline-flex items-center gap-[4px]">
        <Swatch dash="5 3" className="stroke-amber" /> K-1 flow
      </span>
    </div>
  );
}

function clampZoom(z: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z * 10) / 10));
}

/** The node the arrow key moves focus to: along the layer, or to the nearest node a layer away. */
export function neighbour(
  nodes: readonly LaidOutNode[],
  from: LaidOutNode,
  key: string,
): LaidOutNode | null {
  const cx = (n: LaidOutNode): number => n.x + n.width / 2;
  if (key === "ArrowLeft" || key === "ArrowRight") {
    const row = nodes
      .filter((n) => n.rank === from.rank)
      .sort((a, b) => a.x - b.x || (a.id < b.id ? -1 : 1));
    const i = row.findIndex((n) => n.id === from.id);
    return row[key === "ArrowLeft" ? i - 1 : i + 1] ?? null;
  }
  const want = from.rank + (key === "ArrowDown" ? 1 : -1);
  const row = nodes.filter((n) => n.rank === want);
  if (row.length === 0) return null;
  return (
    [...row].sort(
      (a, b) => Math.abs(cx(a) - cx(from)) - Math.abs(cx(b) - cx(from)) || (a.id < b.id ? -1 : 1),
    )[0] ?? null
  );
}

export function GraphCanvas({
  nodes,
  edges,
  saved,
  selectedId = null,
  onSelect,
  onOpenRecord,
  onLayoutChange,
  hoverId = null,
  label = "Relationships",
  className,
}: GraphCanvasProps): JSX.Element {
  const [moved, setMoved] = useState<Record<string, Point>>({});
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 });
  const [hovered, setHovered] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<{ kind: "pan" | "node"; id?: string; start: Point; origin: Point } | null>(
    null,
  );

  const positions = useMemo(() => ({ ...saved, ...moved }), [saved, moved]);
  const layout = useMemo(
    () => layoutLayered(nodes, edges, { saved: positions }),
    [nodes, edges, positions],
  );
  const routes = useMemo(() => routeOrthogonal(layout, edges), [layout, edges]);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const labelOf = useMemo(() => new Map(edges.map((e) => [e.id, e.label])), [edges]);
  const edgeEnds = useMemo(
    () => new Map(edges.map((e) => [e.id, [e.from, e.to] as const])),
    [edges],
  );
  const trace = hovered ?? hoverId;
  const lit = new Set(hoveredEdge === null ? [] : (edgeEnds.get(hoveredEdge) ?? []));
  const tabStop = focused ?? selectedId ?? layout.nodes[0]?.id ?? null;

  const move = useCallback(
    (id: string, to: Point): void => {
      setMoved((was) => {
        const next = { ...was, [id]: to };
        onLayoutChange?.(next);
        return next;
      });
    },
    [onLayoutChange],
  );

  const focusNode = (id: string): void => {
    setFocused(id);
    viewport.current?.querySelector<HTMLButtonElement>(`[data-node="${CSS.escape(id)}"]`)?.focus();
  };

  const onNodeKey = (n: LaidOutNode, e: KeyboardEvent<HTMLButtonElement>): void => {
    const arrow = e.key.startsWith("Arrow");
    if (arrow && e.altKey) {
      e.preventDefault();
      const dx = e.key === "ArrowLeft" ? -NUDGE : e.key === "ArrowRight" ? NUDGE : 0;
      const dy = e.key === "ArrowUp" ? -NUDGE : e.key === "ArrowDown" ? NUDGE : 0;
      move(n.id, { x: n.x + dx, y: n.y + dy });
    } else if (arrow) {
      e.preventDefault();
      const next = neighbour(layout.nodes, n, e.key);
      if (next !== null) focusNode(next.id);
    } else if (e.key === "Enter" && e.shiftKey) {
      e.preventDefault();
      onOpenRecord?.(n.id);
    } else if (e.key === "Enter") {
      e.preventDefault();
      onSelect?.(n.id);
    }
  };

  const fit = (): void => {
    const box = viewport.current;
    const w = box?.clientWidth ?? 0;
    const h = box?.clientHeight ?? 0;
    const scale = w > 0 && h > 0 ? Math.min(w / layout.width, h / layout.height) : 1;
    setZoom(clampZoom(scale));
    setPan({ x: 0, y: 0 });
  };

  const onPointerDown = (e: PointerEvent<HTMLDivElement>): void => {
    if (e.button !== 0) return;
    const target = (e.target as HTMLElement).closest<HTMLElement>("[data-node]");
    if (target !== null) {
      const id = target.dataset.node ?? "";
      const n = layout.nodes.find((x) => x.id === id);
      if (n !== undefined)
        drag.current = {
          kind: "node",
          id,
          start: { x: e.clientX, y: e.clientY },
          origin: { x: n.x, y: n.y },
        };
    } else if ((e.target as HTMLElement).closest("button") === null) {
      drag.current = { kind: "pan", start: { x: e.clientX, y: e.clientY }, origin: pan };
    }
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>): void => {
    const d = drag.current;
    if (d === null) return;
    const dx = e.clientX - d.start.x;
    const dy = e.clientY - d.start.y;
    if (d.kind === "pan") setPan({ x: d.origin.x + dx, y: d.origin.y + dy });
    else if (d.id !== undefined && Math.abs(dx) + Math.abs(dy) > 3)
      setMoved((was) => ({
        ...was,
        [d.id as string]: { x: d.origin.x + dx / zoom, y: d.origin.y + dy / zoom },
      }));
  };
  const onPointerUp = (): void => {
    const d = drag.current;
    drag.current = null;
    if (d?.kind === "node" && d.id !== undefined && moved[d.id] !== undefined)
      onLayoutChange?.(moved);
  };

  return (
    <div
      ref={viewport}
      role="group"
      aria-label={label}
      data-graph-canvas=""
      className={cn(
        "relative h-full min-h-[240px] w-full touch-none overflow-hidden bg-shell select-none",
        className,
      )}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
    >
      <div
        className="absolute top-0 left-0 origin-top-left"
        style={{
          width: layout.width,
          height: layout.height,
          transform: `translate(${String(pan.x)}px, ${String(pan.y)}px) scale(${String(zoom)})`,
        }}
      >
        <svg
          width={layout.width}
          height={layout.height}
          className="absolute inset-0 overflow-visible"
          aria-hidden="true"
        >
          {routes.map((r) => {
            const ends = edgeEnds.get(r.id);
            const dark =
              trace !== null && ends !== undefined && (ends[0] === trace || ends[1] === trace);
            return (
              <GraphEdge
                key={r.id}
                route={r}
                label={labelOf.get(r.id) ?? ""}
                dark={dark || hoveredEdge === r.id}
                onHover={setHoveredEdge}
              />
            );
          })}
        </svg>
        {layout.nodes.map((n) => {
          const data = byId.get(n.id);
          if (data === undefined) return null;
          const selected = n.id === selectedId;
          const isReturn = data.kind === "return";
          const external = data.kind === "external";
          const line = safeLine(data.line);
          return (
            <button
              key={n.id}
              type="button"
              data-node={n.id}
              data-kind={data.kind}
              data-lit={lit.has(n.id) ? "" : undefined}
              aria-pressed={selected}
              aria-label={line === "" ? data.name : `${data.name}, ${line}`}
              tabIndex={n.id === tabStop ? 0 : -1}
              className={cn(
                "absolute flex flex-col justify-center gap-[2px] rounded-nested px-[10px] py-[8px] text-left outline-none",
                isReturn ? "bg-shell inset-shadow-hair" : "bg-card shadow-e1",
                external && "border-[1px] border-dashed border-stroke bg-card shadow-none",
                selected && "inset-shadow-[0_0_0_1.5px_var(--color-espresso)]",
                lit.has(n.id) && "inset-shadow-[0_0_0_1px_var(--color-ink-2)]",
                "focus-visible:outline-[1.5px] focus-visible:outline-offset-2 focus-visible:outline-espresso",
              )}
              style={{ left: n.x, top: n.y, width: n.width, height: n.height }}
              onClick={() => {
                setFocused(n.id);
                onSelect?.(n.id);
              }}
              onDoubleClick={() => onOpenRecord?.(n.id)}
              onFocus={() => {
                setFocused(n.id);
              }}
              onKeyDown={(e) => {
                onNodeKey(n, e);
              }}
              onMouseEnter={() => {
                setHovered(n.id);
              }}
              onMouseLeave={() => {
                setHovered(null);
              }}
            >
              <span className="flex min-w-0 items-center gap-[6px]">
                <Icon
                  name={GLYPH[data.kind]}
                  size={15}
                  className={external ? "text-ink-3" : "text-ink-2"}
                />
                <span
                  className={cn(
                    "truncate text-[13px] font-medium",
                    external ? "text-ink-3" : "text-ink",
                  )}
                >
                  {data.name}
                </span>
              </span>
              <span className="flex min-w-0 items-center gap-[6px]">
                {isReturn && data.state ? (
                  <Pill variant={data.state.variant} size="micro">
                    {data.state.label}
                  </Pill>
                ) : null}
                {isReturn && data.tag ? (
                  <Pill variant="tag" size="micro">
                    {data.tag}
                  </Pill>
                ) : null}
                {line === "" || (isReturn && data.state) ? null : (
                  <span className="truncate text-[11.5px] text-ink-3">{line}</span>
                )}
              </span>
            </button>
          );
        })}
      </div>
      <ZoomCapsule
        zoom={zoom}
        onZoom={(z) => {
          setZoom(clampZoom(z));
        }}
        onFit={fit}
      />
      <GraphLegend />
    </div>
  );
}
