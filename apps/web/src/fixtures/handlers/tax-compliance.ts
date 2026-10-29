// Fixture handlers for T-01's reads (T-01-T09): the consent summary (ADM-05 tiles) and TAX-12's
// payment instructions, as the live routes will answer them. The designed lists and drawers join
// with each screen's build task.
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { CONSENT_SUMMARY, FELD_PAYMENTS, FELD_RETURN_ID } from "../seed/tax-compliance";

const NOT_FOUND = { detail: "not found" };

export function taxComplianceHandlers(): Record<string, FixtureHandler> {
  return {
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
