// TAX-12's Feld delivery (T-01-T24; docs/screens/TAX-12.md; handoff spec "TAX-12"): the
// final-approval facts, the delivery packet and the Form 8879 + TR-579-IT envelope as the live
// routes and C7's envelope view will answer them, per artboard. Synthetic seed (Brightwater Hale):
// the figures are the pack ledger's (refund 123,476 − 123,223 = 253; NY 52,805 − 51,536 = 1,269).
import type { DeliveryOut, EnvelopeOut, FinalApprovalOut, SignerOut } from "@abacus/api-client";
import { stableId } from "../prng";
import { FELD_PAYMENTS, FELD_RETURN_ID } from "../tax-compliance";

export const FELD_ENVELOPE_ID = stableId("envelope:feld-2025-8879");
export const FELD_PACKET_ID = stableId("delivery-packet:feld-2025");
const DANIEL_REYES = stableId("user:daniel-reyes");
const CHECKPOINT = "1d5c7b2e-4a9f-4e3b-8a1c-2f6e9d0b7a35";

/** The packet's items in the handoff's order (TAX-12 B). */
export const FELD_PACKET_ITEMS = [
  "client_copy",
  "filing_instructions_letter",
  "form_8879_tr_579_it",
  "voucher_1040es_q4",
  "voucher_it2105_q4",
  "engagement_invoice",
] as const;

export function feldFinalApproval(state: string): FinalApprovalOut {
  const blocked = state === "b";
  return {
    return_id: FELD_RETURN_ID,
    eligible: !blocked,
    blockers: blocked ? [{ kind: "draft_k1", ref_id: null }] : [],
    approver_user_id: DANIEL_REYES,
    checkpoint_id: CHECKPOINT,
    content_hash: `sha256:${"0".repeat(64)}`,
    approved_at: blocked ? null : "2026-09-16T11:20:00-05:00",
  };
}

export function feldDelivery(state: string): DeliveryOut {
  const blocked = state === "b";
  return {
    return_id: FELD_RETURN_ID,
    packet_id: blocked ? null : FELD_PACKET_ID,
    packet_status: blocked ? null : "approved",
    items: blocked
      ? []
      : FELD_PACKET_ITEMS.map((kind) => ({
          kind,
          evidence_version_id: kind === "engagement_invoice" ? null : stableId(`ev:feld:${kind}`),
          included: kind !== "engagement_invoice",
        })),
    payments: [...FELD_PAYMENTS],
    envelope_id: blocked ? null : FELD_ENVELOPE_ID,
    binding_id: blocked ? null : stableId("binding:feld-2025"),
    binding_superseded: false,
    transmitted_on: null,
    acks: [],
    allowed_actions: blocked ? [] : ["delivery_packet.prepare"],
  };
}

function signer(
  order: number,
  name: string,
  title: string,
  status: SignerOut["status"],
  viewed: string | null,
  signed: string | null,
): SignerOut {
  return {
    decline_reason: null,
    id: stableId(`signer:feld-8879:${String(order)}`),
    identity_method: "kba",
    kba_failures: 0,
    name,
    title,
    order,
    provider_recipient_id: null,
    role: "signer",
    routing_group: 1,
    signature_method: signed === null ? null : "provider_adopted",
    signed_at: signed,
    status,
    viewed_at: viewed,
  };
}

/** C7's view of envelope E-Feld (a, a2): Claire signed, Jonah viewed. */
export function feldEnvelope(): EnvelopeOut {
  return {
    date_as_of: null,
    date_as_of_mode: "none",
    documents: [
      {
        id: stableId("envelope-doc:feld:8879"),
        order: 1,
        page_count: 2,
        read_only: false,
        sha256: null,
        title: "Form 8879 + TR-579-IT",
        tri: true,
      },
    ],
    engagement_id: stableId("engagement:jonah-and-claire-feld"),
    evidence: [],
    expires_at: "2026-09-30T23:59:00-05:00",
    fields: [],
    message: null,
    policy_family: "efile_authorization",
    provider_envelope_id: null,
    reminder_cadence: null,
    row: {
      allowed_actions: ["envelope.remind"],
      client_id: stableId("client:jonah-and-claire-feld"),
      client_name: "Jonah & Claire Feld",
      drafted_by_name: "Grace Holloway",
      due_on: "2026-09-30",
      form_code: "8879",
      id: FELD_ENVELOPE_ID,
      needs_handwritten: false,
      number: "E-Feld",
      provider: "fake",
      purpose: "form_8879",
      sent_at: "2026-09-16T13:05:00-05:00",
      sent_by_name: "Grace Holloway",
      signed: 1,
      signer_chips: [
        { name: "Claire Feld", signed: true },
        { name: "Jonah Feld", signed: false },
      ],
      status: "partially_signed",
      title: "Form 8879 + TR-579-IT · TY2025 · Jonah & Claire Feld",
      total: 2,
      work_item_id: FELD_RETURN_ID,
    },
    signer_order: "parallel",
    signers: [
      signer(
        1,
        "Claire Feld",
        "spouse",
        "signed",
        "2026-09-16T19:40:00-05:00",
        "2026-09-16T19:48:00-05:00",
      ),
      signer(2, "Jonah Feld", "taxpayer", "viewed", "2026-09-17T08:02:00-05:00", null),
    ],
    source_id: FELD_RETURN_ID,
    source_kind: "tax_return",
    superseded_at: null,
    version: 1,
    voided_reason: null,
  };
}
