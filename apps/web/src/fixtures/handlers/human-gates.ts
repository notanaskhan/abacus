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
  ReassignCandidatesOut,
  ReassignIn,
  ReassignedOut,
  SnoozeIn,
  SnoozedOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { Seed } from "../seed";
import { HOME_TODAY, homeGates } from "../seed/home";
import { stableId } from "../seed/prng";

/** I-01-T19: who a gate may move to (the owner's hook names them, walls applied). */
const CANDIDATES: ReassignCandidatesOut = {
  candidates: [
    { user_id: stableId("user:priya-raman"), role: "partner", display_name: "Priya Raman" },
  ],
};

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

/** The one count source over the persona's rows (a snooze in this session counts as snoozed). */
export function countsOf(
  gates: readonly HumanGateOut[],
  today = HOME_TODAY,
  snoozed = 0,
): HumanGateCountsOut {
  const bands: GateBandsOut = { decisions: 0, sign_offs: 0, agent_outputs: 0, approvals_sends: 0 };
  for (const g of gates) bands[g.band] += 1;
  return {
    total: gates.length,
    bands,
    overdue: gates.filter((g) => g.due_on !== null && g.due_on < today).length,
    snoozed,
  };
}

export interface GateHandlerOptions {
  /** A scenario's own rows (HOME-01 f: none). */
  rows?: (persona: string) => HumanGateOut[];
  /** The seed's today for `overdue`. */
  today?: string;
  /** `state=done` (Show done, HOME-02 b): the persona's done rows; the open rows when absent. */
  done?: (persona: string) => HumanGateOut[];
}

export function humanGateHandlers(
  seed: Seed,
  options: GateHandlerOptions = {},
): Record<string, FixtureHandler> {
  // I-01-T19: a snooze or a reassignment moves a gate off the persona's queue and every count,
  // only once its write answers (the screen never moves it first, DEC-24).
  const snoozed = new Set<string>();
  const moved = new Set<string>();
  const mine = (request: FixtureRequest): HumanGateOut[] =>
    gatesFor(seed, request.persona ?? DEFAULT_PERSONA, options.rows).filter(
      (g) => !snoozed.has(g.id) && !moved.has(g.id),
    );
  const today = options.today ?? HOME_TODAY;
  return {
    "GET /v1/human-gates/counts": (request) => {
      const office = request.query.get("office_id");
      const rows = mine(request).filter((g) => office === null || g.office_id === office);
      return json(countsOf(rows, options.today, snoozed.size) satisfies HumanGateCountsOut);
    },
    "POST /v1/human-gates/{gate_id}/snooze": (request) => {
      const gate = gatesFor(seed, request.persona ?? DEFAULT_PERSONA, options.rows).find(
        (g) => g.id === request.params.gate_id,
      );
      if (gate === undefined) return json({ detail: "not_found" }, 404);
      if (gate.due_on !== null && gate.due_on < today)
        return json({ detail: "gate_overdue" }, 409);
      const { until } = request.body as SnoozeIn;
      if (gate.due_on !== null && until.slice(0, 10) > gate.due_on) {
        return json({ detail: "snooze_past_due" }, 422);
      }
      snoozed.add(gate.id);
      return json({ gate_id: gate.id, until } satisfies SnoozedOut);
    },
    "GET /v1/human-gates/{gate_id}/reassign-candidates": () => json(CANDIDATES),
    "POST /v1/human-gates/{gate_id}/reassign": (request) => {
      const body = request.body as ReassignIn;
      if (!(CANDIDATES.candidates ?? []).some((c) => c.user_id === body.to_user_id)) {
        return json({ detail: "candidate_not_eligible" }, 422);
      }
      moved.add(request.params.gate_id ?? "");
      return json({
        gate_id: request.params.gate_id ?? "",
        to_user_id: body.to_user_id,
        version: body.seen_version + 1,
      } satisfies ReassignedOut);
    },
    "GET /v1/human-gates": (request) => {
      const kind = request.query.get("kind");
      const done = options.done;
      const rows =
        request.query.get("state") === "done" && done !== undefined
          ? gatesFor(seed, request.persona ?? DEFAULT_PERSONA, done)
          : mine(request);
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
