// IAU screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const iauScreens = {
  "IAU-01": {
    name: "Internal audit plan — Ashford Manufacturing FY2026",
    status: "planned",
    path: null,
  },
  "IAU-02": {
    name: "RCM and walkthroughs — Ashford ITGC",
    status: "planned",
    path: null,
    entry: true,
  },
  "IAU-03": { name: "Issues and action plans — Ashford FY2026", status: "planned", path: null },
  "IAU-04": {
    name: "Committee dashboard — Ashford Q3 2026",
    status: "planned",
    path: null,
    entry: true,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
