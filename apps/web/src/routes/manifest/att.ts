// ATT screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const attScreens = {
  "ATT-01": {
    name: "Attest cockpit — Tessellate SOC 2 Type 2",
    status: "planned",
    path: null,
    navArea: "Audits",
  },
  "ATT-02": { name: "Scoping — Tessellate SOC 2 Type 2", status: "planned", path: null },
  "ATT-03": {
    name: "System description — Tessellate Scheduling & Intake",
    status: "planned",
    path: null,
  },
  "ATT-04": { name: "Control matrix — Tessellate SOC 2 Type 2", status: "planned", path: null },
  "ATT-05": { name: "Control test — TES-38", status: "planned", path: null },
  "ATT-06": { name: "Exceptions — Tessellate SOC 2 Type 2", status: "planned", path: null },
  "ATT-07": { name: "Attest report — SOC 2 Type 2", status: "planned", path: null, entry: true },
  "ATT-08": {
    name: "ISO/IEC 27001:2022 readiness — Tessellate Health Cloud",
    status: "planned",
    path: null,
    entry: true,
  },
  "ATT-09": { name: "GRC sync — Drata", status: "planned", path: null, entry: true },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
