// NOT-03 (N-04-T20): the Whitley response at each artboard's epoch, verbatim from the handoff. Figures
// equal NOT-02's: 686.40 + 66.61 = 753.01. All names are fictional. Dev and test only.

import type { BlockOut, ResponseOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type Not03Variant = "a" | "b" | "c" | "d" | "d2" | "e" | "f" | "g";

const BLOCKS: readonly [string, string, number][] = [
  ["address", "Marcus and Dana Whitley · Denver, CO", 0],
  ["date", "September 14, 2026", 0],
  ["re", "Re: Notice CP2000 dated August 24, 2026 · Tax year 2024 · SSN •••-••-6631", 0],
  [
    "agree",
    "We have reviewed the proposed changes to our 2024 tax return and agree with them. The two Forms 1099-INT listed in the notice — Front Range Bank, $1,870.00, and Lakeview Credit Union, $1,250.00 — reached us after we filed on March 14, 2025, and were not included on the return.",
    2,
  ],
  [
    "pay",
    "We have signed the enclosed response page and are paying the full amount due of $753.01 ($686.40 tax and $66.61 interest) through IRS Direct Pay; the payment confirmation is enclosed.",
    1,
  ],
  ["contact", "Please contact us at the address above with any questions.", 0],
];

function blocks(): BlockOut[] {
  return BLOCKS.map(([key, text, cites]) => ({
    citation_ids: Array.from({ length: cites }, (_, i) =>
      stableId(`citation:not03:${key}:${String(i)}`),
    ),
    edited: false,
    key,
    origin: "template",
    template_block_key: key,
    text,
  }));
}

const READINESS: Record<Not03Variant, ResponseOut["readiness"]> = {
  a: "in_review",
  b: "approved",
  c: "out_for_signature",
  d: "ready_to_send",
  d2: "ready_to_send",
  e: "sent",
  f: "sent",
  g: "waiting_decision",
};

function approvals(variant: Not03Variant): ResponseOut["approvals"] {
  const reviewed = variant === "a" || variant === "g" ? "in_progress" : "done";
  const approved = variant === "a" || variant === "g" ? "pending" : "done";
  const person = (name: string, initials: string) => ({
    user_id: stableId(`user:${initials}`),
    initials,
    name,
  });
  return [
    { level: "Prepared · KO", person: person("Kevin Osei", "KO"), state: "done" },
    { level: "Reviewed · SI", person: person("Samuel Ito", "SI"), state: reviewed },
    { level: "Approved · DR", person: person("Daniel Reyes", "DR"), state: approved },
  ] as ResponseOut["approvals"];
}

export function not03Response(variant: Not03Variant = "a"): ResponseOut {
  const out = variant === "c";
  const signed = variant === "d" || variant === "d2" || variant === "e" || variant === "f";
  return {
    approvals: approvals(variant),
    blocks: blocks(),
    channel: "dut",
    content_hash: "d".repeat(64),
    enclosures: [
      {
        evidence_version_id: signed ? stableId("evidence-version:response-page") : null,
        label: "CP2000 response page, signed",
        n: 1,
        on: true,
        required: true,
      },
      {
        evidence_version_id: stableId("evidence-version:N1:1099-int:front-range"),
        label: "Form 1099-INT — Front Range Bank (corrected)",
        n: 2,
        on: true,
        required: true,
      },
      {
        evidence_version_id: stableId("evidence-version:N1:1099-int:lakeview"),
        label: "Form 1099-INT — Lakeview Credit Union",
        n: 3,
        on: true,
        required: true,
      },
      {
        evidence_version_id: signed ? stableId("evidence-version:direct-pay") : null,
        label: "IRS Direct Pay confirmation (added after payment)",
        n: 4,
        on: signed,
        required: false,
      },
    ],
    envelope_id: out || signed ? stableId("envelope:not03") : null,
    envelope_status: out ? "sent" : signed ? "completed" : null,
    follow_up_days: 60,
    id: stableId("notice-response:N1"),
    locked: variant === "e" || variant === "f",
    owner: { user_id: stableId("user:KO"), initials: "KO", name: "Kevin Osei" },
    payment: {
      amounts: { interest: "66.61", penalty: null, tax: "686.40", total: "753.01" },
      confirmation_request_item_id: null,
      method_label: "irs_direct_pay",
      paid_on: signed ? "2026-09-16" : null,
    },
    position: variant === "g" ? null : "agree",
    position_mismatch: false,
    position_source: variant === "g" ? "provisional" : "decided",
    readiness: READINESS[variant],
    readiness_facts: [],
    row_version: 3,
    signer_contact_ids: [stableId("contact:marcus-whitley"), stableId("contact:dana-whitley")],
    template_key: "cp2000_agree",
    version_no: 1,
  } as unknown as ResponseOut;
}
