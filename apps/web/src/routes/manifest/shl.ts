// SHL screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.
// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,
// path and folder when the screen is built.
import type { Manifest } from "./types";

export const shlScreens = {
  "SHL-01": {
    name: "Firm app shell · toolbar and nav",
    status: "fixture", // P-01-T02: chrome over every firm route; the artboard is fixture-only
    path: null,
    entry: true,
  },
  "SHL-02": { name: "Command palette · Go…", status: "planned", path: null, entry: true },
  "SHL-03": {
    name: "Firm switcher & profile menu",
    status: "fixture", // P-01-T08: the tray under the firm pill; the artboard is fixture-only
    path: null,
  },
  // P-01-T10 built the drawer on fixtures (screens/SHL-04), but it stays planned until its
  // "Notification settings" link (SHL-04 → SHL-03, link-contract rule 1) and the inline approval
  // land: neither overlay has a path, so the link cannot be wired with a builder yet.
  "SHL-04": { name: "Notifications panel", status: "planned", path: null, entry: true },
  "SHL-05": { name: "Support panel", status: "planned", path: null, entry: true },
  // P-01-T11: g and the sign-in error state at /signin/callback, the BFF's landing (a route outside
  // the area tree, reached only by redirect); a–f are the hosted provider's pages.
  "SHL-06": { name: "Firm sign-in", status: "live", path: null, entry: true },
  "SHL-07": { name: "Citation popover", status: "planned", path: null },
  // P-03-T14 built a, b, e, f, h (`?ov=viewer:…` and the dock pane); it turns `fixture` with
  // P-03-T19, whose d state wires the designed SHL-08 → SHL-14 "Ask …" link (link rule 1).
  "SHL-08": { name: "Source viewer · drawer and pane", status: "planned", path: null },
  "SHL-09": { name: "Field provenance popover", status: "planned", path: null },
  // P-04-T41: a, b, c and f on fixtures as `?ov=approve:<ref>` (d, e, e′, g are later P-04 rows).
  "SHL-10": { name: "Approve agent output", status: "planned", path: null },
  "SHL-11": { name: "Decision card", status: "planned", path: null },
  "SHL-12": { name: "Sign-off modal", status: "planned", path: null },
  "SHL-13": { name: "Agent dock · run pane", status: "planned", path: null },
  // SHL-14 artboard c (Sample-driven bulk) is deferred to A-03, not missing (P-06 §2.3, §5.5).
  // P-06-T13: a, b, e, f on fixtures as `?ov=request:…` over BND-02; P-06-T24: d, the close
  // variant, on the same overlay over a close_intake binder until C-01's CLS-03; c is A-03's.
  "SHL-14": { name: "Request composer drawer", status: "fixture", path: null },
  "SHL-15": { name: "Issue composer & fix instructions", status: "planned", path: null },
  // P-04-T43: a–f on fixtures as `?ov=checkpoints:<type>:<id>` behind `review.checkpoints`.
  "SHL-16": { name: "Checkpoint diff drawer", status: "fixture", path: null },
  "SHL-17": { name: "To-do drawer", status: "planned", path: null },
  "SHL-18": { name: "Comments and @mentions", status: "planned", path: null },
  "SHL-19": { name: "Agent review package", status: "planned", path: null },
  // P-06-T22: a–f on fixtures, the C-34 card in local state over its host (BND-02 here).
  "SHL-20": { name: "Evidence screening", status: "fixture", path: null },
  "SHL-21": { name: "Link requests", status: "planned", path: null },
  "SHL-22": { name: "Template update", status: "planned", path: null },
  "SHL-23": { name: "Today brief panel", status: "planned", path: null, entry: true },
  // seed-manifest: new screens are added above this line
} as const satisfies Manifest;
