// ENG screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const engScreens = {
  "ENG-01": {
    name: "Engagements index",
    status: "planned",
    path: "/engagements", // legacy Engagements
    navArea: "Engagements",
  },
  // P-07-T20 built b, c, d, e and the prospect state on fixtures behind `engagements.v2` (the
  // legacy EngagementLayout answers while it is off). It stays planned for the reason CLI-02 does
  // (cli.ts): ENG-02 → CLI-02 is wired in routes/firm. f (Dashboard tab) and g (Board tab) are
  // fixture-only until K-04 registers ENG-12 and ENG-10 (docs/screens/ENG-02.md, P-07 §2.1).
  "ENG-02": {
    name: "Engagement record",
    status: "planned",
    path: "/engagements/$engagementId",
    navArea: "Engagements",
  },
  // ENG-03 artboards e (§7216 consent gate), g (group audit) and h (SOC 2) are fixture-only until
  // T-01, A-09 and X-01 register their targets, not missing (docs/screens/ENG-03.md, P-07 §2.1).
  // P-07-T21 built a, b, c, d, f on fixtures at /engagements/new behind `engagements.v2`; planned
  // for the reason CLI-02 is (cli.ts, DEC-195). e, g, h are P-07-T34's.
  "ENG-03": {
    name: "New engagement wizard · Fairhaven Foods 401(k) Plan",
    status: "planned",
    path: "/engagements/new",
  },
  "ENG-04": {
    name: "Engagement letter composer · Ridgeline cost segregation & §754 analysis",
    status: "planned",
    path: null,
  },
  "ENG-05": { name: "Team & roles", status: "planned", path: null },
  "ENG-06": { name: "Budget, time & AI effort", status: "planned", path: null },
  "ENG-07": { name: "Season setup / roll-forward", status: "planned", path: null },
  "ENG-08": { name: "Billing & WIP read-through", status: "planned", path: null, entry: true },
  "ENG-09": { name: "Proposals & scope builder", status: "planned", path: null },
  "ENG-10": {
    name: "Board — Granite Peak FY2026 audit programs",
    status: "planned",
    path: null,
    navArea: "Engagements",
  },
  "ENG-11": { name: "Engagement settings", status: "planned", path: null },
  "ENG-12": {
    name: "Engagement dashboard — Granite Peak FY2026 Financial Statement Audit",
    status: "planned",
    path: "/engagements/$engagementId/dashboard", // legacy EngagementDashboard (SPEC-317)
  },
  "ENG-13": { name: "Roll forward — Tessellate SOC 2 Type 2", status: "planned", path: null },
  "ENG-14": {
    name: "Set up with AI — Harlow & Pike Holdings, Inc.",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
