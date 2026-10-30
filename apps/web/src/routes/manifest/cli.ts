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
  // P-07-T33 built a–g on fixtures at /clients/$clientId/contacts (CLI-02's "Contacts & access"
  // tab) behind `contacts.v2`; planned for CLI-02's reason (its links are wired in routes/firm).
  "CLI-04": {
    name: "Contacts & portal access",
    status: "planned",
    path: "/clients/$clientId/contacts",
    navArea: "Clients",
  },
  // T-01-T14 built d and f (the consents section) on fixtures; a, b, c, e, g with T-01-T43 to T46.
  "CLI-05": {
    name: "Tax profile, authorizations & consents · with Transcripts",
    // Fixture-built (T-01-T14); planned until its designed links are wired (link-contract rule 1)
    // and walked on staging (DEC-195; DEC-1272).
    status: "planned",
    path: "/clients/$clientId/tax-profile/$sub",
    navArea: "Clients",
  },
  // P-07-T49 built the single-client intake a–f, h and i live over the intake routes (P-07-T42)
  // at /clients/new behind `clients.v2`; g (bulk import) is P-07-T54's. Like CLI-02 it stays
  // planned until its inbound links (CLI-01 "+ New client", "Bulk import") are wired with
  // to.<ID>() by CLI-01's owner; the route and its outbound links are wired in routes/firm.
  "CLI-06": {
    name: "New client / prospect intake · single + bulk import",
    status: "planned",
    path: "/clients/new",
    navArea: "Clients",
  },
  // P-07-T46 built a, b, d, e and f live over the acceptance routes (P-07-T35) and c and g on
  // fixtures, at /clients/$clientId/acceptance/$engagementId behind `engagements.acceptance_v2`.
  // Live: no to.<ID>() is needed while every designed target (ENG-04, CLI-02, CLI-08, INS-05,
  // BND-04) is planned; the back chip and "Open ‹client›" reach CLI-02 through routes/firm
  // (DEC-195, DEC-431).
  "CLI-07": {
    name: "Acceptance & continuance · Estate of Walter Thornbury",
    status: "live",
    path: "/clients/$clientId/acceptance/$engagementId",
    navArea: "Clients",
  },
  // P-07-T48 built a–g and the declined-note state live over the independence routes (P-07-T41)
  // at /clients/$clientId/independence/$engagementId behind `engagements.acceptance_v2`. Its
  // designed targets (SHL-11, ENG-02, ENG-05, CLI-02) stay planned links. Planned for CLI-02's
  // reason until CLI-07's "Independence" link is wired with to.<ID>() (CLI-07 → CLI-08).
  "CLI-08": {
    name: "Independence & conflicts · PY2025 EBP Audit · Northwind Robotics 401(k) Plan",
    status: "planned",
    path: "/clients/$clientId/independence/$engagementId",
    navArea: "Clients",
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
