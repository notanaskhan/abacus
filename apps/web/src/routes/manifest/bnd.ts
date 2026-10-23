// BND screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const bndScreens = {
  "BND-01": {
    name: "Binders index",
    status: "fixture", // P-06-T09: a, c, d, e on fixtures; live with P-06-T11 and T16
    path: "/binders",
    navArea: "Binders",
  },
  // P-06-T12 built a–f on fixtures at /binders/$binderId. It stays planned until every designed link
  // into it can be wired: CLI-01's "Opens BND-02 · open binder" needs a binder id on ClientRowOut
  // (docs/screens/BND-02.md, Open gaps). BND-01 → BND-02 and BND-02 → BND-01 are wired already.
  "BND-02": {
    name: "Binder builder & tracker · Feld 2025 Binder",
    status: "planned",
    path: "/binders/$binderId",
    navArea: "Binders",
  },
  "BND-03": { name: "Questionnaire editor", status: "planned", path: null, entry: true },
  "BND-04": { name: "Request tracker", status: "planned", path: null, navArea: "Binders" },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
