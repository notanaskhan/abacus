// WB screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const wbScreens = {
  // W-02-T08: the Workbench sessions skeleton on fixtures behind `workbench.enabled`.
  "WB-01": {
    name: "Workbench › Sessions",
    status: "fixture",
    path: "/workbench",
    navArea: "Workbench",
  },
  "WB-02": {
    name: "New session & context picker",
    status: "fixture",
    path: "/workbench/sessions/new",
    navArea: "Workbench",
  },
  "WB-03": {
    name: "Run progress & review-ready results · TY2025 season progress by office",
    status: "fixture",
    path: "/workbench/sessions/$sessionId",
    entry: true,
    navArea: "Workbench",
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
    path: "/engagements/$engagementId/activity", // legacy TraceDrawer on Activity (SPEC-318)
  },
  // W-01-T12: a–i on fixtures; live with W-01-T07/T08 behind `integrations.connect_v1`.
  "WB-10": {
    name: "Connect · integrations catalogue",
    status: "fixture",
    path: "/workbench/connect",
  },
  "WB-11": {
    name: "Integration detail & connect drawer · CCH Axcess Tax",
    status: "fixture", // W-01-T16/T17: a to f on fixtures (the gallery)
    path: null,
  },
  "WB-12": {
    name: "Workbench › Agents › Saved prompts",
    status: "planned",
    path: null,
    navArea: "Workbench",
  },
  "WB-13": { name: "Learned context", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
