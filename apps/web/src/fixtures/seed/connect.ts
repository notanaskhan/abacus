// Workbench › Connect on fixtures (W-01-T03; SPEC-659 AC-1 to AC-6; docs/screens/WB-10.md, WB-11.md).
// The tiles are the scenario's catalogue content (`connect-catalog.json`, a copy of
// backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/files/connect_catalog.json, the
// canvas `CX.items` list with Drata and Vanta published Oct 1 for E2; DF-35, DF-36). Counts are
// computed from the rows: status counts follow the filters, category counts are catalogue totals
// at the clock instant (AC-2). Typed with the generated C20 v2 shapes.
import type {
  ConnectCatalogOut,
  ConnectCategoryOut,
  ConnectTileOut,
  ConnectIntegrationDetailOut,
} from "@abacus/api-client";
import catalog from "./connect-catalog.json";

type Row = (typeof catalog.items)[number];
type Code = ConnectCategoryOut["code"];
type TileStatus = ConnectTileOut["status"];

export const E0 = "2026-09-14T09:24:00-05:00";
export const E2 = "2026-10-01T09:24:00-05:00";
export const AUG17 = "2026-08-17T09:05:00-05:00";
const TONE: Record<string, string> = {
  tax: "olive",
  erp: "olive",
  practice: "olive",
  docs: "clay",
  comms: "ochre",
  prod: "ochre",
  crm: "brick",
  spend: "brick",
  hris: "espresso",
  grc: "espresso",
};
const FELIX = "Felix Andersen";

export interface ConnectView {
  at?: string;
  viewer?: "felix-andersen" | "hannah-leclerc";
  category?: Code;
  status?: "connected" | "available" | "coming_soon";
  q?: string;
  /** Per-key status overrides for a state (connecting, needs_reauth). */
  overrides?: Readonly<Record<string, TileStatus>>;
}

const published = (row: Row, at: string): boolean =>
  Date.parse(row.published_at) <= Date.parse(at);

function kindOf(row: Row): ConnectTileOut["kind"] {
  if (row.kind === "personal") return "personal";
  return row.auth_line.startsWith("Firm app") ? "client_authorised" : "firm";
}

function tile(row: Row, view: ConnectView): ConnectTileOut {
  const admin = (view.viewer ?? "felix-andersen") === "felix-andersen";
  const status = (view.overrides?.[row.key] ?? row.status_e0) as TileStatus;
  const kind = kindOf(row);
  const firmTile = kind !== "personal";
  const actions: ConnectTileOut["allowed_actions"] = [];
  if (firmTile && admin)
    actions.push(
      status === "connected" ? "integration.disconnect_firm" : "integration.connect_firm",
    );
  if (!firmTile)
    actions.push(
      status === "connected" ? "integration.disconnect_personal" : "integration.connect_personal",
    );
  if (status === "coming_soon") actions.splice(0, actions.length, "integration.interest");
  const blocked =
    row.blocked_reason ??
    (firmTile && !admin && status !== "coming_soon" ? `${FELIX} manages firm connections.` : null);
  return {
    key: row.key,
    name: row.name,
    categories: row.categories as Code[],
    icon: row.categories[0] ?? "tax",
    tone: TONE[row.categories[0] ?? "tax"] ?? "olive",
    description: row.description,
    auth_line: row.auth_line,
    kind,
    status,
    viewer_status: status,
    connected_by_label:
      status === "connected" && kind === "firm" && row.auth_line.includes(FELIX) ? FELIX : null,
    blocked_reason: blocked,
    allowed_actions: actions,
  };
}

export function connectCatalog(view: ConnectView = {}): ConnectCatalogOut {
  const at = view.at ?? E0;
  const live = catalog.items
    .filter((r) => published(r, at))
    .sort((a, b) => a.sort_order - b.sort_order);
  const tiles = live.map((r) => tile(r, view));
  const q = (view.q ?? "").trim().toLowerCase();
  const label = (c: string) => catalog.categories.find((k) => k.code === c)?.label ?? c;
  const inCategory = tiles.filter(
    (t) => view.category === undefined || t.categories.includes(view.category),
  );
  const searched = inCategory.filter(
    (t) =>
      q === "" ||
      `${t.name} ${t.description} ${t.categories.map(label).join(" ")}`.toLowerCase().includes(q),
  );
  const items = searched.filter((t) => view.status === undefined || t.status === view.status);
  const count = (s: string) => searched.filter((t) => t.status === s).length;
  return {
    items,
    counts: {
      all: searched.length,
      connected: count("connected"),
      available: count("available"),
      coming_soon: count("coming_soon"),
    },
    categories: catalog.categories
      .map((c) => ({
        code: c.code as Code,
        label: c.label,
        description: c.description,
        count: tiles.filter((t) => t.categories.includes(c.code as Code)).length,
      }))
      .filter((c) => c.count > 0),
    total: tiles.length,
    build_on_accrued: [
      { key: "api_keys", label: "API keys & webhooks", target: "ADM-09", planned: true },
      { key: "mcp", label: "MCP for AI assistants", target: "ADM-09", planned: true },
      { key: "workflow_sync", label: "Workflow status sync", target: "ADM-08", planned: false },
    ],
  };
}

const EVENTS: ConnectIntegrationDetailOut["health"]["events"] = [
  { id: "e5", kind: "synced", at: "2026-09-14T09:02:00-05:00", label: "Synced", ok: true },
  {
    id: "e4",
    kind: "synced",
    at: "2026-09-11T16:18:00-05:00",
    label: "Export complete — 2025 Form 1065 · Harborview Dental Properties, LP",
    ok: true,
  },
  {
    id: "e3",
    kind: "synced",
    at: "2026-09-10T15:06:00-05:00",
    label: "Synced — 2025 Form 1040 · Jonah & Claire Feld",
    ok: true,
  },
  {
    id: "e2",
    kind: "reconnected",
    at: "2026-08-17T09:58:00-05:00",
    label: "Reconnected by Felix Andersen",
    ok: true,
  },
  {
    id: "e1",
    kind: "token_expired",
    at: "2026-08-17T09:00:00-05:00",
    label: "Token expired — 1 scheduled run failed (Season Progress Reporter)",
    ok: false,
  },
];
const AGENTS = [
  "Season Progress Reporter",
  "Return Drafter",
  "Return Review Packet",
  "Notice Intake & Response Drafter",
  "K-1 Reconciliation Workpaper",
];

/** WB-11 a (token mode, staging), c (needs reauth), f (non-admin), file bridge (real firms, AC-23). */
/** WB-11 d: QuickBooks Online, a client-ledger firm app (W-01-T19 end pass). Only what the
 * artboard and the catalogue row give: the auth line (WB-11 d verbatim) and the row's description;
 * no firm-side connect, no connection facts of the firm's own (each client authorizes its company). */
export function ledgerAppDetail(): ConnectIntegrationDetailOut {
  const row = catalog.items.find((r) => r.key === "qbo");
  return {
    key: "qbo",
    name: row?.name ?? "QuickBooks Online",
    status: "connected",
    status_line: null,
    connection: {
      mode: "firm_app",
      auth_mode_label: "Firm app · each client authorizes its own company",
      connected_by: null,
      connected_at: null,
      token_renews_at: null,
      last_sync_at: null,
      linked_count: null,
      linked_label_code: null,
      mapping_ref: null,
    },
    may_do: { read: [], write: [], never: [] },
    health: { summary: "", events: [] },
    dependents: { count: 0, paused: false, items: [] },
    who_can_use: row?.description ?? "",
    managed_by: null,
    consent: null,
    allowed_actions: [],
    version: 1,
  };
}

export function cchDetail(state: "a" | "c" | "f" | "file_bridge"): ConnectIntegrationDetailOut {
  const reauth = state === "c";
  const bridge = state === "file_bridge";
  return {
    key: "cch",
    name: "CCH Axcess Tax",
    status: reauth ? "needs_reauth" : "connected",
    status_line: reauth ? "Token expired at 9:00 AM · 1 run failed · 5 agents paused" : null,
    connection: {
      mode: bridge ? "file_bridge" : "token",
      auth_mode_label: bridge
        ? "File bridge · a person exports and imports"
        : "Firm connection · access token",
      connected_by: FELIX,
      connected_at: "2026-01-14T09:12:00-06:00",
      token_renews_at: bridge ? null : "2026-10-12T00:00:00-05:00",
      last_sync_at: "2026-09-14T09:02:00-05:00",
      linked_count: 224,
      linked_label_code: "returns_ty2025",
      mapping_ref: "2025I:FeldJ:V3",
    },
    may_do: {
      read: [],
      write: [],
      never: [
        {
          label: "E-file or change a return's status in CCH Axcess",
          gate_label: null,
          state: "never",
        },
      ],
    },
    health: {
      summary: reauth ? "Token expired at 9:00 AM" : "Synced · today 9:02 AM · 0 errors",
      events: reauth ? EVENTS.slice(4) : EVENTS,
    },
    dependents: {
      count: AGENTS.length,
      paused: reauth,
      items: AGENTS.map((name, i) => ({ key: `agent-${String(i)}`, name })),
    },
    who_can_use: "Everyone at Brightwater Hale with access to the return",
    managed_by: FELIX,
    consent: null,
    allowed_actions:
      state === "f" ? [] : reauth ? ["integration.connect_firm"] : ["integration.disconnect_firm"],
    version: 3,
  };
}
