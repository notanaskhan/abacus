// C5's intake reads in fixture mode for INB-01 (N-01-T10; docs/contracts/firm-intake.md): the
// summary, the thread list (client, status, received, q, show ignored and filed) and a thread's
// detail, from seed/inbox.ts, seen by Grace Holloway (Intake team) at E0. One scenario per
// artboard; the selection is the screen's state. Nothing here files, ignores or matches.
import type { InboxSummaryOut, ListPageInboxThreadRow } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { inboxThreads, threadDetail, threadRow } from "../seed/inbox";

export const INB01_PERSONA = "grace-holloway";
export const INB01_CLOCK = "2026-09-14T09:24:00-05:00";
const NOT_FOUND = { detail: "not_found" };

export function inboxHandlers(filed = false): Record<string, FixtureHandler> {
  const threads = inboxThreads(filed);
  const rows = threads.map(threadRow);
  return {
    "GET /v1/inbox/summary": () => {
      const summary: InboxSummaryOut = {
        waiting: rows.reduce((n, r) => n + r.waiting, 0),
        unmatched: rows.filter((r) => r.match_state === "unmatched").length,
        by_source: [
          {
            source_kind: "mailbox",
            source_display: "docs@brightwaterhale.com",
            waiting: rows.reduce((n, r) => n + r.waiting, 0),
          },
        ],
      };
      return json(summary);
    },
    "GET /v1/inbox/threads": ({ query }) => {
      const client = query.get("client_id");
      const q = query.get("q")?.trim().toLowerCase() ?? "";
      const since = query.get("received_since");
      const showIgnored = query.get("show_ignored") === "true";
      const showFiled = query.get("show_filed") !== "false";
      const items = rows.filter(
        (r) =>
          (client === null || r.client_id === client) &&
          (since === null || r.last_received_at >= since) &&
          (q === "" || `${r.subject_display} ${r.sender_display}`.toLowerCase().includes(q)) &&
          (showIgnored || r.status !== "ignored") &&
          (showFiled || r.status !== "filed"),
      );
      const page: ListPageInboxThreadRow = { items, total: items.length };
      return json(page);
    },
    "GET /v1/inbox/threads/{thread_id}": ({ params }) => {
      const found = threads.find((m) => threadRow(m).id === params.thread_id);
      return found === undefined ? json(NOT_FOUND, 404) : json(threadDetail(found));
    },
  };
}

const base = (state: string, handlers: Record<string, FixtureHandler>): Scenario => ({
  state,
  persona: INB01_PERSONA,
  clock: INB01_CLOCK,
  handlers,
});

/** a Feld selected · b row 9 (unmatched) · c row 3 (Stein; notice kind, fixture-only) · d after
 * INB-02 a (W0-filed) · e rows 2, 10, 11 checked · f Ridgeline, past 30 days → nothing · g the
 * list never answers (8 skeleton rows). */
export const INB01_SCENARIOS = defineScenarios({
  a: base("a", inboxHandlers()),
  b: base("b", inboxHandlers()),
  c: base("c", inboxHandlers()),
  d: base("d", inboxHandlers(true)),
  e: base("e", inboxHandlers()),
  f: base("f", inboxHandlers()),
  g: base("g", { ...inboxHandlers(), "GET /v1/inbox/threads": () => never() }),
});
