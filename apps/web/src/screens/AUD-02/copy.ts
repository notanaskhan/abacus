// AUD-02 copy, verbatim from the handoff spec.md and revision.md R2 (docs/screens/AUD-02.md, Copy).
// The audit bar, rail and dock words the shared cockpit parts draw live in domain/audits/messages.ts;
// row text (request titles, file paths, category names) is data, never copy.

export const COPY = {
  canvas: {
    title: "Source Documents",
    add: "Add",
    filter: "Filter",
    search: "Search",
    missingFirst: "Missing first",
    receivedFirst: "Received first",
    noMatch: (q: string) => `No documents match ‘${q}’.`,
    empty: "No requests yet",
  },
  /** What a blocked section's card says, by section (AUD-02 d). */
  blocked: {
    materiality: "Planning materiality is reserved to the engagement partner.",
  } as Readonly<Record<string, string>>,
  notFound: "This audit isn't available.",
} as const;
