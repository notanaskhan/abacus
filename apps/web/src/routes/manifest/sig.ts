// SIG screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const sigScreens = {
  "SIG-01": {
    name: "Signatures hub · evidence drawer",
    status: "planned",
    path: null,
    navArea: "Signatures",
  },
  "SIG-02": {
    name: "Envelope builder · Form 8879-PE · Harborview",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
