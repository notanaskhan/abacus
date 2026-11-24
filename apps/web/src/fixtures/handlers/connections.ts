// Fixture handlers for C20 v1, POR-16 (A-02-T06; docs/contracts/c20-integrations.md): the
// entity's cards for one artboard, the details drawer, and the start, retry and disconnect the stub
// fixes. A start without the authorization toggle answers 422 `authorization_required` and an old
// consent copy 409 `consent_version_stale`; another entity or connection answers 404 (INV-4); a
// second Try again while the run is live returns the same run.
import type {
  ConnectionStartIn,
  PortalConnectionCardOut,
  PortalConnectionDetailOut,
  PortalWriteRowOut,
  W1WriteGrantIn,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  COPPERLEAF_ENTITY_ID,
  IDS,
  type Por16State,
  QUICKBOOKS_WRITE_CONSENT,
  TESS,
  copperleafConnections,
} from "../seed/connections";
import cls11 from "../seed/scenario.cls11-console.json";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not found" };

/** C-02-T40: the write log POR-16's drawer reads (the CLS-11 export's posted batches and the
 * closing date the firm set), newest first; `august` adds 2026-08-A as posted at 10:22 AM. */
export function copperleafWrites(august = false): PortalWriteRowOut[] {
  const batches = [...(august ? [cls11.august_posted] : []), ...cls11.batches];
  const rows: PortalWriteRowOut[] = batches
    .filter((b) => b.status === "posted" && b.posted_at !== null)
    .map((b) => ({
      at: b.posted_at ?? "",
      kind: "posted_entries",
      count: b.entry_count,
      batch_code: b.batch_code,
    }));
  rows.push({
    at: cls11.connection.closing_date_set_at,
    kind: "closing_date",
    closing_date: cls11.connection.closing_date,
  });
  return rows.sort((x, y) => Date.parse(y.at) - Date.parse(x.at));
}

export interface W1Fixture {
  /** The posting scope's state on arrival (the firm holds W1 for this non-attest client). */
  write: "offered" | "granted" | "read_only";
  /** The drawer's write log includes August's batch (after 10:22 AM). */
  august?: boolean;
}

export function connectionsHandlers(
  state: Por16State,
  options: { clock: string; w1?: W1Fixture },
): Record<string, FixtureHandler> {
  const page = copperleafConnections(state);
  const cards = new Map<string, PortalConnectionCardOut>();
  const w1 = options.w1;
  const withWrite = (card: PortalConnectionCardOut, state: W1Fixture["write"]) =>
    ({
      ...card,
      write:
        state === "read_only"
          ? { state, can_change: false }
          : {
              state,
              consent: QUICKBOOKS_WRITE_CONSENT,
              can_change: true,
              ...(state === "granted"
                ? { granted_at: "2026-03-09T15:00:00Z", granted_by: TESS.display_name }
                : {}),
            },
    }) satisfies PortalConnectionCardOut;
  if (w1 !== undefined) {
    page.items = page.items.map((c) =>
      c.connection_id === IDS.quickbooks ? withWrite(c, w1.write) : c,
    );
  }
  for (const card of page.items) {
    if (card.connection_id) cards.set(card.connection_id, card);
  }
  const setWrite = (next: W1Fixture["write"]): PortalConnectionCardOut | undefined => {
    const card = cards.get(IDS.quickbooks);
    if (card === undefined) return undefined;
    const updated = withWrite(card, next);
    cards.set(IDS.quickbooks, updated);
    page.items = page.items.map((c) => (c.connection_id === IDS.quickbooks ? updated : c));
    return updated;
  };
  const runs = new Map<string, string>();
  const plusMinutes = (minutes: number): string =>
    new Date(Date.parse(options.clock) + minutes * 60_000).toISOString().replace(".000Z", "Z");
  return {
    "GET /v1/portal/entities/{entity_id}/connections": ({ params }) =>
      params.entity_id === COPPERLEAF_ENTITY_ID ? json(page) : json(NOT_FOUND, 404),
    "POST /v1/portal/entities/{entity_id}/connections/{catalog_key}/start": ({ params, body }) => {
      if (params.entity_id !== COPPERLEAF_ENTITY_ID) return json(NOT_FOUND, 404);
      const card = page.items.find((c) => c.catalog_key === params.catalog_key);
      if (card?.consent == null) return json(NOT_FOUND, 404);
      const start = body as ConnectionStartIn;
      if (!start.authorized) return json({ detail: "authorization_required" }, 422);
      if (start.consent_version !== card.consent.version) {
        return json({ detail: "consent_version_stale" }, 409);
      }
      return json(
        {
          consent_id: stableId(`connections:consent:${card.catalog_key}`),
          // Fixture mode never leaves the app: the provider's sign-in is not drawn (POR-16 c).
          authorise_url: `/connect/callback?fixture=${card.catalog_key}`,
          expires_at: plusMinutes(10),
        },
        201,
      );
    },
    "GET /v1/portal/connections/{connection_id}": ({ params }) => {
      const card = cards.get(params.connection_id ?? "");
      if (card === undefined) return json(NOT_FOUND, 404);
      const detail: PortalConnectionDetailOut = {
        card,
        recent_syncs: [],
        ...(w1 !== undefined && card.category === "ledger"
          ? { writes: copperleafWrites(w1.august === true) }
          : {}),
      };
      return json(detail);
    },
    // C-02-T40: the owner's grant (consent copy v2) and revoke; the fixture keeps the state.
    "POST /v1/portal/connections/{connection_id}/write-grants": ({ params, body }) => {
      if (w1 === undefined || params.connection_id !== IDS.quickbooks) return json(NOT_FOUND, 404);
      const asked = body as W1WriteGrantIn;
      if (asked.consent_copy_version !== QUICKBOOKS_WRITE_CONSENT.version) {
        return json({ code: "conflict", facts: { reason: "consent_copy_outdated" } }, 409);
      }
      setWrite("granted");
      return json(
        {
          connection_id: IDS.quickbooks,
          event: "granted",
          at: options.clock,
          consent_copy_version: asked.consent_copy_version,
        },
        201,
      );
    },
    "DELETE /v1/portal/connections/{connection_id}/write-grants/current": ({ params }) => {
      if (w1 === undefined || params.connection_id !== IDS.quickbooks) return json(NOT_FOUND, 404);
      setWrite("offered");
      return json({
        connection_id: IDS.quickbooks,
        event: "revoked",
        at: options.clock,
        consent_copy_version: QUICKBOOKS_WRITE_CONSENT.version,
      });
    },
    "POST /v1/portal/connections/{connection_id}/retry": ({ params }) => {
      const card = cards.get(params.connection_id ?? "");
      if (card === undefined) return json(NOT_FOUND, 404);
      const run = runs.get(card.catalog_key) ?? stableId(`connections:run:${card.catalog_key}`);
      runs.set(card.catalog_key, run);
      return json({ sync_run_id: run, status: "running" }, 202);
    },
    "POST /v1/portal/connections/{connection_id}/disconnect": ({ params }) => {
      const card = cards.get(params.connection_id ?? "");
      if (card === undefined) return json(NOT_FOUND, 404);
      const gone: PortalConnectionCardOut = {
        ...card,
        status: "disconnected",
        status_reason: null,
        version: (card.version ?? 0) + 1,
        allowed_actions: ["connect"],
      };
      cards.set(params.connection_id ?? "", gone);
      return json(gone);
    },
  };
}
