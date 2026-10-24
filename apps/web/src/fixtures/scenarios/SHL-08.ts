// SHL-08 Source viewer: one fixture scenario per artboard P-03 builds (a–f, h; g Annotate is
// K-03's, planned). P-03-T07; handoff SHL-08 README and spec. a and c–f as Samuel Ito at Mon Sep
// 14, 2026, 9:24 AM CT on the Feld 2025 Form 1040 review; b as Hannah Leclerc at 9:41 AM on the
// Northwind trial balance (AUD-06); h as Hannah at 2:30 PM (revision R2):
//
//   a  drawer: the draft Ridgeline K-1, box 18A lit ("Form 1040 · line 2a 1,550"), the linked
//      figures 307,900 · 4,600 · 1,550, source 1 of 3, EIN ••-•••0287 and SSN •••-••-4417 masked
//   b  dock pane: Harborline page 2 of 3, TOTAL INVESTMENTS 16,500,000.00 lit
//   c  masked PII: Claire's W-2, box a •••-••-6081, box 1 268,400.00 lit
//   d  password-locked: the Halvard consolidated 1099
//   e  loading: the K-1's manifest never answers (three skeleton pages, "Processing…")
//   f  multi-source stepped: source 2 of 3, the Ridgeline 2025 K-1 statement p. 3
//   h  auto-highlight: Harborline, every cited region outlined, 2,915,330.00 hovered
//
// OPENS names the version, match and stack each artboard opens with.

import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { stableId } from "../seed/prng";
import {
  CLOCK_AFTERNOON,
  CLOCK_POPOVER,
  CLOCK_VIEWER,
  DOCUMENTS,
  HALVARD_1099,
  HARBORLINE,
  HARBORLINE_CITATIONS,
  HOVERED_2045,
  K1_DRAFT,
  K1_FIGURES,
  K1_PROCESSING,
  K1_STACK,
  LINE_2A,
  type SeededCitation,
  TB_TOTAL_INVESTMENTS,
  TOTAL_INVESTMENTS_CITATION,
  W2_CLAIRE,
  W2_WAGES,
} from "../seed/trust";

const E0 = seedScenario();
/** The Feld 2025 Form 1040 line 1a (wages), which Claire's W-2 box 1 supports (SHL-08c). */
const LINE_1A = stableId("tax-form-line:feld:2025:1040:1a");

export type Shl08State = "a" | "b" | "c" | "d" | "e" | "f" | "h";

export interface Shl08Opens {
  host: "drawer" | "dock";
  versionId: string;
  /** The match lit on open; null opens on page 1. */
  matchId: string | null;
  /** The anchor's stack the viewer steps (‹ ›), and the source in view. */
  stack: readonly string[];
  index: number;
  /** A region hovered in the artboard (h). */
  hovered?: string;
}

const k1 = (c: (typeof K1_STACK)[number], n: number): SeededCitation => ({
  anchor: { type: "tax_form_line", id: LINE_2A, ref: "line_2a", section: null },
  out: { ...c, n },
});

const FELD_CITATIONS: SeededCitation[] = [
  ...K1_STACK.map((c) => k1(c, c.n)),
  // The linked-figure rows the drawer reads with `host_ref` and `source_version_id`.
  ...K1_FIGURES.slice(0, 2).map((c) => ({
    anchor: { type: "tax_form_line", id: LINE_2A, ref: "k1_figures", section: null },
    out: c,
  })),
  {
    anchor: { type: "tax_form_line", id: LINE_1A, ref: "line_1a", section: null },
    out: W2_WAGES,
  },
];

const NORTHWIND_CITATIONS: SeededCitation[] = HARBORLINE_CITATIONS.map((out, i) => ({
  anchor: {
    type: "tb_row",
    id: i === 8 ? TB_TOTAL_INVESTMENTS : out.id,
    ref: "end_of_year",
    section: null,
  },
  out,
}));

const K1_STACK_IDS = K1_STACK.map((c) => c.id);

export const OPENS: Record<Shl08State, Shl08Opens> = {
  a: {
    host: "drawer",
    versionId: K1_DRAFT,
    matchId: K1_STACK[0]?.match_id ?? null,
    stack: K1_STACK_IDS,
    index: 0,
  },
  b: {
    host: "dock",
    versionId: HARBORLINE,
    matchId: TOTAL_INVESTMENTS_CITATION.match_id,
    stack: [TOTAL_INVESTMENTS_CITATION.id],
    index: 0,
  },
  c: {
    host: "drawer",
    versionId: W2_CLAIRE,
    matchId: W2_WAGES.match_id,
    stack: [W2_WAGES.id],
    index: 0,
  },
  d: { host: "drawer", versionId: HALVARD_1099, matchId: null, stack: [], index: 0 },
  e: { host: "drawer", versionId: K1_PROCESSING, matchId: null, stack: [], index: 0 },
  f: {
    host: "drawer",
    versionId: K1_STACK[1]?.source.evidence_version_id ?? "",
    matchId: K1_STACK[1]?.match_id ?? null,
    stack: K1_STACK_IDS,
    index: 1,
  },
  h: {
    host: "drawer",
    versionId: HARBORLINE,
    matchId: null,
    stack: [],
    index: 0,
    hovered: HOVERED_2045.match_id ?? "",
  },
};

function scenario(
  state: Shl08State,
  persona: string,
  clock: string,
  citations: readonly SeededCitation[],
): Scenario {
  return {
    state,
    persona,
    clock,
    handlers: {
      ...E0.handlers,
      ...trustHandlers({ citations, documents: DOCUMENTS, loading: [K1_PROCESSING] }),
    },
  };
}

export const scenarios = defineScenarios({
  a: scenario("a", "samuel-ito", CLOCK_VIEWER, FELD_CITATIONS),
  b: scenario("b", "hannah-leclerc", CLOCK_POPOVER, NORTHWIND_CITATIONS),
  c: scenario("c", "samuel-ito", CLOCK_VIEWER, FELD_CITATIONS),
  d: scenario("d", "samuel-ito", CLOCK_VIEWER, FELD_CITATIONS),
  e: scenario("e", "samuel-ito", CLOCK_VIEWER, FELD_CITATIONS),
  f: scenario("f", "samuel-ito", CLOCK_VIEWER, FELD_CITATIONS),
  h: scenario("h", "hannah-leclerc", CLOCK_AFTERNOON, NORTHWIND_CITATIONS),
});
