// POR-03 copy (docs/screens/POR-03.md, Copy): the screen's own strings, verbatim from the handoff.
// The rows' receipts and lines are the domain's (`domain/portal/messages.ts`); the C-16 kit draws
// its own (Upload…, Ignore, the three reasons, the banner, the empty state). Firm-written words
// (titles, guidance) come from the server. Never the product's name, the agent or a firm status.

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
} as const;
