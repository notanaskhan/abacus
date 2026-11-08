// AUD-08 · Risk assessment register & linkage (A-04-T20): copy verbatim from the handoff spec and
// its R2 revision.
export const COPY = {
  // A-04-T26 (R2 revision): states c, e, f and g.
  linkage: {
    title: "Linkage",
    linked: "Linked",
    suggested: "Suggested",
    link: "Link EBP-03…",
  },
  revising: "Revising after Internal Control…",
  drafted: {
    adopt: "Adopt",
    edit: "Edit",
    discard: "Discard",
    draft: "Draft with agent",
    tooltip: (n: number): string =>
      `Suggested by Accrued Agent · ${String(n)} citations · not yet adopted`,
  },
  identify: {
    button: "Identify risks with agent",
    check: "Check coverage",
    agentLine: (c: {
      material_areas: number;
      covered: number;
      unaddressed_codes: string[];
    }): string =>
      `I compared the register with the trial balance, the plan profile and Internal Control. Every material area has an assessed risk (${String(c.covered)} of ${String(c.material_areas)}). ${c.unaddressed_codes.length === 1 ? "One risk has no response" : `${String(c.unaddressed_codes.length)} risks have no response`}: ${c.unaddressed_codes.join(", ")}.`,
    codeLine: (c: {
      material_areas: number;
      covered: number;
      unaddressed_codes: string[];
    }): string =>
      `Material areas with an assessed risk: ${String(c.covered)} of ${String(c.material_areas)}. Without a response: ${c.unaddressed_codes.join(", ") || "none"}.`,
    open: (code: string): string => `Open ${code} →`,
  },
  title: "Risk Assessment",
  version: (n: number): string => `Version ${String(n)}`,
  edit: "Edit",
  signOff: "Sign off…",
  openExcel: "Open in Excel",
  tabs: ["Risk Assessment", "Fraud Brainstorming", "Summary", "Audit Approach", "Linkage"],
  tally: {
    risks: "RISKS",
    significant: "SIGNIFICANT",
    fraud: "FRAUD RISKS",
    highRmm: "HIGH RMM",
    unaddressed: "UNADDRESSED",
    epApproval: "EP APPROVAL",
  },
  proposed: (n: number): string => `${String(n)} proposed`,
  presumed: "Presumed",
  pending: "Pending",
  approved: "Approved",
  columns: {
    code: "#",
    area: "Area",
    assertions: "Assertions",
    ir: "IR",
    cr: "CR",
    rmm: "RMM",
    significant: "Significant",
    fraud: "Fraud",
    response: "Response (procedure → workpaper)",
    status: "Status",
  },
  groups: { financial_statement: "FINANCIAL STATEMENT LEVEL", assertion: "ASSERTION LEVEL" },
  rating: { low: "Low", moderate: "Moderate", high: "High", max: "Max" } as Record<string, string>,
  significance: {
    mandatory: "Mandatory",
    proposed: "Proposed",
    approved: "Approved",
    not_significant: "Not significant",
  } as Record<string, string>,
  fraud: {
    presumed: "Presumed",
    rebuttal_proposed: "Rebuttal proposed",
    rebuttal_approved: "Rebuttal approved",
  } as Record<string, string>,
  status: { draft: "Draft", ep_approved: "EP approved", revised: "Revised" } as Record<
    string,
    string
  >,
  assertion: {
    existence: "Existence",
    occurrence: "Occurrence",
    completeness: "Completeness",
    rights_obligations: "Rights & obligations",
    accuracy: "Accuracy",
    valuation: "Valuation",
    cutoff: "Cutoff",
    classification: "Classification",
    presentation: "Presentation",
  } as Record<string, string>,
  all: "All",
  unaddressed: "Unaddressed risk",
  standBack: "Stand-back: 0 material areas without an assessment.",
  drawer: {
    factors: "Inherent risk factors (SAS 145)",
    rationaleCard: "Rationale",
    responseCard: "Response",
    assertions: "Relevant assertions",
    versions: "Versions",
    factor: {
      susceptibility_to_fraud: "Susceptibility to fraud",
      change: "Change",
      complexity: "Complexity",
      subjectivity: "Subjectivity",
      uncertainty: "Uncertainty",
    } as Record<string, string>,
    routed: (name: string, at: string): string => `Routed to ${name} · ${at}`,
    remind: (first: string): string => `Remind ${first}…`,
    approve: "Approve as significant risk",
    notSignificant: "Not significant…",
    citations: (n: number): string => `${String(n)} citations`,
  },
} as const;
