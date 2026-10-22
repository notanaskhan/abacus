// TPL screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const tplScreens = {
  "TPL-01": {
    name: "Index list specimen · Tax Returns",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-02": {
    name: "Record cockpit specimen · Northwind 401(k) audit",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-03": {
    name: "Evidence triad specimen · Feld 1040 review",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-04": {
    name: "Workbench chat specimen · TY2025 season progress by office",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-05": {
    name: "Catalog grid specimen · Workbench › Agents › Library",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-06": {
    name: "Workbook grid specimen · Ridgeline capital accounts",
    status: "planned",
    path: null,
  },
  "TPL-07": {
    name: "Client portal specimen · Feld 2025 Binder · 1400 + 390",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-08": {
    name: "Inbox master-detail specimen · firm Inbox, Feld thread",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-09": {
    name: "Queue · detail · evidence specimen · three presets",
    status: "planned",
    path: null,
  },
  "TPL-10": {
    name: "Document on well specimen · Ridgeline preparer memo",
    status: "planned",
    path: null,
  },
  "TPL-11": { name: "Dashboard specimen · Home", status: "planned", path: null, entry: true },
  "TPL-12": {
    name: "Settings form specimen · Firm settings › General",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-13": {
    name: "Calendar specimen · firm deadlines, September 2026",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-14": {
    name: "Graph canvas specimen · Ridgeline relationships",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-15": {
    name: "Auth card specimen · portal sign-in and confirmation response",
    status: "planned",
    path: null,
  },
  "TPL-16": {
    name: "Signing ceremony specimen · Form 8879, Dev & Mira Kapoor",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-17": {
    name: "Form renderer specimen · Ridgeline 2025 Form 1065",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-18": {
    name: "Stepper wizard specimen · new advisory engagement",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-19": {
    name: "Portal mobile specimen · Feld, camera capture",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-20": {
    name: "T18 Sheet specimen · Granite Peak FY2026 · BH-FS-430 Search for unrecorded liabilities",
    status: "planned",
    path: null,
  },
  "TPL-21": {
    name: "T19 Board specimen · Granite Peak FY2026 audit programs · Sep 24",
    status: "planned",
    path: null,
  },
  "TPL-22": {
    name: "T20 Document editor specimen · Granite Peak FY2026 balance sheets · Oct 21",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-23": {
    name: "T21 Analytics dashboard specimen · Insights › Client responsiveness · Oct 1",
    status: "planned",
    path: null,
    entry: true,
  },
  "TPL-24": {
    name: "T22 Office add-in pane specimen · Excel add-in on the Granite Peak AP leadsheet",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
