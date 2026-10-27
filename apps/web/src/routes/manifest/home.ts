// HOME screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const homeScreens = {
  "HOME-01": {
    name: "Home dashboard",
    status: "fixture",
    path: "/home",
    navArea: "Home",
  },
  "HOME-02": { name: "My approvals & review queue", status: "planned", path: null },
  "HOME-03": { name: "Deadlines calendar", status: "planned", path: null },
  "HOME-04": { name: "Capacity & resource planner", status: "planned", path: null },
  "HOME-05": { name: "Home with Today brief", status: "planned", path: null, navArea: "Home" },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
