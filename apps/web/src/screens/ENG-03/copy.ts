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
  create: "Create",
  gates: {
    g1: (person: string, date: string) => `G1 Continuance approved — ${person} · ${date}`,
    g1Unmet: "Acceptance is not approved yet (G1).",
    g2: "G2 Team independence — step 4",
    g3: "G3 Letter signed — after Create",
    startAcceptance: "Start acceptance",
  },
  card: {
    client: "Client",
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
