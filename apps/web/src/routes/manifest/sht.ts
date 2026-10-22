// SHT screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const shtScreens = {
  "SHT-01": {
    name: "BH-FS-430 Search for Unrecorded Liabilities — sheet",
    status: "planned",
    path: null,
  },
  "SHT-02": { name: "Column and field configurator", status: "planned", path: null },
  "SHT-03": { name: "Scoping rules editor", status: "planned", path: null },
  "SHT-04": { name: "Agent-column editor", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
