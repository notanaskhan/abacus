// ENG-04's composed letter in fixture mode (N-02-T34; docs/screens/ENG-04.md; N-02 §3.11): the
// Ridgeline cost segregation & §754 analysis letter on C7's composer shape (ComposerLetterOut),
// seen by Daniel Reyes on Mon Sep 14, 2026 at 8:35 AM CT. a is partner approved at 8:32 AM, b is
// its Draft, c is Sent (E13, 0 of 2 signed). Names, wording, amounts and dates verbatim from the
// ENG-04 handoff; every money value is one the server computes from the fee terms (6,500 +
// 12,000 = 18,500, billed 9,250 + 9,250; the engineer's 9,800 shown and never added).
import type {
  CompareOut,
  ComposerLetterOut,
  LetterDocumentOut,
  SectionBlockOutput,
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

type Block = SectionBlockOutput["blocks"][number];
type Paper = Block[];

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

export type Eng04Frame = "a" | "b" | "c" | "d" | "e" | "f";

/** a partner approved, b its Draft, c Sent with E13 (0 of 2 signed). */
export const RIDGELINE_LETTERS: Readonly<Record<"a" | "b" | "c", ComposerLetterOut>> = {
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

// --- N-02-T37: ENG-04 d, e, f and Compare to standard ----------------------------------------
// d is Copperleaf's 2026 Close letter, signed and locked; e is Fairhaven's PY2025 EBP audit
// letter, sent Sep 8; f is the Feld TY2025 letter with its two §7216 consents as separate
// documents. The handoff names their status lines, signers, dates, the SSARS note, the AU-C 210
// clauses and the fee; their paper is the firm's template bodies as Brightwater Hale imported them
// (P-11-T13: BH CAS Engagement Letter, BH Audit Letter · EBP, BH §7216 consents), synthetic.

const LETTERHEAD = {
  firm: "Brightwater Hale LLP",
  address: ["311 West Brannock Street, Chicago, IL"],
};

export const COPPERLEAF_ENGAGEMENT = stableId("engagement:copperleaf:2026-close");
export const FAIRHAVEN_ENGAGEMENT = stableId("engagement:fairhaven:py2025");
export const FELD_ENGAGEMENT = stableId("engagement:feld");
export const E11_ENVELOPE = stableId("envelope:E11");

const signature = (...lines: [string, string][]): Block => ({
  type: "signature_block",
  signers: lines.map(([label, key]) => ({ label, name: [v(key)] })),
});

const section = (id: string, title: string, ...blocks: Block[]): Block =>
  clause(id, title, false, blocks);

const states = (titles: readonly (readonly [string, string])[]): LetterClause[] =>
  titles.map(([key, title]) => ({ key, title, state: "on", non_standard: false }));

const AI_USE = p(
  text(
    "We use Accrued, a platform whose AI agents draft work under our supervision. Data stays " +
      "in the United States, is not used to train models, and every output is reviewed and " +
      "approved by a named Brightwater Hale professional.",
  ),
);
const FEES = p(
  text("Our fee for these services is "),
  v("fee.total"),
  text(", billed as set out below."),
);

const CAS_CLAUSES = [
  ["scope", "Scope of services"],
  ["ssars-route", "Reporting on the monthly statements"],
  ["approver", "Approver of record"],
  ["fees", "Fees and billing"],
  ["technology-ai", "Use of technology and AI"],
] as const;

export const SSARS_NOTE =
  "Monthly statements: AR-C 70 preparation with the 'No assurance is provided' legend for " +
  "periods ending before Dec 15, 2026 (SSARS 27 not early-adopted); from the December 2026 " +
  "period, statements prepared within this CAS engagement are outside AR-C 70 (SSARS 27).";

/** d: Copperleaf's 2026 Close letter, signed Mar 2 and countersigned Mar 3, locked. */
export const COPPERLEAF_LETTER: ComposerLetterOut = {
  engagement_id: COPPERLEAF_ENGAGEMENT,
  mode: "composed",
  status: "signed",
  version_no: 2,
  template_version_id: stableId("report-template-version:bh-cas-engagement-letter:1"),
  clauses: states(CAS_CLAUSES),
  variables: [
    fact("client.name", "Copperleaf Coffee Roasters, Inc."),
    fact("client.signer", "Tess Moreno"),
    fact("firm.signer", "Priya Raman, Partner"),
    fact("approver_of_record", "Ben Ashby, Controller"),
    fact("ske_designee", null, "attest_only"),
    fact("ebp.limited_scope_election", null, "ebp_only"),
    fact("ai_use.disclosure", "on"),
  ],
  fees: null,
  redline_count: 0,
  generated_document_id: stableId("generated-document:copperleaf-letter"),
  template_name: "BH CAS Engagement Letter",
  template_version_no: 1,
  clause_library: "BH clauses 2026.1",
  letterhead: LETTERHEAD,
  paper: [
    p(v("client.name")),
    { type: "heading", level: 1, text: "Re: Client accounting services" },
    section(
      "scope",
      "Scope of services",
      p(
        text(
          "We will maintain your books, reconcile your accounts each month and prepare " +
            "monthly financial statements from the posted ledger.",
        ),
      ),
    ),
    section(
      "ssars-route",
      "Reporting on the monthly statements",
      p(
        text(
          "Monthly statements are prepared under AR-C 70 with the legend 'No assurance is " +
            "provided' on each page for periods ending before December 15, 2026; from the " +
            "December 2026 period, statements prepared within this engagement are outside " +
            "AR-C 70 (SSARS 27).",
        ),
      ),
    ),
    section(
      "approver",
      "Approver of record",
      p(text("You name an approver of record who approves each month's package.")),
    ),
    section("technology-ai", "Use of technology and AI", AI_USE),
    signature(["BRIGHTWATER HALE LLP", "firm.signer"], ["ACCEPTED", "client.signer"]),
  ],
  signers: [
    {
      order: 1,
      name: "Tess Moreno",
      role: "client",
      identity: "email_code",
      signed: true,
      signed_on: "2026-03-02",
    },
    {
      order: 2,
      name: "Priya Raman",
      role: "firm",
      identity: "email_code",
      signed: true,
      signed_on: "2026-03-03",
    },
  ],
  consents: [],
  approved_by_name: "Priya Raman",
  approved_at: "2026-02-27T15:00:00Z",
  approval_content_hash: "3a7f0c2e9b1d4a6f8e2c5b9d0a3f7e1c6b4d8a2f9e0c3b7d5a1f6e8c2b4d9a07",
  envelope_id: stableId("envelope:L1"),
  allowed_actions: ["letter.read", "letter.amend"],
  version: 2,
  sent_at: "2026-02-27T15:00:00Z",
  routing_note: SSARS_NOTE,
  documents: [],
};

const AUDIT_CLAUSES = [
  ["objective", "Objective and scope"],
  ["management", "Management's responsibilities"],
  ["auditor", "Auditor's responsibilities"],
  ["limitations", "Limitations"],
  ["report", "Form of report"],
  ["technology-ai", "Use of technology and AI"],
  ["fees", "Fees ($26,500)"],
  ["signatures", "Signatures"],
] as const;

/** e: Fairhaven's PY2025 EBP audit letter (AU-C 210), sent Sep 8, 0 of 2 signed. */
export const FAIRHAVEN_LETTER: ComposerLetterOut = {
  engagement_id: FAIRHAVEN_ENGAGEMENT,
  mode: "composed",
  status: "sent",
  version_no: 1,
  template_version_id: stableId("report-template-version:bh-audit-letter-ebp:3"),
  clauses: states(AUDIT_CLAUSES),
  variables: [
    fact("client.name", "Fairhaven Foods 401(k) Plan"),
    fact("client.signer", "Plan administrator"),
    fact("firm.signer", "Margaret Okonkwo, Partner"),
    computed("fee.summary", "$26,500"),
    computed("fee.total", "$26,500"),
    fact("approver_of_record", null, "cas_only"),
    fact("ske_designee", null, "no_nonattest"),
    fact("ebp.limited_scope_election", "Plan administrator elects (certification required)"),
    fact("ai_use.disclosure", "on"),
  ],
  fees: null,
  redline_count: 0,
  generated_document_id: stableId("generated-document:fairhaven-letter"),
  template_name: "BH Audit Letter · EBP",
  template_version_no: 3,
  clause_library: "BH clauses 2026.1",
  letterhead: LETTERHEAD,
  paper: [
    p(v("client.name")),
    { type: "heading", level: 1, text: "Re: Audit of the plan's financial statements" },
    section(
      "objective",
      "Objective and scope",
      p(text("We will audit the plan's financial statements.")),
    ),
    section(
      "management",
      "Management's responsibilities",
      p(text("Management is responsible for the financial statements and the plan's records.")),
    ),
    section(
      "auditor",
      "Auditor's responsibilities",
      p(text("We will conduct the audit under auditing standards generally accepted in the US.")),
    ),
    section("limitations", "Limitations", p(text("An audit does not detect every misstatement."))),
    section(
      "report",
      "Form of report",
      p(text("We expect to issue a written report on the audit.")),
    ),
    section("technology-ai", "Use of technology and AI", AI_USE),
    section("fees", "Fees and billing", FEES),
    signature(["BRIGHTWATER HALE LLP", "firm.signer"], ["ACCEPTED", "client.signer"]),
  ],
  signers: [
    {
      order: 1,
      name: "Plan administrator",
      role: "client",
      identity: "email_code",
      signed: false,
    },
    { order: 2, name: "Margaret Okonkwo", role: "firm", identity: "email_code", signed: false },
  ],
  consents: [],
  approved_by_name: "Margaret Okonkwo",
  approved_at: "2026-09-08T13:30:00Z",
  approval_content_hash: "9e4b1f7a2c6d0e3b8f5a1c9d4e7b2a6f0c3e8d1b5a9f4c7e2d6b0a3f8e1c5d92",
  envelope_id: E11_ENVELOPE,
  allowed_actions: ["letter.read"],
  version: 1,
  sent_at: "2026-09-08T14:00:00Z",
  routing_note: null,
  documents: [],
};

const consentPaper = (heading: string, ask: string, recipients: string): Block[] => [
  { type: "heading", level: 1, text: heading },
  p(text("Taxpayer: "), v("taxpayer.name")),
  p(text(ask)),
  p(text(`Recipients: ${recipients}`)),
  p(text("Tax years covered: "), v("consent.tax_years")),
  signature(["Taxpayer", "taxpayer.name"]),
];

const FELD_SIGNERS: LetterDocumentOut["signers"] = [
  {
    order: 1,
    name: "Claire Feld",
    role: "client",
    identity: "email_code",
    signed: true,
    signed_on: "2026-02-02",
  },
  {
    order: 2,
    name: "Jonah Feld",
    role: "client",
    identity: "email_code",
    signed: true,
    signed_on: "2026-02-02",
  },
];

/** f's two documents: one purpose each, signed separately (Rev. Proc. 2013-14 §5.05). */
export const FELD_CONSENT_DOCUMENTS: LetterDocumentOut[] = [
  {
    id: stableId("consent-document:feld:use"),
    title: "Consent to use tax return information",
    template_name: "BH §7216 Consent to Use",
    template_version_no: 2,
    signers: FELD_SIGNERS,
    paper: consentPaper(
      "Consent to use tax return information",
      "Brightwater Hale may use the tax return information named here for the purpose stated.",
      "Brightwater Hale LLP",
    ),
  },
  {
    id: stableId("consent-document:feld:ai-disclosure"),
    title: "Consent to disclose tax return information to AI service providers",
    template_name: "BH §7216 Consent to Disclose — AI sub-processors",
    template_version_no: 2,
    signers: FELD_SIGNERS,
    paper: consentPaper(
      "Consent to disclose tax return information to AI service providers",
      "Brightwater Hale may disclose the tax return information named here to the recipients " +
        "listed below, who process it on the firm's behalf.",
      "Accrued Agent sub-processors (US)",
    ),
  },
];

/** f: the Feld TY2025 letter and its two §7216 consents, each its own signed document. */
export const FELD_LETTER: ComposerLetterOut = {
  ...COPPERLEAF_LETTER,
  engagement_id: FELD_ENGAGEMENT,
  template_version_id: stableId("report-template-version:bh-tax-advisory:4"),
  template_name: "BH Tax Advisory Letter",
  template_version_no: 4,
  clauses: states([
    ["scope", "Scope of services"],
    ["fees", "Fees and billing"],
    ["technology-ai", "Use of technology and AI"],
  ]),
  variables: [
    fact("client.name", "Jonah & Claire Feld"),
    fact("client.signer", "Claire Feld · Jonah Feld"),
    fact("firm.signer", "Daniel Reyes, Partner"),
    fact("approver_of_record", null, "cas_only"),
    fact("ske_designee", null, "attest_only"),
    fact("ebp.limited_scope_election", null, "ebp_only"),
    fact("ai_use.disclosure", "on"),
    fact("taxpayer.name", "Jonah & Claire Feld"),
    fact("consent.tax_years", "2025"),
  ],
  generated_document_id: stableId("generated-document:feld-letter"),
  paper: [
    p(v("client.name")),
    { type: "heading", level: 1, text: "Re: Tax advisory services" },
    section(
      "scope",
      "Scope of services",
      p(text("We will provide the tax advisory services described in this letter.")),
    ),
    section("technology-ai", "Use of technology and AI", AI_USE),
    signature(["BRIGHTWATER HALE LLP", "firm.signer"], ["ACCEPTED", "client.signer"]),
  ],
  signers: [
    ...FELD_SIGNERS,
    {
      order: 3,
      name: "Daniel Reyes",
      role: "firm",
      identity: "email_code",
      signed: true,
      signed_on: "2026-02-02",
    },
  ],
  consents: [
    {
      purpose: "use",
      label: "Consent to use tax return information · Jonah & Claire Feld",
      status: "on_file",
      signed_on: "2026-02-02",
      expires_on: "2026-12-31",
    },
    {
      purpose: "ai_disclosure",
      label: "Consent to disclose — AI sub-processors · Jonah & Claire Feld",
      status: "on_file",
      signed_on: "2026-02-02",
      expires_on: "2026-12-31",
    },
  ],
  approved_by_name: "Daniel Reyes",
  approved_at: "2026-02-02T15:00:00Z",
  envelope_id: stableId("envelope:feld-letter"),
  allowed_actions: ["letter.read"],
  routing_note: null,
  documents: FELD_CONSENT_DOCUMENTS,
};

/** Every frame's letter. */
export const LETTERS: Readonly<Record<Eng04Frame, ComposerLetterOut>> = {
  ...RIDGELINE_LETTERS,
  d: COPPERLEAF_LETTER,
  e: FAIRHAVEN_LETTER,
  f: FELD_LETTER,
};

/** The engagement each frame opens and its name in the breadcrumb. */
export const ENG04_OPENS: Readonly<Record<Eng04Frame, { id: string; name: string }>> = {
  a: { id: RIDGELINE_ENGAGEMENT, name: "Ridgeline cost segregation & §754 analysis" },
  b: { id: RIDGELINE_ENGAGEMENT, name: "Ridgeline cost segregation & §754 analysis" },
  c: { id: RIDGELINE_ENGAGEMENT, name: "Ridgeline cost segregation & §754 analysis" },
  d: { id: COPPERLEAF_ENGAGEMENT, name: "2026 Close" },
  e: { id: FAIRHAVEN_ENGAGEMENT, name: "PY2025 EBP audit · Fairhaven Foods 401(k) Plan" },
  f: { id: FELD_ENGAGEMENT, name: "TY2025 Form 1040 · Jonah & Claire Feld" },
};

/**
 * Compare to standard (C11 compare, word level by block and clause): Ridgeline's two non-standard
 * clauses are its own wording over the standard library's, so their text reads as inserted; every
 * other clause equals the standard.
 */
export function standardCompare(letter: ComposerLetterOut): CompareOut {
  const blocks: CompareOut["blocks"] = [];
  for (const block of (letter.paper ?? []) as Block[]) {
    if (block.type !== "section") continue;
    const inner = block.blocks.find((b) => b.type === "clause");
    const nonStandard = inner?.type === "clause" && inner.non_standard;
    const words = (inner?.type === "clause" ? inner.blocks : [])
      .flatMap((b) => (b.type === "paragraph" ? b.runs : []))
      .map((r) => (r.type === "text" ? r.text : ""))
      .join("");
    blocks.push({
      block_id: block.id,
      clause_id: inner?.type === "clause" ? inner.clause_id : null,
      ops: [{ op: nonStandard ? "insert" : "equal", text: words }],
    });
  }
  return { to: "standard", blocks };
}
