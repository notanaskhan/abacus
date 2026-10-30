// POR screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const porScreens = {
  // P-08-T09, T19: every artboard (a to g, c′ and 390), in the portal entry at /sign-in and
  // /accept (routes/portal), outside the firm's tree, so it carries no firm path. Live since
  // P-08-T29: it reads the served pre-session routes (P-08-T10, T11).
  "POR-01": {
    name: "Portal sign-in", // the handoff adds "· Brightwater Hale"; no seed name ships (dist.test.ts)
    status: "live",
    path: null,
    entry: true,
  },
  // P-08-T15: a, b, c, f at the portal root; P-08-T23: d, e, g, h and M. Live since P-08-T29 over
  // GET /v1/portal/home (P-08-T13); g and h stay fixture-only until their sources register.
  "POR-02": { name: "Portal home · Feld household", status: "live", path: null },
  // R-01-T06, T10: all twelve artboards render in the gallery on fixtures, and the portal entry
  // mounts the screen at /documents with POR-02's "Go to Documents →" wired. The entry stays
  // planned with a null path: manifest paths resolve in the firm's route tree, so the link
  // checker cannot see the portal's (DEC-347).
  "POR-03": { name: "Documents · Feld 2025 Binder", status: "planned", path: null },
  // R-01-T12: all seven artboards render in the gallery on fixtures, and the portal entry opens
  // the sheet at /documents/requests/$requestId over POR-03 (a row's title opens it). Planned with
  // a null path for the reason POR-03 gives (DEC-347).
  "POR-04": { name: "Request detail · ignore reason sheet", status: "planned", path: null },
  "POR-05": { name: "Questions · Feld 2025 Tax Organizer", status: "planned", path: null },
  // N-02-T26: part 1 (list, review, ERSD, the provider's view, the return, decline) renders in the
  // gallery on fixtures, and the portal entry mounts /sign. Planned with a null path for the reason
  // POR-03 gives (DEC-347).
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
  // R-01-T14: all six artboards render in the gallery on fixtures, and the portal entry mounts
  // the room at /requests (a row at /requests/$requestId). Planned with a null path for the reason
  // POR-03 gives (DEC-347).
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
  // A-02-T28: the portal entry mounts the screen live at /connections. The entry stays planned
  // with a null path for the reason POR-03 gives (DEC-347).
  "POR-16": { name: "Connections · Copperleaf", status: "planned", path: null },
  "POR-17": {
    name: "Confirmation response · Granite Peak receivables (C2)",
    status: "planned",
    path: null,
    entry: true,
  },
  "POR-18": { name: "Prospect intake", status: "planned", path: null, entry: true },
  "POR-19": { name: "Mobile capture · IRS notice (Whitley)", status: "planned", path: null },
  // R-01-T25: built on fixtures and routed at /settings/portal/email-templates/$templateKey (a
  // firm screen with a POR- id). Link-contract's rule 2 admits it as a firm-hosted POR screen
  // (DEC-567, DEC-589); "planned" until the staging walk.
  "POR-20": {
    name: "Transactional email templates · Reminder",
    status: "planned",
    path: "/settings/portal/email-templates/$templateKey",
  },
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
