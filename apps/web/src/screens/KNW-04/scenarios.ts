// KNW-04 a–h (K-02-T13): one scenario per read artboard plus the staff, empty-examples and flag-off
// conditions; the data and handlers live under fixtures/scenarios/KNW-04.ts. Each state names the
// section it opens on (b with the 1065 checklist selected, as the artboard draws it).
import { type Knw04State, scenarios } from "../../fixtures/scenarios/KNW-04";
import type { Knw04Initial } from ".";

export { scenarios, type Knw04State };

export const STATES = Object.keys(scenarios) as Knw04State[];

const CHECKLIST = "bh-1065-review-checklist";

export const OPENS: Readonly<Record<Knw04State, Knw04Initial>> = {
  a: { section: "aje_thresholds" },
  b: { section: "review_checklists", checklist: CHECKLIST },
  c: { section: "review_levels" },
  d: { section: "return_approval" },
  e: { section: "variance_thresholds" },
  f: { section: "materiality_ranges" },
  g: { section: "document_confidence" },
  h: { section: "ssars_cas" },
  draft_hidden: { section: "review_checklists", checklist: CHECKLIST },
  no_examples: { section: "aje_thresholds" },
  flag_off: { section: "aje_thresholds" },
  i: { section: "aje_thresholds" },
  i_stale: { section: "aje_thresholds" },
};
