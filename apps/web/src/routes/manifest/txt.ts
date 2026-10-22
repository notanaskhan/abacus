// TXT screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const txtScreens = {
  "TXT-01": {
    name: "Review › Instrument · Calloway Family Trust 2025 Form 1041",
    status: "planned",
    path: null,
  },
  "TXT-02": {
    name: "Review › Trust Calculation · Calloway Family Trust",
    status: "planned",
    path: null,
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
