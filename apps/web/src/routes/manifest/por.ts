// POR screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const porScreens = {
  // P-08-T09, T19: every artboard (a to g, c′ and 390) on fixtures, in the portal entry at
  // /sign-in and /accept (routes/portal), outside the firm's tree, so it carries no firm path.
  "POR-01": {
    name: "Portal sign-in · Brightwater Hale",
    status: "fixture",
    path: null,
    entry: true,
  },
  // P-08-T15: a, b, c, f on fixtures at the portal root; d, e, g, h and M are P-08-T23's.
  "POR-02": { name: "Portal home · Feld household", status: "fixture", path: null },
  // R-01-T06: a, c, e, f, g and h render in the gallery on fixtures. The entry stays planned until
  // R-01-T10 mounts it at the portal's /documents and POR-02's "Go to Documents →" is wired to it
  // (link-contract rule 1: a fixture-to-fixture link must be wired).
  "POR-03": { name: "Documents · Feld 2025 Binder", status: "planned", path: null },
  "POR-04": { name: "Request detail · ignore reason sheet", status: "planned", path: null },
  "POR-05": { name: "Questions · Feld 2025 Tax Organizer", status: "planned", path: null },
  "POR-06": { name: "Sign · Ridgeline engagement letter", status: "planned", path: null },
  "POR-07": { name: "Messages · Feld household", status: "planned", path: null },
  "POR-08": { name: "Approvals · Copperleaf August 2026 Close", status: "planned", path: null },
  "POR-09": {
    name: "Deliverables · Northwind Robotics 401(k) Plan",
    status: "planned",
    path: null,
  },
  "POR-10": { name: "Payments", status: "planned", path: null },
  "POR-11": {
    name: "Close requests & transaction questions · Copperleaf August 2026",
    status: "planned",
    path: null,
  },
  "POR-12": { name: "Entities, people & account", status: "planned", path: null },
  "POR-13": { name: "K-1 recipient view · My K-1s", status: "planned", path: null },
  "POR-14": {
    name: "Third-party request room · Keystone Retirement Services",
    status: "planned",
    path: null,
  },
  "POR-15": {
    name: "Governance room · Northwind benefits committee",
    status: "planned",
    path: null,
  },
  "POR-16": { name: "Connections · Copperleaf", status: "planned", path: null },
  "POR-17": {
    name: "Confirmation response · Granite Peak receivables (C2)",
    status: "planned",
    path: null,
    entry: true,
  },
  "POR-18": { name: "Prospect intake", status: "planned", path: null, entry: true },
  "POR-19": { name: "Mobile capture · IRS notice (Whitley)", status: "planned", path: null },
  "POR-20": { name: "Transactional email templates · Reminder", status: "planned", path: null },
  "POR-21": {
    name: "SOC 2 requests and responses — Tessellate Health Cloud",
    status: "planned",
    path: null,
  },
  "POR-22": {
    name: "Internal audit — Ashford Manufacturing",
    status: "planned",
    path: null,
    entry: true,
  },
  "POR-23": {
    name: "Group audit — Harlow & Pike Distribution, Inc.",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
