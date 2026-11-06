// SHL-08 copy, verbatim from the handoff (SHL-08 spec.md frames A, B, E, F; revision R2 change 4).
export const COPY = {
  // P-11-T31: how a page's words were read, in the status words of the copy registry (DF-31).
  ocr: {
    textLayer: "Text from the PDF",
    read: "Text read by OCR",
    readConfidence: (pct: number) => `Text read by OCR · ${String(pct)}% confidence`,
    none: "No readable text on this page",
    low: "Low confidence",
    lowLabel: (n: number) => `${String(n)} fields read with low confidence`,
    retry: "Read text again",
    refused: {
      kill_switch: "Text reading is paused.",
      flag_off: "Text reading is off for this firm.",
      provider_terms: "Text reading isn't permitted under the current provider terms.",
      boundary_basis: "Text reading isn't permitted for this firm.",
      consent_7216: "Text reading needs the taxpayer's consent.",
      daily_page_cap: "Today's text-reading limit is reached.",
      size_limit: "This file is too large for text reading.",
      provider_error: "Text reading didn't finish. Try again.",
    },
  },
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
  /** SHL-08c (spec frame C; P-03 §5.6). */
  reveal: {
    label: "Reveal (logged)",
    hide: "Hide",
    line: (person: string, at: string): string =>
      `Revealed by ${person} · ${at} · logged to the audit trail`,
    /** P-03 §5.6's live-region words. */
    shown: (seconds: number): string => `Revealed for ${String(seconds)} seconds`,
    hidden: "Hidden again",
  },
  /** SHL-08d (spec frame D; P-03 AC5.1, AC5.3). */
  locked: {
    title: "This PDF is password-protected.",
    body: (issuer: string): string =>
      `Enter the password ${issuer} sent the client, or ask the client for it.`,
    /** Not in the frame: the body without an issuer name (any other file). */
    bodyPlain: "Enter the password the client was sent, or ask the client for it.",
    password: "Password",
    unlock: "Unlock",
    ask: (client: string): string => `Ask ${client}…`,
    askHint: "Opens SHL-14 with a prefilled request",
    wrong: "That password didn't open the file.",
    /** Not handoff copy (DEC-426): POR-01 g's title for the attempt limit, with the wait. */
    limited: (minutes: number): string =>
      `Too many attempts. Try again in ${String(minutes)} ${minutes === 1 ? "minute" : "minutes"}.`,
    /** Not handoff copy (DEC-426): TASK-323's words for a file that won't open. */
    failed: "The file couldn't be unlocked. Please upload a copy without a password.",
  },
  search: {
    /** Not handoff copy (DEC-426): the search capsule's count, as the find bar reads it. */
    hits: (n: number, truncated: boolean): string =>
      n === 0
        ? "No matches"
        : `${String(n)}${truncated ? "+" : ""} ${n === 1 ? "match" : "matches"}`,
  },
} as const;
