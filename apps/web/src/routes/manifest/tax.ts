// TAX screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const taxScreens = {
  "TAX-01": {
    name: "Tax Returns · practice board",
    status: "fixture", // T-02-T12 a–g behind `tax.returns_v1`; live once walked on staging
    path: "/tax-returns",
    navArea: "Tax Returns",
  },
  "TAX-02": { name: "Return › Overview", status: "planned", path: null },
  "TAX-03": { name: "Return › Intake · Feld 2025 Form 1040", status: "planned", path: null },
  "TAX-04": {
    name: "Return › Review · Prepare preset · Feld 2025 Form 1040",
    status: "planned",
    path: null,
    entry: true,
  },
  "TAX-05": {
    name: "Return › Review · Review preset · Feld 2025 Form 1040",
    status: "planned",
    path: null,
  },
  "TAX-06": { name: "Return › Issues · Feld 2025 Form 1040", status: "planned", path: null },
  "TAX-07": {
    name: "Return › Activity & Checkpoints · Feld 2025 Form 1040",
    status: "planned",
    path: null,
  },
  "TAX-08": {
    name: "Return › Assistant panel · Feld 2025 Form 1040",
    status: "planned",
    path: null,
  },
  "TAX-09": {
    name: "Return › Tax-engine sync · Feld 2025 Form 1040",
    status: "planned",
    path: null,
  },
  "TAX-10": {
    name: "Return › Review › 2-Year Comparison · Feld 2025 Form 1040",
    status: "planned",
    path: null,
  },
  "TAX-11": {
    name: "Form preview · Ridgeline 2025 Form 1065 with K-1s",
    status: "planned",
    path: null,
    entry: true,
  },
  "TAX-12": {
    name: "Return › Delivery & e-file · Feld 2025 Form 1040",
    status: "planned",
    path: null,
  },
  "TAX-13": { name: "Extensions, estimates & payments · TY2025", status: "planned", path: null },
  "TAX-14": {
    name: "Firm standards run · 1065 Review Checklist v4",
    status: "planned",
    path: null,
  },
  "TAX-15": { name: "Planning opportunities · TY2025 portfolio", status: "planned", path: null },
  "TAX-16": {
    name: "Amendments & administrative adjustment requests",
    status: "planned",
    path: null,
    entry: true,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
