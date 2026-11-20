// T-06-T40 (TASK-8836): CLI-03's relationship graphs in fixture mode, as
// `GET /v1/clients/{id}/relationship-graph` answers them (CLI-03 a–f, built from TPL-14 a–f: no CLI-03
// board exists, T-06-T68; DEC-32, DF-02). Names, masked lines and labels are the TPL-14 handoff's;
// ownership ties to blueprint §9.3 (2 + 38 + 30 + 5 + 25 = 100 at year end). Positions are Olivia
// Brandt's saved layout (`/users/me/graph-layouts`).
import type {
  RelationshipEdgeOut,
  RelationshipGraphOut,
  RelationshipNodeOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type GraphVariant = "ridgeline" | "trust" | "external" | "single" | "released";
export const RIDGELINE_CLIENT_ID = stableId("client:ridgeline");
export const CALLOWAY_CLIENT_ID = stableId("client:calloway");

type N = readonly [
  id: string,
  kind: RelationshipNodeOut["kind"],
  label: string,
  sub: string,
  x: number,
  y: number,
  state?: string,
];

const RIDGELINE_NODES: readonly N[] = [
  ["owen-calder", "client", "Owen Calder", "Person · Managing member", 24, 150],
  [
    "ridgeline-lp",
    "entity",
    "Ridgeline Property Partners, LP",
    "Form 1065 · ••-•••0287",
    428,
    150,
  ],
  ["ridgeline-gp", "entity", "Ridgeline GP LLC", "GP · ••-•••0291", 24, 320],
  ["meera-shah", "client", "Meera Shah", "LP · •••-••-3352", 232, 320],
  ["pell-street-ventures", "entity", "Pell Street Ventures LLC", "LP · ••-•••7724", 440, 320],
  ["pell-street-ii", "entity", "Pell Street II LLC", "LP from 7/1/2025 · ••-•••8810", 648, 320],
  ["jonah-feld", "client", "Jonah Feld", "LP · •••-••-4417", 836, 320],
  ["shah-1040", "return", "Meera Shah · 2025 Form 1040", "Return", 232, 500, "Preparing"],
  ["claire-feld", "client", "Claire Feld", "Spouse · •••-••-6081", 636, 500],
  ["feld-1040", "return", "Feld Household · 2025 Form 1040 MFJ", "Return", 836, 500, "In review"],
];

type E = readonly [
  id: string,
  from: string,
  to: string,
  kind: RelationshipEdgeOut["kind"],
  label: string,
  rk: RelationshipEdgeOut["relationship_kind"] | null,
  percent: string | null,
  since: string,
  source: RelationshipEdgeOut["source"],
];

const RIDGELINE_EDGES: readonly E[] = [
  [
    "gp-lp",
    "ridgeline-gp",
    "ridgeline-lp",
    "relationship",
    "2% GP",
    "gp_of",
    "2",
    "2019-01-01",
    "person",
  ],
  [
    "shah-lp",
    "meera-shah",
    "ridgeline-lp",
    "relationship",
    "38% LP",
    "lp_of",
    "38",
    "2019-01-01",
    "person",
  ],
  [
    "psv-lp",
    "pell-street-ventures",
    "ridgeline-lp",
    "relationship",
    "30% LP (35% to 6/30/2025)",
    "lp_of",
    "30",
    "2019-01-01",
    "person",
  ],
  [
    "ps2-lp",
    "pell-street-ii",
    "ridgeline-lp",
    "relationship",
    "5% LP from 7/1/2025",
    "lp_of",
    "5",
    "2025-07-01",
    "person",
  ],
  [
    "feld-lp",
    "jonah-feld",
    "ridgeline-lp",
    "relationship",
    "25% LP",
    "lp_of",
    "25",
    "2019-01-01",
    "person",
  ],
  [
    "owen-gp",
    "owen-calder",
    "ridgeline-gp",
    "relationship",
    "Managing member",
    "owner_of",
    null,
    "2019-01-01",
    "intake",
  ],
  [
    "shah-k1",
    "meera-shah",
    "shah-1040",
    "k1",
    "Draft K-1 · pre-release",
    null,
    null,
    "2026-09-11",
    "k1_package",
  ],
  [
    "feld-k1",
    "jonah-feld",
    "feld-1040",
    "k1",
    "Draft K-1 · pre-release",
    null,
    null,
    "2026-09-11",
    "k1_package",
  ],
  [
    "spouse",
    "claire-feld",
    "jonah-feld",
    "relationship",
    "Spouse",
    "spouse",
    null,
    "2012-06-02",
    "intake",
  ],
];

const TRUST_NODES: readonly N[] = [
  ["eleanor-calloway", "client", "Eleanor Calloway", "Trustee · •••-••-1188", 120, 150],
  ["calloway-trust", "entity", "Calloway Family Trust", "Form 1041 · ••-•••5530", 428, 150],
  ["nora-calloway", "client", "Nora Calloway", "Beneficiary · •••-••-2074", 300, 320],
  ["theo-calloway", "client", "Theo Calloway", "Beneficiary · •••-••-2091", 556, 320],
  ["harborline", "entity", "Harborline Trust Company", "Custodian · ••-•••6602", 736, 150],
];
const TRUST_EDGES: readonly E[] = [
  [
    "trustee",
    "eleanor-calloway",
    "calloway-trust",
    "relationship",
    "Trustee",
    "trustee_of",
    null,
    "2016-03-01",
    "person",
  ],
  [
    "nora-b",
    "calloway-trust",
    "nora-calloway",
    "relationship",
    "Beneficiary · discretionary",
    "beneficiary_of",
    null,
    "2016-03-01",
    "person",
  ],
  [
    "theo-b",
    "calloway-trust",
    "theo-calloway",
    "relationship",
    "Beneficiary · discretionary",
    "beneficiary_of",
    null,
    "2016-03-01",
    "person",
  ],
  [
    "nora-k1",
    "calloway-trust",
    "nora-calloway",
    "k1",
    "K-1 (1041) · Prepared",
    null,
    null,
    "2026-09-10",
    "k1_package",
  ],
  [
    "theo-k1",
    "calloway-trust",
    "theo-calloway",
    "k1",
    "K-1 (1041) · Prepared",
    null,
    null,
    "2026-09-10",
    "k1_package",
  ],
  [
    "custodian",
    "harborline",
    "calloway-trust",
    "relationship",
    "Custodian",
    "owner_of",
    null,
    "2016-03-01",
    "person",
  ],
];

function node([id, kind, label, sub, x, y, state]: N, external = false): RelationshipNodeOut {
  return {
    node_id: id,
    kind,
    label,
    sublabel: sub,
    x: String(x),
    y: String(y),
    external,
    return_state: state ?? null,
  };
}

function edge(
  [id, from, to, kind, label, rk, percent, since, source]: E,
  released: boolean,
): RelationshipEdgeOut {
  const k1 = kind === "k1";
  return {
    edge_id: id,
    from_node_id: from,
    to_node_id: to,
    kind,
    label: k1 && released ? "Released Sep 15" : label,
    relationship_kind: rk ?? null,
    percent,
    since,
    source,
    state: k1 ? (released ? "released" : "draft") : null,
    version: 1,
  };
}

export function graph(variant: GraphVariant): RelationshipGraphOut {
  if (variant === "trust") {
    return {
      client_id: CALLOWAY_CLIENT_ID,
      nodes: TRUST_NODES.map((n) => node(n)),
      edges: TRUST_EDGES.map((e) => edge(e, false)),
      banner: null,
    };
  }
  if (variant === "single") {
    return {
      client_id: stableId("client:lakeshore"),
      nodes: [
        node([
          "lakeshore",
          "entity",
          "Lakeshore Literacy Alliance",
          "501(c)(3) · ••-•••4410",
          428,
          150,
        ]),
      ],
      edges: [],
      banner: null,
    };
  }
  const released = variant === "released";
  const nodes = RIDGELINE_NODES.map((n) => node(n));
  const edges = RIDGELINE_EDGES.map((e) => edge(e, released));
  if (variant === "external") {
    nodes.push(
      node(
        [
          "pell-street-holdings",
          "external_party",
          "Pell Street Holdings LP",
          "Not a Brightwater Hale client",
          440,
          24,
        ],
        true,
      ),
    );
    edges.push(
      edge(
        [
          "upper-psv",
          "pell-street-holdings",
          "pell-street-ventures",
          "relationship",
          "100% member",
          "upper_tier_of",
          "100",
          "2018-01-01",
          "person",
        ],
        false,
      ),
    );
  }
  return {
    client_id: RIDGELINE_CLIENT_ID,
    nodes,
    edges,
    selected_node_id: variant === "ridgeline" || released ? "jonah-feld" : null,
    banner: released
      ? { tone: "green", text: "K-1s released Sep 15 · Feld and Shah 1040s updated" }
      : {
          tone: "amber",
          text: "Ridgeline 1065 → 2 K-1s at risk: Feld 1040 holds a draft K-1 · Shah 1040 is waiting on its K-1 · final pending Ridgeline partner approval (due Sep 15)",
        },
  };
}
