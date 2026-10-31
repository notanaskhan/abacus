// Fixture handlers for T-01's reads (T-01-T09): the consent summary (ADM-05 tiles) and TAX-12's
// payment instructions, as the live routes will answer them. The designed lists and drawers join
// with each screen's build task.
import type { ConsentOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";
import { REGISTRY_CONSENTS, REGISTRY_TOTAL, consentDetail, renewalDraft } from "../seed/consents";
import { ENGINE_SYNC, FELD_IMPORT, FELD_IMPORT_ID } from "../seed/engine-sync";
import {
  FELD_ENVELOPE_ID,
  FELD_PACKET_ID,
  FELD_TRANSMISSION_ID,
  feldDelivery,
  feldEnvelope,
  feldPacket,
  feldFinalApproval,
} from "../seed/tax/feld-delivery";
import { CONSENT_SUMMARY, FELD_RETURN_ID } from "../seed/tax-compliance";
import { SYNTHETIC_TINS, TAX_PROFILES, WHITLEY_ENTITY } from "../seed/tax-profile";
import { WHITLEY_COMPARISON_2024, WHITLEY_TRANSCRIPTS } from "../seed/transcripts";

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
    // T-01-T32: the evidence drawer (c), renewals (d, h) and the CSV export (queued, logged).
    "GET /v1/consents/{consent_id}": ({ params }) => {
      const found = consentDetail(params.consent_id ?? "");
      return found === null ? json(NOT_FOUND, 404) : json(found);
    },
    "GET /v1/consents/{consent_id}/documents/{document_id}/evidence": () =>
      new Response("%PDF-1.7\n% fixture signed consent\n%%EOF", {
        status: 200,
        headers: { "Content-Type": "application/pdf" },
      }),
    "POST /v1/consents/renewals": ({ body }) => {
      const found = renewalDraft((body as { consent_ids?: string[] }).consent_ids ?? []);
      return found === null ? json(NOT_FOUND, 404) : json(found, 201);
    },
    "POST /v1/consents/exports": () =>
      json({ export_id: "00000000-0000-4000-8000-0000000000c5", status: "queued" }, 202),
    // T-01-T14: CLI-05's profiles, and a logged reveal of their synthetic TINs (P-07's shape).
    "GET /v1/client-entities/{client_entity_id}/tax-profile": ({ params }) => {
      const found = TAX_PROFILES[params.client_entity_id ?? ""];
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    // T-01-T50: CLI-05 a's register and comparison (b, at 9:04 AM, is before Kevin's upload).
    "GET /v1/client-entities/{client_entity_id}/transcripts": ({ params }) =>
      json(params.client_entity_id === WHITLEY_ENTITY && state !== "b" ? WHITLEY_TRANSCRIPTS : []),
    "GET /v1/transcripts/{transcript_id}/comparison": ({ params }) =>
      params.transcript_id === WHITLEY_COMPARISON_2024.transcript_id
        ? json(WHITLEY_COMPARISON_2024)
        : json(NOT_FOUND, 404),
    "POST /v1/transcripts/{transcript_id}/comparisons": ({ params }) =>
      params.transcript_id === WHITLEY_COMPARISON_2024.transcript_id
        ? json(WHITLEY_COMPARISON_2024, 201)
        : json(NOT_FOUND, 404),
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
      params.envelope_id === FELD_ENVELOPE_ID ? json(feldEnvelope(state)) : json(NOT_FOUND, 404),
    // T-01-T39 c2: Daniel records what he transmitted from CCH Axcess (a person's record, R-04).
    "POST /v1/tax-returns/{return_id}/transmissions": ({ params, body }) => {
      if (params.return_id !== FELD_RETURN_ID) return json(NOT_FOUND, 404);
      const asked = body as { jurisdictions: string[]; transmitted_on: string };
      return json(
        {
          id: FELD_TRANSMISSION_ID,
          return_id: FELD_RETURN_ID,
          ero_user_id: stableId("user:daniel-reyes"),
          jurisdictions: asked.jurisdictions,
          transmitted_on: asked.transmitted_on,
          recorded_at: "2026-09-18T11:06:00-05:00",
        },
        201,
      );
    },
    // The packet editor (TAX-12 B): vouchers toggle, the letter regenerates, a manager approves.
    "PATCH /v1/delivery-packets/{packet_id}": ({ params, body }) => {
      if (params.packet_id !== FELD_PACKET_ID) return json(NOT_FOUND, 404);
      const included = (body as { included: Record<string, boolean> }).included;
      return json(feldPacket(state, included));
    },
    "POST /v1/delivery-packets/{packet_id}/letter:regenerate": ({ params }) =>
      params.packet_id === FELD_PACKET_ID ? json(feldPacket(state)) : json(NOT_FOUND, 404),
    "POST /v1/delivery-packets/{packet_id}/approve": ({ params }) =>
      params.packet_id === FELD_PACKET_ID
        ? json({ ...feldPacket(state), status: "approved", approved_by_name: "Daniel Reyes" })
        : json(NOT_FOUND, 404),
    // a2: Grace sends the pre-approved reminder (a person's click, INV-1).
    "POST /v1/envelopes/remind/send": ({ body }) =>
      json({ count: (body as { envelope_ids: string[] }).envelope_ids.length, skipped: [] }),
  };
}
