// TPL-14 "Graph canvas specimen — Ridgeline relationships" (F-07-T17; handoff TPL-14 spec.md a–f;
// F-07 §G1). Olivia Brandt is the viewer (F-07 §3), Mon Sep 14, 2026, 9:24 AM CT. Words and figures
// are the handoff's; ownership ties to blueprint §9.3 (2 + 38 + 30 + 5 + 25 = 100 at year end) and
// Jonah Feld's draft K-1 band to TXP-05/TXP-12 (307,900 · 4,600 · 1,550 · 150,000; ending capital
// as drafted 1,912,500). Data in: the specimen computes nothing but the tie tests.
import type { GraphCanvasNode } from "../graph/canvas";
import type { GraphEdgeIn, Point } from "../graph/layout";
import type { DependencyBanner, GraphInspector, RelationshipRow } from "../templates/graph-layout";
import { TPL14_EDGES, TPL14_FACES, TPL14_NODES, TPL14_SAVED } from "./fixtures/tpl-14";

export const TPL14_VIEWER = "olivia-brandt";
export const TPL14_CLOCK = "2026-09-14T09:24:00-05:00";

/** Year-end ownership of Ridgeline (blueprint §9.3). */
export const TPL14_OWNERSHIP: Readonly<Record<string, number>> = {
  "ridgeline-gp": 2,
  "meera-shah": 38,
  "pell-street-ventures": 30,
  "pell-street-ii": 5,
  "jonah-feld": 25,
};

export function ridgelineNodes(): GraphCanvasNode[] {
  return TPL14_NODES.map((n) => {
    const face = TPL14_FACES[n.id];
    return {
      ...n,
      name: face?.name ?? n.id,
      line: face?.line ?? "",
      ...(face?.state ? { state: face.state } : {}),
      ...(face?.tag ? { tag: face.tag } : {}),
    };
  });
}

export const RIDGELINE_EDGES: readonly GraphEdgeIn[] = TPL14_EDGES;
export const RIDGELINE_SAVED: Readonly<Record<string, Point>> = TPL14_SAVED;

/** f: after Ridgeline's approval the K-1 flow edges are released (solid olive). */
export function releasedEdges(): GraphEdgeIn[] {
  return TPL14_EDGES.map((e) =>
    e.kind === "k1_draft" ? { ...e, kind: "k1_released", label: "Released Sep 15" } : e,
  );
}

export const BANNER_AT_RISK: DependencyBanner = {
  tone: "at_risk",
  text: "Ridgeline 1065 → 2 K-1s at risk: Feld 1040 holds a draft K-1 · Shah 1040 is waiting on its K-1 · final pending Ridgeline partner approval (due Sep 15)",
};

export const BANNER_RELEASED: DependencyBanner = {
  tone: "released",
  text: "K-1s released Sep 15 · Feld and Shah 1040s updated",
};

/** Jonah Feld's draft K-1 from Ridgeline (TY2025), as the server sends it. */
export const FELD_K1 = [
  { key: "box2", label: "Box 2 Net rental real estate income", amount: "307900" },
  { key: "box5", label: "Box 5 Interest", amount: "4600" },
  { key: "box18a", label: "Box 18A Tax-exempt interest", amount: "1550" },
  { key: "box19a", label: "Box 19A Distributions", amount: "150000" },
  { key: "ending", label: "Ending capital (as drafted)", amount: "1912500" },
] as const;

export function feldInspector(released = false): GraphInspector {
  return {
    title: "Jonah Feld",
    sub: "Person · Brooklyn, NY",
    icon: "user",
    tin: "•••-••-4417",
    kv: [
      {
        key: "roles",
        label: "Roles",
        lines: ["LP 25.0000% · Ridgeline", "Taxpayer · Feld Household (MFJ with Claire Feld)"],
      },
      { key: "portal", label: "Portal", lines: ["Taxpayer & K-1 recipient (role union)"] },
    ],
    k1: {
      title: "TY2025 K-1 from Ridgeline",
      rows: FELD_K1,
      status: released
        ? { text: "Released Sep 15", tone: "green", sub: "→ Feld 1040 · updated" }
        : { text: "Draft K-1 · pre-release", tone: "amber", sub: "→ Feld 1040 · draft" },
    },
    linked: [
      { id: "feld-1040", title: "2025 Form 1040 · Feld ›" },
      { id: "ridgeline-1065", title: "2025 Form 1065 · Ridgeline ›" },
      { id: "cost-seg", title: "Ridgeline cost segregation & §754 analysis · Scoping ›" },
    ],
  };
}

/** b: the list view (T1 grammar). */
export const RIDGELINE_LIST: readonly RelationshipRow[] = [
  {
    id: "gp-lp",
    from: "Ridgeline GP LLC",
    relationship: "2% GP",
    to: "Ridgeline Property Partners, LP",
    since: "1/1/2019",
    source: "Partnership agreement",
  },
  {
    id: "shah-lp",
    from: "Meera Shah",
    relationship: "38% LP",
    to: "Ridgeline Property Partners, LP",
    since: "1/1/2019",
    source: "Partnership agreement",
  },
  {
    id: "psv-lp",
    from: "Pell Street Ventures LLC",
    relationship: "30% LP (35% to 6/30/2025)",
    to: "Ridgeline Property Partners, LP",
    since: "1/1/2019",
    source: "Partnership agreement",
  },
  {
    id: "psv-ps2",
    from: "Pell Street Ventures LLC",
    relationship: "Sold 5 points ($360,000)",
    to: "Pell Street II LLC",
    since: "6/30/2025",
    source: "Assignment agreement (requested)",
  },
  {
    id: "ps2-lp",
    from: "Pell Street II LLC",
    relationship: "5% LP from 7/1/2025",
    to: "Ridgeline Property Partners, LP",
    since: "7/1/2025",
    source: "Assignment agreement (requested)",
  },
  {
    id: "feld-lp",
    from: "Jonah Feld",
    relationship: "25% LP",
    to: "Ridgeline Property Partners, LP",
    since: "1/1/2019",
    source: "Partnership agreement",
  },
  {
    id: "spouse",
    from: "Claire Feld",
    relationship: "Spouse",
    to: "Jonah Feld",
    since: "—",
    source: "Client record",
  },
];

/** c: the trust variant (Calloway Family Trust). */
export const TRUST_NODES: readonly GraphCanvasNode[] = [
  { id: "eleanor", kind: "person", name: "Eleanor Calloway", line: "Trustee · •••-••-1188" },
  { id: "trust", kind: "trust", name: "Calloway Family Trust", line: "Form 1041 · ••-•••5530" },
  { id: "nora", kind: "person", name: "Nora Calloway", line: "Beneficiary · •••-••-2074" },
  { id: "theo", kind: "person", name: "Theo Calloway", line: "Beneficiary · •••-••-2091" },
  {
    id: "harborline",
    kind: "entity",
    name: "Harborline Trust Company",
    line: "Custodian · ••-•••6602",
  },
];
export const TRUST_EDGES: readonly GraphEdgeIn[] = [
  { id: "trustee", from: "eleanor", to: "trust", kind: "role", label: "Trustee" },
  { id: "nora-b", from: "trust", to: "nora", kind: "k1_released", label: "K-1 (1041) · Prepared" },
  { id: "theo-b", from: "trust", to: "theo", kind: "k1_released", label: "K-1 (1041) · Prepared" },
  { id: "custodian", from: "harborline", to: "trust", kind: "role", label: "Custodian" },
];

/** d: an upper-tier entity the firm does not serve (dashed, ink-3). */
export const EXTERNAL_NODE: GraphCanvasNode = {
  id: "upper-tier",
  kind: "external",
  name: "Pell Street Holdings LP",
  line: "Not a Brightwater Hale client",
};
export const EXTERNAL_EDGE: GraphEdgeIn = {
  id: "upper-psv",
  from: "upper-tier",
  to: "pell-street-ventures",
  kind: "ownership",
  label: "100% member",
};

/** e: one entity, no relationships. */
export const SINGLE_NODE: GraphCanvasNode = {
  id: "lakeshore",
  kind: "entity",
  name: "Lakeshore Literacy Alliance",
  line: "501(c)(3) · ••-•••4410",
};
