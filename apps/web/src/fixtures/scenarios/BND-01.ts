// BND-01 binders index: one fixture scenario per artboard P-06-T09 builds (a, c, d, e; b and the
// follow-up sheet are P-06-T16's). All four stand at E0, Mon Sep 14, 2026, 9:24 AM CT. Data:
// fixtures/seed/binders.ts. `GET /v1/binders` is still the C5 stub (501) until P-06-T11, so these
// handlers answer it in the contract's shape (`ListPage[BinderRowOut]`) and apply the filters the
// read model will: status (the tile), q, season, service, office, preparer and client activity.
// `counts` are computed over the filters minus the tile, so a tile never counts itself out; `total`
// is the tile's count when one is set. Rows that the handoff does not name are counted, not listed.
//
// They live under fixtures/ (dev and test only); src/screens/BND-01/scenarios.ts re-exports them.

import type {
  BinderIn,
  BinderOut,
  BinderRowOut,
  BinderStatus,
  CapabilitiesOut,
  ListPageBinderRowOut,
  UnpublishIn,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  BINDER_ACTIONS,
  BINDER_COUNTS,
  BINDER_PARTS,
  BINDER_ROWS,
  BINDER_SEASON,
  BINDER_SERVICE,
  OSTERBERG_ROW,
  binderFacets,
  officeOfClient,
  toBinderRow,
} from "../seed/binders";
import { DEMO_INSTANT, DEMO_MS } from "../seed/clock";
import { stableId } from "../seed/prng";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

const STATUSES: readonly BinderStatus[] = [
  "draft",
  "published",
  "unpublished",
  "complete",
  "closed",
];
const DAY_MS = 86_400_000;

interface Data {
  rows: BinderRowOut[];
  counts: Record<BinderStatus, number>;
  loading?: boolean;
}

function isStatus(v: string | null): v is BinderStatus {
  return v !== null && (STATUSES as readonly string[]).includes(v);
}

/** Over the filters minus the tile: what the tiles count and the rows are drawn from. */
function filtered(data: Data, q: URLSearchParams): { rows: BinderRowOut[]; seasonal: boolean } {
  const season = q.get("season");
  const service = q.get("service");
  // Only TY2025 tax-return binders exist at E0: TY2026 has none until season setup runs (d).
  const seasonal =
    (season === null || season === BINDER_SEASON) &&
    (service === null || service === BINDER_SERVICE);
  let rows = seasonal ? data.rows : [];
  const office = q.get("office");
  if (office !== null) {
    const name = seed.firm.offices.find((o) => stableId(`office:${o.name}`) === office)?.name;
    rows = rows.filter((r) => officeOfClient(seed, r.client_name) === name);
  }
  const preparer = q.get("preparer");
  if (preparer !== null) rows = rows.filter((r) => r.preparer_user_id === preparer);
  if (q.get("client_activity") === "none_30_days") {
    rows = rows.filter(
      (r) =>
        r.status === "published" &&
        r.last_client_activity_at !== null &&
        DEMO_MS - Date.parse(r.last_client_activity_at) > 30 * DAY_MS,
    );
  }
  const text = (q.get("q") ?? "").trim().toLowerCase();
  if (text !== "") {
    rows = rows.filter((r) =>
      [r.name, r.client_name, r.work_item_label ?? ""].some((v) => v.toLowerCase().includes(text)),
    );
  }
  return { rows, seasonal };
}

/** True while no chip but the season and service narrows the list: the tiles are the §9.5 counts. */
function unnarrowed(q: URLSearchParams): boolean {
  return (
    q.get("office") === null &&
    q.get("preparer") === null &&
    (q.get("client_activity") ?? "any") === "any" &&
    (q.get("q") ?? "").trim() === ""
  );
}

function listPage(data: Data, request: FixtureRequest): ListPageBinderRowOut {
  const q = request.query;
  const { rows, seasonal } = filtered(data, q);
  const counts: Record<BinderStatus, number> = {
    draft: 0,
    published: 0,
    unpublished: 0,
    complete: 0,
    closed: 0,
  };
  if (seasonal && unnarrowed(q)) Object.assign(counts, data.counts);
  else for (const r of rows) counts[r.status] += 1;
  const tile = q.get("status");
  const items = isStatus(tile) ? rows.filter((r) => r.status === tile) : rows;
  const total = isStatus(tile) ? counts[tile] : STATUSES.reduce((sum, s) => sum + counts[s], 0);
  return {
    items,
    next_cursor: null,
    total,
    total_capped: false,
    counts,
    facets: {
      ...binderFacets(seed, seasonal ? data.rows : []),
      // "224 returns · 17 second-part binders": the read model's `part` facet (P-06-T11).
      ...(seasonal && unnarrowed(q)
        ? {
            part: [
              { value: "1", label: "Returns", n: BINDER_PARTS.returns },
              { value: "2+", label: "Second-part binders", n: BINDER_PARTS.secondParts },
            ],
          }
        : {}),
    },
  };
}

function binderOut(row: BinderRowOut, status: BinderStatus = row.status): BinderOut {
  return {
    id: row.id,
    engagement_id: row.engagement_id,
    work_item_id: row.work_item_id,
    name: row.name,
    kind: row.kind,
    part: row.part,
    status,
    created_from: "blank",
    done_count: row.done_count,
    total_count: row.total_count,
    allowed_actions: row.allowed_actions ?? [],
  };
}

function handlers(data: Data): Record<string, FixtureHandler> {
  // Publish, unpublish and duplicate change the persona's own copy of the rows.
  let rows = [...data.rows];
  const counts = { ...data.counts };
  const find = (id: string | undefined): BinderRowOut | undefined => rows.find((r) => r.id === id);
  const move = (row: BinderRowOut, to: BinderStatus, patch: Partial<BinderRowOut> = {}): void => {
    counts[row.status] -= 1;
    counts[to] += 1;
    rows = rows.map((r) => (r.id === row.id ? { ...r, ...patch, status: to } : r));
  };
  const capabilities = (persona: string | undefined): CapabilitiesOut => {
    const base = capabilitiesFor(seed, persona ?? "grace-holloway");
    return { ...base, capabilities: [...base.capabilities, ...BINDER_ACTIONS] };
  };
  return {
    ...E0.handlers,
    "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
    "GET /v1/binders": (request) =>
      data.loading === true ? never() : json(listPage({ ...data, rows, counts }, request)),
    "POST /v1/binders/{binder_id}/publish": ({ params }) => {
      const row = find(params.binder_id);
      if (row === undefined) return json({ detail: "not_found" }, 404);
      move(row, "published", {
        unpublished_at: null,
        unpublished_by: null,
        unpublish_reason: null,
      });
      return json(binderOut(row, "published"));
    },
    "POST /v1/binders/{binder_id}/publish/undo": ({ params }) => {
      const row = find(params.binder_id);
      if (row === undefined) return json({ detail: "not_found" }, 404);
      const before = data.rows.find((r) => r.id === row.id)?.status ?? "draft";
      move(row, before);
      return json(binderOut(row, before));
    },
    "POST /v1/binders/{binder_id}/unpublish": ({ params, body }) => {
      const row = find(params.binder_id);
      if (row === undefined) return json({ detail: "not_found" }, 404);
      const reason = (body as Partial<UnpublishIn> | null)?.reason?.trim() ?? "";
      if (reason === "") return json({ detail: "reason_required" }, 422);
      move(row, "unpublished", {
        unpublished_at: DEMO_INSTANT,
        unpublished_by: seed.people.find((p) => p.slug === "grace-holloway")?.userId ?? null,
        unpublish_reason: reason,
      });
      return json(binderOut(row, "unpublished"));
    },
    "POST /v1/binders/{binder_id}/duplicate": ({ params }) => {
      const row = find(params.binder_id);
      if (row === undefined) return json({ detail: "not_found" }, 404);
      const part = row.part + 1;
      const copy: BinderRowOut = {
        ...row,
        id: stableId(`binder:${row.id}:pt:${String(part)}`),
        name: `${row.name.replace(/ pt \d+$/, "")} pt ${String(part)}`,
        part,
        status: "draft",
        done_count: 0,
        last_client_activity_at: null,
        unpublished_at: null,
        unpublished_by: null,
        unpublish_reason: null,
      };
      counts.draft += 1;
      rows = [...rows, copy];
      return json(binderOut(copy), 201);
    },
    "POST /v1/binders": ({ body }) => {
      const given = body as Partial<BinderIn> | null;
      if (given?.work_item_id === undefined || given.kind === undefined) {
        return json({ detail: "invalid" }, 422);
      }
      const id = stableId(`binder:new:${given.work_item_id}`);
      const created: BinderOut = {
        ...binderOut({ ...(rows[0] as BinderRowOut), id, work_item_id: given.work_item_id }),
        name: given.name ?? "2025 Binder",
        kind: given.kind,
        status: "draft",
      };
      return json(created, 201);
    },
  };
}

const named = (): BinderRowOut[] => BINDER_ROWS.map((r) => toBinderRow(seed, r));

const at = (state: string, data: Data, persona = "grace-holloway"): Scenario => ({
  state,
  persona,
  clock: DEMO_INSTANT,
  handlers: handlers(data),
});

/** BND-01c: Osterberg sits after Quintero (newest client activity within each state, none yet). */
function withOsterberg(): BinderRowOut[] {
  const rows = named();
  const after = rows.findIndex((r) => r.client_name === "Rafael Quintero");
  rows.splice(after + 1, 0, toBinderRow(seed, OSTERBERG_ROW));
  return rows;
}

export const scenarios = defineScenarios({
  /** Default: Service │ Tax returns, Season │ TY2025; 1 · 48 · 0 · 40 · 152 = 241; 15 rows. */
  a: at("a", { rows: named(), counts: { ...BINDER_COUNTS } }),
  /** Remy Vidal unpublished Benjamin Osterberg's binder Sep 2: 1 · 47 · 1 · 40 · 152; 16 rows. */
  c: at(
    "c",
    {
      rows: withOsterberg(),
      counts: { ...BINDER_COUNTS, published: BINDER_COUNTS.published - 1, unpublished: 1 },
    },
    "remy-vidal",
  ),
  /** Season │ TY2026 before season setup: no binders. The screen opens on that season. */
  d: at("d", { rows: named(), counts: { ...BINDER_COUNTS } }),
  /** Loading: `GET /v1/binders` never answers; skeleton tiles and 8 skeleton rows. */
  e: at("e", { rows: [], counts: { ...BINDER_COUNTS }, loading: true }),
});
