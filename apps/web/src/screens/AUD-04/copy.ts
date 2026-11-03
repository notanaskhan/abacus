// AUD-04 Audit program & workpaper: words verbatim from the handoff spec (A-04-T27).
export const COPY = {
  title: "Service Organizations",
  tabs: ["Service Organizations", "Linkage", "Audit Approach"] as const,
  openInExcel: "Open in Excel",
  download: "Download",
  signOff: "Sign off…",
  adopt: "Adopt (L1)…",
  draft: "Draft · Accrued Agent",
  prepared: (initials: string) => `Prepared · ${initials}`,
  signedOff: "Signed off",
  check: (initials: string) => `✓ ${initials}`,
  adoptFirst: "Adopt the agent's draft before signing off",
  captions: {
    organizations:
      "Determines whether the plan uses service organizations and whether their controls are significant to the plan's internal control.",
    changes:
      "Identifies amendments, operational changes and prior-year matters that affect this year's risks.",
  } as Readonly<Record<string, string>>,
  keys: {
    procedure: "Procedure performed",
    result: "Result",
    ebp_140_required: "BH-EBP-140 required",
    bridge_letter: "Bridge letter needed",
    amendments: "Plan amendments",
    prior_findings: "Prior-year findings",
    mergers: "Plan mergers or terminations",
    keystone: "Reliance on Keystone controls",
    paygrid: "Reliance on PayGrid",
    harborline: "Harborline",
  } as Readonly<Record<string, string>>,
  columns: {
    organization: "Service organization",
    services: "Services provided",
    relevant: "Relevant",
    soc: "SOC report / evidence",
    subservice: "Subservice treatment",
    procedure: "Procedure",
    workpaper: "Workpaper",
  } as Readonly<Record<string, string>>,
  widths: { organization: 230, services: 300, relevant: 70, soc: 250 } as Readonly<
    Record<string, number>
  >,
  after: ["ebp_140_required", "bridge_letter"] as const,
  error: "this workpaper",
} as const;
