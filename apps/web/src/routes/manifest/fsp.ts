// FSP screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const fspScreens = {
  "FSP-01": { name: "Statements studio — Granite Peak FY2026", status: "planned", path: null },
  "FSP-02": { name: "Line items — Granite Peak FY2026 statements", status: "planned", path: null },
  "FSP-03": {
    name: "Roll forward last year’s statements — Granite Peak FY2026",
    status: "planned",
    path: null,
    entry: true,
  },
  "FSP-04": {
    name: "Disclosure assistant — Note 9, Granite Peak FY2026",
    status: "planned",
    path: null,
    entry: true,
  },
  "FSP-05": { name: "Tie-out — Granite Peak FY2026 statements", status: "planned", path: null },
  "FSP-06": { name: "Report templates — Granite Peak FY2026", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
