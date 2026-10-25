// SHL-08 copy, verbatim from the handoff (SHL-08 spec.md frames A, B, E, F; revision R2 change 4).
export const COPY = {
  figure: (name: string | null): string =>
    name === null ? "Linked figure" : `Linked figure · ${name}`,
  source: (n: number, of: number): string => `Source ${String(n)} of ${String(of)}`,
  previousSource: "Previous source",
  nextSource: "Next source",
  alsoCited: "Also cited: ",
  menu: {
    download: "Download",
    openInFiles: "Open in Files",
    autoHighlight: "Auto-highlight cited fields",
  },
  openInFilesHint: "Opens FIL-01 · document drawer",
  dock: { label: "Dock", agent: "Agent", viewer: "Viewer", notes: "Notes" },
  tb: {
    title: "Trial Balance",
    description: "Description",
    endOfYear: "End of Year",
  },
  close: "Close",
} as const;
