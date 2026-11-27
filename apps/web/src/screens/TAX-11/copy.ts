// TAX-11's words, verbatim from the handoff (screens/TAX-11 spec.md) where it words them. Each
// diagnostic's words are code's (the diagnostics read's `title`).
export const COPY = {
  title: (year: number, form: string) => `${String(year)} Form ${form}`,
  approve: "Approve return…",
  blocking: (n: number) => `${String(n)} blocking ${n === 1 ? "diagnostic" : "diagnostics"}`,
  export: "Export to tax engine…",
  exportClosed: "Available once the return is approved",
  download: "Download draft",
  downloadFailed: "The draft could not be downloaded.",
  watermark: "Draft — not for filing",
  values: "Typed values on this page",
  noValues: "No typed values on this page.",
  placeholder: "Preview available after export from the engine",
  k1Face: (name: string) => `Schedule K-1 (Form 1065) · ${name}`,
  k1FaceNote:
    "The K-1 face renders with its form template. Each partner's K-1 and its delivery are in the K-1 package.",
  openK1Package: "Open K-1 package",
  failed: "The form preview could not load.",
  retry: "Retry",
  draftK1: "Draft K-1 · pre-release",
};
