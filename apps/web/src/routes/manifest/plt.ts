// PLT screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const pltScreens = {
  "PLT-01": { name: "Accrued tenant console", status: "planned", path: null, entry: true },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
