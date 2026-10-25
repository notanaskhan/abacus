// POR-03 copy (docs/screens/POR-03.md, Copy): the screen's own strings, verbatim from the handoff.
// The rows' receipts and lines are the domain's (`domain/portal/messages.ts`); the C-16 kit draws
// its own (Upload…, Ignore, the three reasons, the banner, the empty state). Firm-written words
// (titles, guidance) come from the server. Never the product's name, the agent or a firm status.

/** "Keystone, Harborline, PayGrid and Summit". */
function listOf(names: readonly string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1] ?? ""}`;
}

export const COPY = {
  pane: "Documents",
  binderPicker: "Binder",
  loading: "Loading",
  // The load error has no handoff frame: written by R-01-T06 on POR-02's error grammar.
  error: {
    title: "Couldn’t load your documents.",
    body: "We could not reach the server. Nothing was lost; try again in a moment.",
    retry: "Retry",
  },
  /** motion: the packet's badge ("3 files"). */
  motionBadge: (n: number) => `${String(n)} ${n === 1 ? "file" : "files"}`,
  /** i: the other-parties note (organisation names only, R-01 Story 1.2). */
  otherParties: (names: readonly string[]) => `Some requests go to ${listOf(names)} directly.`,
  categories: "Categories",
  /** The list of files the upload policy refused at the door. */
  refusedLabel: "Files not uploaded",
  /** i's rail rows: a band's open requests. */
  bandOpen: (n: number) => `${String(n)} open`,
} as const;

/** The portal's upload policy (DEC-58 c): PDF, JPG, PNG, HEIC, XLSX, DOCX and CSV. On a phone the
 * native picker offers the camera for the image types (POR-03 M, DF-03). */
export const UPLOAD_ACCEPT =
  "application/pdf,image/jpeg,image/png,image/heic,.heic,.xlsx,.docx,.csv";
