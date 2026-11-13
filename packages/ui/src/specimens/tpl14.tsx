// TPL-14 "Graph canvas specimen — Ridgeline relationships" (F-07-T17; handoff TPL-14 a–f): six
// artboards on the T14 GraphCanvasLayout for Olivia Brandt, Mon Sep 14, 2026 9:24 AM CT.
//   a  Default graph, Jonah Feld selected      b  List view
//   c  Trust variant (Calloway Family Trust)   d  External node (not a firm client)
//   e  Single entity, no relationships         f  After Ridgeline's approval (K-1s released)
// Data in, intents out (tpl14-data.ts); the specimen computes nothing.
import { type JSX, useState } from "react";
import { GraphCanvas, type GraphCanvasNode } from "../graph/canvas";
import type { GraphEdgeIn } from "../graph/layout";
import { GraphCanvasLayout, type GraphView } from "../templates/graph-layout";
import { Artboard } from "./portal";
import {
  BANNER_AT_RISK,
  BANNER_RELEASED,
  EXTERNAL_EDGE,
  EXTERNAL_NODE,
  RIDGELINE_EDGES,
  RIDGELINE_LIST,
  RIDGELINE_SAVED,
  SINGLE_NODE,
  TRUST_EDGES,
  TRUST_NODES,
  feldInspector,
  releasedEdges,
  ridgelineNodes,
} from "./tpl14-data";

export type Tpl14State = "a" | "b" | "c" | "d" | "e" | "f";

interface Board {
  id: Tpl14State;
  name: string;
  note: string;
  view: GraphView;
  nodes: readonly GraphCanvasNode[];
  edges: readonly GraphEdgeIn[];
  selected?: string;
  banner?: "at_risk" | "released";
  single?: boolean;
}

export const TPL14_BOARDS: readonly Board[] = [
  { id: "a", name: "Default graph", note: "Jonah Feld selected; two K-1s at risk", view: "graph", nodes: ridgelineNodes(), edges: RIDGELINE_EDGES, selected: "jonah-feld", banner: "at_risk" },
  { id: "b", name: "List view", note: "From · Relationship · To · Since · Source", view: "list", nodes: ridgelineNodes(), edges: RIDGELINE_EDGES, banner: "at_risk" },
  { id: "c", name: "Trust variant", note: "Calloway Family Trust: trustee, beneficiaries, custodian", view: "graph", nodes: TRUST_NODES, edges: TRUST_EDGES },
  { id: "d", name: "External node", note: "An upper-tier entity the firm does not serve", view: "graph", nodes: [...ridgelineNodes(), EXTERNAL_NODE], edges: [...RIDGELINE_EDGES, EXTERNAL_EDGE], banner: "at_risk" },
  { id: "e", name: "Single entity", note: "No relationships yet", view: "graph", nodes: [SINGLE_NODE], edges: [], single: true },
  { id: "f", name: "After Ridgeline approval", note: "K-1s released Sep 15", view: "graph", nodes: ridgelineNodes(), edges: releasedEdges(), selected: "jonah-feld", banner: "released" },
];  // prettier-ignore

function Tpl14({ board }: { board: Board }): JSX.Element {
  const [view, setView] = useState<GraphView>(board.view);
  const [selected, setSelected] = useState<string | null>(board.selected ?? null);
  const inspector =
    selected === "jonah-feld" ? feldInspector(board.banner === "released") : null;
  return (
    <Artboard id={`tpl-14${board.id}`} badge={`TPL-14${board.id}`} name={board.name} note={board.note}>
      <div className="relative h-[800px] w-[1400px] bg-shell" data-tpl14={board.id}>
        <GraphCanvasLayout
          view={view}
          onView={setView}
          banner={board.banner === "at_risk" ? BANNER_AT_RISK : board.banner === "released" ? BANNER_RELEASED : null}
          single={board.single === true}
          rows={RIDGELINE_LIST}
          inspector={inspector}
          canReveal
          onReveal={async () => null}
          canvas={
            <GraphCanvas
              nodes={board.nodes}
              edges={board.edges}
              {...(board.id === "c" || board.id === "e" ? {} : { saved: RIDGELINE_SAVED })}
              selectedId={selected}
              onSelect={setSelected}
              label="Relationships"
            />
          }
        />
      </div>
    </Artboard>
  );
}

export function Tpl14Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-[24px]">
      {TPL14_BOARDS.map((b) => (
        <Tpl14 key={b.id} board={b} />
      ))}
    </div>
  );
}
