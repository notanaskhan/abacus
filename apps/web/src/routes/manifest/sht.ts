// SHT screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const shtScreens = {
  "SHT-01": {
    name: "BH-FS-430 Search for Unrecorded Liabilities — sheet",
    // K-03-T16: a, b, c, f render on the SH-1 fixtures at this path (d, e with the agent row). It
    // stays `planned` until SHL-14 carries a sheet origin, so the SHT-01 ↔ SHL-14 links can be
    // wired both ways (link contract rule 1; DEC-5934).
    status: "planned",
    path: "/audits/$auditId/sheets/$sheetId",
    navArea: "Audits",
  },
  "SHT-02": { name: "Column and field configurator", status: "planned", path: null },
  "SHT-03": { name: "Scoping rules editor", status: "planned", path: null },
  "SHT-04": { name: "Agent-column editor", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
