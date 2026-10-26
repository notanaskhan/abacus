// Fixture handlers for C20 v1, POR-16 (A-02-T06; docs/contracts/c20-integrations.md): the
// entity's cards for one artboard, the details drawer, and the start, retry and disconnect the stub
// fixes. A start without the authorization toggle answers 422 `authorization_required` and an old
// consent copy 409 `consent_version_stale`; another entity or connection answers 404 (INV-4); a
// second Try again while the run is live returns the same run.
import type {
  ConnectionStartIn,
  PortalConnectionCardOut,
  PortalConnectionDetailOut,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { COPPERLEAF_ENTITY_ID, type Por16State, copperleafConnections } from "../seed/connections";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not found" };

export function connectionsHandlers(
  state: Por16State,
  options: { clock: string },
): Record<string, FixtureHandler> {
  const page = copperleafConnections(state);
  const cards = new Map<string, PortalConnectionCardOut>();
  for (const card of page.items) {
    if (card.connection_id) cards.set(card.connection_id, card);
  }
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
      const detail: PortalConnectionDetailOut = { card, recent_syncs: [] };
      return json(detail);
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
