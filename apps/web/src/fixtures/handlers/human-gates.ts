// The C13 gate half in fixture mode (I-01-T05; docs/contracts/home-and-gates.md): the list of what
// waits on the persona and the one count source, both computed from the same seeded rows
// (seed/home.ts) so the badge, the header, the summary and the list can never disagree. A walled
// client's gates are left out of both, and nothing says any were (INV-3, DEC-43). `office_id`
// narrows the counts and never authorises (DEC-30). Typed with the generated client.

import type {
  GateBandsOut,
  HumanGateCountsOut,
  HumanGateOut,
  ListPageHumanGateOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { Seed } from "../seed";
import { HOME_TODAY, homeGates } from "../seed/home";

/** The persona's open gates, less any client they are walled from. */
export function gatesFor(
  seed: Seed,
  persona: string,
  rows: (persona: string) => HumanGateOut[] = homeGates,
): HumanGateOut[] {
  const walled = new Set(
    seed.walls.filter((w) => w.personSlug === persona).map((w) => w.clientId),
  );
  return rows(persona).filter((g) => g.client_id === null || !walled.has(g.client_id));
}

/** The one count source over the persona's rows (snoozes are a live-only fact: 0 here). */
export function countsOf(gates: readonly HumanGateOut[], today = HOME_TODAY): HumanGateCountsOut {
  const bands: GateBandsOut = { decisions: 0, sign_offs: 0, agent_outputs: 0, approvals_sends: 0 };
  for (const g of gates) bands[g.band] += 1;
  return {
    total: gates.length,
    bands,
    overdue: gates.filter((g) => g.due_on !== null && g.due_on < today).length,
    snoozed: 0,
  };
}

export interface GateHandlerOptions {
  /** A scenario's own rows (HOME-01 f: none). */
  rows?: (persona: string) => HumanGateOut[];
  /** The seed's today for `overdue`. */
  today?: string;
}

export function humanGateHandlers(
  seed: Seed,
  options: GateHandlerOptions = {},
): Record<string, FixtureHandler> {
  const mine = (request: FixtureRequest): HumanGateOut[] =>
    gatesFor(seed, request.persona ?? DEFAULT_PERSONA, options.rows);
  return {
    "GET /v1/human-gates/counts": (request) => {
      const office = request.query.get("office_id");
      const rows = mine(request).filter((g) => office === null || g.office_id === office);
      return json(countsOf(rows, options.today) satisfies HumanGateCountsOut);
    },
    "GET /v1/human-gates": (request) => {
      const kind = request.query.get("kind");
      const rows = mine(request);
      const counts: Record<string, number> = {};
      for (const g of rows) counts[g.kind] = (counts[g.kind] ?? 0) + 1;
      const items = rows.filter((g) => kind === null || g.kind === kind);
      return json({
        items,
        next_cursor: null,
        total: items.length,
        total_capped: false,
        counts,
        facets: {},
      } satisfies ListPageHumanGateOut);
    },
  };
}
