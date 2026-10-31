// HOME-02's evidence summaries in fixture mode (I-01-T18; docs/screens/HOME-02.md, Copy and
// Figures; AC7.7): a's basis table and calc card, c's capital rollforward with the agent's
// proposed M-2 fix, d's preparer memo (transcribed from the d artboard) and g's K-1 items. Tax
// content is fixture-only until T-05 (DV-4). The table totals and the differences are computed
// here from the seeded rows (whole dollars, integers), so the footing test proves them against
// the screen contract's figures; the screen only lays them out.

import type { ViewerManifestOut } from "@abacus/api-client";
import { prose } from "@abacus/ui";
import type { EvidenceRow, EvidenceSummary } from "../../app-core/evidence-summary";
import { BASIS_ROWS, CALC_CARD } from "./approvals";
import {
  CITED_RECTS,
  DECISION_754,
  DECISION_754_CITATIONS,
  FELD_PROPOSAL,
  TRANSFER,
  gateSubject,
} from "./approvals-detail";
import type { SeededDocument } from "./trust";

const n = (v: number): string => prose(String(v), "whole");
const off = (v: number): string => `off ${n(v)}`;

/** The transfer agreement's evidence version (the decision card's first source). */
export const TRANSFER_AGREEMENT = TRANSFER;

// ---- a: Basis at 12/31/2025 -------------------------------------------------------------------

export const BASIS_FOOTING = {
  taxCapital: BASIS_ROWS.reduce((s, r) => s + r.taxCapital, 0),
  liabilityShare: BASIS_ROWS.reduce((s, r) => s + r.liabilityShare, 0),
  outsideBasis: BASIS_ROWS.reduce((s, r) => s + r.outsideBasis, 0),
  insideShare: BASIS_ROWS.reduce((s, r) => s + r.insideShare, 0),
} as const;
const reconciled = BASIS_ROWS.filter((r) => r.outsideBasis === r.insideShare).length;
const difference = BASIS_FOOTING.outsideBasis - BASIS_FOOTING.insideShare;

const basisRows: EvidenceRow[] = BASIS_ROWS.map((r) => {
  const d = r.outsideBasis - r.insideShare;
  const lit = d !== 0;
  return {
    lit,
    cells: [
      { text: r.partner },
      { text: n(r.taxCapital) },
      { text: n(r.liabilityShare) },
      { text: n(r.outsideBasis), match: lit },
      { text: n(r.insideShare), match: lit },
      d === 0
        ? { text: "Reconciled", pill: { variant: "green-tint", check: true } }
        : { text: off(d), pill: { variant: "amber" } },
    ],
  };
});

const { outsideParts: o } = CALC_CARD;
const capitalTransferred = Math.round(
  (CALC_CARD.capitalAtSale * CALC_CARD.transferredShare[0]) / CALC_CARD.transferredShare[1],
);

export const BASIS_SUMMARY: EvidenceSummary = {
  title: "Basis at 12/31/2025 · Ridgeline",
  segment: "Basis",
  planned: "Open in workpaper ↗",
  tally: [
    { label: "OUTSIDE BASIS", value: n(BASIS_FOOTING.outsideBasis) },
    { label: "INSIDE SHARE", value: n(BASIS_FOOTING.insideShare) },
    {
      label: "RECONCILED",
      pill: { text: `${String(reconciled)} of ${String(BASIS_ROWS.length)}`, variant: "green" },
    },
  ],
  aside: { text: off(difference), variant: "amber" },
  table: {
    label: "Basis at 12/31/2025",
    columns: [
      "Partner",
      "Tax capital",
      "§752 share",
      "Outside basis",
      "Inside share",
      "Difference",
    ],
    rows: [
      ...basisRows,
      {
        total: true,
        cells: [
          { text: "TOTAL" },
          { text: n(BASIS_FOOTING.taxCapital) },
          { text: n(BASIS_FOOTING.liabilityShare) },
          { text: n(BASIS_FOOTING.outsideBasis) },
          { text: n(BASIS_FOOTING.insideShare) },
          { text: n(difference) },
        ],
      },
    ],
  },
  calc: {
    lines: [
      { label: "Purchase price paid by Pell Street II LLC", value: n(CALC_CARD.purchasePrice) },
      {
        label: `− Capital transferred (${String(CALC_CARD.transferredShare[0])}/${String(CALC_CARD.transferredShare[1])} × ${n(CALC_CARD.capitalAtSale)})`,
        value: n(capitalTransferred),
      },
      {
        label: "= §743(b) placeholder",
        value: n(CALC_CARD.purchasePrice - capitalTransferred),
        result: true,
      },
    ],
    note: `Pell Street II outside basis ${n(o.price + o.income + o.taxExempt - o.distributions + o.liabilities)} = ${n(o.price)} + ${n(o.income)} income + ${n(o.taxExempt)} tax-exempt − ${n(o.distributions)} distributions + ${n(o.liabilities)} liabilities.`,
  },
  sources: { [TRANSFER_AGREEMENT]: "Transfer agreement" },
};

// ---- c: Capital Accounts ----------------------------------------------------------------------

export const ROLLFORWARD = {
  beginning: 5_960_000,
  contributions: 250_000,
  income: 1_250_000,
  distributions: 600_000,
  scheduleL: 6_866_200,
} as const;
export const ENDING =
  ROLLFORWARD.beginning +
  ROLLFORWARD.contributions +
  ROLLFORWARD.income -
  ROLLFORWARD.distributions;
const capitalOff = ROLLFORWARD.scheduleL - ENDING;

export const CAPITAL_SUMMARY: EvidenceSummary = {
  title: "Capital Accounts · Ridgeline",
  segment: "Capital Accounts",
  planned: "Open in workpaper ↗",
  tally: [
    { label: "ROLLFORWARD", value: n(ENDING) },
    { label: "SCHEDULE L", value: n(ROLLFORWARD.scheduleL) },
  ],
  aside: { text: off(capitalOff), variant: "amber" },
  table: {
    label: "Capital rollforward · 2025",
    columns: ["Capital rollforward · 2025", "Amount"],
    rows: [
      { cells: [{ text: "Beginning capital" }, { text: n(ROLLFORWARD.beginning) }] },
      { cells: [{ text: "Contributions" }, { text: n(ROLLFORWARD.contributions) }] },
      {
        cells: [{ text: "Income (Schedule K, boxes 2 and 5)" }, { text: n(ROLLFORWARD.income) }],
      },
      {
        cells: [
          { text: "Distributions (box 19A)" },
          { text: `(${n(ROLLFORWARD.distributions)})`, negative: true },
        ],
      },
      { total: true, cells: [{ text: "Ending capital per rollforward" }, { text: n(ENDING) }] },
      {
        cells: [{ text: "Schedule L, partners' capital" }, { text: n(ROLLFORWARD.scheduleL) }],
      },
      {
        cells: [{ text: "Difference" }, { text: off(capitalOff), pill: { variant: "amber" } }],
      },
    ],
  },
  proposal: {
    by: "Proposed by Accrued Agent · awaits Samuel Ito",
    text: "Add tax-exempt interest 6,200 (Schedule K, box 18A) as an other increase on Schedule M-2. The rollforward then ties to Schedule L at 6,866,200.",
  },
};

// ---- d: the preparer memo (TXP-01), transcribed from the d artboard ---------------------------

export const MEMO_SUMMARY: EvidenceSummary = {
  title: "Preparer memo · Ridgeline",
  segment: "Preparer memo",
  planned: "Open memo ↗",
  paper: {
    title: "Ridgeline Property Partners, LP — 2025 Form 1065 preparer memo",
    byline: "Prepared by Olivia Brandt · Reviewed by Samuel Ito",
    paragraphs: [
      "Ownership changed during the year. On 6/30/2025 Pell Street Ventures LLC sold 5 of its 35 points to Pell Street II LLC for $360,000. Items are allocated with an interim closing under the monthly convention (§706(d)).",
      "Open decision: whether to recommend a §754 election. Without it, Pell Street II's 28,595 outside/inside difference is explained on the Basis workpaper and no §743(b) adjustment is recorded.",
      "Capital Accounts: Schedule M-2 is off 6,200 from Schedule L. The proposed fix adds tax-exempt interest as an other increase and awaits Samuel Ito.",
      "States: apportionment is Illinois 46.0%, Colorado 31.5% and New York 22.5%, with PTET of 28,044, 17,070 and 18,982.",
    ],
  },
};

// ---- g: the Feld K-1 --------------------------------------------------------------------------

export const K1_SUMMARY: EvidenceSummary = {
  title: "2025 Schedule K-1 · Feld",
  segment: "2025 Schedule K-1",
  planned: "Open source ↗",
  table: {
    label: "2025 Schedule K-1 · Feld",
    columns: ["Item", "Current", "Proposed"],
    rows: [
      {
        cells: [
          { text: "Ridgeline Property Partners, LP · Schedule E, Part II" },
          { text: "Nonpassive" },
          { text: "Passive", match: true },
        ],
      },
      {
        cells: [
          { text: "Form 8582 · rental real estate activities" },
          { text: "Not included" },
          { text: "Included", match: true },
        ],
      },
      {
        cells: [
          { text: "TY2024 treatment (prior year)" },
          { text: "Passive" },
          { text: "Passive" },
        ],
      },
    ],
  },
  cited: {
    title: "Cited on the 2025 Schedule K-1",
    items: ["Part II, item G · Limited partner", "Box 2 · Net rental real estate income (loss)"],
  },
};

/** The summaries by gate subject (a and b share the Basis summary). */
const SUMMARIES: Readonly<Record<string, EvidenceSummary>> = {
  [DECISION_754]: BASIS_SUMMARY,
  [gateSubject("daniel-reyes", 7)]: CAPITAL_SUMMARY,
  [gateSubject("daniel-reyes", 4)]: MEMO_SUMMARY,
  [FELD_PROPOSAL]: K1_SUMMARY,
};

export function evidenceSummaryOf(subjectId: string): EvidenceSummary | undefined {
  return SUMMARIES[subjectId];
}

// ---- The transfer agreement's page (the "Transfer agreement" segment and SHL-08) --------------

const transferManifest: ViewerManifestOut = {
  evidence_version_id: TRANSFER_AGREEMENT,
  file_name: "Pell Street membership interest transfer agreement.pdf",
  media_type: "application/pdf",
  status: "ready",
  reason: null,
  kind: "pages",
  page_count: 1,
  truncated: false,
  pages: [
    {
      n: 1,
      width_pt: 612,
      height_pt: 792,
      rotation: 0,
      image_w: 1240,
      image_h: 1605,
      text_layer: true,
      pii_scan: "done",
    },
  ],
  pii_masks: [],
  derivation_id: null,
  allowed_actions: [],
};

const TRANSFER_KEYS = ["transfer-1", "transfer-2"] as const;

/** The agreement as the C4 viewer serves it: one page with its two cited regions. */
export const TRANSFER_DOCUMENT: SeededDocument = {
  face: "statement",
  manifest: transferManifest,
  regions: DECISION_754_CITATIONS.filter((c) => c.source.evidence_version_id === TRANSFER).map(
    (c, i) => ({
      match_id: c.match_id ?? "",
      page: 1,
      rects: [CITED_RECTS[TRANSFER_KEYS[i] ?? "transfer-1"] ?? [0, 0, 0, 0]],
      sheet: null,
      cell: null,
      citation_id: c.id,
      label: c.loc,
    }),
  ),
};
