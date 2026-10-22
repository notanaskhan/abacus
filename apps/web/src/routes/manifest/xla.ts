// XLA screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const xlaScreens = {
  "XLA-01": { name: "Excel add-in — Granite Peak AP leadsheet", status: "planned", path: null },
  "XLA-02": {
    name: "Word add-in — Granite Peak FY2026 statements",
    status: "planned",
    path: null,
    entry: true,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
