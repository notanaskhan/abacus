// TXT screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const txtScreens = {
  "TXT-01": {
    name: "Review › Instrument · Calloway Family Trust 2025 Form 1041",
    status: "fixture", // T-07-T15: a–d, d1–d3 on fixtures; live with T-07-T12's service
    path: "/tax-returns/$returnId/review/instrument",
  },
  "TXT-02": {
    name: "Review › Trust Calculation · Calloway Family Trust",
    status: "fixture", // T-07-T17: a–e and f1 on fixtures; live with T-07-T16's service (T21)
    path: "/tax-returns/$returnId/review/trust-calculation",
  },
  "TXT-03": {
    name: "Beneficiaries, K-1s & 65-day election · Calloway Family Trust",
    status: "planned",
    path: null,
    entry: true,
  },
  "TXT-04": { name: "Gift & estate workpapers (706 / 709)", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
