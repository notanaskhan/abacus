// TPL-14a "Ridgeline relationships" (F-07-T13; handoff TPL-14 spec.md; F-07 §G1): the graph's nodes,
// edges and the spec's exact saved positions (top-left inside the canvas body, below the banner).
// Labels are the handoff's words. Ownership ties to blueprint §9.3: 2 + 38 + 30 + 5 + 25 = 100 % at
// year end, Pell Street Ventures 35 % through 6/30/2025. Viewer Olivia Brandt (F-07 §3, not the
// README's "Jonah Feld"). Masked lines and the inspector arrive with the canvas (F-07-T14, T16).
import type { GraphEdgeIn, GraphNodeIn, Point } from "../../graph/layout";

export const TPL14_NODES: readonly GraphNodeIn[] = [
  { id: "owen-calder", kind: "person" },
  { id: "ridgeline-lp", kind: "partnership" },
  { id: "ridgeline-gp", kind: "entity" },
  { id: "meera-shah", kind: "person" },
  { id: "pell-street-ventures", kind: "entity" },
  { id: "pell-street-ii", kind: "entity" },
  { id: "jonah-feld", kind: "person" },
  { id: "shah-1040", kind: "return" },
  { id: "claire-feld", kind: "person" },
  { id: "feld-1040", kind: "return" },
];

export const TPL14_EDGES: readonly GraphEdgeIn[] = [
  { id: "gp-lp", from: "ridgeline-gp", to: "ridgeline-lp", kind: "ownership", label: "2% GP" },
  { id: "shah-lp", from: "meera-shah", to: "ridgeline-lp", kind: "ownership", label: "38% LP" },
  {
    id: "psv-lp",
    from: "pell-street-ventures",
    to: "ridgeline-lp",
    kind: "ownership",
    label: "30% LP (35% to 6/30/2025)",
  },
  {
    id: "ps2-lp",
    from: "pell-street-ii",
    to: "ridgeline-lp",
    kind: "ownership",
    label: "5% LP from 7/1/2025",
  },
  { id: "feld-lp", from: "jonah-feld", to: "ridgeline-lp", kind: "ownership", label: "25% LP" },
  {
    id: "owen-gp",
    from: "owen-calder",
    to: "ridgeline-gp",
    kind: "role",
    label: "Managing member",
  },
  { id: "owen-lp", from: "owen-calder", to: "ridgeline-lp", kind: "role", label: "Signs 8879-PE" },
  {
    id: "psv-ps2",
    from: "pell-street-ventures",
    to: "pell-street-ii",
    kind: "transfer",
    label: "Sold 5 points · 6/30/2025 · $360,000",
  },
  {
    id: "shah-k1",
    from: "meera-shah",
    to: "shah-1040",
    kind: "k1_draft",
    label: "Draft K-1 · pre-release",
  },
  {
    id: "feld-k1",
    from: "jonah-feld",
    to: "feld-1040",
    kind: "k1_draft",
    label: "Draft K-1 · pre-release",
  },
  { id: "spouse", from: "claire-feld", to: "jonah-feld", kind: "spouse", label: "Spouse" },
  {
    id: "claire-1040",
    from: "claire-feld",
    to: "feld-1040",
    kind: "taxpayer",
    label: "Taxpayer (MFJ)",
  },
];

/** The spec's coordinates, exactly (saved layout). */
export const TPL14_SAVED: Readonly<Record<string, Point>> = {
  "owen-calder": { x: 24, y: 150 },
  "ridgeline-lp": { x: 428, y: 150 },
  "ridgeline-gp": { x: 24, y: 320 },
  "meera-shah": { x: 232, y: 320 },
  "pell-street-ventures": { x: 440, y: 320 },
  "pell-street-ii": { x: 648, y: 320 },
  "jonah-feld": { x: 836, y: 320 },
  "shah-1040": { x: 232, y: 500 },
  "claire-feld": { x: 636, y: 500 },
  "feld-1040": { x: 836, y: 500 },
};
