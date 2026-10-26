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
  /** AUD-02 f (A-01-T31): `autoMode.confirm`, the O3 confirm behind the audit bar's switch. */
  autoMode: {
    title: "Turn on Auto mode?",
    body: "Agents will dispatch each level without waiting for plan approval. Decisions reserved to people still wait.",
    cancel: "Cancel",
    confirm: "Turn on",
    /** The server's refusal (a real firm in Season 1): no AUD-02 copy exists, so ADM-04h's reason
     * (SPEC-349 AC-35, ADR-186 §6), docs/screens/AUD-02.md DV-12. */
    refused: "Auto mode isn't available for client data yet",
  },
} as const;
