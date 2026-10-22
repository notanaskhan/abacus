// TXI screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const txiScreens = {
  "TXI-01": {
    name: "Worksheet editor · Feld 2025 Form 1040 · New York IT-201",
    status: "planned",
    path: null,
  },
  "TXI-02": {
    name: "K-1 treatment resolver · Ridgeline K-1 on the Feld 2025 Form 1040",
    status: "planned",
    path: null,
  },
  "TXI-03": {
    name: "State residency & allocation · Feld 2025 Form 1040",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
