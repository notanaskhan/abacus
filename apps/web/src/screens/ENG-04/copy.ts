// ENG-04 copy, verbatim from the handoff spec.md (docs/screens/ENG-04.md, Copy). Names, values,
// dates and the paper's wording are data (the composed letter), never copy.

export const COPY = {
  crumb: (engagement: string) => `Letter › ${engagement}`,
  bands: {
    template: "Template",
    variables: "Variables",
    clauses: "Clauses",
    consents: "§7216 consents",
    signers: "Signers & order",
  },
  keys: {
    template: "Template",
    library: "Clause library",
    status: "Status",
    approved: "Approved",
    redline: "Redline",
  },
  templateName: (name: string, n: number) => `${name} v${String(n)}`,
  approved: (name: string, when: string) => `${name} · ${when}`,
  redline: (n: number) => `${String(n)} non-standard clause${n === 1 ? "" : "s"}`,
  signedCount: (signed: number, total: number) => `${String(signed)} of ${String(total)} signed`,
  /** The variables ENG-04 names itself; a template's own keys carry the template's label. */
  variables: {
    "client.signer": "Client signer",
    "firm.signer": "Firm signer",
    "fee.summary": "Fee",
    "billing.terms": "Billing",
    "third_party_fee.summary": "Engineer's fee",
    approver_of_record: "Approver of record",
    ske_designee: "SKE designee",
    "ebp.limited_scope_election": "§103(a)(3)(C) election",
    "ai_use.disclosure": "AI-use disclosure",
  } as Readonly<Record<string, string>>,
  reasons: {
    cas_only: "CAS only",
    attest_only: "attest clients only",
    ebp_only: "EBP audits only",
  } as Readonly<Record<string, string>>,
  aiDefault: "Firm default · ADM-04",
  nonStandard: "Non-standard",
  consents: {
    needed: "Needs §7216 consent",
    signed: (on: string, expires: string) => `Signed ${on} · expires ${expires}`,
    notOnFile: (client: string, party: string) =>
      `Not on file. No ${client} return information goes to ${party} (POR-14) until it is signed.`,
    bundle: "Bundle a new consent document",
    separate: "Consents are separate documents, never clauses.",
    sentAlone: (party: string) =>
      `The ${party} disclosure consent is sent on its own before the engineer data request.`,
  },
  signer: {
    client: (n: number, name: string) => `${String(n)} ${name} (client) · email code`,
    firm: (n: number, name: string) => `${String(n)} ${name} (firm countersignature)`,
  },
  paper: {
    title: "Engagement letter",
    edit: "Edit",
    compare: "Compare to standard",
    send: "Send for signature…",
    requestApproval: "Request partner approval…",
    viewEnvelope: "View envelope ›",
    watermark: "DRAFT",
    cite: (label: string) => `Lights ${label}`,
  },
  // N-02-T35: no handoff frame draws the dialog; its words follow ENG-04's spec ("Only a
  // partner can approve.") and the consent band's.
  approval: {
    open: "Approve letter…",
    title: "Approve this letter",
    body: "Only a partner can approve. The approval holds for this version; any later change makes it a new draft.",
    consents: "§7216 consents",
    onFile: "On file",
    confirm: "Approve",
  },
  withdraw: {
    open: "Withdraw envelope…",
    title: "Withdraw this envelope?",
    body: (status: string) =>
      `The envelope came back ${status}. The letter stays approved and Send drafts a new envelope.`,
    confirm: "Withdraw",
  },
  failed: "Couldn’t load the letter.",
} as const;
