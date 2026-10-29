// HOME screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const homeScreens = {
  "HOME-01": {
    name: "Home dashboard",
    status: "live", // I-01-T13: on for Dev and synthetic firms; "/" opens it
    path: "/home",
    navArea: "Home",
  },
  // I-01-T16: the queue on fixtures behind `home.approvals`; detail T17, evidence T18, bulk T19.
  "HOME-02": {
    name: "My approvals & review queue",
    status: "fixture",
    path: "/home/approvals",
    navArea: "Home",
  },
  "HOME-03": { name: "Deadlines calendar", status: "planned", path: null },
  "HOME-04": { name: "Capacity & resource planner", status: "planned", path: null },
  "HOME-05": { name: "Home with Today brief", status: "planned", path: null, navArea: "Home" },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
