// T-04-T07 (TASK-6322; SPEC-649; T-04 §5.3; DEC-3022): the Feld 2025 Form 1040 return workspace on
// the E0 snapshot, for RW-1 and WS-1 in fixture mode. Personas kevin-osei (preparer) and
// samuel-ito (manager reviewer); clocks Wed Aug 26, 2026 10:15 AM to Sat Sep 19. Figures verbatim
// from the T-04 epic and the screen contracts; footed in tax-workspace.foot.test.ts. Synthetic only.
//
// Shapes are the generated client's RW-1 and WS-1 types (`tax/workspace_contract.py`).
import type {
  K1TreatmentOut,
  ReturnResidencyOut,
  ReviewDocumentOut,
  WorkspaceSummaryOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const PERSONAS = { kevin: "kevin-osei", samuel: "samuel-ito" } as const;
export const CLOCKS = {
  tax04: "2026-08-26T10:15:00-05:00",
  tax05: "2026-09-15T16:30:00-05:00",
  txi03b: "2026-09-15T16:55:00-05:00",
  delivered: "2026-09-19T11:00:00-05:00",
} as const;

export const FELD_RETURN_ID = stableId("tax-return:feld-2025-1040");
export const IDS = {
  halvard1099: stableId("evidence-version:feld-halvard-2025-1099"),
  ridgelineK1: stableId("evidence-version:feld-ridgeline-2025-k1-draft"),
  ridgelineActivity: stableId("k1-activity:feld-ridgeline-2025"),
  it201: stableId("worksheet:feld-it201"),
  schE: stableId("worksheet:feld-sch-e-p2-ridgeline"),
} as const;

/** TAX-04 a → b: Review 36 → 35 at Kevin's (preparer) level; 36 documents, 7 issues raised. */
export function workspace(state: "a" | "b" | "c" | "e"): WorkspaceSummaryOut {
  return {
    return_id: FELD_RETURN_ID,
    review_count: state === "b" ? 35 : state === "e" ? 0 : 36,
    viewer_level: state === "e" ? "manager" : "preparer",
    issues_open: 4,
    checkpoints_proposed: 0,
    k1_dependency: "draft_pre_release",
    assistant: "available",
    allowed_actions: state === "c" ? [] : ["document.approve"],
  };
}

/** TAX-04's two documents the artboards draw (the rest of the 36 are the seed's rows). */
export const REVIEW_TREE: ReviewDocumentOut[] = [
  {
    evidence_version_id: IDS.halvard1099,
    title: "Halvard Securities 2025 Consolidated 1099",
    category: "Income",
    sub_head: "Brokerage",
    approval: "unapproved",
    approvals_count: 0,
    flagged: false,
    mismatch_field_key: null,
    version: 1,
  },
  {
    evidence_version_id: IDS.ridgelineK1,
    title: "Ridgeline Property Partners, LP — 2025 Schedule K-1 (draft)",
    category: "Income",
    sub_head: "K-1s",
    approval: "unapproved",
    approvals_count: 0,
    flagged: true,
    mismatch_field_key: null,
    version: 1,
  },
] as const;

/** TAX-04 c: line 3b reads 14,280 while the 1099-DIV box 1a reads 14,820. */
export const LINE_3B = {
  line_key: "1040.3b",
  label: "Ordinary dividends",
  amount: "14820.00",
  typed: "14280.00",
};

/** The figures the screen contracts foot (T-04-T06 holds the same sums on the backend). */
export const FIGURES = {
  line8Parts: ["598030", "1550", "16025"] as const, // = 615,605
  line8Total: "615605",
  ridgelineBox2Shares: ["141634", "96989", "69277"] as const, // = 307,900
  ridgelineBox2Total: "307900",
  reviewDocuments: 41,
  reviewApproved: 4, // Review 37 = 41 − 4, then 36 (DF-34)
  k1Box5: "4600.00", // TAX-04 d "Taxable interest — Ridgeline K-1 box 5 $4,600"
  it201Line20: "1550.00", // TXI-01 b provenance 0 → 1,550
} as const;

/** TXI-02 a: seven treatments awaiting one approval; treatment 8 Approved · SI 9:31. */
export const TREATMENTS: K1TreatmentOut[] = Array.from({ length: 8 }, (_, i) => ({
  id: stableId(`k1-treatment:feld-ridgeline-${String(i + 1)}`),
  line: i === 7 ? "Box 20Z" : `Line ${String(i + 1)}`,
  treatment: i === 3 ? "Passive" : "Default",
  status: i === 7 ? "approved" : "proposed",
  changed_vs_year: i === 5 ? 2024 : null,
  decided_by_name: i === 7 ? "Samuel Ito" : null,
  version: 1,
}));

/** TXI-03 a (Review point) and b (Confirmed by Samuel Ito · Sep 15, 4:55 PM). */
export function residency(state: "a" | "b"): ReturnResidencyOut {
  return {
    status: state === "b" ? "confirmed" : "review_point",
    facts: ["150 NYC days", "Rhinebeck main home"],
    options: [
      { key: "brooklyn", label: "Brooklyn", recommended: false },
      { key: "rhinebeck", label: "Rhinebeck", recommended: true },
      { key: "both", label: "Both", recommended: false },
    ],
    confirmed_by_name: state === "b" ? "Samuel Ito" : null,
    confirmed_at: state === "b" ? "2026-09-15T21:55:00Z" : null,
  };
}
