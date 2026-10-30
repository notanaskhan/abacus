// P-04-T34: the C3 review-grammar fixtures in fixture mode (docs/contracts/review-grammar.md §8; the
// P-04 epic's artboard rows; the handoff's SHL-09, SHL-10, SHL-11, SHL-12, SHL-15 and SHL-16
// READMEs). One typed frame for every one of the 44 artboards, built against the generated client
// (a removed or renamed field fails tsc), with the persona and the instant each artboard is drawn
// at: E0 Mon Sep 14, 2026 (9:24 AM CT; SHL-12 at 9:41, SHL-11 at 10:01), and the Thu Sep 24,
// Thu Oct 1 and Tue Oct 6 snapshots. Figures foot in code (bigint thousandths, never floats); copy
// and figures come verbatim from the contract and the artboards; ids are stable placeholders.
//
// fixtures/handlers/review.ts serves these frames on the C3 routes; the consumer assertions in
// fixtures/contracts/review-grammar.test.ts read them from here (no frame is drafted in a test).
// P-04-T36 replaces the frames with the scenario's own events through the services.

import type {
  AgentProposalOut as ProposalOut,
  AgentSuggestionOut as SuggestionOut,
  CardDecideIn as DecideIn,
  CardDecisionOut as DecisionOut,
  ReviewNoteDetailOut as ReviewNoteOut,
  ApproveProposalIn,
  BulkFixInstructionsIn,
  BulkFixInstructionsOut,
  BulkSignOffOut,
  CheckpointApproveIn,
  CheckpointCreateIn,
  CheckpointDecisionOut,
  CheckpointDetailOut,
  CheckpointDiffRowOut,
  CheckpointHistoryOut,
  CheckpointItemOut,
  CheckpointRejectIn,
  CheckpointRenameIn,
  CheckpointRestoreIn,
  DecisionCardOut,
  DecisionCardVersionOut,
  EligibilityCheckOut,
  ExplainAcceptedOut,
  FieldEditIn,
  FieldProvenanceOut,
  FieldReferenceIn,
  FieldReferenceOut,
  FieldTickIn,
  FieldTickOut,
  FieldVersionOut,
  FixInstructionsAcceptedOut,
  FixInstructionsIn,
  IssueCreateIn,
  IssueDetailOut,
  IssueItemOut,
  IssueSendToClientIn,
  LadderLevelOut,
  ListPageDecisionCardItemOut,
  ListPageIssueItemOut,
  ListPageReviewNoteItemOut,
  ProposalRowOut,
  RejectProposalIn,
  RouteProposalIn,
  SignOffEligibilityOut,
  SignOffIn,
  SignOffLadderOut,
  SignOffOut,
} from "@abacus/api-client";

export const id = (n: number): string => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const HASH = "sha256:9f4c" + "0".repeat(56) + "e21a"; // SHL-12 shows sha256:9f4c…e21a

export const SCALE = 1000n;
/** A doc figure ("$16,812,400", "0.015", "14,900.00") as an exact integer of thousandths. */
export function milli(text: string): bigint {
  const [whole = "0", frac = ""] = text.replace(/[$,]/g, "").split(".");
  return BigInt(whole) * SCALE + BigInt((frac + "000").slice(0, 3));
}
export const times = (a: bigint, b: bigint): bigint => (a * b) / SCALE;
/** Nearest multiple of `inc`, halves up (the scenario golden's materiality rounding). */
export const roundTo = (x: bigint, inc: bigint): bigint => ((x + inc / 2n) / inc) * inc;
/** Whole dollars with thousands commas ("$252,200"), in code: figures never pass through floats. */
export const dollars = (x: bigint): string =>
  `$${String(x / SCALE).replace(/\B(?=(\d{3})+(?!\d))/gu, ",")}`;
export const sum = (xs: bigint[]): bigint => xs.reduce((a, b) => a + b, 0n);

// --- SHL-12 a–h: sign-off modal (stub 1) -------------------------------------------------------

export const TB = id(1);
export const MARCUS = id(11);
export const HANNAH = id(12);
export const MARGARET = id(13);
export const THOMAS = id(14);
export const STATEMENT = "bh-review-v1";

export const target = {
  target_type: "workpaper",
  target_id: TB,
  label: "Trial Balance",
  context_label: "Northwind Robotics 401(k) Plan · PY2025",
  version_no: 1,
  content_hash: HASH,
  cell_count: 14,
  citation_count: 3,
};
export const marcusL1: SignOffOut = {
  id: id(21),
  target_type: "workpaper",
  target_id: TB,
  kind: "ladder",
  level: "L1_preparer",
  signer_user_id: MARCUS,
  signer_name: "Marcus Delaney",
  initials: "MD",
  signed_at: "2026-09-14T14:33:00Z",
  content_hash: HASH,
  version_no: 1,
  statement_version: STATEMENT,
  adopted_run_id: id(31),
  adopted_run_number: 4127,
  stale: false,
};
export const hannahL2: SignOffOut = {
  ...marcusL1,
  id: id(22),
  level: "L2_reviewer",
  signer_user_id: HANNAH,
  signer_name: "Hannah Leclerc",
  initials: "HL",
  signed_at: "2026-09-14T14:41:00Z",
  adopted_run_id: null,
  adopted_run_number: null,
};
export const ladder = (l2: SignOffOut | null): LadderLevelOut[] => [
  {
    level: "L1_preparer",
    required: true,
    expected_signer_user_id: null,
    expected_signer_name: null,
    latest: marcusL1,
  },
  {
    level: "L2_reviewer",
    required: true,
    expected_signer_user_id: null,
    expected_signer_name: null,
    latest: l2,
  },
  {
    level: "L3_manager",
    required: false,
    expected_signer_user_id: null,
    expected_signer_name: null,
    latest: null,
  },
  {
    level: "L4_partner",
    required: true,
    expected_signer_user_id: MARGARET,
    expected_signer_name: "Margaret Okonkwo",
    latest: null,
  },
  {
    level: "L5_eqr",
    required: true,
    expected_signer_user_id: THOMAS,
    expected_signer_name: "Thomas Whitcombe",
    latest: null,
  },
];
export const passing: EligibilityCheckOut[] = [
  { code: "open_review_notes", result: "pass", facts: { count: 0 }, refs: [] },
  {
    code: "independence",
    result: "pass",
    facts: { person: "Hannah Leclerc", confirmed_on: "2026-08-03" },
    refs: [],
  },
  { code: "segregation", result: "pass", facts: { preparer: "Marcus Delaney" }, refs: [] },
  { code: "all_cited", result: "pass", facts: { cited: 14, cells: 14 }, refs: [] },
  {
    code: "gate_g4",
    result: "warn",
    facts: { awaiting: "Margaret Okonkwo" },
    refs: [{ type: "decision_card", id: id(41) }],
  },
];
export const eligibility = (over: Partial<SignOffEligibilityOut>): SignOffEligibilityOut => ({
  target,
  level: "L2_reviewer",
  levels_allowed: ["L1_preparer", "L2_reviewer", "L3_manager", "L4_partner"],
  ladder: ladder(null),
  checks: passing,
  eligible: true,
  statement: {
    version: STATEMENT,
    text: "I reviewed this work. It is sufficient and appropriate, and its conclusions are supported.",
  },
  ...over,
});
export const withCheck = (check: EligibilityCheckOut): EligibilityCheckOut[] =>
  passing.map((c) => (c.code === check.code ? check : c));

export const SHL12 = {
  a: eligibility({}),
  b: eligibility({
    checks: withCheck({
      code: "open_review_notes",
      result: "fail",
      facts: { count: 2 },
      refs: [
        { type: "review_note", id: id(51) },
        { type: "review_note", id: id(52) },
      ],
    }),
    eligible: false,
  }),
  c: eligibility({
    checks: withCheck({
      code: "segregation",
      result: "fail",
      facts: { preparer: "Marcus Delaney" },
      refs: [],
    }),
    eligible: false,
  }),
  d: eligibility({
    checks: withCheck({
      code: "independence",
      result: "fail",
      facts: { person: "Hannah Leclerc", confirmed_on: null },
      refs: [],
    }),
    eligible: false,
  }),
  g: eligibility({ level: "L5_eqr", levels_allowed: ["L5_eqr"] }),
  h: eligibility({
    level: "L4_partner",
    levels_allowed: ["L4_partner"],
    checks: [{ code: "open_issues", result: "fail", facts: { count: 11 }, refs: [] }],
    eligible: false,
  }),
} satisfies Record<string, SignOffEligibilityOut>;

export const notes: ListPageReviewNoteItemOut = {
  items: [
    ["RA!C14", HANNAH, "HL", ["review_note.clear"]],
    ["RA!C22", MARGARET, "MO", []],
  ].map(([ref, by, initials, actions], i) => ({
    id: id(51 + i),
    engagement_id: id(2),
    target_type: "workpaper",
    target_id: id(3),
    anchor: { kind: "cell", ref: ref as string },
    status: "open",
    raised_by_user_id: by as string,
    raised_by_initials: initials as string,
    raised_at: "2026-09-14T14:00:00Z",
    assignee_user_id: MARCUS,
    allowed_actions: actions as string[],
  })),
  next_cursor: null,
  total: 2,
  total_capped: false,
  counts: { open: 2 },
  facets: {},
};

// --- SHL-11 a–h: decision card (stub 2) --------------------------------------------------------

export const CARD_ID = id(41);
export const proposedV1: DecisionCardVersionOut = {
  version_no: 1,
  event: "proposed",
  actor_kind: "agent",
  actor_user_id: null,
  actor_initials: null,
  at: "2026-09-14T14:27:00Z",
  option_key: "pct_1_5",
  changed: null,
  figures: {},
};
export const option = (rate: string, materiality: string, pm: string, ct: string) => ({
  rate,
  materiality,
  performance_materiality: pm,
  clearly_trivial: ct,
});
export const materialityCard: DecisionCardOut = {
  card: {
    id: CARD_ID,
    engagement_id: id(2),
    work_item_id: id(4),
    kind: "planning_materiality",
    version_no: 1,
    status: "awaiting_role",
    reserved_role: "engagement_partner",
    reserved_user_id: MARGARET,
    reserved_user_name: "Margaret Okonkwo",
    requested_at: "2026-09-14T14:27:00Z",
    blocking_count: 3,
    superseded_by_version: null,
    allowed_actions: ["decision.decide", "decision.request_analysis"],
  },
  question: "Which planning materiality should the Northwind PY2025 audit use?",
  context: [
    {
      key: "benchmark",
      label: "Benchmark",
      value: "Net assets available for benefits, unadjusted, 12/31/2025",
      citation_id: null,
    },
    { key: "amount", label: "Amount", value: "$16,812,400", citation_id: id(42) },
  ],
  options: [
    {
      key: "pct_1_0",
      label: "1.0% — $168,100",
      detail: "Performance materiality 75% = $126,075 · clearly trivial 5% = $8,405.",
      figures: option("0.010", "168100", "126075", "8405"),
      recommended: false,
    },
    {
      key: "pct_1_5",
      label: "1.5% — $252,200",
      detail: "PM 75% = $189,150 · CT 5% = $12,610",
      figures: option("0.015", "252200", "189150", "12610"),
      recommended: true,
    },
  ],
  factors: [
    {
      key: "first_year",
      label: "First-year engagement or change in recordkeeper",
      applicable: false,
      checked: false,
    },
  ],
  citation_ids: [id(42)],
  note: null,
  recommendation: {
    suggestion_id: id(43),
    option_key: "pct_1_5",
    reasons: ["Same basis and percentage as PY2024"],
  },
  blocking_refs: [{ type: "workpaper", id: id(44) }],
  decision: null,
  history: [proposedV1],
};
export const decision: DecisionOut = {
  id: id(45),
  option_key: "pct_1_5",
  factors: ["late_deposits", "users"],
  rationale:
    "Recurring engagement, stable plan, no prior misstatements above CT. 1.5% of net assets, consistent with PY2024.",
  seen_card_version: 1,
  decided_by_user_id: MARGARET,
  decided_by_name: "Margaret Okonkwo",
  decided_at: "2026-09-14T15:02:00Z",
};
export const decidedV2: DecisionCardVersionOut = {
  ...proposedV1,
  version_no: 2,
  event: "decided",
  actor_kind: "human",
  actor_user_id: MARGARET,
  actor_initials: "MO",
  at: "2026-09-14T15:02:00Z",
};
export const decided: DecisionCardOut = {
  ...materialityCard,
  card: { ...materialityCard.card, status: "decided", version_no: 2, allowed_actions: [] },
  decision,
  history: [proposedV1, decidedV2],
};
export const reassessedV3: DecisionCardVersionOut = {
  ...decidedV2,
  version_no: 3,
  event: "reassessed",
  actor_kind: "system",
  actor_user_id: null,
  actor_initials: null,
  at: "2026-10-06T15:00:00Z",
  changed: false,
  figures: { benchmark: "16861000", materiality: "252900", difference: "700" },
};

export const SHL11 = {
  a: materialityCard,
  b: {
    ...materialityCard,
    card: {
      ...materialityCard.card,
      allowed_actions: ["decision.notify", "decision.request_analysis"],
    },
  },
  c: decided,
  d: {
    ...decided,
    card: { ...decided.card, version_no: 3 },
    history: [proposedV1, decidedV2, reassessedV3],
  },
  f: {
    ...materialityCard,
    card: { ...materialityCard.card, kind: "deficiency_severity" },
    question: "<deficiency severity question>", // copy arrives with the A-06 kind
    options: ["Deficiency", "Significant deficiency", "Material weakness"].map((label, i) => ({
      key: ["deficiency", "significant_deficiency", "material_weakness"][i] ?? "",
      label,
      detail: null,
      figures: {},
      recommended: i === 1,
    })),
    recommendation: { suggestion_id: id(46), option_key: "significant_deficiency", reasons: [] },
  },
  g: {
    ...materialityCard,
    card: {
      ...materialityCard.card,
      kind: "section_754",
      reserved_role: "signer",
      reserved_user_id: id(15),
      reserved_user_name: "Daniel Reyes",
    },
    options: [
      {
        key: "elect",
        label: "<§754 option>", // copy arrives with the T-05 kind
        detail: null,
        figures: { step_up: "28595" },
        recommended: true,
      },
    ],
    note: "The election is Ridgeline's to make (Owen Calder signs the statement).",
  },
  h: {
    ...decided,
    card: { ...decided.card, status: "superseded", superseded_by_version: 3, allowed_actions: [] },
  },
} satisfies Record<string, DecisionCardOut>;

// --- SHL-10 a–g: approve agent output (stub 2) -------------------------------------------------

export const row = (
  n: number,
  field_key: string,
  label: string,
  before: string | null,
  after: string | null,
  cause: string | null,
  cites: number,
): ProposalRowOut => ({
  n,
  suggestion_id: cites > 0 ? id(80 + n) : null,
  field_key,
  label,
  before,
  after,
  cause,
  citation_ids: Array.from({ length: cites }, (_, i) => id(90 + i)),
  unsupported: cites === 0,
});
export const k1: ProposalOut = {
  ref: id(100),
  kind: "field_change_set",
  title: "K-1 treatment: Ridgeline",
  context_label: "2025 Form 1040 · Feld",
  state: "pending",
  version: 1,
  agent_run_id: id(31),
  proposed_at: "2026-09-14T14:18:00Z",
  change_count: 4,
  reasoning: "Prior-year treatment and the draft Ridgeline K-1 support passive classification.",
  rows: [
    row(
      1,
      "activity_classification.ridgeline",
      "Activity classification · Ridgeline Property Partners, LP",
      "Nonpassive",
      "Passive",
      "K-1 box G; 2024 Sch E",
      2,
    ),
    row(
      2,
      "sch_e.p2.28a_k",
      "Sch E p. 2 line 28A (k) Nonpassive income from K-1",
      "307900",
      null,
      "moved to (h)",
      1,
    ),
    row(
      3,
      "sch_e.p2.28a_h",
      "Sch E p. 2 line 28A (h) Passive income from K-1",
      null,
      "307900",
      "K-1 box 2",
      1,
    ),
    row(
      4,
      "f8995a.p1.l1.ridgeline",
      "Form 8995-A Part I line 1 · Ridgeline QBI",
      null,
      "307900",
      "K-1 box 20 Z statement",
      1,
    ),
  ],
  totals: [{ label: "Net change to Form 1040 total income", value: "0", ties: true }],
  evidence: [
    {
      evidence_version_id: id(101),
      label: "2025 Schedule K-1 — Ridgeline (Draft K-1 · pre-release)",
      citation_count: 2,
    },
    {
      evidence_version_id: id(102),
      label: "2024 Form 1040 — Schedule E, p. 2",
      citation_count: 1,
    },
    {
      evidence_version_id: id(103),
      label: "Ridgeline K-1 statement — box 20 code Z (§199A)",
      citation_count: 1,
    },
  ],
  policy: {
    policy_name: null,
    result: null,
    routed_to_user_id: null,
    routed_to_name: null,
    note: "Return proposals need a Tax Reviewer. Final approval of this return stays with Daniel Reyes (BH-TAX-02).",
  },
  set: null,
  checkpoint_id: null,
  decision: null,
  allowed_actions: ["proposal.approve", "proposal.reject", "proposal.follow_up"],
};
export const RAJ = id(16);
export const PRIYA = id(17);
export const SAMUEL = id(18);
export const decidedBy = (by: string, name: string, at: string) => ({
  id: id(110),
  reason_code: null,
  note: null,
  decided_by_user_id: by,
  decided_by_name: name,
  decided_at: at,
  routed_to_user_id: null,
});
export const AJE05 = ["12,600.00", "1,480.00", "820.00"]; // §8 SHL-10 d
export const BATCH = "20,020.00"; // SHL-10 e: 4 entries, tie

export const SHL10 = {
  a: k1,
  c: {
    ...k1,
    rows: [
      ...k1.rows,
      row(5, "sch_a.l5b", "Sch A line 5b Real estate taxes (co-op share)", null, "18240", null, 0),
    ],
    change_count: 5,
    allowed_actions: ["proposal.reject", "proposal.follow_up"],
  },
  d: {
    ...k1,
    kind: "adjusting_entry",
    title: "AJE-05",
    context_label: "Copperleaf",
    rows: [],
    change_count: 0,
    totals: [{ label: "AJE-05", value: "14900.00", ties: true }],
    policy: {
      policy_name: "BH AJE thresholds v2",
      result: "review_required",
      routed_to_user_id: PRIYA,
      routed_to_name: "Priya Raman",
      note: null,
    },
    allowed_actions: ["proposal.route", "proposal.reject", "proposal.follow_up"],
  },
  e: {
    ...k1,
    kind: "adjusting_entry_batch",
    title: "Approve 4 under BH AJE thresholds v2",
    rows: [],
    change_count: 0,
    totals: [{ label: "4 entries", value: "20020.00", ties: true }],
    policy: {
      policy_name: "BH AJE thresholds v2",
      result: "within_threshold",
      routed_to_user_id: null,
      routed_to_name: null,
      note: null,
    },
    allowed_actions: ["proposal.approve", "proposal.reject", "proposal.follow_up"],
  },
  e_prime: {
    ...k1,
    kind: "adjusting_entry_batch",
    title: "Approve 4 under BH AJE thresholds v2",
    rows: [],
    change_count: 0,
    state: "approved",
    totals: [{ label: "4 entries", value: "20020.00", ties: true }],
    policy: {
      policy_name: "BH AJE thresholds v2",
      result: "within_threshold",
      routed_to_user_id: null,
      routed_to_name: null,
      note: null,
    },
    decision: {
      ...decidedBy(RAJ, "Raj Malhotra", "2026-09-14T14:24:00Z"),
      decision: "approved",
      undo_until: "2026-09-14T14:24:10Z",
    },
    allowed_actions: ["proposal.undo"],
  },
  f: {
    ...k1,
    state: "rejected",
    decision: {
      ...decidedBy(SAMUEL, "Samuel Ito", "2026-09-14T14:24:00Z"),
      decision: "rejected",
      reason_code: "needs_client_input",
      undo_until: "2026-09-14T14:24:10Z",
    },
    allowed_actions: [],
  },
  g: {
    ...k1,
    kind: "procedure_conclusion",
    title: "Front Range Freight Co.",
    context_label: "Granite Peak FY2026",
    set: {
      set_type: "procedure_result_set",
      set_id: id(120),
      label: "BH-FS-430 Search for unrecorded liabilities",
      results: 40,
      exceptions: 1,
    },
  },
} satisfies Record<string, ProposalOut>;

// --- Stub 3 (P-04-T12): SHL-09 a–f, SHL-15 a–e, SHL-16 a–f ------------------------------------
// An additive extension of C3 v1: new frames on new types; the frames above are unchanged.

export const FELD_1040 = id(200);
export const KEVIN = id(280);
export const ANA = id(281);
export const DANA = id(282);
export const digest = (head: string, tail: string): string =>
  `sha256:${head}${"0".repeat(56)}${tail}`;
export const FIELD_V2 = digest("7d20", "c4b1"); // SHL-09 a, the current value's hash
export const FIELD_V1 = digest("e913", "5a02"); // Kevin's tick, on the imported value
export const CP6_HASH = digest("5e1d", "a6f0");

// SHL-09 a–f: field provenance tray -------------------------------------------------------------

export const importRef: FieldReferenceOut = {
  id: id(201),
  kind: "engine_import",
  label: "Imported Return — CCH Axcess 2025I:FeldJ:V3",
  detail: null,
  citation_id: null,
  document_id: null,
  page: null,
};
export const updated: FieldVersionOut = {
  seq: 2,
  value: { t: "decimal", v: "2310" },
  value_kind: "exact",
  value_source: "agent_suggested",
  cause: "suggestion_adopted",
  actor_kind: "agent",
  actor_user_id: null,
  actor_name: "Accrued Agent",
  recorded_at: "2026-09-10T19:12:00Z",
  citation:
    "Box 1 of the corrected Halvard Securities 2025 Form 1099-INT (issued Mar 6, 2026), consolidated statement p. 4.",
  citation_ids: [id(202)],
  references: [
    { ...importRef, label: `${importRef.label} (prior value 2,190)` },
    {
      id: id(203),
      kind: "document",
      label: "Halvard Securities 2025 Consolidated 1099 (Corrected) · p. 4",
      detail: "Interest income, Box 1: 2,310.00",
      citation_id: id(202),
      document_id: id(204),
      page: 4,
    },
  ],
  unsupported: false,
  suggestion_id: id(205),
  checkpoint_id: id(214),
  issue_id: null,
};
export const previous: FieldVersionOut = {
  ...updated,
  seq: 1,
  value: { t: "decimal", v: "2190" },
  value_source: "engine_import",
  cause: "import",
  actor_kind: "system",
  actor_name: "Imported Return",
  recorded_at: "2026-08-28T15:46:00Z",
  citation:
    "Box 1 of the original Halvard Securities 2025 Form 1099-INT (issued Feb 14, 2026), p. 4.",
  citation_ids: [id(206)],
  references: [importRef],
  suggestion_id: null,
  checkpoint_id: id(212),
};
export const koTick: FieldTickOut = {
  sign_off_id: id(207),
  level: "L1_preparer",
  signer_user_id: KEVIN,
  signer_name: "Kevin Osei",
  initials: "KO",
  signed_at: "2026-09-08T17:00:00Z",
  content_hash: FIELD_V1,
  stale: true,
};
export const tray: FieldProvenanceOut = {
  target_type: "tax_return",
  target_id: FELD_1040,
  field_key: "sch_b.p1.l1.halvard",
  label: "Taxable interest — Halvard Securities",
  current_seq: 2,
  content_hash: FIELD_V2,
  versions: [updated, previous],
  ticks: [koTick],
  flags: [
    {
      note_id: id(208),
      raised_by_user_id: SAMUEL,
      raised_by_initials: "SI",
      raised_at: "2026-09-11T17:00:00Z",
      body: "Confirm corrected 1099 replaces the original",
      status: "open",
    },
  ],
  allowed_actions: ["field.edit", "field.add_reference", "field.sign_off"],
};
export const SHL09 = {
  a: tray,
  b: {
    ...tray,
    field_key: "f1040es.federal.2025",
    label: "2025 federal estimated tax payments",
    current_seq: 1,
    versions: [
      {
        ...updated,
        seq: 1,
        value: { t: "decimal", v: "48000" },
        value_kind: "estimate",
        citation:
          "Four 2025 Form 1040-ES vouchers of $12,000 prepared with the 2024 return; payment confirmations not received.",
        references: [
          { ...importRef, kind: "prior_return", label: "2024 Form 1040 — estimate worksheet" },
        ],
        issue_id: id(209),
      },
    ],
    ticks: [],
    flags: [],
  },
  c: {
    ...tray,
    versions: [
      {
        ...updated,
        value_source: "human",
        cause: "edit",
        actor_kind: "human",
        actor_user_id: KEVIN,
        actor_name: "Kevin Osei",
        citation: "Per client email Sep 9 — Jonah confirmed…",
        suggestion_id: null,
      },
      updated,
      previous,
    ],
    current_seq: 3,
  },
  d: {
    ...tray,
    ticks: [
      { ...koTick, signed_at: "2026-09-11T17:00:00Z", content_hash: FIELD_V2, stale: false },
      {
        ...koTick,
        sign_off_id: id(210),
        level: "L2_reviewer",
        signer_user_id: SAMUEL,
        signer_name: "Samuel Ito",
        initials: "SI",
        signed_at: "2026-09-14T17:00:00Z",
        content_hash: FIELD_V2,
        stale: false,
      },
    ],
    flags: [],
  },
  e: {
    ...tray,
    versions: [
      { ...updated, citation: null, citation_ids: [], references: [], unsupported: true },
    ],
    current_seq: 1,
    ticks: [],
    flags: [],
    allowed_actions: ["field.edit", "field.add_reference"],
  },
  f: tray,
} satisfies Record<string, FieldProvenanceOut>;
export const PROVENANCE = "/v1/fields/{target_type}/{target_id}/{field_key}/provenance";

// SHL-16 a–f: checkpoint drawer -----------------------------------------------------------------

export const checkpoint = (seq: number, over: Partial<CheckpointItemOut>): CheckpointItemOut => ({
  id: id(210 + seq),
  target_type: "tax_return",
  target_id: FELD_1040,
  seq,
  name: null,
  starred: false,
  author_kind: "agent",
  author_user_id: null,
  author_name: "Accrued Agent",
  cause: "agent_run",
  status: "saved",
  current: false,
  summary: null,
  created_at: "2026-09-14T14:18:00Z",
  content_hash: digest(String(seq).repeat(4), "0000"),
  proposal_id: null,
  restored_from_id: null,
  agent_run_id: null,
  decision: null,
  allowed_actions: ["checkpoint.restore", "checkpoint.rename"],
  ...over,
});
export const approval = (by: string, name: string, at: string): CheckpointDecisionOut => ({
  id: id(230),
  decision: "approved",
  reason: null,
  decided_by_user_id: by,
  decided_by_name: name,
  decided_at: at,
  proposal_decision_id: id(231),
});
export const cp6 = checkpoint(6, {
  status: "proposed",
  summary: "K-1 treatment: Ridgeline",
  content_hash: CP6_HASH,
  proposal_id: k1.ref,
  agent_run_id: id(31),
  allowed_actions: ["checkpoint.approve", "checkpoint.reject", "checkpoint.rename"],
});
export const cards: CheckpointItemOut[] = [
  cp6,
  checkpoint(5, {
    author_kind: "person",
    author_user_id: KEVIN,
    author_name: "Kevin Osei",
    cause: "human_edit",
    current: true,
    summary: "Preparer review edits",
    created_at: "2026-09-11T21:40:00Z",
    allowed_actions: ["checkpoint.rename"],
  }),
  checkpoint(4, {
    status: "approved",
    summary: "Corrected Halvard 1099-INT (2,190 → 2,310)",
    created_at: "2026-09-10T19:12:00Z",
    decision: approval(KEVIN, "Kevin Osei", "2026-09-10T19:12:00Z"),
  }),
  checkpoint(3, {
    status: "approved",
    summary: "Initial draft self-checked",
    created_at: "2026-09-03T16:05:00Z",
  }),
  checkpoint(2, {
    author_kind: "import",
    author_name: "Imported Return",
    cause: "engine_import",
    summary: "Imported from CCH Axcess 2025I:FeldJ:V3",
    created_at: "2026-08-28T15:46:00Z",
  }),
  checkpoint(1, {
    name: "Extension estimate (4868)",
    starred: true,
    author_kind: "person",
    author_user_id: KEVIN,
    author_name: "Kevin Osei",
    cause: "manual_save",
    created_at: "2026-04-13T17:00:00Z",
  }),
];
export const history = (items: CheckpointItemOut[]): CheckpointHistoryOut => ({
  target_type: "tax_return",
  target_id: FELD_1040,
  filter: "all",
  items,
  current_checkpoint_id: items.find((c) => c.current)?.id ?? null,
  total: items.length,
  allowed_actions: ["checkpoint.create"],
});
export const diffRow = (
  field_key: string,
  label: string,
  old: string | null,
  next: string | null,
  cause: string,
): CheckpointDiffRowOut => ({ field_key, label, old, new: next, cause, citation_ids: [id(33)] });
export const cp6Detail: CheckpointDetailOut = {
  checkpoint: cp6,
  compare: "previous",
  compared_to_id: id(215),
  steps: [
    {
      kind: "analyzed",
      title: "Analyzed the drafted return",
      detail: "Read 11 worksheets and the 2024 return's Schedule E, p. 2.",
      at: "2026-09-14T14:16:00Z",
    },
    {
      kind: "analyzed",
      title: "Analyzed the draft Ridgeline K-1 (pre-release)",
      detail: "Boxes G, 2, 5, 18A, 19A and the box 20 Z statement.",
      at: "2026-09-14T14:17:00Z",
    },
    {
      kind: "updated_worksheet",
      title: "Updated worksheet",
      detail: "Federal › Income › Sch E, p 2 - Partnership Passthrough (K-1 1065) › Ridgeline",
      at: "2026-09-14T14:17:00Z",
    },
    {
      kind: "updated_worksheet",
      title: "Updated worksheet",
      detail: "Federal › Deductions › Form 8995-A — Qualified business income",
      at: "2026-09-14T14:18:00Z",
    },
    {
      kind: "skipped_worksheet",
      title: "Skipped creating worksheet",
      detail: "Form 8582 — no passive losses this year, so it isn't required.",
      at: "2026-09-14T14:18:00Z",
    },
  ],
  diff: [
    diffRow(
      "activity_classification.ridgeline",
      "Activity classification · Ridgeline",
      "Nonpassive",
      "Passive",
      "K-1 box G; 2024 Sch E",
    ),
    diffRow(
      "sch_e.p2.28a_k",
      "Sch E p. 2 line 28A (k) Nonpassive income",
      "307900",
      null,
      "moved to (h)",
    ),
    diffRow(
      "sch_e.p2.28a_h",
      "Sch E p. 2 line 28A (h) Passive income",
      null,
      "307900",
      "K-1 box 2",
    ),
    diffRow(
      "f8995a.p1.l1.ridgeline",
      "Form 8995-A Part I line 1 · Ridgeline QBI",
      null,
      "307900",
      "K-1 box 20 Z",
    ),
  ],
  totals: [{ label: "Net change to total income", value: "0", ties: true }],
};
export const SHL16 = {
  a: history(cards),
  b: history([
    {
      ...cp6,
      status: "approved",
      current: true,
      decision: approval(SAMUEL, "Samuel Ito", "2026-09-14T14:26:00Z"),
      allowed_actions: ["checkpoint.rename"],
    },
    ...cards.slice(1).map((c) => ({ ...c, current: false })),
  ]),
  d: history(
    cards.map((c) => (c.seq === 5 ? { ...c, name: "Before K-1 treatment", starred: true } : c)),
  ),
  e: history([
    {
      ...cp6,
      status: "rejected",
      decision: {
        ...approval(SAMUEL, "Samuel Ito", "2026-09-14T14:26:00Z"),
        decision: "rejected",
        reason: "Wait for final K-1",
      },
      allowed_actions: ["checkpoint.rename"],
    },
    ...cards.slice(1),
  ]),
  f: { ...history([]), target_id: id(240) },
} satisfies Record<string, CheckpointHistoryOut>;

// SHL-15 a–e: issue composer and fix instructions -----------------------------------------------

export const SUGGESTION =
  "Add 1,550 from the draft Ridgeline K-1 box 18A to Form 1040 line 2a. Check the K-1 statement for the state of the bonds and add any non-New York portion to IT-201 line 20. Mark both values as draft until Ridgeline releases final K-1s.";
export const issueRow: IssueItemOut = {
  id: id(250),
  engagement_id: id(251),
  work_item_id: FELD_1040,
  record: { type: "tax_return", id: FELD_1040 },
  kind: "missing_information",
  priority: "high",
  status: "open",
  instructions_required: true,
  assignee_user_id: null,
  assignee_name: null,
  assignee_agent: true,
  blocks: [],
  link_count: 2,
  version: 1,
  created_at: "2026-09-14T14:00:00Z",
  allowed_actions: ["issue.update", "issue.resolve", "fix_instruction.set", "issue.explain"],
};
export const issue18a: IssueDetailOut = {
  issue: issueRow,
  record_label: "2025 Form 1040 · Jonah & Claire Feld",
  title: "Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet",
  internal_note: null,
  client_wording: null,
  client_contact: null,
  links: [
    {
      kind: "file",
      label: "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
      target_type: "document",
      target_id: id(252),
      anchor: null,
    },
    {
      kind: "form_field",
      label: "Form 1040 · line 2a",
      target_type: "tax_return",
      target_id: FELD_1040,
      anchor: "f1040.l2a",
    },
  ],
  suggestion: { text: SUGGESTION, agent_run_id: id(253), suggested_at: "2026-09-14T14:00:00Z" },
  fix_instructions: null,
  fix_run: null,
  explanations: [
    {
      id: id(254),
      text: "Line 2a is informational federally, but New York adds interest on other states' bonds back on IT-201 line 20. Leaving it out would understate New York income by up to $1,550, and the IRS matches K-1 reporting to the return.",
      agent_run_id: id(255),
      explained_at: "2026-09-14T14:22:00Z",
      citations: [
        { citation_id: id(256), label: "K-1 box 18A" },
        { citation_id: id(257), label: "K-1 statement p. 3" },
        { citation_id: id(258), label: "IT-201 instructions, line 20" },
      ],
      pinned: true,
    },
  ],
  request_item_id: null,
  events: [],
};
export const INSTRUCTIONS = `${SUGGESTION}\nDon't change taxable interest on line 2b (6,910).`;
export const fixing: IssueDetailOut = {
  ...issue18a,
  issue: { ...issueRow, status: "in_progress", instructions_required: false, version: 2 },
  fix_instructions: {
    text: INSTRUCTIONS,
    scope: "this_issue",
    set_by_user_id: KEVIN,
    set_by_name: "Kevin Osei",
    set_at: "2026-09-14T14:24:00Z",
  },
  fix_run: {
    agent_run_id: id(259),
    label: "Adding 1,550 to Form 1040 line 2a",
    status: "running",
    proposal_id: null,
  },
};
export const NOTE =
  "The plan is a QACA with 6% default deferral. Four eligible participants had no 2025 deferrals and no opt-out election on file. If none exists, this is a missed-deferral failure to correct under EPCRS (start the correct deferrals, notify the participants and fund any missed QACA safe-harbor match; a QNEC for the missed deferrals may be 0% under the auto-enrollment safe harbor if corrected in time); evaluate as a control exception in AUD-15.";
export const WORDING =
  "Four employees were automatically enrolled in the 401(k) but had no contributions in 2025. Please upload their signed opt-out forms, or let us know if none exist. The list is attached.";
export const optOuts: IssueCreateIn = {
  record_type: "workpaper",
  record_id: id(260),
  kind: "waiting_on_client",
  priority: "high",
  title: "Opt-out elections missing for 4 auto-enrolled participants who are not deferring",
  internal_note: NOTE,
  client_wording: WORDING,
  client_contact_id: DANA,
  assignee_user_id: ANA,
  assignee_agent: false,
  links: [
    { kind: "cell_range", target_type: "workpaper", target_id: id(260), anchor: "F12:F15" },
    { kind: "file", target_type: "document", target_id: id(261), anchor: null },
  ],
  blocks: [],
};
export const SHL15 = {
  a: issue18a,
  a_prime: fixing,
  a_double_prime: {
    ...fixing,
    fix_run: {
      agent_run_id: id(259),
      label: "Adding 1,550 to Form 1040 line 2a",
      status: "succeeded",
      proposal_id: k1.ref,
    },
  },
  b: {
    ...issue18a,
    issue: {
      ...issueRow,
      id: id(262),
      kind: "waiting_on_client",
      assignee_agent: false,
      assignee_user_id: ANA,
      assignee_name: "Ana Cruz",
      instructions_required: false,
    },
    record_label: "EBP-04 Participant data · Northwind Robotics 401(k) Plan",
    title: optOuts.title,
    internal_note: NOTE,
    client_wording: WORDING,
    client_contact: { contact_id: DANA, name: "Dana Kowalski", role_label: "Plan administrator" },
    suggestion: null,
    explanations: [],
    request_item_id: id(263),
  },
  d: issue18a,
} satisfies Record<string, IssueDetailOut>;

// --- The frames the artboards draw beyond the reads above (requests and write answers) ----------

/** SHL-12 a: the Trial Balance ladder before Hannah signs; a′: after, "✓ MD ✓ HL". */
export const LADDER_A: SignOffLadderOut = {
  target,
  levels: ladder(null),
  allowed_actions: ["sign_off.create"],
};
export const LADDER_A_PRIME: SignOffLadderOut = { ...LADDER_A, levels: ladder(hannahL2) };
/** SHL-12 a′: sign with the full digest seen; the 201 is Hannah's L2 row. */
export const SIGN_A_PRIME: SignOffIn = {
  target_type: "workpaper",
  target_id: TB,
  level: "L2_reviewer",
  kind: "ladder",
  seen_hash: HASH,
  statement_version: STATEMENT,
};
/** SHL-12 b: the first open note in full (its body is Restricted and only in the detail). */
export const NOTE_DETAIL: ReviewNoteOut = {
  note: notes.items[0] ?? (undefined as never),
  body: "Explain why participant loans are not a significant risk",
  events: [],
};
/** SHL-12 e (Thu Sep 24, 2:15 PM): a later change makes Hannah's L2 stale; only Re-sign. */
export const STALE_LADDER: SignOffLadderOut = {
  target: { ...target, content_hash: "sha256:" + "b".repeat(64) },
  levels: ladder({ ...hannahL2, stale: true }),
  allowed_actions: ["sign_off.create"],
};
const BULK_REASONS = ["incomplete", "open_review_notes", "segregation"] as const;
/** SHL-12 f (Thu Sep 24): six selected, three signed and three excluded with their reasons. */
export const BULK_F: BulkSignOffOut = {
  results: [0, 1, 2, 3, 4, 5].map((n) => ({
    target_type: "workpaper",
    target_id: id(60 + n),
    ok: n < 3,
    sign_off_id: n < 3 ? id(70 + n) : null,
    detail: n < 3 ? null : (BULK_REASONS[n - 3] ?? null),
  })),
  signed: 3,
  excluded: 3,
};

/** SHL-11 a–c: Margaret decides 1.5% with a sealed rationale. */
export const DECIDE_A: DecideIn = {
  option_key: "pct_1_5",
  factors: ["late_deposits", "users"],
  rationale: decision.rationale,
  seen_version: 1,
};
/** SHL-11 e: the inline dock card reads the list row. */
export const CARD_PAGE_E: ListPageDecisionCardItemOut = {
  items: [SHL11.a.card],
  total: 1,
  counts: { awaiting_role: 1 },
};
/** SHL-11 f: a rationale-less decide still parses; the service answers 422 rationale_required. */
export const DECIDE_F: DecideIn = { option_key: "significant_deficiency", seen_version: 1 };

/** SHL-10 b: approve with edits needs a citation note; one suggestion adopts line 2a. */
export const APPROVE_EDITS_B: ApproveProposalIn = {
  seen_version: 1,
  edits: [{ n: 3, after: "307900", citation_note: "K-1 box 2" }],
};
export const ADOPTED_B: SuggestionOut = {
  id: id(130),
  target_type: "tax_return",
  target_id: id(131),
  field_key: "f1040.l2a",
  proposed_value: "1550",
  rationale: null,
  citation_ids: [id(132)],
  status: "adopted",
  version: 1,
  agent_run_id: id(31),
  decision: "adopted",
  decided_by_user_id: SAMUEL,
  decided_at: "2026-09-14T14:24:00Z",
  allowed_actions: [],
};
/** SHL-10 d: AJE-05 routes to Priya Raman. */
export const ROUTE_D: RouteProposalIn = { seen_version: 1, approver_user_id: PRIYA };
/** SHL-10 f: reject with Needs client input. */
export const REJECT_F: RejectProposalIn = { seen_version: 1, reason_code: "needs_client_input" };

/** SHL-09 a: Samuel ticks the current value's hash. */
export const TICK_A: FieldTickIn = { level: "L2_reviewer", seen_hash: FIELD_V2 };
/** SHL-09 c: a person's edit carries its citation note. */
export const EDIT_C: FieldEditIn = {
  value: { t: "decimal", v: "2310" },
  value_kind: "exact",
  citation_note: "Per client email Sep 9",
  seen_seq: 2,
};
/** SHL-09 e: Add reference, verified through C4. */
export const REFERENCE_E: FieldReferenceIn = { document_id: id(204), page: 4, seen_seq: 1 };

/** SHL-16 a, b: approve on the hash Samuel saw. */
export const APPROVE_A: CheckpointApproveIn = { seen_hash: CP6_HASH };
const three = cards.find((c) => c.seq === 3);
/** SHL-16 c: restoring Checkpoint 3 creates Checkpoint 7 as a copy (nothing deleted). */
export const SEVEN: CheckpointItemOut = checkpoint(7, {
  cause: "restore",
  status: "saved",
  restored_from_id: three?.id ?? null,
});
export const RESTORE_C: CheckpointRestoreIn = { seen_hash: three?.content_hash ?? "" };
/** SHL-16 c: an older checkpoint compared with Current. */
export const COMPARE_C: CheckpointDetailOut = { ...cp6Detail, compare: "current" };
/** SHL-16 c (P-04-T43): Checkpoint 3 selected, its steps (spec state 3) and its diff vs Current. */
export const DETAIL_C3: CheckpointDetailOut | undefined =
  three === undefined
    ? undefined
    : {
        checkpoint: three,
        compare: "current",
        compared_to_id: cards.find((c) => c.current)?.id ?? null,
        steps: [
          { kind: "created_worksheet", title: "Created worksheet", detail: "Federal › Income › Wages (W-2)", at: "2026-09-03T16:03:00Z" },
          { kind: "created_worksheet", title: "Created worksheet", detail: "Sch E, p 2 › Ridgeline", at: "2026-09-03T16:04:00Z" },
          { kind: "self_check", title: "Self-check: 0 errors, 2 warnings", detail: null, at: "2026-09-03T16:05:00Z" },
        ],
        diff: cp6Detail.diff,
        totals: cp6Detail.totals,
      };
/** SHL-16 d: rename and star change only name and starred. */
export const RENAME_D: CheckpointRenameIn = { name: "Before K-1 treatment", starred: true };
/** SHL-16 e: rejected with a reason. */
export const REJECT_E: CheckpointRejectIn = { seen_hash: CP6_HASH, reason: "Wait for final K-1" };
/** SHL-16 f: an empty return offers Save checkpoint…. */
export const SAVE_F: CheckpointCreateIn = {
  target_type: "tax_return",
  target_id: id(240),
  name: null,
};

const issuePage = (n: number): ListPageIssueItemOut => ({
  items: Array.from({ length: n }, () => issueRow),
  next_cursor: null,
  total: n,
  total_capped: false,
  counts: { open: n },
  facets: {},
});
/** SHL-15: Feld's four open issues; c's field flag makes five. */
export const ISSUES_FOUR: ListPageIssueItemOut = issuePage(4);
export const ISSUES_FIVE: ListPageIssueItemOut = issuePage(5);
/** SHL-15 a: Use suggestion plus one constraint; runs always propose. */
export const FIX_A: FixInstructionsIn = {
  seen_version: 1,
  text: INSTRUCTIONS,
  scope: "this_issue",
};
export const FIX_ACCEPTED_A: FixInstructionsAcceptedOut = {
  issue_id: issueRow.id,
  agent_run_id: id(259),
  status: "in_progress",
};
/** SHL-15 b: only the client wording goes to the client. */
export const SEND_B: IssueSendToClientIn = {
  seen_version: 1,
  client_wording: WORDING,
  contact_id: DANA,
  due_on: null,
};
/** SHL-15 c: a field flag raises a Review point. */
export const FLAG_C: IssueCreateIn = {
  record_type: "tax_return",
  record_id: FELD_1040,
  kind: "review_point",
  title: "Confirm Ridgeline K-1 amounts against the final K-1 before export",
  assignee_user_id: KEVIN,
  assignee_agent: false,
  links: [
    { kind: "form_field", target_type: "tax_return", target_id: FELD_1040, anchor: "f1040.l2b" },
  ],
};
/** SHL-15 d: Explain… is a run; its result is read-only agent text with three citations. */
export const EXPLAIN_ACCEPTED_D: ExplainAcceptedOut = {
  issue_id: issueRow.id,
  agent_run_id: id(255),
};
/** SHL-15 e: bulk instructions for the 2 Missing information issues. */
export const BULK_E: BulkFixInstructionsIn = {
  issues: [
    { issue_id: id(209), seen_version: 1 },
    { issue_id: issueRow.id, seen_version: 1 },
  ],
  text: "Obtain the confirmations",
};
export const BULK_OUT_E: BulkFixInstructionsOut = {
  results: BULK_E.issues.map((i) => ({
    issue_id: i.issue_id,
    ok: true,
    agent_run_id: id(270),
    detail: null,
  })),
  accepted: 2,
  excluded: 0,
};

// --- The 44 artboards -----------------------------------------------------------------------

/** E0 and the snapshots the artboards are drawn at (the handoff READMEs' "Rendered" column). */
export const REVIEW_CLOCKS = {
  e0: "2026-09-14T09:24:00-05:00",
  signOff: "2026-09-14T09:41:00-05:00", // SHL-12
  decision: "2026-09-14T10:01:00-05:00", // SHL-11
  sep24: "2026-09-24T14:15:00-05:00", // SHL-12 e, f
  oct1: "2026-10-01T09:24:00-05:00", // SHL-10
  oct6: "2026-10-06T09:24:00-05:00", // SHL-11 d
} as const;

export type ReviewScreen = "SHL-09" | "SHL-10" | "SHL-11" | "SHL-12" | "SHL-15" | "SHL-16";

/** One answer an artboard's route gives: `route` as fixture mode keys it, the OpenAPI schema its
 * body is, and the status. `params` narrow a route to one record. */
export interface ReviewFrame {
  route: string;
  schema: string;
  status: number;
  body: unknown;
  params?: Readonly<Record<string, string>>;
}

/** A request body an artboard sends, typed with the generated client. */
export interface ReviewRequest {
  route: string;
  schema: string;
  body: unknown;
}

export interface ReviewArtboard {
  screen: ReviewScreen;
  /** The handoff's artboard letter; a prime is `ap`, `app`, `ep` as its screenshot is named. */
  state: string;
  title: string;
  /** The persona slug it is seen as; null where the artboard names no viewer. */
  viewer: string | null;
  clock: string;
  frames: readonly ReviewFrame[];
  requests: readonly ReviewRequest[];
}

const get = (
  route: string,
  schema: string,
  body: unknown,
  params?: Record<string, string>,
): ReviewFrame =>
  params === undefined
    ? { route: `GET ${route}`, schema, status: 200, body }
    : { route: `GET ${route}`, schema, status: 200, body, params };
const post = (route: string, schema: string, body: unknown, status = 200): ReviewFrame => ({
  route: `POST ${route}`,
  schema,
  status,
  body,
});
const send = (route: string, schema: string, body: unknown): ReviewRequest => ({
  route,
  schema,
  body,
});

const FIELD = "/v1/fields/{target_type}/{target_id}/{field_key}";
const PROVENANCE_OF = (frame: FieldProvenanceOut) => get(PROVENANCE, "FieldProvenanceOut", frame);
const PROPOSAL = (frame: ProposalOut) =>
  get("/v1/proposals/{ref}", "AgentProposalOut", frame, { ref: frame.ref });
const CARD = (frame: DecisionCardOut) =>
  get("/v1/decision-cards/{card_id}", "DecisionCardOut", frame, { card_id: frame.card.id });
const ELIGIBILITY = (frame: SignOffEligibilityOut) =>
  get("/v1/sign-offs/eligibility", "SignOffEligibilityOut", frame);
const ISSUE = (frame: IssueDetailOut) =>
  get("/v1/issues/{issue_id}", "IssueDetailOut", frame, { issue_id: frame.issue.id });
const HISTORY = (frame: CheckpointHistoryOut) =>
  get("/v1/checkpoints", "CheckpointHistoryOut", frame);
const DETAIL = (frame: CheckpointDetailOut) =>
  get("/v1/checkpoints/{checkpoint_id}", "CheckpointDetailOut", frame, {
    checkpoint_id: frame.checkpoint.id,
  });
const seqOf = (frame: CheckpointHistoryOut, seq: number): CheckpointItemOut =>
  frame.items.find((c) => c.seq === seq) ?? (undefined as never);

const board = (
  screen: ReviewScreen,
  state: string,
  title: string,
  viewer: string | null,
  clock: string,
  frames: readonly ReviewFrame[],
  requests: readonly ReviewRequest[] = [],
): ReviewArtboard => ({ screen, state, title, viewer, clock, frames, requests });

const { e0, signOff, decision: decisionClock, sep24, oct1, oct6 } = REVIEW_CLOCKS;

export const REVIEW_ARTBOARDS: readonly ReviewArtboard[] = [
  // SHL-09 Field provenance popover (Samuel Ito; c Kevin Osei).
  board(
    "SHL-09",
    "a",
    "Agent-set, flagged, stale sign-off",
    "samuel-ito",
    e0,
    [PROVENANCE_OF(SHL09.a)],
    [send(`POST ${FIELD}/ticks`, "FieldTickIn", TICK_A)],
  ),
  board("SHL-09", "b", "Estimate", "samuel-ito", e0, [PROVENANCE_OF(SHL09.b)]),
  board(
    "SHL-09",
    "c",
    "Human-edited",
    "kevin-osei",
    e0,
    [PROVENANCE_OF(SHL09.c)],
    [send(`PUT ${FIELD}/value`, "FieldEditIn", EDIT_C)],
  ),
  board("SHL-09", "d", "Signed off", "samuel-ito", e0, [PROVENANCE_OF(SHL09.d)]),
  board(
    "SHL-09",
    "e",
    "Uncited agent value",
    "samuel-ito",
    e0,
    [PROVENANCE_OF(SHL09.e)],
    [send(`POST ${FIELD}/references`, "FieldReferenceIn", REFERENCE_E)],
  ),
  board("SHL-09", "f", "Collapsed Previous", "samuel-ito", e0, [PROVENANCE_OF(SHL09.f)]),
  // SHL-10 Approve agent output (Thu Oct 1; the artboards name no viewer).
  board("SHL-10", "a", "Feld K-1 treatment", null, oct1, [PROPOSAL(SHL10.a)]),
  board(
    "SHL-10",
    "b",
    "Single source change",
    null,
    oct1,
    [
      PROPOSAL(SHL10.a),
      post("/v1/suggestions/{suggestion_id}/adopt", "AgentSuggestionOut", ADOPTED_B),
    ],
    [send("POST /v1/proposals/{proposal_id}/approve", "ApproveProposalIn", APPROVE_EDITS_B)],
  ),
  board("SHL-10", "c", "Uncited value", null, oct1, [PROPOSAL(SHL10.c)]),
  board(
    "SHL-10",
    "d",
    "Over threshold",
    null,
    oct1,
    [PROPOSAL(SHL10.d)],
    [send("POST /v1/proposals/{proposal_id}/route", "RouteProposalIn", ROUTE_D)],
  ),
  board("SHL-10", "e", "Within-threshold batch", null, oct1, [PROPOSAL(SHL10.e)]),
  board("SHL-10", "ep", "Batch approved", null, oct1, [PROPOSAL(SHL10.e_prime)]),
  board(
    "SHL-10",
    "f",
    "Reject",
    null,
    oct1,
    [PROPOSAL(SHL10.f), post("/v1/proposals/{proposal_id}/reject", "AgentProposalOut", SHL10.f)],
    [send("POST /v1/proposals/{proposal_id}/reject", "RejectProposalIn", REJECT_F)],
  ),
  board("SHL-10", "g", "Part of a set", null, oct1, [PROPOSAL(SHL10.g)]),
  // SHL-11 Decision card (10:01 AM; d at the Oct 6 reassessment).
  board(
    "SHL-11",
    "a",
    "Deciding",
    "margaret-okonkwo",
    decisionClock,
    [CARD(SHL11.a)],
    [send("POST /v1/decision-cards/{card_id}/decide", "CardDecideIn", DECIDE_A)],
  ),
  board("SHL-11", "b", "Awaiting role", "hannah-leclerc", decisionClock, [CARD(SHL11.b)]),
  board("SHL-11", "c", "Decided", "margaret-okonkwo", decisionClock, [
    CARD(SHL11.c),
    post("/v1/decision-cards/{card_id}/decide", "DecisionCardOut", SHL11.c),
  ]),
  board("SHL-11", "d", "History · reassessed", "margaret-okonkwo", oct6, [CARD(SHL11.d)]),
  board("SHL-11", "e", "Inline dock variant", "margaret-okonkwo", decisionClock, [
    get("/v1/decision-cards", "ListPage_DecisionCardItemOut_", CARD_PAGE_E),
    CARD(SHL11.a),
  ]),
  board(
    "SHL-11",
    "f",
    "Deficiency severity",
    "margaret-okonkwo",
    decisionClock,
    [CARD(SHL11.f)],
    [send("POST /v1/decision-cards/{card_id}/decide", "CardDecideIn", DECIDE_F)],
  ),
  board("SHL-11", "g", "§754 recommendation", "margaret-okonkwo", decisionClock, [CARD(SHL11.g)]),
  board("SHL-11", "h", "Superseded", "margaret-okonkwo", decisionClock, [CARD(SHL11.h)]),
  // SHL-12 Sign-off modal (9:41 AM; e and f on Thu Sep 24).
  board("SHL-12", "a", "Allowed", "hannah-leclerc", signOff, [
    ELIGIBILITY(SHL12.a),
    get("/v1/sign-offs", "SignOffLadderOut", LADDER_A),
  ]),
  board(
    "SHL-12",
    "ap",
    "Signed",
    "hannah-leclerc",
    signOff,
    [
      get("/v1/sign-offs", "SignOffLadderOut", LADDER_A_PRIME),
      post("/v1/sign-offs", "SignOffOut", hannahL2, 201),
    ],
    [send("POST /v1/sign-offs", "SignOffIn", SIGN_A_PRIME)],
  ),
  board("SHL-12", "b", "Blocked · open notes", "hannah-leclerc", signOff, [
    ELIGIBILITY(SHL12.b),
    get("/v1/review-notes", "ListPage_ReviewNoteItemOut_", notes),
    get("/v1/review-notes/{note_id}", "ReviewNoteDetailOut", NOTE_DETAIL, {
      note_id: NOTE_DETAIL.note.id,
    }),
  ]),
  board("SHL-12", "c", "Blocked · same preparer", "marcus-delaney", signOff, [
    ELIGIBILITY(SHL12.c),
  ]),
  board("SHL-12", "d", "Blocked · independence", "hannah-leclerc", signOff, [
    ELIGIBILITY(SHL12.d),
  ]),
  board("SHL-12", "e", "Stale after change", "hannah-leclerc", sep24, [
    get("/v1/sign-offs", "SignOffLadderOut", STALE_LADDER),
  ]),
  board("SHL-12", "f", "Bulk", "hannah-leclerc", sep24, [
    post("/v1/sign-offs:bulk", "BulkSignOffOut", BULK_F),
  ]),
  board("SHL-12", "g", "EQR viewer", "thomas-whitcombe", signOff, [ELIGIBILITY(SHL12.g)]),
  board("SHL-12", "h", "Tax · final approval", "daniel-reyes", signOff, [ELIGIBILITY(SHL12.h)]),
  // SHL-15 Issue composer and fix instructions (E0).
  board(
    "SHL-15",
    "a",
    "Set fix instructions",
    "kevin-osei",
    e0,
    [
      ISSUE(SHL15.a),
      get("/v1/issues", "ListPage_IssueItemOut_", ISSUES_FOUR),
      post(
        "/v1/issues/{issue_id}/fix-instructions",
        "FixInstructionsAcceptedOut",
        FIX_ACCEPTED_A,
        202,
      ),
    ],
    [send("POST /v1/issues/{issue_id}/fix-instructions", "FixInstructionsIn", FIX_A)],
  ),
  board("SHL-15", "ap", "Agent fixing", null, e0, [ISSUE(SHL15.a_prime)]),
  board("SHL-15", "app", "Proposed value", null, e0, [ISSUE(SHL15.a_double_prime)]),
  board(
    "SHL-15",
    "b",
    "New issue · audit",
    "ana-cruz",
    e0,
    [ISSUE(SHL15.b)],
    [
      send("POST /v1/issues", "IssueCreateIn", optOuts),
      send("POST /v1/issues/{issue_id}/send-to-client", "IssueSendToClientIn", SEND_B),
    ],
  ),
  board(
    "SHL-15",
    "c",
    "New issue · field flag",
    "samuel-ito",
    e0,
    [get("/v1/issues", "ListPage_IssueItemOut_", ISSUES_FIVE)],
    [send("POST /v1/issues", "IssueCreateIn", FLAG_C)],
  ),
  board("SHL-15", "d", "Explain… result", null, e0, [
    ISSUE(SHL15.d),
    post("/v1/issues/{issue_id}/explanations", "ExplainAcceptedOut", EXPLAIN_ACCEPTED_D, 202),
  ]),
  board(
    "SHL-15",
    "e",
    "Bulk instructions",
    null,
    e0,
    [
      get("/v1/issues", "ListPage_IssueItemOut_", ISSUES_FOUR),
      post("/v1/issues/fix-instructions:bulk", "BulkFixInstructionsOut", BULK_OUT_E, 202),
    ],
    [send("POST /v1/issues/fix-instructions:bulk", "BulkFixInstructionsIn", BULK_E)],
  ),
  // SHL-16 Checkpoint diff drawer (Samuel Ito, E0).
  board(
    "SHL-16",
    "a",
    "Agent proposed",
    "samuel-ito",
    e0,
    [HISTORY(SHL16.a), DETAIL(cp6Detail)],
    [send("POST /v1/checkpoints/{checkpoint_id}/approve", "CheckpointApproveIn", APPROVE_A)],
  ),
  board("SHL-16", "b", "Approved", "samuel-ito", e0, [
    HISTORY(SHL16.b),
    post("/v1/checkpoints/{checkpoint_id}/approve", "CheckpointItemOut", seqOf(SHL16.b, 6)),
  ]),
  board(
    "SHL-16",
    "c",
    "Older checkpoint",
    "samuel-ito",
    e0,
    [
      HISTORY(SHL16.a),
      DETAIL(COMPARE_C),
      ...(DETAIL_C3 === undefined ? [] : [DETAIL(DETAIL_C3)]),
      post("/v1/checkpoints/{checkpoint_id}/restore", "CheckpointItemOut", SEVEN, 201),
    ],
    [send("POST /v1/checkpoints/{checkpoint_id}/restore", "CheckpointRestoreIn", RESTORE_C)],
  ),
  board(
    "SHL-16",
    "d",
    "Rename · star",
    "samuel-ito",
    e0,
    [
      HISTORY(SHL16.d),
      {
        route: "PATCH /v1/checkpoints/{checkpoint_id}",
        schema: "CheckpointItemOut",
        status: 200,
        body: seqOf(SHL16.d, 5),
      },
    ],
    [send("PATCH /v1/checkpoints/{checkpoint_id}", "CheckpointRenameIn", RENAME_D)],
  ),
  board(
    "SHL-16",
    "e",
    "Rejected",
    "samuel-ito",
    e0,
    [
      HISTORY(SHL16.e),
      post("/v1/checkpoints/{checkpoint_id}/reject", "CheckpointItemOut", SHL16.e.items[0]),
    ],
    [send("POST /v1/checkpoints/{checkpoint_id}/reject", "CheckpointRejectIn", REJECT_E)],
  ),
  board(
    "SHL-16",
    "f",
    "Empty",
    "samuel-ito",
    e0,
    [HISTORY(SHL16.f)],
    [send("POST /v1/checkpoints", "CheckpointCreateIn", SAVE_F)],
  ),
];
