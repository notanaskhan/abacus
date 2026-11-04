// AUD-09 · Internal control & exceptions (A-04-T32): every word verbatim from the handoff spec and
// docs/screens/AUD-09.md. Status words are the vocabulary's (deficiency_severity proposal words,
// control_exception_disposition, control_design, audit_section).

export const COPY = {
  title: "Internal Control",
  download: "Download",
  tabs: { internal_control: "Internal Control", exceptions: "Exceptions" },
  openInExcel: "Open in Excel",
  sheet: "Exceptions",
  headers: {
    matter: "Matter",
    description: "Description",
    severity: "Severity (proposed)",
    coso: "COSO component",
  },
  severity: {
    deficiency: "Deficiency",
    significant_deficiency: "Significant deficiency",
    material_weakness: "Material weakness",
  } as Record<string, string>,
  disposition: { exception_for_resolution: "Exception for resolution" } as Record<string, string>,
  coso: {
    control_environment: "Control environment",
    risk_assessment: "Risk assessment",
    control_activities: "Control activities",
    information_communication: "Information & communication",
    monitoring: "Monitoring",
  } as Record<string, string>,
  none: "—",
  concluded: (severity: string, initials: string) => `${severity} · Concluded ${initials}`,
  communicated: "Communicated",
  footer: {
    none: (address: string) => `No evidence is linked to ${address}.`,
    cited: (address: string, n: number) =>
      `${address} · ${String(n)} ${n === 1 ? "citation" : "citations"}`,
    noEvidence: "No evidence written.",
  },
  picker: {
    label: "Proposed severity",
    note: "Proposed by Accrued Agent. Concluding severity is reserved to the engagement partner (Findings).",
    openInFindings: "Open in Findings",
  },
  menu: {
    label: (address: string) => `Row actions for ${address}`,
    sendToFindings: "Send to Findings",
    convert: "Convert to misstatement",
    requestEvidence: "Request evidence…",
  },
  processes: {
    process: "Process",
    walkthrough: "Walkthrough",
    design: "Design",
    implementation: "Implementation",
    reliance: "Reliance",
    done: (on: string) => `Done ${on}`,
    viaSoc: (name: string) => `${name} SOC 1`,
    design_status: {
      effective: "Effective",
      deficient: "Deficient",
      not_assessed: "—",
    } as Record<string, string>,
    implementation_status: {
      implemented: "Implemented",
      not_implemented: "Not implemented",
      not_assessed: "—",
    } as Record<string, string>,
    reliance_status: { none: "None", via_soc1: "Via SOC 1", tested: "Tested" } as Record<
      string,
      string
    >,
  },
  failed: {
    rail: "Failed — see run",
    retry: "Retry",
    fix: "Fix in Knowledge",
    arrow: "→",
    card: "Run internal control workpaper",
    execute: "Execute",
  },
  states: { empty: "No exceptions yet." },
} as const;
