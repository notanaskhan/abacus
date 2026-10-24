// SHL-07 copy, verbatim from the handoff (SHL-07 spec.md and README) and the DF-31 words
// (docs/product/status-vocabulary.yaml `citation`; "Unverified" for `verified=false`, P-03 §4.10).
// Titles, quotes, locations and figures are data from C4, never copy.

export const COPY = {
  popover: {
    label: "Citation",
    previous: "Previous source",
    next: "Next source",
    stepper: (index: number, count: number) => `${String(index)} / ${String(count)}`,
    announce: (index: number, count: number) => `Source ${String(index)} of ${String(count)}`,
    footer: (count: number) => (count === 1 ? "1 citation" : `${String(count)} citations`),
    openStep: "Open the step in the program editor",
    openSource: "Open source",
    thumb: (page: number) => `Page ${String(page)}, highlighted`,
    unverified: "Unverified",
    moved: (ref: string, version: string, successor: string, on: string) =>
      `Source moved — ${ref} v${version} was superseded by ${successor} on ${on}`,
    broken: "Broken",
    relink: "Re-link…",
  },
  chips: {
    citations: (n: number) => `Citations (${String(n)})`,
    procedures: (n: number) => `Procedures (${String(n)})`,
    citationsLabel: "Citations in this section",
    proceduresLabel: "Procedures in this section",
  },
  workpaper: {
    title: "Service Organizations",
    band: "SECTION 1 — SERVICE ORGANIZATIONS",
    caption:
      "Determines whether the plan uses service organizations and whether their controls are part of the plan's information system relevant to financial reporting (AU-C 402).",
    procedureKey: "Procedure performed",
    procedure:
      "BH-EBP-110 step 4. Identified each organization that processes plan transactions and assessed whether its services are relevant to the plan's financial statements.",
    resultKey: "Result",
    result:
      "The plan uses four service organizations; three are relevant to the financial statements.",
    columns: ["Service organization", "Services provided", "Relevant"],
    requiredKey: "BH-EBP-140 required",
    required: "Yes",
  },
  guidance: { title: "Risk Assessment" },
} as const;
