// Fixture handlers for T-01's reads (T-01-T09): the consent summary (ADM-05 tiles) and TAX-12's
// payment instructions, as the live routes will answer them. The designed lists and drawers join
// with each screen's build task.
import type { ConsentOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { REGISTRY_CONSENTS, REGISTRY_TOTAL } from "../seed/consents";
import { ENGINE_SYNC, FELD_IMPORT, FELD_IMPORT_ID } from "../seed/engine-sync";
import {
  FELD_ENVELOPE_ID,
  feldDelivery,
  feldEnvelope,
  feldFinalApproval,
} from "../seed/tax/feld-delivery";
import { CONSENT_SUMMARY, FELD_RETURN_ID } from "../seed/tax-compliance";
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

const FELD_EXPORT_ID = "6b1f2a40-6f0e-4a8c-9a39-0b0f3c8e2f11";

/** `state` is the artboard: TAX-09's engine-sync answer differs by state (T-01-T15). */
export function taxComplianceHandlers(state = "a"): Record<string, FixtureHandler> {
  const exported = {
    id: FELD_EXPORT_ID,
    return_id: FELD_RETURN_ID,
    checkpoint_id: "1d5c7b2e-4a9f-4e3b-8a1c-2f6e9d0b7a35",
    file_name: "Feld_2025_1040_V3_export.xlsx",
    sha256: "sha256:" + "0".repeat(64),
    generated_at: "2026-09-16T11:43:00-05:00",
    marked_exported_at: null as string | null,
  };
  return {
    "GET /v1/tax-returns/{return_id}/engine-sync": ({ params }) =>
      params.return_id === FELD_RETURN_ID
        ? json(ENGINE_SYNC[state] ?? ENGINE_SYNC.a)
        : json(NOT_FOUND, 404),
    "POST /v1/tax-returns/{return_id}/engine-exports": ({ params }) =>
      params.return_id === FELD_RETURN_ID ? json(exported, 201) : json(NOT_FOUND, 404),
    "GET /v1/engine-exports/{export_id}/file": () =>
      new Response("Feld 2025 Form 1040 · 2025I:FeldJ:V3 (fixture export workbook)", {
        status: 200,
        headers: { "Content-Type": "application/octet-stream" },
      }),
    "POST /v1/engine-exports/{export_id}/mark-exported": () =>
      json({ ...exported, marked_exported_at: "2026-09-16T11:44:00-05:00" }),
    "POST /v1/tax-returns/{return_id}/engine-imports": () => json(FELD_IMPORT, 201),
    "GET /v1/engine-imports/{import_id}": ({ params }) =>
      params.import_id === FELD_IMPORT_ID ? json(FELD_IMPORT) : json(NOT_FOUND, 404),
    "POST /v1/engine-imports/{import_id}/approve": () =>
      json({ ...FELD_IMPORT, status: "approved", allowed_actions: [] }),
    "POST /v1/engine-imports/{import_id}/reject": () =>
      json({ ...FELD_IMPORT, status: "rejected", allowed_actions: [] }),
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
    // T-01-T24: TAX-12's delivery, final approval and the 8879 envelope (C7's view), by artboard.
    "GET /v1/tax-returns/{return_id}/delivery": ({ params }) =>
      params.return_id === FELD_RETURN_ID ? json(feldDelivery(state)) : json(NOT_FOUND, 404),
    "GET /v1/tax-returns/{return_id}/final-approval": ({ params }) =>
      params.return_id === FELD_RETURN_ID ? json(feldFinalApproval(state)) : json(NOT_FOUND, 404),
    "GET /v1/envelopes/{envelope_id}": ({ params }) =>
      params.envelope_id === FELD_ENVELOPE_ID ? json(feldEnvelope()) : json(NOT_FOUND, 404),
    // a2: Grace sends the pre-approved reminder (a person's click, INV-1).
    "POST /v1/envelopes/remind/send": ({ body }) =>
      json({ count: (body as { envelope_ids: string[] }).envelope_ids.length, skipped: [] }),
  };
}
