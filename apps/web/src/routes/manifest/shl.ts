// SHL screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const shlScreens = {
  "SHL-01": {
    name: "Firm app shell · toolbar and nav",
    status: "fixture", // P-01-T02: chrome over every firm route; the artboard is fixture-only
    path: null,
    entry: true,
  },
  "SHL-02": { name: "Command palette · Go…", status: "planned", path: null, entry: true },
  "SHL-03": { name: "Firm switcher & profile menu", status: "planned", path: null },
  "SHL-04": { name: "Notifications panel", status: "planned", path: null, entry: true },
  "SHL-05": { name: "Support panel", status: "planned", path: null, entry: true },
  "SHL-06": { name: "Firm sign-in", status: "planned", path: null, entry: true },
  "SHL-07": { name: "Citation popover", status: "planned", path: null },
  "SHL-08": { name: "Source viewer · drawer and pane", status: "planned", path: null },
  "SHL-09": { name: "Field provenance popover", status: "planned", path: null },
  "SHL-10": { name: "Approve agent output", status: "planned", path: null },
  "SHL-11": { name: "Decision card", status: "planned", path: null },
  "SHL-12": { name: "Sign-off modal", status: "planned", path: null },
  "SHL-13": { name: "Agent dock · run pane", status: "planned", path: null },
  // SHL-14 artboard c (Sample-driven bulk) is deferred to A-03, not missing (P-06 §2.3, §5.5).
  "SHL-14": { name: "Request composer drawer", status: "planned", path: null },
  "SHL-15": { name: "Issue composer & fix instructions", status: "planned", path: null },
  "SHL-16": { name: "Checkpoint diff drawer", status: "planned", path: null },
  "SHL-17": { name: "To-do drawer", status: "planned", path: null },
  "SHL-18": { name: "Comments and @mentions", status: "planned", path: null },
  "SHL-19": { name: "Agent review package", status: "planned", path: null },
  "SHL-20": { name: "Evidence screening", status: "planned", path: null },
  "SHL-21": { name: "Link requests", status: "planned", path: null },
  "SHL-22": { name: "Template update", status: "planned", path: null },
  "SHL-23": { name: "Today brief panel", status: "planned", path: null, entry: true },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
