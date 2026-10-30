// SIG-02's builder records in fixture mode (N-02-T21; docs/screens/SIG-02.md): the envelopes the
// frames open, on the C7 shapes (EnvelopeOut, EnvelopePolicyOut, ValidationOut), seen by Grace
// Holloway at Mon Sep 14, 2026, 9:40 AM CT. a is Harborview's 8879-PE draft (E18), e is E13's
// Ridgeline engagement letter (Owen Calder, then Daniel Reyes), f is a with Sofia Lindqvist's email
// missing. Names, titles, messages and dates verbatim from the SIG-02 handoff.
import type { EnvelopeOut, EnvelopePolicyOut, SignerOut, ValidationOut } from "@abacus/api-client";
import { rowOf } from "../handlers/signatures";
import { stableId } from "./prng";
import { OUT, TO_SEND } from "./signatures";

export const SIG02_PERSONA = "grace-holloway";
export const SIG02_CLOCK = "2026-09-14T09:40:00-05:00";

const signer = (
  key: string,
  order: number,
  name: string,
  role: SignerOut["role"],
  identity: SignerOut["identity_method"],
  title: string,
  email: string | null,
): SignerOut => ({
  id: stableId(`signer:${key}`),
  order,
  routing_group: order,
  name,
  role,
  identity_method: identity,
  status: "pending",
  kba_failures: 0,
  viewed_at: null,
  signed_at: null,
  signature_method: null,
  decline_reason: null,
  provider_recipient_id: null,
  title,
  email,
});

const E18 = TO_SEND.find((e) => e.key === "E18");
const E13 = OUT.find((e) => e.key === "E13");
if (E18 === undefined || E13 === undefined) throw new Error("SIG-02 fixtures need E18 and E13");

const SOFIA = signer(
  "E18:sofia",
  1,
  "Dr. Sofia Lindqvist",
  "signer",
  "kba",
  "Managing member, Harborview Property GP LLC",
  "sofia@harborviewdental.com",
);
const ERO = signer(
  "E18:daniel",
  2,
  "Daniel Reyes",
  "ero",
  "firm_sso",
  "Countersigns after the signer · practitioner PIN",
  "daniel.reyes@brightwaterhale.com",
);
const E18_8879 = stableId("envelope-doc:E18:8879pe");
const E18_1065 = stableId("envelope-doc:E18:1065");

export const HARBORVIEW: EnvelopeOut = {
  row: rowOf(E18),
  version: 3,
  source_kind: "tax_return",
  source_id: stableId("work-item:TY2025 Form 1065 · Harborview"),
  engagement_id: null,
  policy_family: "efile_authorization",
  signer_order: "sequential",
  documents: [
    {
      id: E18_8879,
      order: 1,
      title: "Form 8879-PE (2025)",
      page_count: 2,
      read_only: false,
      tri: true,
      sha256: null,
    },
    {
      id: E18_1065,
      order: 2,
      title: "2025 Form 1065 — client copy",
      page_count: 46,
      read_only: true,
      tri: true,
      sha256: null,
    },
  ],
  signers: [SOFIA, ERO],
  fields: [
    {
      id: stableId("field:E18:sign"),
      document_id: E18_8879,
      page: 1,
      kind: "signature",
      signer_id: SOFIA.id,
      x: 72,
      y: 520,
      w: 300,
      h: 36,
      anchor: null,
    },
    {
      id: stableId("field:E18:date"),
      document_id: E18_8879,
      page: 1,
      kind: "date",
      signer_id: SOFIA.id,
      x: 400,
      y: 520,
      w: 140,
      h: 36,
      anchor: null,
    },
  ],
  message:
    "Please review and sign your 2025 Form 8879-PE so we can e-file Harborview's return by September 15.",
  reminder_cadence: "daily_until_signed",
  expires_at: "2026-09-22T23:59:00-05:00",
  date_as_of_mode: "none",
  date_as_of: null,
  evidence: [],
  provider_envelope_id: null,
  superseded_at: null,
  voided_reason: null,
};

const OWEN = signer(
  "E13:owen",
  1,
  "Owen Calder",
  "signer",
  "email_code",
  "Managing partner, Ridgeline Property GP",
  "owen@ridgelinepp.com",
);
const REYES = signer(
  "E13:daniel",
  2,
  "Daniel Reyes",
  "countersigner",
  "firm_sso",
  "Countersigns for Brightwater Hale LLP",
  "daniel.reyes@brightwaterhale.com",
);
const E13_LETTER = stableId("envelope-doc:E13:letter");

export const RIDGELINE_LETTER: EnvelopeOut = {
  row: rowOf(E13, "draft"),
  version: 2,
  source_kind: "engagement_letter",
  source_id: stableId("letter:E13"),
  engagement_id: null,
  policy_family: "engagement_letter",
  signer_order: "sequential",
  documents: [
    {
      id: E13_LETTER,
      order: 1,
      title: "Engagement letter — E13",
      page_count: 4,
      read_only: false,
      tri: false,
      sha256: null,
    },
  ],
  signers: [OWEN, REYES],
  fields: [
    {
      id: stableId("field:E13:sign"),
      document_id: E13_LETTER,
      page: 1,
      kind: "signature",
      signer_id: OWEN.id,
      x: 72,
      y: 430,
      w: 468,
      h: 40,
      anchor: null,
    },
    {
      id: stableId("field:E13:date"),
      document_id: E13_LETTER,
      page: 1,
      kind: "date",
      signer_id: OWEN.id,
      x: 72,
      y: 480,
      w: 468,
      h: 28,
      anchor: null,
    },
    {
      id: stableId("field:E13:firm"),
      document_id: E13_LETTER,
      page: 1,
      kind: "signature",
      signer_id: REYES.id,
      x: 72,
      y: 520,
      w: 468,
      h: 40,
      anchor: null,
    },
  ],
  message:
    "Please review and sign the engagement letter for the cost segregation and §754 analysis.",
  reminder_cadence: "daily_until_signed",
  expires_at: "2026-09-28T23:59:00-05:00",
  date_as_of_mode: "none",
  date_as_of: null,
  evidence: [],
  provider_envelope_id: null,
  superseded_at: null,
  voided_reason: null,
};

/** f: a with Sofia Lindqvist's email missing. */
export const HARBORVIEW_NO_EMAIL: EnvelopeOut = {
  ...HARBORVIEW,
  signers: [{ ...SOFIA, email: null }, ERO],
};

const CADENCES = ["daily_until_signed", "every_3_days", "weekly"];

/** The firm's signing policies (N-02-T13): the 8879 family takes KBA, never an email or SMS code
 * (SPEC-381 AC-8; IRS Pub 1345). */
export const POLICIES: readonly EnvelopePolicyOut[] = [
  {
    policy_family: "efile_authorization",
    version: 1,
    allowed_identity_methods: ["kba", "in_person_id", "firm_sso"],
    default_identity_method: "kba",
    kba_max_attempts: 3,
    failure_path: "wet_signature",
    countersign_required: true,
    default_expiry_days: 8,
    max_reminders: 7,
    reminder_cadences: CADENCES,
  },
  {
    policy_family: "engagement_letter",
    version: 1,
    allowed_identity_methods: ["kba", "email_code", "in_person_id", "firm_sso"],
    default_identity_method: "email_code",
    kba_max_attempts: 3,
    failure_path: "wet_signature",
    countersign_required: true,
    default_expiry_days: 14,
    max_reminders: 7,
    reminder_cadences: CADENCES,
  },
];

export const CHECKS: Readonly<Record<"a" | "e", ValidationOut>> = {
  a: {
    ok: true,
    problems: [],
    checks: [
      { code: "amounts_match", ok: true },
      { code: "signer_gp_managing_member", ok: true },
      { code: "ero_efin", ok: true },
      { code: "no_ssn_visible", ok: true },
    ],
  },
  e: {
    ok: true,
    problems: [],
    checks: [
      { code: "letter_partner_approved", ok: true },
      { code: "signer_gp_managing_partner", ok: true },
      { code: "countersign_after_client", ok: true },
      { code: "no_tin_visible", ok: true },
    ],
  },
};

/** f: Send stays disabled; the server names the signer whose email is missing. */
export const CHECKS_F: ValidationOut = {
  ok: false,
  problems: [`signer_email_missing:${SOFIA.id}`],
  checks: CHECKS.a.checks ?? [],
};
