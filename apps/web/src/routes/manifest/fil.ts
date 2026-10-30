// FIL screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const filScreens = {
  "FIL-01": {
    name: "Files browser & document drawer",
    status: "live",
    path: "/files",
    navArea: "Files",
  },
  "FIL-02": { name: "Retention & legal hold", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
