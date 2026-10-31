// AUD-11 · Sampling copy (A-03-T11): verbatim from the handoff (screens/AUD-11, spec.md, R1, R2).
// Figures, names, seeds and labels are server data; these are the words around them.

export const COPY = {
  title: "Sample Selection",
  version: (n: number): string => `Version ${String(n)}`,
  actions: { edit: "Edit", signOff: "Sign off…", sourceDocs: "Source Docs" },
  picker: "Sample set",
  pickerRow: (title: string, size: string, of: string, status: string): string =>
    `${title} · ${size} of ${of} · ${status}`,
  population: {
    title: "Population",
    source: "Source",
    sources: ["Upload", "General ledger", "HR or ticketing system"] as const,
    hrTooltip: "Ask the client to connect their HR system: Request a connection (POR-16)",
    file: "File",
    fileDetail: (v: number, on: string, by: string): string =>
      `v${String(v)}, uploaded ${on} by ${by}`,
    records: "Records",
    hash: "Hash",
    completeness: "Completeness",
    left: (amount: string): string => `Census compensation ${amount}`,
    samplingUnit: "Sampling unit",
    deviation: "Deviation",
  },
  method: {
    title: "Method & parameters",
    method: "Method",
    methods: {
      attribute_nonstatistical: "Attribute (non-statistical, BH-EBP-210 Table 2)",
      attribute_statistical: "Attribute (statistical)",
      threshold_random_stratified: "Threshold + random (stratified)",
    } as Record<string, string>,
    rmm: "RMM",
    rmms: { low: "Low (AUD-08)", moderate: "Moderate (AUD-08)", high: "High (AUD-08)" } as Record<
      string,
      string
    >,
    tolerable: "Tolerable deviation rate",
    expected: "Expected deviation rate",
    confidence: "Confidence",
    size: "Computed size",
    crosscheck: (n: number, confidence: string, tolerable: string, expected: string): string =>
      `statistical cross-check: ${String(n)} at ${confidence} / ${tolerable} / ${expected}`,
    seed: "Seed",
    copySeed: (hex: string): string => `Copy seed ${hex}`,
    algorithm: "Algorithm",
    algorithms: {
      attribute_nonstatistical: "uniform without replacement",
      attribute_statistical: "uniform without replacement",
      threshold_random_stratified: "threshold, then uniform without replacement",
    } as Record<string, string>,
    sampler: (v: string, how: string): string => `Accrued sampler v${v} · ${how}`,
  },
  override: {
    banner: (n: number): string =>
      `Size below methodology (${String(n)}). Needs manager approval and a rationale.`,
    size: "New size",
    rationaleLabel: "Rationale (required)",
    save: "Save and draw",
    cancel: "Cancel",
  },
  items: {
    title: (n: number): string => `Selected items · ${String(n)}`,
    search: "Search participants",
    excel: "Open in Excel",
    none: "No participant matches the search.",
  },
  versions: {
    title: "Versions",
    line: (at: string, by: string | null, seed: string, label: string, records: number): string =>
      [
        at,
        ...(by === null ? [] : [by]),
        `seed ${seed}`,
        `${label} (${String(records)} records)`,
      ].join(" · "),
    off: (amount: string): string => `completeness off ${amount}`,
    approved: "Approved",
    prepared: (initials: string): string => `Prepared · ${initials}`,
    superseded: "Superseded",
    draft: "Draft",
  },
  // The generate sheet's five templates per participant (AUD-11c; the sheet is A-03-T15's).
  templates: 5,
  footer: {
    generate: (items: number, per: number): string =>
      `Generate item requests (${String(items)} × ${String(per)})…`,
    disabled: "A manager must approve the sample first",
    citations: (n: number): string => `Citations (${String(n)})`,
    procedures: (n: number): string => `Procedures (${String(n)})`,
  },
  states: {
    off: "Sampling is not turned on for this firm.",
    empty: "No sample yet",
    create: "Create sample…",
    error: "The sample couldn't be loaded.",
  },
} as const;
