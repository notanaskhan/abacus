// INS screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const insScreens = {
  "INS-01": { name: "Insights — Performance", status: "planned", path: null, navArea: "Home" },
  "INS-02": { name: "Insights — AI adoption", status: "planned", path: null },
  "INS-03": {
    name: "Insights — Efficiency and benchmarks",
    status: "planned",
    path: null,
    entry: true,
  },
  "INS-04": { name: "Insights — My week", status: "planned", path: null, entry: true },
  "INS-05": { name: "Insights — Client responsiveness", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
