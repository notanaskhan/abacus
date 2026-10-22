// CLI screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const cliScreens = {
  "CLI-01": { name: "Clients index", status: "planned", path: "/clients", navArea: "Clients" }, // legacy Clients
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
