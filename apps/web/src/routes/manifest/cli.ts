// CLI screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const cliScreens = {
  // P-07-T12: on fixtures behind `clients.v2`; the legacy list answers while the flag is off.
  "CLI-01": { name: "Clients index", status: "fixture", path: "/clients", navArea: "Clients" },
  // P-07-T19 built a, a2, b, c, e and f on fixtures at /clients/$clientId behind `clients.v2` (the
  // legacy ClientRecord answers while it is off). Like BND-02 it stays planned until its links can
  // be wired with to.<ID>() from the screen: `to` carries the manifest's names, which the
  // production dist must not hold (dist.test.ts), so CLI-01 → CLI-02, CLI-02 → ENG-02 and
  // CLI-02 → BND-02 are wired in routes/firm (docs/screens/CLI-02.md, Deviations). d (agent dock)
  // and f (responsiveness) are fixture-only until P-09/P-10 and I-03 register their targets.
  "CLI-02": {
    name: "Client record · Overview",
    status: "planned",
    path: "/clients/$clientId",
    navArea: "Clients",
  },
  "CLI-04": { name: "Contacts & portal access", status: "planned", path: null },
  "CLI-05": {
    name: "Tax profile, authorizations & consents · with Transcripts",
    status: "planned",
    path: null,
  },
  "CLI-06": {
    name: "New client / prospect intake · single + bulk import",
    status: "planned",
    path: null,
  },
  "CLI-07": {
    name: "Acceptance & continuance · Estate of Walter Thornbury",
    status: "planned",
    path: null,
  },
  "CLI-08": {
    name: "Independence & conflicts · PY2025 EBP Audit · Northwind Robotics 401(k) Plan",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
