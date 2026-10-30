// ENG-04's composed letter in fixture mode (N-02-T34; docs/screens/ENG-04.md; N-02 §3.11): the
// Ridgeline cost segregation & §754 analysis letter on C7's composer shape (ComposerLetterOut),
// seen by Daniel Reyes on Mon Sep 14, 2026 at 8:35 AM CT. a is partner approved at 8:32 AM, b is
// its Draft, c is Sent (E13, 0 of 2 signed). Names, wording, amounts and dates verbatim from the
// ENG-04 handoff; every money value is one the server computes from the fee terms (6,500 +
// 12,000 = 18,500, billed 9,250 + 9,250; the engineer's 9,800 shown and never added).
import type {
  ComposerLetterOut,
  LetterClause,
  LetterConsentOut,
  LetterFeesOut,
  LetterVariable,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const ENG04_PERSONA = "daniel-reyes";
export const ENG04_CLOCK = "2026-09-14T08:35:00-05:00";
export const RIDGELINE_ENGAGEMENT = stableId(
  "engagement:ridgeline-property-partners-lp:ridgeline-cost-segregation-754-analysis",
);
export const RIDGELINE_TEMPLATE_VERSION = stableId("report-template-version:bh-tax-advisory:4");
export const RIDGELINE_DOCUMENT = stableId("generated-document:ridgeline-letter");
export const E13_ENVELOPE = stableId("envelope:E13");

type Paper = NonNullable<ComposerLetterOut["paper"]>;
type Block = Paper[number];

const text = (t: string) => ({ type: "text" as const, text: t });
const v = (key: string) => ({ type: "var" as const, key });
const p = (...runs: ({ type: "text"; text: string } | { type: "var"; key: string })[]): Block => ({
  type: "paragraph",
  runs,
});

function clause(id: string, title: string, nonStandard: boolean, blocks: Block[]): Block {
  return {
    type: "section",
    id,
    title,
    override: false,
    blocks: [{ type: "clause", clause_id: id, enabled: true, non_standard: nonStandard, blocks }],
  };
}

/** The paper: BH Tax Advisory Letter v4's body as Ridgeline's letter uses it. */
export const RIDGELINE_PAPER: Paper = [
  p(v("letter.date")),
  p(v("letter.addressee")),
  { type: "heading", level: 1, text: "Re: Cost segregation and section 754 analysis" },
  clause("scope", "1. Scope of services", false, [
    p(
      text(
        "We will (a) analyze whether the partnership should elect under section 754 for the June 30, 2025 transfer of a 5% interest from Pell Street Ventures LLC to Pell Street II LLC, model the resulting section 743(b) adjustment and its section 755 allocation, and give you a written recommendation.",
      ),
    ),
    p(
      text(
        "We will also (b) coordinate a cost segregation study of the Elm Street building in Chicago (placed in service April 2018; depreciable cost $6,240,000) performed by Tallgrass Cost Engineering, LLC, review the study, and prepare Form 3115 (automatic change, DCN 7) with the section 481(a) adjustment for the 2026 tax year.",
      ),
    ),
  ]),
  clause("not-included", "2. Services not included", false, [
    p(
      text(
        "Studies of Larimer Lofts and Bergen Street; amended returns or administrative adjustment requests; representation in an IRS examination.",
      ),
    ),
  ]),
  clause("timing-754", "3. Timing and the section 754 deadline", true, [
    p(
      text(
        "A section 754 election is made with a statement attached to the partnership's timely filed 2025 Form 1065, due ",
      ),
      v("section_754.due"),
      text("."),
    ),
    p(
      text(
        "If the partners have not decided by then, relief under Treas. Reg. §301.9100-2 may allow the election until September 15, 2027.",
      ),
    ),
  ]),
  clause("responsibilities", "4. The partnership's responsibilities", false, [
    p(
      text(
        "The decision to make any election is the partnership's. You will provide the documents we request and the engineer's access to the property.",
      ),
    ),
  ]),
  clause("engineer-reliance", "5. Reliance on the engineer's study", true, [
    p(
      text(
        "The cost allocations come from the engineer's study. We will review its methodology but do not audit it.",
      ),
    ),
  ]),
  clause("fees", "6. Fees and billing", false, [
    p(
      text("A fixed fee of "),
      v("fee.total"),
      text(" ("),
      v("fee.breakdown"),
      text("), billed "),
      v("billing.installment_1"),
      text(" on signature and "),
      v("billing.installment_2"),
      text(" on delivery of the Form 3115 package. The engineer bills its fee, estimated at "),
      v("third_party_fee.estimate_1"),
      text(", directly."),
    ),
  ]),
  clause("technology-ai", "7. Use of technology and AI", false, [
    p(
      text(
        "We use Accrued, a platform whose AI agents draft analyses under our supervision. Data stays in the United States, is not used to train models, and every output is reviewed and approved by a named Brightwater Hale professional.",
      ),
    ),
  ]),
  clause("confidentiality", "8. Confidentiality and records", false, []),
  clause("liability", "9. Limitation of liability", false, []),
  clause("signatures", "10. Signatures", false, [
    {
      type: "signature_block",
      signers: [
        { label: "BRIGHTWATER HALE LLP — Daniel Reyes, Partner", name: [v("firm.signer")] },
        {
          label:
            "ACCEPTED: Ridgeline Property Partners, LP, by Ridgeline GP LLC, its general partner — Owen Calder, Managing Member",
          name: [text("Owen Calder")],
        },
      ],
    },
  ]),
];

const CLAUSE_TITLES: readonly [string, string, boolean][] = [
  ["scope", "Scope of services", false],
  ["not-included", "Services not included", false],
  ["timing-754", "Timing and the §754 deadline", true],
  ["responsibilities", "Partnership's responsibilities", false],
  ["engineer-reliance", "Reliance on the engineer's study", true],
  ["fees", "Fees and billing", false],
  ["technology-ai", "Use of technology and AI", false],
  ["confidentiality", "Confidentiality and records", false],
  ["liability", "Limitation of liability", false],
  ["signatures", "Signatures", false],
];

export const RIDGELINE_CLAUSES: LetterClause[] = CLAUSE_TITLES.map(([key, title, ns]) => ({
  key,
  title,
  state: "on",
  non_standard: ns,
}));

export const RIDGELINE_FEES: LetterFeesOut = {
  basis: "fixed",
  lines: [
    { label: "for the section 754 work", amount_cents: 650_000 },
    { label: "for cost segregation coordination and Form 3115", amount_cents: 1_200_000 },
  ],
  total_cents: 1_850_000,
  installments: [
    { label: "on signature", share_bp: 5_000, amount_cents: 925_000 },
    { label: "on Form 3115 delivery", share_bp: 5_000, amount_cents: 925_000 },
  ],
  third_party: [
    {
      payee: "Tallgrass Cost Engineering, LLC",
      estimated_cents: 980_000,
      included_in_total: false,
    },
  ],
};

const fact = (
  key: string,
  value: string | null,
  reason: string | null = null,
): LetterVariable => ({
  key,
  value,
  source: "facts",
  reason,
  label: null,
});
const computed = (key: string, value: string): LetterVariable => ({
  key,
  value,
  source: "computed",
  reason: null,
  label: null,
});
const declared = (key: string, label: string, value: string): LetterVariable => ({
  key,
  value,
  source: "override",
  reason: null,
  label,
});

export const RIDGELINE_VARIABLES: LetterVariable[] = [
  fact("client.name", "Ridgeline Property Partners, LP"),
  fact("client.signer", "Owen Calder · Managing Member, Ridgeline GP LLC (general partner)"),
  fact("firm.signer", "Daniel Reyes, Partner"),
  fact("approver_of_record", null, "cas_only"),
  fact("ske_designee", null, "attest_only"),
  fact("ebp.limited_scope_election", null, "ebp_only"),
  fact("ai_use.disclosure", "on"),
  fact("acceptance.decided_on", "September 12, 2026"),
  fact("letter.date", "September 14, 2026"),
  computed("fee.total", "$18,500"),
  computed("fee.summary", "$18,500 fixed"),
  computed(
    "fee.breakdown",
    "$6,500 for the section 754 work; $12,000 for cost segregation coordination and Form 3115",
  ),
  computed("billing.terms", "50% on signature · 50% on Form 3115 delivery"),
  computed("billing.schedule", "$9,250 on signature · $9,250 on Form 3115 delivery"),
  computed("billing.installment_1", "$9,250"),
  computed("billing.installment_2", "$9,250"),
  computed("third_party_fee.summary", "Est. $9,800 · billed by Tallgrass Cost Engineering, LLC"),
  computed("third_party_fee.estimate_1", "$9,800"),
  declared(
    "letter.addressee",
    "Addressee",
    "Owen Calder, Managing Member, Ridgeline GP LLC, General Partner of Ridgeline Property Partners, LP",
  ),
  declared("section_754.decision_by", "§754 decision needed by", "Sep 15, 2026"),
  declared("section_754.due", "§754 statement due", "September 15, 2026"),
  declared("cost_seg.deliverables", "Cost-segregation deliverables", "Feb 15, 2027"),
];

export const RIDGELINE_CONSENTS: LetterConsentOut[] = [
  {
    purpose: "disclosure_ai_subprocessors",
    label: "Consent to disclose — AI sub-processors · Ridgeline Property Partners, LP",
    status: "on_file",
    signed_on: "2026-02-06",
    expires_on: "2027-02-06",
  },
  {
    purpose: "disclosure_named_third_party",
    label: "Consent to disclose — named third party · Tallgrass Cost Engineering, LLC",
    status: "needed",
    signed_on: null,
    expires_on: null,
  },
];

const BASE: ComposerLetterOut = {
  engagement_id: RIDGELINE_ENGAGEMENT,
  mode: "composed",
  status: "partner_approved",
  version_no: 3,
  template_version_id: RIDGELINE_TEMPLATE_VERSION,
  clauses: RIDGELINE_CLAUSES,
  variables: RIDGELINE_VARIABLES,
  fees: RIDGELINE_FEES,
  redline_count: 2,
  generated_document_id: RIDGELINE_DOCUMENT,
  template_name: "BH Tax Advisory Letter",
  template_version_no: 4,
  clause_library: "BH clauses 2026.1",
  letterhead: {
    firm: "Brightwater Hale LLP",
    address: ["311 West Brannock Street, Chicago, IL"],
  },
  paper: RIDGELINE_PAPER,
  signers: [
    { order: 1, name: "Owen Calder", role: "client", identity: "email_code", signed: false },
    { order: 2, name: "Daniel Reyes", role: "firm", identity: "email_code", signed: false },
  ],
  consents: RIDGELINE_CONSENTS,
  approved_by_name: "Daniel Reyes",
  approved_at: "2026-09-14T13:32:00Z",
  approval_content_hash: "7c1e0d4b9a2f3e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a7f8e9d",
  envelope_id: null,
  allowed_actions: ["letter.read", "letter.draft", "letter.send"],
  version: 3,
};

export type Eng04Frame = "a" | "b" | "c";

/** a partner approved, b its Draft, c Sent with E13 (0 of 2 signed). */
export const RIDGELINE_LETTERS: Readonly<Record<Eng04Frame, ComposerLetterOut>> = {
  a: BASE,
  b: {
    ...BASE,
    status: "draft",
    version_no: 4,
    version: 4,
    approved_by_name: null,
    approved_at: null,
    approval_content_hash: null,
    allowed_actions: ["letter.read", "letter.draft"],
  },
  c: {
    ...BASE,
    status: "sent",
    envelope_id: E13_ENVELOPE,
    allowed_actions: ["letter.read"],
  },
};
