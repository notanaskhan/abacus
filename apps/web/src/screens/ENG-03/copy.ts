// ENG-03 copy, verbatim from the handoff spec.md and revision.md R2 (docs/screens/ENG-03.md,
// Copy). Picker values (clients, entities, team rows, methodology) are data; the catalogue's
// labels come from `GET /v1/engagement-types`. Only the Single audit tile and its tooltip are
// static (D10).

import type { EngagementDraftOut } from "@abacus/api-client";

export type StepCode = EngagementDraftOut["step"];

export const COPY = {
  title: "New engagement",
  saved: (time: string) => `Draft · saved ${time}`,
  steps: {
    client_type: "Client & type",
    standards_methodology: "Standards & methodology",
    period_deadlines: "Period & deadlines",
    team_independence: "Team & independence",
    binder_portal: "Binder & portal",
    letter_review: "Letter & review",
  } satisfies Record<StepCode, string>,
  /** Step 2 by the selected type's work-item kind (e: "Return setup"; spec.md: Monthly close
   * swaps step 2 to "Close plan template", planned until C-01). */
  stepByKind: {
    tax_return: { standards_methodology: "Return setup" },
    close: { standards_methodology: "Close plan template" },
  } as Readonly<Record<string, Partial<Record<StepCode, string>>>>,
  create: "Create",
  gates: {
    g1: (person: string, date: string) => `G1 Continuance approved — ${person} · ${date}`,
    g1Unmet: "Acceptance is not approved yet (G1).",
    g2: "G2 Team independence — step 4",
    /** g: every member confirmed. */
    g2Met: "G2 Team independence — all confirmed",
    /** e: a non-attest engagement has no G2. */
    g2NotRequired: "G2 Independence — not required (non-attest)",
    g3: "G3 Letter signed — after Create",
    startAcceptance: "Start acceptance",
  },
  /** R2: the Set up with AI card (planned until K-04; fixture builds only). */
  ai: {
    title: "Start from last year's files",
    body: "Attach prior statements, a component list or a draft letter; the agent proposes a plan you confirm.",
    action: "Set up with AI…",
    hint: "Opens ENG-14 · Set up with AI",
  },
  /** R2: on card "Name" with FS audit selected and the `group_audit` entitlement. */
  groupAudit: {
    label: "Group audit (SAS 149)",
    helper:
      "Adds the Group band (structure, scoping, component auditors) to the cockpit. SAS 149 applies to periods ending on or after Dec 15, 2026.",
  },
  advisory: {
    proposal: "Start from proposal ⇕",
    proposalHint: "Opens ENG-09",
  },
  /** e: "{type} already exists for {client} · Open it · Create anyway". */
  duplicate: {
    notice: (type: string, client: string) => `${type} already exists for ${client}`,
    open: "Open it",
    anyway: "Create anyway",
  },
  /** e: fixture-only until C19 (T-01). */
  consents: {
    card: "§7216 consents",
    key: "Consents",
    helper: (family: string) =>
      `Agents cannot read ${family} return information until both spouses sign.`,
  },
  /** Monthly close: planned until C-01 (fixture builds only). */
  closePlan: {
    key: "Close plan template",
    hint: "Close plans arrive with closes (C-01).",
  },
  card: {
    client: "Client",
    name: "Name",
    type: "Engagement type",
    standards: "Standards & methodology",
    team: "Team",
    period: "Period & deadlines",
    portal: "Binder & portal",
    review: "Letter & review",
  },
  keys: {
    client: "Client",
    entity: "Entity",
    acceptance: "Acceptance",
    methodology: "Methodology",
    standardsSet: "Standards set",
    auditScope: "Audit scope",
    periodStart: "Period start",
    periodEnd: "Period end",
    name: "Engagement name",
    portalContacts: "Portal contacts",
    display: "Display",
    proposal: "Proposal",
    period: "Period",
    approverOfRecord: "Approver of record",
  },
  acceptance: (date: string) => `Continuance approved · ${date} ✓`,
  groups: { tax: "Tax", audit_assurance: "Audit & assurance", cas_advisory: "CAS & Advisory" },
  comingSoon: {
    label: "Single audit",
    sub: "Uniform Guidance",
    badge: "Coming soon",
    tooltip: "Not in this release. Run single audits outside Accrued for now.",
  },
  scope: ["§103(a)(3)(C)", "Full scope"] as const,
  team: {
    confirmed: "✓ Confirmed",
    requested: "○ Requested",
    eqrEligible: "EQR eligible — not on team, no cooling-off conflict",
    g2Footer: (name: string) =>
      `${name} cannot be assigned or sign off until she confirms independence (G2).`,
  },
  discard: {
    title: "Discard this draft?",
    discard: "Discard",
    keep: "Keep editing",
  },
  toast: {
    created: (name: string) => `Engagement created · ${name}`,
    failed: "Couldn’t save the draft.",
    createFailed: "Couldn’t create the engagement.",
  },
  roles: {
    engagement_partner: "Engagement partner",
    eqr_reviewer: "EQR reviewer",
    manager: "Manager",
    senior: "Senior (in-charge)",
    staff: "Staff",
  } as Readonly<Record<string, string>>,
  none: "—",
} as const;
