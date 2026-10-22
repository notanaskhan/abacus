// WB screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const wbScreens = {
  "WB-01": { name: "Workbench › Sessions", status: "planned", path: null },
  "WB-02": { name: "New session & context picker", status: "planned", path: null },
  "WB-03": {
    name: "Run progress & review-ready results · TY2025 season progress by office",
    status: "planned",
    path: null,
    entry: true,
  },
  "WB-04": { name: "Agents › Library", status: "planned", path: null },
  "WB-06": {
    name: "Workbench › Agents › My Agents · Request Chaser",
    status: "planned",
    path: null,
  },
  "WB-07": { name: "Edit Agent sheet · Request Chaser", status: "planned", path: null },
  "WB-08": {
    name: "Run history & schedules · Season Progress Reporter",
    status: "planned",
    path: null,
  },
  "WB-09": {
    name: "Run trace drawer · Season Progress Reporter, Sep 14",
    status: "planned",
    path: null,
  },
  "WB-10": { name: "Connect · integrations catalogue", status: "planned", path: null },
  "WB-11": {
    name: "Integration detail & connect drawer · CCH Axcess Tax",
    status: "planned",
    path: null,
  },
  "WB-12": { name: "Workbench › Agents › Saved prompts", status: "planned", path: null },
  "WB-13": { name: "Learned context", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
