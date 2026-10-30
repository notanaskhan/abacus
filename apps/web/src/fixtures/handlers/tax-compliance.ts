// Fixture handlers for T-01's reads (T-01-T09): the consent summary (ADM-05 tiles) and TAX-12's
// payment instructions, as the live routes will answer them. The designed lists and drawers join
// with each screen's build task.
import type { ConsentOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { REGISTRY_CONSENTS, REGISTRY_TOTAL } from "../seed/consents";
import { CONSENT_SUMMARY, FELD_PAYMENTS, FELD_RETURN_ID } from "../seed/tax-compliance";
import { SYNTHETIC_TINS, TAX_PROFILES } from "../seed/tax-profile";

/** E0 (Mon Sep 14, 2026, 9:24 AM CT): "expiring" is signed and ending within 30 days. */
const E0 = Date.parse("2026-09-14T09:24:00-05:00");
const DAY = 86_400_000;

function expiring(c: ConsentOut): boolean {
  if (c.status !== "signed" || c.expires_at === null) return false;
  const left = Date.parse(c.expires_at) - E0;
  return left >= 0 && left <= 30 * DAY;
}

/** ADM-05's list: `status` (the registry's codes, plus derived `expiring`), `purpose`, `q`. */
function registry(query: URLSearchParams): Response {
  const status = query.get("status");
  const purpose = query.get("purpose");
  const q = query.get("q")?.toLowerCase();
  const items = REGISTRY_CONSENTS.filter(
    (c) =>
      (status === null || (status === "expiring" ? expiring(c) : c.status === status)) &&
      (purpose === null || c.purpose === purpose) &&
      (q === undefined || c.client_name.toLowerCase().includes(q)),
  );
  const filtered = status !== null || purpose !== null || q !== undefined;
  return json({ items, next_cursor: null, total: filtered ? items.length : REGISTRY_TOTAL });
}

const NOT_FOUND = { detail: "not found" };

export function taxComplianceHandlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/consents/summary": () => json(CONSENT_SUMMARY),
    "GET /v1/consents": ({ query }) => registry(query),
    // T-01-T14: CLI-05's profiles, and a logged reveal of their synthetic TINs (P-07's shape).
    "GET /v1/client-entities/{client_entity_id}/tax-profile": ({ params }) => {
      const found = TAX_PROFILES[params.client_entity_id ?? ""];
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    "POST /v1/client-entities/{entity_id}/tin/reveal": ({ params, body }) => {
      const entityId = params.entity_id ?? "";
      const value = SYNTHETIC_TINS[entityId];
      if (value === undefined) return json(NOT_FOUND, 404);
      if ((body as { reason?: string } | null)?.reason === undefined) {
        return json({ detail: "validation" }, 422);
      }
      return json({ entity_id: entityId, kind: "ssn", value, remask_after_seconds: 10 });
    },
    "GET /v1/tax-returns/{return_id}/delivery": ({ params }) =>
      params.return_id === FELD_RETURN_ID
        ? json({
            return_id: FELD_RETURN_ID,
            packet_id: null,
            packet_status: null,
            items: [],
            payments: FELD_PAYMENTS,
            envelope_id: null,
            binding_id: null,
            binding_superseded: false,
            transmitted_on: null,
            acks: [],
            allowed_actions: [],
          })
        : json(NOT_FOUND, 404),
  };
}
