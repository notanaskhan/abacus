// CLS screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built. C-01-T12 routes the close shell: CLS-02 to CLS-06,
// CLS-09 and CLS-10 have paths (still `planned` until each screen row builds its body).
import type { Manifest } from "./types";

export const clsScreens = {
  "CLS-01": {
    name: "Closes index — August 2026",
    status: "live", // C-01-T33 fixtures; live from C-01-T42 (C-01-T14's service)
    path: "/closes",
    navArea: "Closes",
  },
  "CLS-02": { name: "Close › Overview · run", status: "live", path: "/closes/$closeId" }, // C-01-T42
  "CLS-03": {
    name: "Close › Intake · Copperleaf August 2026",
    status: "live", // C-01-T42
    path: "/closes/$closeId/intake",
  },
  "CLS-04": {
    name: "Close › Accounts · Prepaid Insurance workpaper",
    status: "live", // C-01-T43
    path: "/closes/$closeId/accounts",
  },
  "CLS-05": {
    name: "Close › Reconciliation · Operating Checking (Front Range Bank) ••4410, Aug 31, 2026",
    status: "live", // C-01-T43
    path: "/closes/$closeId/accounts/$accountRef",
  },
  "CLS-06": {
    name: "Close › Review · Copperleaf August 2026",
    status: "live", // C-01-T43
    path: "/closes/$closeId/review",
  },
  "CLS-07": {
    name: "Adjustments & thresholds · Copperleaf August 2026",
    status: "planned",
    path: null,
  },
  "CLS-08": {
    name: "Close › Deliverables · Copperleaf August 2026 statements",
    status: "live", // C-02-T23 (S51 partials): the package read, edit and commentary
    path: "/closes/$closeId/deliverables",
    entry: true,
  },
  "CLS-09": {
    name: "Close plan editor · Copperleaf close plan v3",
    status: "live", // C-01-T36 fixtures; live from C-01-T42
    path: "/close-plans/$clientId",
  },
  "CLS-10": {
    name: "Flux analysis · Copperleaf August vs July 2026",
    status: "live", // C-01-T40 fixtures; live from C-01-T43
    path: "/closes/$closeId/flux",
  },
  "CLS-11": {
    name: "GL sync console · Copperleaf · QuickBooks Online",
    status: "live", // C-02-T35: a, a2, c, d, d2 on the C20 W1 reads (b, b2, e with C-02's later rows)
    path: "/clients/$clientId/entities/$entityId/ledger",
  },
  "CLS-12": {
    name: "Handoff to tax · Copperleaf December 2026 close → 2026 Form 1120-S",
    status: "planned",
    path: null,
  },
  "CLS-13": { name: "1099 / W-9 tracker · Copperleaf 2026", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
