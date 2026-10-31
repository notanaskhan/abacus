// TXP screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const txpScreens = {
  "TXP-00": {
    name: "Return › Agent · entity returns",
    status: "planned",
    path: null,
    entry: true,
  },
  "TXP-01": { name: "Review › Summary · Ridgeline preparer memo", status: "planned", path: null },
  "TXP-02": {
    name: "Review › Financials (TB → TTB) · Ridgeline 2025 Form 1065",
    status: "planned",
    path: null,
  },
  "TXP-03": {
    name: "Review › Fixed Assets · Ridgeline depreciation register",
    status: "planned",
    path: null,
  },
  "TXP-04": {
    name: "Review › M-1/M-3 and Schedule M-2 · Ridgeline",
    status: "planned",
    path: null,
  },
  "TXP-05": {
    name: "Review › Schedule K · Ridgeline 2025 Form 1065",
    status: "planned",
    path: null,
  },
  "TXP-06": {
    name: "Allocation Structure (modal sheet) · Ridgeline and Harborview 2025 Form 1065",
    status: "planned",
    path: null,
  },
  "TXP-07": {
    name: "Review › Capital Accounts · Ridgeline 2025 Form 1065",
    status: "planned",
    path: null,
  },
  "TXP-08": {
    name: "Review › Basis · Ridgeline inside / outside basis",
    status: "planned",
    path: null,
  },
  "TXP-09": { name: "Review › States & PTET · Ridgeline", status: "planned", path: null },
  "TXP-10": { name: "Return › Issues · Ridgeline 2025 Form 1065", status: "planned", path: null },
  "TXP-11": {
    name: "Workpaper · Ridgeline workbook, sheet 05 Capital",
    status: "planned",
    path: null,
  },
  // T-02-T25: A–F on fixtures over T-02-T20/T21's routes behind `tax.k1_release`.
  "TXP-12": {
    name: "K-1 package · Ridgeline 2025 Form 1065",
    status: "fixture",
    path: "/tax-returns/$returnId/k1",
  },
  "TXP-13": {
    name: "Other entity workpapers · 1120-S · 1120 · 990",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
