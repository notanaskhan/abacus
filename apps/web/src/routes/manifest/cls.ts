// CLS screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const clsScreens = {
  "CLS-01": {
    name: "Closes index — August 2026",
    status: "planned",
    path: null,
    navArea: "Closes",
  },
  "CLS-02": { name: "Close › Overview · run", status: "planned", path: null },
  "CLS-03": { name: "Close › Intake · Copperleaf August 2026", status: "planned", path: null },
  "CLS-04": {
    name: "Close › Accounts · Prepaid Insurance workpaper",
    status: "planned",
    path: null,
  },
  "CLS-05": {
    name: "Close › Reconciliation · Operating Checking (Front Range Bank) ••4410, Aug 31, 2026",
    status: "planned",
    path: null,
  },
  "CLS-06": { name: "Close › Review · Copperleaf August 2026", status: "planned", path: null },
  "CLS-07": {
    name: "Adjustments & thresholds · Copperleaf August 2026",
    status: "planned",
    path: null,
  },
  "CLS-08": {
    name: "Close › Deliverables · Copperleaf August 2026 statements",
    status: "planned",
    path: null,
    entry: true,
  },
  "CLS-09": {
    name: "Close plan editor · Copperleaf close plan v3",
    status: "planned",
    path: null,
  },
  "CLS-10": {
    name: "Flux analysis · Copperleaf August vs July 2026",
    status: "planned",
    path: null,
  },
  "CLS-11": {
    name: "GL sync console · Copperleaf · QuickBooks Online",
    status: "planned",
    path: null,
  },
  "CLS-12": {
    name: "Handoff to tax · Copperleaf December 2026 close → 2026 Form 1120-S",
    status: "planned",
    path: null,
  },
  "CLS-13": { name: "1099 / W-9 tracker · Copperleaf 2026", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
