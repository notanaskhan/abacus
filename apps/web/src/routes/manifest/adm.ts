// ADM screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const admScreens = {
  "ADM-01": {
    name: "Settings home · firm profile",
    status: "fixture", // G-01-T07: live behind firm_settings.v2 once walked on staging
    path: "/settings/general",
  },
  // G-01-T10 built a–g on fixtures at /settings/people behind `firm_settings.v2`. It stays planned
  // for the reason CLI-02 does (cli.ts, DEC-195): ADM-01 → ADM-02 is wired in routes/firm
  // (settings.tsx), since `to` carries the manifest's names, which the production dist must not hold.
  "ADM-02": {
    name: "Users & roles · permission matrix",
    status: "planned",
    path: "/settings/people",
  },
  "ADM-03": { name: "Offices, teams, walls & offshore", status: "planned", path: null },
  "ADM-04": { name: "AI policy & approval gates", status: "planned", path: null },
  "ADM-05": { name: "Consent registry (§7216)", status: "planned", path: null },
  "ADM-06": { name: "Security center & data residency", status: "planned", path: null },
  "ADM-07": { name: "Audit log explorer", status: "planned", path: null },
  "ADM-08": { name: "Integration settings", status: "planned", path: null },
  "ADM-09": { name: "Developer (API, webhooks, MCP)", status: "planned", path: null },
  "ADM-10": { name: "Portal branding & client experience", status: "planned", path: null },
  "ADM-11": { name: "Quality management dashboard", status: "planned", path: null },
  "ADM-12": { name: "Monitoring & inspections", status: "planned", path: null },
  "ADM-13": { name: "Firm settings › Data model", status: "planned", path: null },
  "ADM-14": { name: "Firm settings › Plan & usage", status: "planned", path: null, entry: true },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
