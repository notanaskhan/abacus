// INB screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const inbScreens = {
  "INB-01": { name: "Inbox", status: "planned", path: null, navArea: "Inbox" },
  "INB-02": { name: "Attachment triage & File-to", status: "planned", path: null },
  "INB-03": { name: "Compose / reply · Irene Kowal’s thread", status: "planned", path: null },
  "INB-04": { name: "Client messages · portal threads", status: "planned", path: null },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
