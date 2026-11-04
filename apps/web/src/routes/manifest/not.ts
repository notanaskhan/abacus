// NOT screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const notScreens = {
  "NOT-01": {
    name: "Notices index · intake sheet",
    status: "fixture",
    path: "/notices",
    navArea: "Notices",
  },
  "NOT-02": {
    name: "Notice workspace · CP2000 · TY2024 · Marcus & Dana Whitley",
    // N-04-T14: a, b, c, d, a2 on fixtures; planned until its CLI-05 and FIL-01 links are wired
    // (the screen's links rule), e and f swap live with N-04-T22.
    status: "planned",
    path: "/notices/$noticeId",
  },
  "NOT-03": {
    name: "Response letter editor & approval · CP2000 · TY2024 · Whitley",
    status: "planned",
    path: null,
  },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
