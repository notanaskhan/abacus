// `GET /v1/engagements/index` over the Brightwater Hale seed (P-07-T11; docs/contracts/
// engagements-v2.md): the ENG-01 read model in the `EngagementIndexPage` shape, typed with the
// generated client. It serves the engagements the interim seed holds (the 27 audits and
// assurance engagements and the Feld Form 1040), after the same wall rule as the clients list
// (404 semantics: a walled client's engagements are absent from rows, counts, facets and `total`),
// with the `service_line`, `status`, `tile`, `client_id`, `office_id` and `q` filters, `counts`
// per status minus the tile and `facets.service_line` as the segments. ENG-01's full tiles
// (1 + 4 + 0 + 128 + 0 + 140 + 2 = 275) need the tax, CAS and advisory engagements the interim
// seed does not carry yet; that footing waits for F-04-T31's exported seed (docs/screens/ENG-01.md).

import type {
  EngagementIndexPage,
  EngagementIndexRowOut,
  EngagementOut,
  EngagementStatus,
  Facet,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import { type Seed, getSeed } from "../seed";
import { officeIdOf } from "../seed/shell";
import { partnerIdOf } from "./clients";

const STATUSES: readonly EngagementStatus[] = [
  "prospect",
  "accepted",
  "declined",
  "contracted",
  "active",
  "on_hold",
  "delivered",
  "archived",
];
const LINES = ["audit", "tax", "cas", "advisory"] as const;

/** An index row for a seed engagement, with the client's office and relationship partner. */
export function engagementRow(seed: Seed, e: EngagementOut): EngagementIndexRowOut {
  const client = seed.clients.find((c) => seed.clientIds[c.slug] === e.client_id);
  const signed = e.status !== "prospect" && e.status !== "accepted";
  return {
    id: e.id,
    name: e.name,
    client_id: e.client_id,
    client_name: e.client_name,
    client_entity_id: e.client_entity_id,
    type: e.type,
    service_line: e.service_line,
    status: e.status,
    period_label: null,
    fiscal_period_start: e.fiscal_period_start,
    fiscal_period_end: e.fiscal_period_end,
    office_id: client === undefined ? null : officeIdOf(client.office),
    office_name: client?.office ?? null,
    partner_user_id: client === undefined ? null : partnerIdOf(client.partner),
    partner_initials: client?.partner ?? null,
    work_items: [],
    letter: { status: signed ? "signed" : "not_signed" },
    next_due: null,
    allowed_actions: [],
  };
}

function walledIds(seed: Seed, request: FixtureRequest): Set<string> {
  const who = request.persona ?? DEFAULT_PERSONA;
  return new Set(seed.walls.filter((w) => w.personSlug === who).map((w) => w.clientId));
}

export function engagementIndexPage(seed: Seed, request: FixtureRequest): EngagementIndexPage {
  const q = request.query;
  const walled = walledIds(seed, request);
  let rows = seed.engagements
    .filter((e) => !walled.has(e.client_id))
    .map((e) => engagementRow(seed, e));
  const client = q.get("client_id");
  if (client !== null) rows = rows.filter((r) => r.client_id === client);
  const office = q.get("office_id");
  if (office !== null) rows = rows.filter((r) => r.office_id === office);
  const text = (q.get("q") ?? "").trim().toLowerCase();
  if (text !== "") {
    rows = rows.filter((r) => [r.name, r.client_name].some((v) => v.toLowerCase().includes(text)));
  }
  const segments: Facet[] = LINES.map((line) => ({
    value: line,
    label: line,
    n: rows.filter((r) => r.service_line === line).length,
  }));
  const line = q.get("service_line");
  if (line !== null) rows = rows.filter((r) => r.service_line === line);
  const status = q.get("status");
  if (status !== null) rows = rows.filter((r) => r.status === status);
  const counts: Record<string, number> = {};
  for (const s of STATUSES) {
    if (s !== "declined") counts[s] = rows.filter((r) => r.status === s).length;
  }
  const tile = q.get("tile");
  const items = tile === null ? rows : rows.filter((r) => r.status === tile);
  return {
    items,
    next_cursor: null,
    total: items.length,
    total_capped: false,
    counts,
    facets: { service_line: segments },
    summary: {
      prospect: rows.filter((r) => r.status === "prospect").length,
      awaiting_letter: rows.filter((r) => r.status === "accepted").length,
      past_due: 0,
    },
  };
}

/** The engagements v2 routes over the seed. */
export function engagementHandlers(seed: Seed = getSeed()): Record<string, FixtureHandler> {
  return {
    "GET /v1/engagements/index": (request) => json(engagementIndexPage(seed, request)),
  };
}
