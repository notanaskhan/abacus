// CLI-03 · Relationships & household map (T-06-T40; docs/screens/CLI-03.md; T-06 §3 F5; built from
// TPL-14 a–f, no CLI-03 board: T-06-T68, DEC-32, DF-02). The T14 GraphCanvasLayout over the
// client's graph (`GET /v1/clients/{id}/relationship-graph`): the canvas (every node reachable by
// keyboard; a walled node is simply absent, the server leaves it out), the List view with the same
// relationships, the amber or green dependency banner, the dashed external node, the single-entity
// empty state and the trust variant; the 330 inspector with the masked TIN and Reveal (logged), the
// roles and the linked work; Add relationship… (O3), edit and end; the viewer's layout saved per
// user. Data in, intents out: the screen computes no figure (ADR-050). Firm-only (INV-4).
import type {
  RelationshipEdgeOut,
  RelationshipGraphOut,
  RelationshipNodeOut,
} from "@abacus/api-client";
import {
  Button,
  GraphCanvasLayout,
  type GraphInspector,
  type GraphView,
  Picker,
  type RelationshipRow,
  SheetModal,
} from "@abacus/ui";
import { GraphCanvas, type GraphCanvasNode, type GraphEdgeIn, type Point } from "@abacus/ui/graph";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

const TIN = /(?:•••-••-\d{4}|••-•••\d{4})/u;

export function nodeKind(n: RelationshipNodeOut): GraphCanvasNode["kind"] {
  if (n.kind === "external_party") return "external";
  if (n.kind === "return") return "return";
  if (n.kind === "client") return "person";
  const sub = n.sublabel ?? "";
  if (sub.startsWith("Form 1065")) return "partnership";
  if (sub.startsWith("Form 1041")) return "trust";
  return "entity";
}

export function edgeKind(e: RelationshipEdgeOut): GraphEdgeIn["kind"] {
  if (e.kind === "k1") return e.state === "released" ? "k1_released" : "k1_draft";
  if (e.relationship_kind === "spouse") return "spouse";
  if (e.relationship_kind === "beneficiary_of") return "beneficiary";
  if (e.relationship_kind === "trustee_of" || e.relationship_kind === "executor_of") return "role";
  return "ownership";
}

export function canvasNodes(g: RelationshipGraphOut): GraphCanvasNode[] {
  return g.nodes.map((n) => ({
    id: n.node_id,
    kind: nodeKind(n),
    name: n.label,
    line: n.sublabel ?? "", // an external party's line ("Not a … client") is the server's
    ...(n.return_state ? { state: { label: n.return_state, variant: "neutral" as const } } : {}),
  }));
}

export function canvasEdges(g: RelationshipGraphOut): GraphEdgeIn[] {
  return g.edges.map((e) => ({
    id: e.edge_id,
    from: e.from_node_id,
    to: e.to_node_id,
    kind: edgeKind(e),
    label: e.label,
  }));
}

export function savedLayout(g: RelationshipGraphOut): Record<string, Point> {
  const out: Record<string, Point> = {};
  for (const n of g.nodes) {
    if (n.x != null && n.y != null) out[n.node_id] = { x: Number(n.x), y: Number(n.y) };
  }
  return out;
}

const day = (iso: string | null | undefined): string => {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${String(Number(m))}/${String(Number(d))}/${y ?? ""}`;
};

export function listRows(g: RelationshipGraphOut): RelationshipRow[] {
  const name = new Map(g.nodes.map((n) => [n.node_id, n.label]));
  return g.edges.map((e) => ({
    id: e.edge_id,
    from: name.get(e.from_node_id) ?? "",
    relationship: e.label,
    to: name.get(e.to_node_id) ?? "",
    since: day(e.since),
    source: COPY.source[e.source],
  }));
}

export function inspectorOf(g: RelationshipGraphOut, id: string | null): GraphInspector | null {
  const n = g.nodes.find((x) => x.node_id === id);
  if (n === undefined) return null;
  const name = new Map(g.nodes.map((x) => [x.node_id, x]));
  const touching = g.edges.filter(
    (e) => e.from_node_id === n.node_id || e.to_node_id === n.node_id,
  );
  const roles = touching
    .filter((e) => e.kind === "relationship")
    .map((e) => {
      const other = name.get(e.from_node_id === n.node_id ? e.to_node_id : e.from_node_id);
      return `${e.label} · ${other?.label ?? ""}`;
    });
  const linked = touching
    .map((e) => name.get(e.from_node_id === n.node_id ? e.to_node_id : e.from_node_id))
    .filter((o): o is RelationshipNodeOut => o !== undefined && o.kind === "return")
    .map((o) => ({ id: o.node_id, title: `${o.label} ›` }));
  const kind = nodeKind(n);
  return {
    title: n.label,
    sub: (n.sublabel ?? "").replace(TIN, "").replace(/ · $/u, ""),
    icon: kind === "person" ? "user" : kind === "return" ? "file-text" : "building-2",
    tin: (n.sublabel ?? "").match(TIN)?.[0] ?? null,
    kv: roles.length ? [{ key: "roles", label: COPY.roles, lines: roles }] : [],
    linked,
  };
}

export interface CLI03Props {
  graph: RelationshipGraphOut | undefined;
  view: GraphView;
  onView?: (v: GraphView) => void;
  selected: string | null;
  onSelect?: (id: string) => void;
  canReveal?: boolean;
  onReveal?: () => Promise<string | null>;
  onLayout?: (positions: Record<string, Point>) => void;
  onAdd?: (body: {
    from: string;
    to: string;
    kind: keyof typeof COPY.kinds;
    percent: string | null;
    effectiveFrom: string;
  }) => void;
  onEnd?: (edgeId: string, reason: string) => void;
  /** a test or an artboard: the sheet open on arrival. */
  sheet?: "add" | "edit" | null;
}

export function CLI03({
  graph,
  view,
  onView,
  selected,
  onSelect,
  canReveal = false,
  onReveal,
  onLayout,
  onAdd,
  onEnd,
  sheet: initialSheet = null,
}: CLI03Props): JSX.Element {
  const [sheet, setSheet] = useState<"add" | "edit" | null>(initialSheet);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [kind, setKind] = useState<keyof typeof COPY.kinds>("owner_of");
  const [percent, setPercent] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [reason, setReason] = useState("");
  if (graph === undefined) {
    return <div data-screen="CLI-03" aria-busy="true" className="flex-1" />;
  }
  const people = graph.nodes.map((n) => ({ value: n.node_id, label: n.label }));
  const mine = graph.edges.filter(
    (e) => e.kind === "relationship" && (e.from_node_id === selected || e.to_node_id === selected),
  );
  const single = graph.nodes.length === 1 && graph.edges.length === 0;
  const banner = graph.banner
    ? {
        tone: graph.banner.tone === "green" ? ("released" as const) : ("at_risk" as const),
        text: graph.banner.text,
      }
    : null;
  return (
    <div data-screen="CLI-03" className="relative flex min-h-0 flex-1 flex-col">
      <GraphCanvasLayout
        view={view}
        {...(onView === undefined ? {} : { onView })}
        banner={banner}
        single={single}
        rows={listRows(graph)}
        inspector={inspectorOf(graph, selected)}
        canReveal={canReveal}
        {...(onReveal === undefined ? {} : { onReveal })}
        onAddRelationship={() => {
          setSheet("add");
        }}
        subbar={
          selected !== null && mine.length > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              opensDialog
              onClick={() => {
                setSheet("edit");
              }}
            >
              {COPY.edit}
            </Button>
          ) : undefined
        }
        canvas={
          <GraphCanvas
            nodes={canvasNodes(graph)}
            edges={canvasEdges(graph)}
            saved={savedLayout(graph)}
            selectedId={selected}
            {...(onSelect === undefined ? {} : { onSelect })}
            {...(onLayout === undefined ? {} : { onLayoutChange: onLayout })}
            label={COPY.canvas}
          />
        }
      />
      <SheetModal
        open={sheet === "add"}
        onOpenChange={(o) => {
          setSheet(o ? "add" : null);
        }}
        title={COPY.add}
        action={
          <Button
            variant="primary"
            disabled={from === "" || to === "" || from === to || effectiveFrom === ""}
            onClick={() => {
              onAdd?.({ from, to, kind, percent: percent === "" ? null : percent, effectiveFrom });
              setSheet(null);
            }}
          >
            {COPY.save}
          </Button>
        }
      >
        <div className="flex flex-col gap-[10px] p-[16px]">
          <Picker label={COPY.from} value={from} onChange={setFrom} options={people} />
          <Picker
            label={COPY.kind}
            value={kind}
            onChange={(v) => {
              setKind(v as keyof typeof COPY.kinds);
            }}
            options={Object.entries(COPY.kinds).map(([value, label]) => ({ value, label }))}
          />
          <Picker label={COPY.toPerson} value={to} onChange={setTo} options={people} />
          <label className="flex flex-col gap-[4px] text-dense text-ink-2">
            {COPY.percent}
            <input
              inputMode="decimal"
              value={percent}
              onChange={(e) => {
                setPercent(e.target.value);
              }}
              className="h-[32px] rounded-[8px] bg-card px-[8px] text-body text-ink shadow-e1"
            />
          </label>
          <label className="flex flex-col gap-[4px] text-dense text-ink-2">
            {COPY.effectiveFrom}
            <input
              type="date"
              value={effectiveFrom}
              onChange={(e) => {
                setEffectiveFrom(e.target.value);
              }}
              className="h-[32px] rounded-[8px] bg-card px-[8px] text-body text-ink shadow-e1"
            />
          </label>
        </div>
      </SheetModal>
      <SheetModal
        open={sheet === "edit"}
        onOpenChange={(o) => {
          setSheet(o ? "edit" : null);
        }}
        title={COPY.edit}
        action={
          <Button
            variant="primary"
            onClick={() => {
              setSheet(null);
            }}
          >
            {COPY.close}
          </Button>
        }
      >
        <label className="mx-[16px] mt-[16px] flex flex-col gap-[4px] text-dense text-ink-2">
          {COPY.reason}
          <input
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
            }}
            className="h-[32px] rounded-[8px] bg-card px-[8px] text-body text-ink shadow-e1"
          />
        </label>
        <ul className="flex flex-col gap-[6px] p-[16px]">
          {mine.map((e) => (
            <li
              key={e.edge_id}
              data-relationship={e.edge_id}
              className="flex items-center gap-[8px] text-body"
            >
              <span className="flex-1 text-ink">
                {listRows({ ...graph, edges: [e] })[0]?.relationship}
              </span>
              <span className="text-ink-3">{day(e.since)}</span>
              <Button
                variant="secondary"
                size="sm"
                disabled={reason.trim() === ""}
                onClick={() => onEnd?.(e.edge_id, reason.trim())}
              >
                {COPY.end}
              </Button>
            </li>
          ))}
        </ul>
      </SheetModal>
    </div>
  );
}
