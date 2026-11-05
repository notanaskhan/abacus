// AUD-10 · Service organizations & SOC 1 (A-04-T37): every word verbatim from the handoff and
// docs/screens/AUD-10.md. Status words are the vocabulary's.

export const COPY = {
  title: "Service Organizations & SOC 1",
  edit: "Edit",
  signOff: "Sign off…",
  inventory: {
    title: "Inventory",
    organization: "Organization",
    service: "Service",
    relevant: "Relevant",
    evidence: "Evidence",
    status: "Status",
    yes: "Yes",
    no: "No",
  },
  evidence: {
    soc1_type2: "SOC 1 Type 2",
    soc1_type1: "SOC 1 Type 1",
    certification: "Certification",
    tested_directly: "Tested directly",
    none: "—",
  },
  status: {
    pending: "Pending",
    gap_found: "Gap found",
    bridge_letter_received: "Bridge letter received",
    reliance_concluded: "Reliance concluded",
    certification_accepted: "Certification accepted",
    no_reliance: "No reliance",
    not_relevant: "Not relevant",
  },
  coverage: {
    title: "Coverage",
    planYear: "Plan year",
    socPeriod: "SOC 1 period",
    gap: (days: number): string => `Gap · ${days} days`,
    bridged: "Bridge letter · no changes reported",
    bridgeRow: "Bridge letter",
    remind: "Remind…",
    alt: (start: string, end: string, days: number): string =>
      `SOC 1 period ${start} to ${end}, leaving ${days} days of the plan year uncovered.`,
  },
  evaluation: {
    title: "Report evaluation",
    auditor: "Service auditor",
    opinion: "Opinion",
    typeAndPeriod: "Type and period",
    objectives: "Control objectives",
    objectivesValue: (total: number, relevant: number): string =>
      `${total} (${relevant} relevant to this audit)`,
    subservice: "Subservice organizations",
    reportDate: "Report date",
    gapProcedures: "Gap procedures",
    opinionWord: {
      unmodified: "Unmodified",
      qualified: "Qualified",
      adverse: "Adverse",
      disclaimer: "Disclaimer",
    },
    type: { type_1: "SOC 1 Type 1", type_2: "SOC 1 Type 2" },
    carveOut: "carve-out",
  },
  exceptions: { title: "Exceptions noted by the service auditor", low: "Low", high: "High" },
  cuecs: {
    title: (done: number, total: number): string => `CUEC mapping · ${done} of ${total} evidenced`,
    evidenced: "Evidenced",
    missing: "Evidence missing",
    internalControl: "Internal Control",
  },
  reliance: {
    pending: "Reliance on Keystone controls: pending the bridge letter and CUEC evidence.",
    draftRequest: "Draft evidence request…",
  },
} as const;
