// BND screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const bndScreens = {
  "BND-01": { name: "Binders index", status: "planned", path: null },
  "BND-02": { name: "Binder builder & tracker · Feld 2025 Binder", status: "planned", path: null },
  "BND-03": { name: "Questionnaire editor", status: "planned", path: null, entry: true },
  "BND-04": { name: "Request tracker", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
