// `GET /v1/clients` over the Brightwater Hale seed (P-07-T11; docs/contracts/clients.md): the
// CLI-01 read model in the `ListPage[ClientRowOut]` shape. Typed with the generated client, so a
// schema change breaks the build here. It applies what the read model will:
// - `visible(scope=client)`: a walled client is absent from rows, `counts`, `facets` and `total`,
//   and the envelope has the same keys as for a firm without it (INV-3, DEC-43);
// - the filters `kind`, `office_id`, `partner_id`, `service_line`, `status` and `q` (name,
//   descriptor and entity names), sorted by newest activity, keyset-paged by an opaque cursor;
// - `counts` per client status over the filters minus `status`; `facets` when `facets=true`.
// Open requests foot from the seed's own request lists where it has them (Northwind 13 = 24 − 11,
// Feld 2; Granite Peak has only draft requests, so "Binder draft"), and from the CLI-01 facts
// otherwise. Dev and test only: the production dist never holds it.

import type {
  ClientRowOut,
  ClientStatus,
  Facet,
  ListPageClientRowOut,
  RequestItemOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import { type Seed, getSeed } from "../seed";
import {
  CLIENT_DISPLAY_NAME,
  NAMED_ROW_FACTS,
  apiKindOf,
  descriptorOf,
  lastActivityOf,
} from "../seed/client-rows";
import type { SeedClient } from "../seed/clients";
import { SEATS, type OfficeName, slugOf } from "../seed/people";
import { stableId } from "../seed/prng";
import { officeIdOf } from "../seed/shell";

const STATUSES: readonly ClientStatus[] = ["prospect", "active", "inactive", "former"];
const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;

/** A request is open while it waits on the client or the firm: requested, uploaded or returned. */
const OPEN: ReadonlySet<RequestItemOut["status"]> = new Set(["requested", "uploaded", "returned"]);

export function partnerIdOf(initials: string): string | null {
  const seat = SEATS.find((s) => s.initials === initials);
  return seat === undefined ? null : stableId(`user:${slugOf(seat.name)}`);
}

function partnerName(initials: string): string {
  return SEATS.find((s) => s.initials === initials)?.name ?? initials;
}

/** The open requests of a client's engagements in the seed, or undefined when it has none. */
function seedRequests(seed: Seed, clientId: string): RequestItemOut[] | undefined {
  const lists = seed.engagements
    .filter((e) => e.client_id === clientId)
    .map((e) => seed.requestItems[e.id])
    .filter((list): list is RequestItemOut[] => list !== undefined);
  return lists.length === 0 ? undefined : lists.flat();
}

/** Every client as a CLI-01 row, in the seed's order (named, roster, filler). */
export function clientRows(seed: Seed = getSeed()): ClientRowOut[] {
  return seed.clients.map((c: SeedClient, index): ClientRowOut => {
    const id = seed.clientIds[c.slug] ?? "";
    const requests = seedRequests(seed, id);
    const open = requests?.filter((r) => OPEN.has(r.status)).length;
    const draftOnly = requests !== undefined && requests.every((r) => r.status === "draft");
    const facts = NAMED_ROW_FACTS[c.name];
    const openCount = draftOnly ? null : open !== undefined && open > 0 ? open : null;
    return {
      id,
      name: CLIENT_DISPLAY_NAME[c.name] ?? c.name,
      descriptor: descriptorOf(c),
      kind: apiKindOf(c),
      status: "active",
      entity_count: c.entities.length,
      service_lines: [...c.services],
      is_attest_client: c.attest,
      office_id: officeIdOf(c.office),
      office_name: c.office,
      relationship_partner_id: partnerIdOf(c.partner),
      relationship_partner_initials: c.partner,
      portal_status: c.portal,
      open_request_count: requests === undefined ? (facts?.openRequests ?? null) : openCount,
      binder_draft_only: draftOnly,
      last_activity_at: lastActivityOf(c, index),
      last_activity_event_type: facts?.eventType ?? null,
      allowed_actions: [],
    };
  });
}

function walledIds(seed: Seed, request: FixtureRequest): Set<string> {
  const who = request.persona ?? DEFAULT_PERSONA;
  return new Set(seed.walls.filter((w) => w.personSlug === who).map((w) => w.clientId));
}

function matchesText(row: ClientRowOut, client: SeedClient | undefined, text: string): boolean {
  const haystack = [row.name, row.descriptor ?? "", ...(client?.entities ?? [])];
  return haystack.some((v) => v.toLowerCase().includes(text));
}

function facet(rows: readonly ClientRowOut[], key: (r: ClientRowOut) => [string, string] | null) {
  const n = new Map<string, Facet>();
  for (const row of rows) {
    const kv = key(row);
    if (kv === null) continue;
    const [value, label] = kv;
    const f = n.get(value) ?? { value, label, n: 0 };
    n.set(value, { ...f, n: f.n + 1 });
  }
  return [...n.values()].sort((a, b) => a.label.localeCompare(b.label));
}

const OFFICES: readonly OfficeName[] = ["Chicago", "Denver", "New York"];

function facetsOf(rows: readonly ClientRowOut[]): Record<string, Facet[]> {
  return {
    kind: facet(rows, (r) => (r.kind === null ? null : [r.kind, r.kind])),
    office: facet(rows, (r) =>
      r.office_id == null || r.office_name == null ? null : [r.office_id, r.office_name],
    ).sort(
      (a, b) => OFFICES.indexOf(a.label as OfficeName) - OFFICES.indexOf(b.label as OfficeName),
    ),
    partner: facet(rows, (r) =>
      r.relationship_partner_id == null || r.relationship_partner_initials == null
        ? null
        : [r.relationship_partner_id, partnerName(r.relationship_partner_initials)],
    ),
    service_line: (["tax", "audit", "cas", "advisory"] as const).map((line) => ({
      value: line,
      label: line,
      n: rows.filter((r) => r.service_lines.includes(line)).length,
    })),
  };
}

/** The opaque keyset cursor: the offset of the next row, base64url. */
function cursorAt(offset: number): string {
  return btoa(`o:${String(offset)}`).replace(/=+$/, "");
}

function offsetOf(cursor: string | null): number {
  if (cursor === null || cursor === "") return 0;
  try {
    const decoded = atob(cursor);
    const n = Number(decoded.startsWith("o:") ? decoded.slice(2) : Number.NaN);
    return Number.isInteger(n) && n >= 0 ? n : 0;
  } catch {
    return 0;
  }
}

/** `GET /v1/clients` for one request, over `rows` (all of the firm's clients). */
export function clientsPage(
  seed: Seed,
  rows: readonly ClientRowOut[],
  request: FixtureRequest,
): ListPageClientRowOut {
  const q = request.query;
  const walled = walledIds(seed, request);
  const byId = new Map(seed.clients.map((c) => [seed.clientIds[c.slug] ?? "", c]));
  let visible = rows.filter((r) => !walled.has(r.id));
  const kind = q.get("kind");
  if (kind !== null) visible = visible.filter((r) => r.kind === kind);
  const office = q.get("office_id");
  if (office !== null) visible = visible.filter((r) => r.office_id === office);
  const partner = q.get("partner_id");
  if (partner !== null) visible = visible.filter((r) => r.relationship_partner_id === partner);
  const line = q.get("service_line");
  if (line !== null) {
    visible = visible.filter((r) => (r.service_lines as readonly string[]).includes(line));
  }
  const text = (q.get("q") ?? "").trim().toLowerCase();
  if (text !== "") visible = visible.filter((r) => matchesText(r, byId.get(r.id), text));

  // Counts over the filters minus `status`; then the status narrows the rows.
  const counts: Record<string, number> = {};
  for (const s of STATUSES) counts[s] = visible.filter((r) => r.status === s).length;
  const status = q.get("status");
  const matched = status === null ? visible : visible.filter((r) => r.status === status);

  const sorted =
    q.get("sort") === "name"
      ? [...matched].sort((a, b) => a.name.localeCompare(b.name))
      : [...matched].sort(
          (a, b) => Date.parse(b.last_activity_at ?? "") - Date.parse(a.last_activity_at ?? ""),
        );
  const limit = Math.min(Number(q.get("limit") ?? DEFAULT_LIMIT) || DEFAULT_LIMIT, MAX_LIMIT);
  const from = offsetOf(q.get("cursor"));
  const items = sorted.slice(from, from + limit);
  const next = from + limit < sorted.length ? cursorAt(from + limit) : null;
  return {
    items,
    next_cursor: next,
    total: matched.length,
    total_capped: false,
    counts,
    ...(q.get("facets") === "true" ? { facets: facetsOf(visible) } : {}),
  };
}

export interface ClientHandlerOptions {
  /** Replace the firm's clients (CLI-01f: a firm with none). */
  rows?: readonly ClientRowOut[];
}

/** The clients routes over the seed. */
export function clientHandlers(
  seed: Seed = getSeed(),
  options: ClientHandlerOptions = {},
): Record<string, FixtureHandler> {
  const rows = options.rows ?? clientRows(seed);
  return {
    "GET /v1/clients": (request) => json(clientsPage(seed, rows, request)),
  };
}
