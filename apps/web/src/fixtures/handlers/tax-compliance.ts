// Fixture handlers for T-01's reads (T-01-T09): the consent summary (ADM-05 tiles) and TAX-12's
// payment instructions, as the live routes will answer them. The designed lists and drawers join
// with each screen's build task.
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { ENGINE_SYNC, FELD_IMPORT, FELD_IMPORT_ID } from "../seed/engine-sync";
import { CONSENT_SUMMARY, FELD_PAYMENTS, FELD_RETURN_ID } from "../seed/tax-compliance";

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
