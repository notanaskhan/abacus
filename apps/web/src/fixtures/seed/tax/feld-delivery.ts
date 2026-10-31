// TAX-12's Feld delivery (T-01-T24; docs/screens/TAX-12.md; handoff spec "TAX-12"): the
// final-approval facts, the delivery packet and the Form 8879 + TR-579-IT envelope as the live
// routes and C7's envelope view will answer them, per artboard. Synthetic seed (Brightwater Hale):
// the figures are the pack ledger's (refund 123,476 − 123,223 = 253; NY 52,805 − 51,536 = 1,269).
import type {
  DeliveryOut,
  DeliveryPacketOut,
  EfileAckOut,
  EnvelopeOut,
  FinalApprovalOut,
  SignerOut,
} from "@abacus/api-client";
import { stableId } from "../prng";
import { FELD_PAYMENTS, FELD_RETURN_ID } from "../tax-compliance";

export const FELD_ENVELOPE_ID = stableId("envelope:feld-2025-8879");
export const FELD_PACKET_ID = stableId("delivery-packet:feld-2025");
export const FELD_TRANSMISSION_ID = stableId("transmission:feld-2025");
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

/** The packet (DeliveryPacketOut) as the editor reads it; `included` overrides the toggles. */
export function feldPacket(
  state: string,
  included: Record<string, boolean> = {},
): DeliveryPacketOut {
  const delivery = feldDelivery(state);
  return {
    id: FELD_PACKET_ID,
    return_id: FELD_RETURN_ID,
    version: 1,
    status: "draft",
    items: delivery.items.map((i) => ({ ...i, included: included[i.kind] ?? i.included })),
    letter_document_id: stableId("generated-document:feld-filing-instructions"),
    approved_by_name: null,
  };
}

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

/** T-01-T39: the ERO's states. c and c2 completed; d accepted (four acks); e rejected. */
const COMPLETED_STATES = new Set(["c", "c2", "d", "e"]);
export const FELD_TRANSMITTED_ON = "2026-09-18";
export const FELD_JURISDICTIONS = ["federal", "NY", "IL", "CO"] as const;

function ack(
  jurisdiction: string,
  receivedAt: string,
  status: EfileAckOut["status"],
  last4: string,
  reject: [string, string] | null = null,
): EfileAckOut {
  return {
    id: stableId(`ack:feld:${jurisdiction}:${status}`),
    jurisdiction,
    received_at: receivedAt,
    reject_code: reject?.[0] ?? null,
    reject_text: reject?.[1] ?? null,
    source: "engine_file",
    status,
    submission_id_last4: last4,
  };
}

/** d: the four acknowledgements as the engine reported them (TAX-12 d, the handoff's times). */
export const FELD_ACKS_ACCEPTED: readonly EfileAckOut[] = [
  ack("federal", "2026-09-18T14:47:00-05:00", "accepted", "2614"),
  ack("IL", "2026-09-18T16:10:00-05:00", "accepted", "8831"),
  ack("CO", "2026-09-18T16:22:00-05:00", "accepted", "4407"),
  ack("NY", "2026-09-19T08:55:00-05:00", "accepted", "1952"),
];
/** e: the federal rejection (the engine's text, client-system content). */
export const FELD_ACK_REJECTED: EfileAckOut = ack(
  "federal",
  "2026-09-17T09:12:00-05:00",
  "rejected",
  "2614",
  ["IND-181-01", "the primary taxpayer's Identity Protection PIN is missing or incorrect"],
);

export function feldDelivery(state: string): DeliveryOut {
  const blocked = state === "b";
  const transmitted = state === "d" || state === "e";
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
    transmitted_on: transmitted ? FELD_TRANSMITTED_ON : null,
    acks: state === "d" ? [...FELD_ACKS_ACCEPTED] : state === "e" ? [FELD_ACK_REJECTED] : [],
    // c2: Daniel Reyes, the ERO, may record the transmission; Grace prepares.
    allowed_actions: blocked
      ? []
      : state === "c2"
        ? ["transmission.record"]
        : ["delivery_packet.prepare"],
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

/** C7's view of envelope E-Feld: a, a2 Claire signed and Jonah viewed; c on, both signed. */
export function feldEnvelope(state = "a"): EnvelopeOut {
  const completed = COMPLETED_STATES.has(state);
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
      signed: completed ? 2 : 1,
      signer_chips: [
        { name: "Claire Feld", signed: true },
        { name: "Jonah Feld", signed: completed },
      ],
      status: completed ? "completed" : "partially_signed",
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
      completed
        ? signer(
            2,
            "Jonah Feld",
            "taxpayer",
            "signed",
            "2026-09-17T08:02:00-05:00",
            "2026-09-17T18:12:00-05:00",
          )
        : signer(2, "Jonah Feld", "taxpayer", "viewed", "2026-09-17T08:02:00-05:00", null),
    ],
    source_id: FELD_RETURN_ID,
    source_kind: "tax_return",
    superseded_at: null,
    version: 1,
    voided_reason: null,
  };
}
