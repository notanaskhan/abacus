// EBP screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const ebpScreens = {
  "EBP-01": { name: "Plan profile & service providers", status: "planned", path: null },
  "EBP-02": { name: "Plan provisions review", status: "planned", path: null },
  "EBP-03": { name: "Eligibility testing", status: "planned", path: null },
  "EBP-04": { name: "Contributions & remittance timeliness", status: "planned", path: null },
  // A-05-T44: a to e on fixtures, the AUD-02 cockpit's Distributions & Loans canvas; planned until
  // its links have a builder (no path of its own, the links rule).
  "EBP-05": { name: "Distributions & participant loans", status: "planned", path: null },
  // A-05-T40: a to e on fixtures, the AUD-02 cockpit's Investments & Certification canvas; planned
  // until its AUD-10 and AUD-11 links have a builder (no path of its own, the links rule).
  "EBP-06": { name: "Investments, certification & trust tie-out", status: "planned", path: null },
  "EBP-07": { name: "Form 5500 tie-out & supplemental schedules", status: "planned", path: null },
  // A-05-T52: a to e on fixtures, the AUD-02 cockpit's Participant Accounts canvas; planned until
  // its links have a builder (no path of its own, the links rule).
  "EBP-08": { name: "Participant accounts summary", status: "planned", path: null },
  "EBP-09": {
    name: "Administrative expenses & operational compliance",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
