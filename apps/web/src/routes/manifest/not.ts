// NOT screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const notScreens = {
  "NOT-01": { name: "Notices index · intake sheet", status: "planned", path: null },
  "NOT-02": {
    name: "Notice workspace · CP2000 · TY2024 · Marcus & Dana Whitley",
    status: "planned",
    path: null,
  },
  "NOT-03": {
    name: "Response letter editor & approval · CP2000 · TY2024 · Whitley",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
