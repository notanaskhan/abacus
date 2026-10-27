// KNW screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const knwScreens = {
  "KNW-01": {
    name: "Knowledge library",
    status: "fixture",
    path: "/knowledge",
    navArea: "Knowledge",
  }, // legacy Knowledge
  "KNW-02": {
    name: "Methodology versions & import review · BH Audit Methodology · EBP v3",
    status: "planned",
    path: null,
  },
  "KNW-03": {
    name: "Program editor · BH-EBP-110 General Planning",
    status: "planned",
    path: null,
  },
  "KNW-04": {
    name: "Firm standards & thresholds · Brightwater Hale",
    status: "planned",
    path: null,
  },
  "KNW-05": { name: "Templates & research", status: "planned", path: null },
  "KNW-06": {
    name: "Engagement template builder — BH Audit Methodology · FS v6 (draft)",
    status: "planned",
    path: null,
    navArea: "Knowledge",
  },
  "KNW-07": {
    name: "Template versions and rollout — BH Audit Methodology · FS",
    status: "planned",
    path: null,
  },
  "KNW-08": { name: "Content packs — FS audit core", status: "planned", path: null, entry: true },
  "KNW-09": { name: "Knowledge › Frameworks", status: "planned", path: null },
  "KNW-10": {
    name: "Control set and cross-map — Tessellate Health Cloud",
    status: "planned",
    path: null,
  },
  "KNW-11": {
    name: "Skills — BH-SK-430 Search for unrecorded liabilities",
    status: "planned",
    path: null,
  },
  "KNW-12": {
    name: "Notes library — Subsequent events — non-recognized (lease)",
    status: "planned",
    path: null,
    entry: true,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
