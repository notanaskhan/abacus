// AUD screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const audScreens = {
  // A-01-T11 built a–h on fixtures at /audits behind `audits.cockpit` (g, h fixture only until
  // A-09, X-01 and X-03; i deferred to K-04). It stays planned for the reason ENG-01 does (eng.ts,
  // DEC-195): AUD-01 → AUD-02 and AUD-02 → AUD-01 are wired in routes/firm/audits.tsx, and AUD-02's
  // composer link (SHL-14, an overlay without a path) has no to.<ID>() builder.
  "AUD-01": {
    name: "Audits index · All Audits",
    status: "planned",
    path: "/audits",
    navArea: "Audits",
  },
  // A-01-T12 built a–e and g on fixtures (b, g live); h is A-09's, i K-04's. f (Auto mode confirm):
  // the frame's owner is A-01 (A-01-T31, on fixtures), the route's P-10 (P-10-T39 serves
  // `PUT /v1/engagements/{id}/auto-mode` and `engagement_run.auto_mode`, which turn it live).
  "AUD-02": {
    name: "Audit cockpit · Overview, Source Documents, Agent",
    status: "planned",
    path: "/audits/$auditId",
    navArea: "Audits",
  },
  // A-01-T15 built a–g on fixtures (A-01-T16 wired Remind, the screening return and delegation to
  // the live P-06 routes). It stays planned for AUD-02's reason: its "+ Add" link (SHL-14, an
  // overlay without a path) has no to.<ID>() builder; the staging swap is A-01-T16's on staging.
  "AUD-03": {
    name: "Source documents · PBC with viewer",
    status: "planned",
    path: "/audits/$auditId/source-documents",
    navArea: "Audits",
  },
  "AUD-04": {
    name: "Audit program & workpaper · General Audit Planning › Service Organizations",
    status: "planned",
    path: null,
  },
  "AUD-05": {
    name: "Narrative workpaper · Risk Assessment (understanding, risk, fraud)",
    status: "planned",
    path: null,
  },
  // A-02-T09 built a and c on fixtures as the AUD-02 cockpit's Trial Balance canvas
  // (`?section=trial_balance`, behind `ledger.tb_workpaper`); it has no path of its own, and stays
  // planned until A-02-T24 swaps it to the live C9 routes.
  "AUD-06": { name: "Trial balance & leadsheets", status: "planned", path: null },
  "AUD-07": { name: "Materiality · partner decision", status: "planned", path: null },
  "AUD-08": { name: "Risk assessment register & linkage", status: "planned", path: null },
  "AUD-09": { name: "Internal control & exceptions", status: "planned", path: null },
  "AUD-10": { name: "Service organizations & SOC 1 evaluation", status: "planned", path: null },
  "AUD-11": { name: "Sampling", status: "planned", path: null },
  "AUD-12": { name: "Testing workspace · details · controls · JE", status: "planned", path: null },
  "AUD-13": {
    name: "Analytics · preliminary · substantive · final",
    status: "planned",
    path: null,
  },
  "AUD-14": { name: "Confirmations manager", status: "planned", path: null },
  "AUD-15": { name: "Findings register (issues & deficiencies)", status: "planned", path: null },
  "AUD-16": {
    name: "Misstatements & adjustments (AJEs, RJEs, SUM)",
    status: "planned",
    path: null,
  },
  "AUD-17": { name: "Review notes & sign-off matrix", status: "planned", path: null },
  "AUD-18": { name: "EQR workspace", status: "planned", path: null },
  "AUD-19": {
    name: "Completion (checklist · subsequent events · legal letters · going concern)",
    status: "planned",
    path: "/engagements/$engagementId/completion", // legacy CompletionRelease (SPEC-314)
  },
  "AUD-20": { name: "Financial statements & disclosure checklist", status: "planned", path: null },
  "AUD-21": { name: "Representation letter builder", status: "planned", path: null },
  "AUD-22": {
    name: "Governance communications (AU-C 260 planning letter; AU-C 260 / 265 / 703 completion letters)",
    status: "planned",
    path: null,
  },
  "AUD-23": { name: "Report builder", status: "planned", path: null },
  "AUD-24": { name: "Issuance & release", status: "planned", path: null },
  "AUD-25": { name: "Assembly & archive", status: "planned", path: null },
  "AUD-26": {
    name: "Review, compilation & preparation workspace · SSARS",
    status: "planned",
    path: null,
    entry: true,
  },
  "AUD-27": {
    name: "Estimates, related parties & parties in interest",
    status: "planned",
    path: null,
  },
  "AUD-28": { name: "Consultations log", status: "planned", path: null },
  "AUD-29": { name: "Engagement activity log · cockpit", status: "planned", path: null },
  "AUD-30": { name: "Post-issuance & subsequent discovery", status: "planned", path: null },
  "AUD-31": {
    name: "Trial balance mapping — Harlow & Pike interim 8/31/2026",
    status: "planned",
    path: null,
  },
  "AUD-32": { name: "Consolidation setup — Harlow & Pike FY2026", status: "planned", path: null },
  "AUD-33": {
    name: "Consolidated trial balance — Harlow & Pike interim 8/31/2026",
    status: "planned",
    path: null,
  },
  "AUD-34": {
    name: "Group scoping & component materiality — Harlow & Pike",
    status: "planned",
    path: null,
  },
  "AUD-35": { name: "Component auditors — Harlow & Pike", status: "planned", path: null },
  "AUD-36": {
    name: "Procedure session — BH-FS-430 Search for unrecorded liabilities",
    status: "planned",
    path: null,
  },
  "AUD-37": {
    name: "Pre-review — Northwind Internal Control",
    status: "planned",
    path: null,
    entry: true,
  },
  "AUD-38": {
    name: "Hand off to tax — Granite Peak FY2026 Final TB → FY2026 Form 1120",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
