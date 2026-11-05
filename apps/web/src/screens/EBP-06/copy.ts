// EBP-06 · Investments & certification (A-05-T40): every word verbatim from the handoff.

export const COPY = {
  title: "Investments & Certification",
  edit: "Edit",
  signOff: "Sign off…",
  sourceDocs: "Source Docs",
  layers: { unadjusted: "Unadjusted", aje: "AJE", rje: "RJE", final: "Final" },
  layerUnavailable: "Available when adjustments are on",
  chips: { balanced: "TB balanced", pyTies: "PY ties", unbalanced: "TB out of balance", pyOff: "PY differs" },
  columns: { description: "Description", boy: "Beginning of Year", eoy: "End of Year", ref: "WP Ref" },
  ms: "✓ MS",
  tick: "✓",
  assets: "ASSETS",
  investments: "INVESTMENTS AT FAIR VALUE",
  total: "Total investments at fair value",
  netAssets: "Net assets available for benefits",
  refs: { trust: "Trust", tb: "TB" },
  certification: {
    title: "Certification evaluation",
    evaluate: "Evaluate",
    evaluated: "Evaluated",
    points: {
      qualifying_institution: "Certifying institution",
      complete_and_accurate: "Statement",
      period: "Period",
      signer_and_date: "Signed",
      covers: "Covers",
      not_covered: "Not covered",
    } as Record<string, string>,
    levels: "Fair value levels",
    levelsValue: (level1: string, nav: string, total: string): string =>
      `Level 1 ${level1} + NAV practical expedient ${nav} = ${total}`,
    hold: "Certified trust report uploaded – needs review. Sign-off is held until the certification is evaluated.",
  },
  provenance: "From Harborline trust report · document extraction",
} as const;
