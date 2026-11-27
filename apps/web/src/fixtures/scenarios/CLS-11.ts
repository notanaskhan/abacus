// CLS-11 fixture scenarios (C-02-T15, DEC-5624; C-02-T35, DEC-5924; handoff CLS-11): Copperleaf's
// QuickBooks Online ledger console, seen by Raj Malhotra. Each artboard's persona and clock (CDT
// until Sun Nov 1, 2026). The console, log, failures and sync events are the Python scenario's
// (`seed/scenario.cls11-console.json`, `make fixtures`, never hand written); each state sets only
// what the artboard changes: c the 10:02 AM rate limit retrying at 10:07 AM, d the expired
// authorization (the 9:02 AM sync failed; Request reconnect… sends at 9:14 AM), d2 the same data with
// the confirm dialog open (`?reconnect=1`). a2 is a's data on the Sync events segment
// (`?log=events`). C-02-T44 (DEC-6029): b is August posted at 10:20 AM (QBO 48213–48218, the
// closing date moved to Aug 31 at 10:22 AM), b2 b's data with 2026-08-A's drawer open
// (`?batch=`), and e the 10:21 AM variant where QuickBooks was closed through Aug 31 before the
// approved August batch could post (its six entries each an open conflict).
import type {
  LedgerSyncStatusOut,
  ReconnectPreviewOut,
  W1ActivityListOut,
  W1ClosingConflictOut,
  W1ConnectionPaneOut,
  W1LedgerConsoleOut,
  W1PostingLogOut,
  W1PostingLogRowOut,
} from "@abacus/api-client";
import {
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { entityIdOf, slugOfClient } from "../seed/clients";
import { CLOSE_IDS } from "../seed/closes";
import { IDS } from "../seed/connections";
import { PREVIEW_LINK, renderEmail, templateSeed } from "../seed/email-templates";
import { stableId } from "../seed/prng";
import exported from "../seed/scenario.cls11-console.json";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const SLUG = slugOfClient(exported.client);
export const CLS11_CLIENT_ID = stableId(`client:${SLUG}`);
export const CLS11_ENTITY_ID = entityIdOf(SLUG, exported.client);
export const CLS11_CLOSE_ID = CLOSE_IDS.august;
const CONNECTION_ID = IDS.quickbooks;

type Row = (typeof exported.batches)[number];
const batchId = (code: string): string => stableId(`posting-batch:${SLUG}:${code}`);
const row = (b: Row): W1PostingLogOut["items"][number] => ({
  ...b,
  batch_id: batchId(b.batch_code),
  status: b.status as W1PostingLogOut["items"][number]["status"],
});

/** b, b2 and e: the 10:02 AM sync read 0 errors; the next is 11:02 AM. */
const AFTER_TEN = {
  last_sync_at: "2026-09-14T10:02:00-05:00",
  last_sync_errors: 0,
  next_sync_at: "2026-09-14T11:02:00-05:00",
};
export const CLS11_AUGUST_BATCH_ID = batchId("2026-08-A");
const entryId = (ref: string): string => stableId(`proposed-entry:${SLUG}:${ref}`);
const SANDBOX_QBO = "https://app.sandbox.qbo.intuit.com/app/journal?txnId=";

/** What each state changes in the connection pane (the clock is the artboard's). */
function pane(state: string): W1ConnectionPaneOut {
  const base: W1ConnectionPaneOut = {
    ...exported.connection,
    health: exported.connection.health as W1ConnectionPaneOut["health"],
    connection_id: CONNECTION_ID,
  };
  switch (state) {
    case "c":
      return {
        ...base,
        health: "needs_attention",
        status_reason: "rate_limited",
        last_failed_at: "2026-09-14T10:02:00-05:00",
        retry_at: "2026-09-14T10:07:00-05:00",
      };
    case "b":
    case "b2":
      return {
        ...base,
        ...AFTER_TEN,
        closing_date: "2026-08-31",
        closing_date_set_by: "Raj Malhotra",
        closing_date_set_at: "2026-09-14T10:22:00-05:00",
      };
    case "e":
      // Closed through Aug 31 in QuickBooks itself: found by the 10:02 AM sync, set by no one here.
      return {
        ...base,
        ...AFTER_TEN,
        closing_date: "2026-08-31",
        closing_date_set_by: null,
        closing_date_set_at: "2026-09-14T10:02:00-05:00",
      };
    case "d":
    case "d2":
      return {
        ...base,
        health: "needs_reauth",
        status_reason: "token_expired",
        last_sync_at: "2026-09-14T08:02:00-05:00",
        last_failed_at: "2026-09-14T09:02:00-05:00",
        next_sync_at: null,
      };
    default:
      return base;
  }
}

function tiles(state: string): W1LedgerConsoleOut["tiles"] {
  if (state === "b" || state === "b2") {
    return {
      ...exported.tiles,
      posted: exported.tiles.posted + 1,
      proposed: 0,
      closing_date: "2026-08-31",
    };
  }
  if (state === "e") return { ...exported.tiles, closing_date: "2026-08-31" };
  return exported.tiles;
}

/** e: each of August's six approved entries, dated Aug 31, is an open conflict. */
function conflicts(state: string): W1ClosingConflictOut[] {
  if (state !== "e") return [];
  return exported.august_entries.map((e) => ({
    conflict_id: stableId(`closing-date-conflict:${SLUG}:${e.ref}`),
    batch_code: "2026-08-A",
    entry_ref: e.ref,
    entry_date: "2026-08-31",
    ledger_closing_date: "2026-08-31",
    status: "open" as const,
  }));
}

export function cls11Console(state: string): W1LedgerConsoleOut {
  return {
    client_entity_id: CLS11_ENTITY_ID,
    client_entity_name: exported.client,
    ledger_label: "QuickBooks Online",
    tiles: tiles(state),
    connection: pane(state),
    failures: exported.failures,
    conflicts: conflicts(state),
  };
}

/** The log's batches in a state: b and b2 with August posted, e with it approved and held. */
function batches(state: string): W1PostingLogOut["items"] {
  const rows = exported.batches.map(row);
  const august = row(exported.august_posted);
  if (state === "b" || state === "b2") return [august, ...rows.slice(1)];
  if (state === "e") {
    return [
      {
        ...august,
        status: "proposed",
        first_external_ref: null,
        last_external_ref: null,
        posted_at: null,
        posted_by: null,
      },
      ...rows.slice(1),
    ];
  }
  return rows;
}

/** b2's drawer: 2026-08-A with its six entries, each linking to its QuickBooks transaction. */
export function cls11Batch(): W1PostingLogRowOut {
  return {
    ...row(exported.august_posted),
    entries: exported.august_entries.map((e) => ({
      entry_id: entryId(e.ref),
      ref: e.ref,
      status: "posted",
      external_txn_ref: e.external_txn_ref,
      deep_link: `${SANDBOX_QBO}${e.external_txn_ref}`,
      description: e.description,
      amount: e.amount,
    })),
  };
}

/** The posting log, filtered as the server filters it (`period`, `status`). */
export function cls11Log(query?: URLSearchParams, state = "a"): W1PostingLogOut {
  const period = query?.get("period") ?? null;
  const status = query?.get("status") ?? null;
  const items = batches(state).filter(
    (b) => (period === null || b.period === period) && (status === null || b.status === status),
  );
  return { items, total: items.length };
}

export function cls11Activity(): W1ActivityListOut {
  const items = exported.activity.map((a) => ({
    ...a,
    kind: a.kind as W1ActivityListOut["items"][number]["kind"],
  }));
  return { items, total: items.length };
}

function syncStatus(state: string): LedgerSyncStatusOut {
  const c = pane(state);
  const word: Record<string, LedgerSyncStatusOut["state"]> = {
    c: "rate_limited",
    d: "needs_reauth",
    d2: "needs_reauth",
  };
  return {
    client_entity_id: CLS11_ENTITY_ID,
    connection_id: CONNECTION_ID,
    provider: "quickbooks_online",
    state: word[state] ?? "synced",
    last_synced_at: c.last_sync_at ?? null,
    next_sync_at: c.next_sync_at ?? null,
    retry_at: c.retry_at ?? null,
    failure_code: c.status_reason ?? null,
    meter: null,
  };
}

/** The Reconnect request email as POR-20's seed renders it for Tess Moreno (the owner). */
export function cls11ReconnectPreview(): ReconnectPreviewOut {
  const seed = templateSeed("reconnect_request");
  if (seed === undefined) return { recipients: ["Tess Moreno"], template_missing: true };
  const shown = renderEmail(
    seed.content,
    {
      client_first_name: "Tess",
      firm_name: "Brightwater Hale",
      portal_link: PREVIEW_LINK,
      connection_name: "QuickBooks Online",
    },
    600,
  );
  return {
    recipients: ["Tess Moreno"],
    template_missing: false,
    subject: shown.subject,
    html: shown.html,
    text: shown.text,
    from_display: "Brightwater Hale",
  };
}

function at(state: string, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          return json({
            ...base,
            flags: {
              ...base.flags,
              "closes.engine": true,
              "adjustments.posting": true,
              "closes.gl_console": true,
            },
          });
        },
        "GET /v1/client-entities/{client_entity_id}/ledger-console": () =>
          json(cls11Console(state)),
        "GET /v1/client-entities/{client_entity_id}/posting-batches": ({
          query,
        }: FixtureRequest) => json(cls11Log(query, state)),
        "GET /v1/posting-batches/{batch_id}": () => json(cls11Batch()),
        "POST /v1/closing-date-conflicts/{conflict_id}/ask-client": ({ params }: FixtureRequest) =>
          json({
            conflict_id: params["conflict_id"],
            entry_id: stableId(`proposed-entry:${SLUG}:asked`),
            entry_date: "2026-08-31",
            ledger_closing_date: "2026-08-31",
            status: "client_asked",
            client_asked_at: "2026-09-14T10:21:00-05:00",
          }),
        "POST /v1/closing-date-conflicts/{conflict_id}/redate": ({ params }: FixtureRequest) =>
          json({
            conflict_id: params["conflict_id"],
            entry_id: stableId(`proposed-entry:${SLUG}:redated`),
            entry_date: "2026-09-01",
            ledger_closing_date: "2026-08-31",
            status: "redated",
          }),
        "GET /v1/client-entities/{client_entity_id}/ledger-activity": () => json(cls11Activity()),
        "GET /v1/client-entities/{client_entity_id}/ledger-pull": () => json(syncStatus(state)),
        "POST /v1/client-entities/{client_entity_id}/ledger-pull": () =>
          json({ state: "syncing", sync_run_id: stableId(`sync-run:${SLUG}:now`) }, 202),
        "GET /v1/connections/{connection_id}/reconnect-requests/preview": () =>
          json(cls11ReconnectPreview()),
        "POST /v1/connections/{connection_id}/reconnect-requests": () =>
          json(
            {
              id: stableId(`reconnect-request:${SLUG}`),
              connection_id: CONNECTION_ID,
              requested_by: {
                user_id: stableId("user:raj-malhotra"),
                display_name: "Raj Malhotra",
                kind: "firm",
              },
              requested_at: "2026-09-14T09:14:00-05:00",
            },
            201,
          ),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  a2: at("a2", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  b: at("b", "raj-malhotra", "2026-09-14T10:22:00-05:00"),
  b2: at("b2", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  c: at("c", "raj-malhotra", "2026-09-14T10:03:00-05:00"),
  d: at("d", "raj-malhotra", "2026-09-14T09:14:00-05:00"),
  d2: at("d2", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  e: at("e", "raj-malhotra", "2026-09-14T10:21:00-05:00"),
});

export type Cls11State = keyof typeof scenarios;
export const INITIAL: Cls11State = "a";
