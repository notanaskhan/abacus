// CLI screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const cliScreens = {
  // P-07-T12: on fixtures behind `clients.v2`; the legacy list answers while the flag is off.
  "CLI-01": { name: "Clients index", status: "fixture", path: "/clients", navArea: "Clients" },
  // CLI-02 artboards d (agent dock) and f (responsiveness) are fixture-only until P-09/P-10 and
  // I-03 register their targets, not missing (docs/screens/CLI-02.md, P-07 §2.1).
  "CLI-02": {
    name: "Client record · Overview",
    status: "planned",
    path: "/clients/$clientId", // legacy ClientRecord
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
