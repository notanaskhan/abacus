// `GET /v1/engagements/index` over the Brightwater Hale seed (P-07-T11, P-07-T27; docs/contracts/
// engagements-v2.md): the ENG-01 read model in the `EngagementIndexPage` shape, typed with the
// generated client. Rows are ENG-01's 17 named engagements (seed/engagement-index.ts); the other
// 258 are counts only, so they join `counts`, `facets` and `total` but never `items`, and only
// while nothing narrows the list past what their counts know (service line and status). Walls
// follow the clients list (404 semantics: a walled client's engagements are absent from rows,
// counts, facets and `total`). Filters: `service_line`, `status`, `tile` (counts minus the tile),
// `letter`, `period`, `client_id`, `office_id`, `partner_id`, `next_due` and `q`. `period=current`
// is every status but archived and declined, `prior` archived, `all` all but declined, as the live
// index reads them (DEC-224; DEC-343 settled ED-027: ENG-01a's Archived tile is 0).

import type {
  EngagementIndexPage,
  EngagementIndexRowOut,
  EngagementStatus,
  Facet,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import { type Seed, getSeed } from "../seed";
import {
  ENG01_ROWS,
  ENG01_TILES,
  type ServiceLineCode,
  eng01Row,
  eng01Unnamed,
} from "../seed/engagement-index";

const LINES: readonly ServiceLineCode[] = ["tax", "audit", "cas", "advisory"];
const TODAY = "2026-09-14";

function walledIds(seed: Seed, request: FixtureRequest): Set<string> {
  const who = request.persona ?? DEFAULT_PERSONA;
  return new Set(seed.walls.filter((w) => w.personSlug === who).map((w) => w.clientId));
}

function days(on: string): number {
  return Math.round(
    (Date.parse(`${on}T12:00:00Z`) - Date.parse(`${TODAY}T12:00:00Z`)) / 86_400_000,
  );
}

function dueWithin(row: EngagementIndexRowOut, window: string): boolean {
  if (row.next_due == null) return false;
  const n = days(row.next_due.on);
  if (window === "past_due") return n < 0;
  if (window === "within_7_days") return n >= 0 && n <= 7;
  if (window === "within_30_days") return n >= 0 && n <= 30;
  return true;
}

function inPeriod(status: EngagementStatus, period: string): boolean {
  if (status === "declined") return false;
  if (period === "prior") return status === "archived";
  if (period === "current") return status !== "archived";
  return true;
}

export function engagementIndexPage(seed: Seed, request: FixtureRequest): EngagementIndexPage {
  const q = request.query;
  const walled = walledIds(seed, request);
  const period = q.get("period") ?? "current";
  const text = (q.get("q") ?? "").trim().toLowerCase();
  const letter = q.get("letter");
  const narrowing = ["client_id", "office_id", "partner_id", "next_due"].some(
    (k) => q.get(k) !== null,
  );
  // The unnamed engagements all have a signed letter and match no search (they have no names).
  const unnamedIn = !narrowing && text === "" && letter !== "not_signed";
  const unnamed = eng01Unnamed(seed);

  let rows = ENG01_ROWS.map((r) => eng01Row(seed, r)).filter(
    (r) => !walled.has(r.client_id) && inPeriod(r.status, period),
  );
  const client = q.get("client_id");
  if (client !== null) rows = rows.filter((r) => r.client_id === client);
  const office = q.get("office_id");
  if (office !== null) rows = rows.filter((r) => r.office_id === office);
  const partner = q.get("partner_id");
  if (partner !== null) rows = rows.filter((r) => r.partner_user_id === partner);
  const nextDue = q.get("next_due");
  if (nextDue !== null) rows = rows.filter((r) => dueWithin(r, nextDue));
  if (letter === "not_signed") {
    rows = rows.filter(
      (r) =>
        r.letter.status === "not_signed" && r.status !== "prospect" && r.status !== "declined",
    );
  } else if (letter === "signed") rows = rows.filter((r) => r.letter.status === "signed");
  if (text !== "") {
    rows = rows.filter((r) => [r.name, r.client_name].some((v) => v.toLowerCase().includes(text)));
  }
  const status = q.get("status");
  if (status !== null) rows = rows.filter((r) => r.status === status);

  const unnamedCount = (line: ServiceLineCode | null, s: string | null): number => {
    if (!unnamedIn) return 0;
    let n = 0;
    for (const l of LINES) {
      if (line !== null && l !== line) continue;
      for (const [code, k] of Object.entries(unnamed[l])) {
        if (!inPeriod(code as EngagementStatus, period)) continue;
        if ((s === null || code === s) && (status === null || code === status)) n += k;
      }
    }
    return n;
  };

  // Segments: over the filters without the service line and the tile.
  const segments: Facet[] = LINES.map((l) => ({
    value: l,
    label: l,
    n: rows.filter((r) => r.service_line === l).length + unnamedCount(l, null),
  }));
  const line = q.get("service_line") as ServiceLineCode | null;
  if (line !== null) rows = rows.filter((r) => r.service_line === line);
  // Tiles: over the filters without the tile.
  const counts: Record<string, number> = {};
  for (const s of ENG01_TILES) {
    counts[s] = rows.filter((r) => r.status === s).length + unnamedCount(line, s);
  }
  const summary = {
    prospect: counts.prospect ?? 0,
    awaiting_letter: rows.filter((r) => r.status === "accepted" && r.letter.status !== "signed")
      .length,
    past_due: rows.filter((r) => r.next_due?.tone === "past_due").length,
  };
  const tile = q.get("tile");
  const items = tile === null ? rows : rows.filter((r) => r.status === tile);
  const total = items.length + unnamedCount(line, tile);
  return {
    items,
    next_cursor: null,
    total,
    total_capped: false,
    counts,
    facets: { service_line: segments },
    summary,
  };
}

/** The engagements v2 routes over the seed. */
export function engagementHandlers(seed: Seed = getSeed()): Record<string, FixtureHandler> {
  return {
    "GET /v1/engagements/index": (request) => json(engagementIndexPage(seed, request)),
  };
}
