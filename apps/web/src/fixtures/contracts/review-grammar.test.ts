// P-04-T09: C3 v1 consumer fixture assertions for stubs 1 and 2. One typed frame per SHL-10 a–g,
// SHL-11 a–h and SHL-12 a–h artboard, built against the generated client's types (a removed or
// renamed field fails tsc) and checked against the OpenAPI document at run time (a field the schema
// no longer has fails here). Figures foot with bigint decimals, never floats. Copy and figures come
// from docs/contracts/review-grammar.md §8 and the P-04 epic's artboard rows; ids are placeholders.
// The UI tasks (P-04 S16–S24) build their scenarios from these shapes. P-04-T12 adds stub 3: one
// frame per SHL-09 a–f, SHL-15 a–e and SHL-16 a–f artboard, an additive extension of C3 v1.
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
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { validateResponse, validateSchema } from "../schema-check";

// --- Helpers ---------------------------------------------------------------------------------

const here = dirname(fileURLToPath(import.meta.url));
const SCHEMAS = (
  JSON.parse(
    readFileSync(
      join(here, "..", "..", "..", "..", "..", "packages", "api-client", "openapi.json"),
      "utf8",
    ),
  ) as {
    components: { schemas: Record<string, { properties?: Record<string, { cls?: string }> }> };
  }
).components.schemas;

/** A field's classification tag in the OpenAPI document (ADR-031). */
function cls(schema: string, field: string): string | undefined {
  return SCHEMAS[schema]?.properties?.[field]?.cls;
}

/** A stable placeholder uuid (v4 shape) for frame `n`. */
const id = (n: number): string => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const HASH = "sha256:9f4c" + "0".repeat(56) + "e21a"; // SHL-12 shows sha256:9f4c…e21a

const SCALE = 1000n;
/** A doc figure ("$16,812,400", "0.015", "14,900.00") as an exact integer of thousandths. */
function milli(text: string): bigint {
  const [whole = "0", frac = ""] = text.replace(/[$,]/g, "").split(".");
  return BigInt(whole) * SCALE + BigInt((frac + "000").slice(0, 3));
}
const times = (a: bigint, b: bigint): bigint => (a * b) / SCALE;
/** Nearest multiple of `inc`, halves up (the scenario golden's materiality rounding). */
const roundTo = (x: bigint, inc: bigint): bigint => ((x + inc / 2n) / inc) * inc;
const dollars = (x: bigint): string => `$${(x / SCALE).toLocaleString("en-US")}`;
const sum = (xs: bigint[]): bigint => xs.reduce((a, b) => a + b, 0n);

// --- SHL-12 a–h: sign-off modal (stub 1) -------------------------------------------------------

const TB = id(1);
const MARCUS = id(11);
const HANNAH = id(12);
const MARGARET = id(13);
const THOMAS = id(14);
const STATEMENT = "bh-review-v1";

const target = {
  target_type: "workpaper",
  target_id: TB,
  label: "Trial Balance",
  context_label: "Northwind Robotics 401(k) Plan · PY2025",
  version_no: 1,
  content_hash: HASH,
  cell_count: 14,
  citation_count: 3,
};
const marcusL1: SignOffOut = {
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
const hannahL2: SignOffOut = {
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
const ladder = (l2: SignOffOut | null): LadderLevelOut[] => [
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
const passing: EligibilityCheckOut[] = [
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
const eligibility = (over: Partial<SignOffEligibilityOut>): SignOffEligibilityOut => ({
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
const withCheck = (check: EligibilityCheckOut): EligibilityCheckOut[] =>
  passing.map((c) => (c.code === check.code ? check : c));

const SHL12 = {
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

const notes: ListPageReviewNoteItemOut = {
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

describe("SHL-12 a–h (stub 1)", () => {
  it("every eligibility frame is the GET /v1/sign-offs/eligibility shape", () => {
    for (const [key, frame] of Object.entries(SHL12)) {
      expect(validateResponse("GET", "/v1/sign-offs/eligibility", frame), key).toEqual([]);
    }
  });

  it("a: every value cited, 14 of 14 cells; the L1 is agent run #4127 adopted by MD", () => {
    const cited = SHL12.a.checks.find((c) => c.code === "all_cited");
    expect(cited?.facts).toEqual({ cited: 14, cells: 14 });
    expect(cited?.facts.cited).toBe(SHL12.a.target.cell_count);
    expect(SHL12.a.ladder[0]?.latest?.adopted_run_number).toBe(4127);
    expect(SHL12.a.checks.find((c) => c.code === "gate_g4")?.result).toBe("warn");
  });

  it("a′: sign with the full digest seen; the 201 is one row; the header reads ✓ MD ✓ HL", () => {
    const body: SignOffIn = {
      target_type: "workpaper",
      target_id: TB,
      level: "L2_reviewer",
      kind: "ladder",
      seen_hash: HASH,
      statement_version: STATEMENT,
    };
    expect(validateSchema("SignOffIn", body)).toEqual([]);
    expect(body.seen_hash).toMatch(/^sha256:[0-9a-f]{64}$/);
    expect(validateSchema("SignOffOut", hannahL2)).toEqual([]);
    expect([marcusL1, hannahL2].map((s) => `✓ ${s.initials}`).join(" ")).toBe("✓ MD ✓ HL");
  });

  it("b: two open notes on RA!C14 and RA!C22; list rows carry no sealed body", () => {
    expect(validateResponse("GET", "/v1/review-notes", notes)).toEqual([]);
    expect(notes.items.map((n) => n.anchor?.ref)).toEqual(["RA!C14", "RA!C22"]);
    expect(notes.counts).toEqual({ open: notes.total });
    expect(notes.items.every((n) => !("body" in n))).toBe(true);
    const first = notes.items[0];
    if (first === undefined) throw new Error("no note");
    const detail: ReviewNoteOut = {
      note: first,
      body: "Explain why participant loans are not a significant risk",
      events: [],
    };
    expect(validateResponse("GET", "/v1/review-notes/{note_id}", detail)).toEqual([]);
    expect(cls("ReviewNoteDetailOut", "body")).toBe("restricted");
    expect(cls("ReviewNoteEventOut", "body")).toBe("restricted");
  });

  it("c, d: the same preparer and a missing independence confirmation block", () => {
    expect(SHL12.c.checks.find((c) => c.code === "segregation")?.result).toBe("fail");
    expect(SHL12.d.checks.find((c) => c.code === "independence")?.result).toBe("fail");
  });

  it("e: a later change makes the L2 stale; staleness is computed, the ladder only re-signs", () => {
    const frame: SignOffLadderOut = {
      target: { ...target, content_hash: "sha256:" + "b".repeat(64) },
      levels: ladder({ ...hannahL2, stale: true }),
      allowed_actions: ["sign_off.create"],
    };
    expect(validateResponse("GET", "/v1/sign-offs", frame)).toEqual([]);
    expect(frame.levels[1]?.latest?.stale).toBe(true);
    expect(sum([milli("16,812,400"), milli("48,600")])).toBe(milli("16,861,000"));
  });

  it("f: six selected, three signed and three excluded with their reasons", () => {
    const reasons = ["incomplete", "open_review_notes", "segregation"] as const;
    const frame: BulkSignOffOut = {
      results: [0, 1, 2, 3, 4, 5].map((n) => ({
        target_type: "workpaper",
        target_id: id(60 + n),
        ok: n < 3,
        sign_off_id: n < 3 ? id(70 + n) : null,
        detail: n < 3 ? null : (reasons[n - 3] ?? null),
      })),
      signed: 3,
      excluded: 3,
    };
    expect(validateResponse("POST", "/v1/sign-offs:bulk", frame)).toEqual([]);
    expect(frame.signed + frame.excluded).toBe(frame.results.length);
  });

  it("g: the EQR sees only L5; h: final approval waits on 11 open issues", () => {
    expect(SHL12.g.levels_allowed).toEqual(["L5_eqr"]);
    expect(SHL12.h.checks[0]?.facts.count).toBe(11);
    expect(SHL12.h.eligible).toBe(false);
  });
});

// --- SHL-11 a–h: decision card (stub 2) --------------------------------------------------------

const CARD_ID = id(41);
const proposedV1: DecisionCardVersionOut = {
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
const option = (rate: string, materiality: string, pm: string, ct: string) => ({
  rate,
  materiality,
  performance_materiality: pm,
  clearly_trivial: ct,
});
const materialityCard: DecisionCardOut = {
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
const decision: DecisionOut = {
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
const decidedV2: DecisionCardVersionOut = {
  ...proposedV1,
  version_no: 2,
  event: "decided",
  actor_kind: "human",
  actor_user_id: MARGARET,
  actor_initials: "MO",
  at: "2026-09-14T15:02:00Z",
};
const decided: DecisionCardOut = {
  ...materialityCard,
  card: { ...materialityCard.card, status: "decided", version_no: 2, allowed_actions: [] },
  decision,
  history: [proposedV1, decidedV2],
};
const reassessedV3: DecisionCardVersionOut = {
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

const SHL11 = {
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

describe("SHL-11 a–h (stub 2)", () => {
  it("every card frame is the GET /v1/decision-cards/{card_id} shape", () => {
    for (const [key, frame] of Object.entries(SHL11)) {
      expect(validateResponse("GET", "/v1/decision-cards/{card_id}", frame), key).toEqual([]);
    }
  });

  it("a: the options foot in code (168,100; 252,200 · PM 189,150 · CT 12,610)", () => {
    const amount = milli(SHL11.a.context.find((c) => c.key === "amount")?.value ?? "0");
    for (const o of SHL11.a.options) {
      const f = o.figures;
      const m = milli(f.materiality ?? "");
      expect(roundTo(times(milli(f.rate ?? ""), amount), milli("100")), o.key).toBe(m);
      expect(times(m, milli("0.75"))).toBe(milli(f.performance_materiality ?? ""));
      expect(times(m, milli("0.05"))).toBe(milli(f.clearly_trivial ?? ""));
      expect(o.label).toContain(dollars(m));
    }
    expect(SHL11.a.options.filter((o) => o.recommended).map((o) => o.key)).toEqual([
      SHL11.a.recommendation?.option_key,
    ]);
  });

  it("a–c: the reserved role decides with a sealed rationale; the card stamps v2", () => {
    const body: DecideIn = {
      option_key: "pct_1_5",
      factors: ["late_deposits", "users"],
      rationale: decision.rationale,
      seen_version: 1,
    };
    expect(validateSchema("CardDecideIn", body)).toEqual([]);
    expect(validateResponse("POST", "/v1/decision-cards/{card_id}/decide", SHL11.c)).toEqual([]);
    expect(cls("CardDecisionOut", "rationale")).toBe("restricted");
    expect(cls("DecisionCardOut", "decision")).toBe("restricted");
    const f = SHL11.c.options.find((o) => o.key === SHL11.c.decision?.option_key)?.figures ?? {};
    const [m, pm, ct] = ["materiality", "performance_materiality", "clearly_trivial"].map((k) =>
      dollars(milli(f[k] ?? "0")),
    );
    expect(
      `v${String(SHL11.c.card.version_no)}: 1.5% = ${m ?? ""} · PM ${pm ?? ""} · CT ${ct ?? ""}`,
    ).toBe("v2: 1.5% = $252,200 · PM $189,150 · CT $12,610");
  });

  it("b: outside the reserved role there is Notify and Request more analysis, no Decide", () => {
    expect(SHL11.b.card.allowed_actions).not.toContain("decision.decide");
    expect(SHL11.b.card.reserved_user_name).toBe("Margaret Okonkwo");
  });

  it("d: reassessed at final on $16,861,000: 252,900, a $700 difference, no change", () => {
    const v3 = SHL11.d.history[2];
    const benchmark = milli(v3?.figures.benchmark ?? "");
    expect(benchmark).toBe(sum([milli("16,812,400"), milli("48,600")]));
    const m = roundTo(times(milli("0.015"), benchmark), milli("100"));
    expect(m).toBe(milli(v3?.figures.materiality ?? ""));
    expect(m - milli("252,200")).toBe(milli(v3?.figures.difference ?? ""));
    expect(v3?.changed).toBe(false);
  });

  it("e: the inline dock card reads the list row", () => {
    const page: ListPageDecisionCardItemOut = {
      items: [SHL11.a.card],
      total: 1,
      counts: { awaiting_role: 1 },
    };
    expect(validateResponse("GET", "/v1/decision-cards", page)).toEqual([]);
  });

  it("f: a rationale-less decide still parses; the service answers 422 rationale_required", () => {
    const body: DecideIn = { option_key: "significant_deficiency", seen_version: 1 };
    expect(validateSchema("CardDecideIn", body)).toEqual([]);
  });

  it("g, h: §754 reserved to the signer; a superseded card points at its successor", () => {
    expect(SHL11.g.card.reserved_role).toBe("signer");
    expect(SHL11.h.card.superseded_by_version).toBe(3);
  });
});

// --- SHL-10 a–g: approve agent output (stub 2) -------------------------------------------------

const row = (
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
const k1: ProposalOut = {
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
const RAJ = id(16);
const PRIYA = id(17);
const SAMUEL = id(18);
const decidedBy = (by: string, name: string, at: string) => ({
  id: id(110),
  reason_code: null,
  note: null,
  decided_by_user_id: by,
  decided_by_name: name,
  decided_at: at,
  routed_to_user_id: null,
});
const AJE05 = ["12,600.00", "1,480.00", "820.00"]; // §8 SHL-10 d
const BATCH = "20,020.00"; // SHL-10 e: 4 entries, tie

const SHL10 = {
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

describe("SHL-10 a–g (stub 2)", () => {
  it("every proposal frame is the GET /v1/proposals/{ref} shape", () => {
    for (const [key, frame] of Object.entries(SHL10)) {
      expect(validateResponse("GET", "/v1/proposals/{ref}", frame), key).toEqual([]);
    }
  });

  it("a: the net change to Form 1040 total income ties at 0; values are sealed", () => {
    const lines = SHL10.a.rows.filter((r) => r.field_key.startsWith("sch_e."));
    const net = sum(lines.map((r) => milli(r.after ?? "0") - milli(r.before ?? "0")));
    expect(net).toBe(milli(SHL10.a.totals[0]?.value ?? ""));
    expect(net).toBe(0n);
    expect(SHL10.a.totals[0]?.ties).toBe(true);
    expect(SHL10.a.change_count).toBe(SHL10.a.rows.length);
    const schema = "AgentProposalOut";
    for (const field of ["reasoning", "rows", "totals", "policy", "decision"]) {
      expect(cls(schema, field), field).toBe("restricted");
    }
    expect([cls("ProposalRowOut", "before"), cls("ProposalRowOut", "after")]).toEqual([
      "restricted",
      "restricted",
    ]);
  });

  it("b: approve with edits needs a citation note; one suggestion adopts line 2a", () => {
    const body: ApproveProposalIn = {
      seen_version: 1,
      edits: [{ n: 3, after: "307900", citation_note: "K-1 box 2" }],
    };
    expect(validateSchema("ApproveProposalIn", body)).toEqual([]);
    const adopted: SuggestionOut = {
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
    expect(validateResponse("POST", "/v1/suggestions/{suggestion_id}/adopt", adopted)).toEqual([]);
    expect(milli(adopted.proposed_value)).toBe(milli("1,550"));
    expect(cls("AgentSuggestionOut", "proposed_value")).toBe("restricted");
  });

  it("c: the uncited row blocks approval and Ask follow-up leads", () => {
    const uncited = SHL10.c.rows.filter((r) => r.unsupported);
    expect(uncited.map((r) => [r.n, r.citation_ids.length])).toEqual([[5, 0]]);
    expect(SHL10.c.allowed_actions).not.toContain("proposal.approve");
  });

  it("d: AJE-05 14,900.00 is over $10,000 and routes to Priya Raman", () => {
    const total = sum(AJE05.map(milli));
    expect(total).toBe(milli(SHL10.d.totals[0]?.value ?? ""));
    expect(total > milli("10,000")).toBe(true);
    expect(SHL10.d.policy.routed_to_name).toBe("Priya Raman");
    const route: RouteProposalIn = { seen_version: 1, approver_user_id: PRIYA };
    expect(validateSchema("RouteProposalIn", route)).toEqual([]);
  });

  it("e, e′: the within-threshold batch is approved by a named person with a 10 s Undo", () => {
    expect(milli(SHL10.e_prime.totals[0]?.value ?? "")).toBe(milli(BATCH));
    const d = SHL10.e_prime.decision;
    expect(d.decided_by_name).toBe("Raj Malhotra");
    expect(Date.parse(d.undo_until) - Date.parse(d.decided_at)).toBe(10_000);
  });

  it("f: reject with Needs client input", () => {
    const body: RejectProposalIn = { seen_version: 1, reason_code: "needs_client_input" };
    expect(validateSchema("RejectProposalIn", body)).toEqual([]);
    expect(validateResponse("POST", "/v1/proposals/{proposal_id}/reject", SHL10.f)).toEqual([]);
    expect(SHL10.f.decision.reason_code).toBe("needs_client_input");
  });

  it("g: the set link row: 40 results, 1 exception", () => {
    expect(SHL10.g.set).toMatchObject({ results: 40, exceptions: 1 });
  });
});

// --- Stub 3 (P-04-T12): SHL-09 a–f, SHL-15 a–e, SHL-16 a–f ------------------------------------
// An additive extension of C3 v1: new frames on new types; the frames above are unchanged.

const FELD_1040 = id(200);
const KEVIN = id(280);
const ANA = id(281);
const DANA = id(282);
const digest = (head: string, tail: string): string => `sha256:${head}${"0".repeat(56)}${tail}`;
const FIELD_V2 = digest("7d20", "c4b1"); // SHL-09 a, the current value's hash
const FIELD_V1 = digest("e913", "5a02"); // Kevin's tick, on the imported value
const CP6_HASH = digest("5e1d", "a6f0");

// SHL-09 a–f: field provenance tray -------------------------------------------------------------

const importRef: FieldReferenceOut = {
  id: id(201),
  kind: "engine_import",
  label: "Imported Return — CCH Axcess 2025I:FeldJ:V3",
  detail: null,
  citation_id: null,
  document_id: null,
  page: null,
};
const updated: FieldVersionOut = {
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
const previous: FieldVersionOut = {
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
const koTick: FieldTickOut = {
  sign_off_id: id(207),
  level: "L1_preparer",
  signer_user_id: KEVIN,
  signer_name: "Kevin Osei",
  initials: "KO",
  signed_at: "2026-09-08T17:00:00Z",
  content_hash: FIELD_V1,
  stale: true,
};
const tray: FieldProvenanceOut = {
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
const SHL09 = {
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
const PROVENANCE = "/v1/fields/{target_type}/{target_id}/{field_key}/provenance";

describe("SHL-09 a–f (stub 3)", () => {
  it("every frame is the GET …/provenance shape", () => {
    for (const [key, frame] of Object.entries(SHL09)) {
      expect(validateResponse("GET", PROVENANCE, frame), key).toEqual([]);
    }
  });

  it("a: 2,190 → 2,310 from the corrected 1099-INT; Kevin's earlier tick is stale", () => {
    const [now, before] = SHL09.a.versions;
    expect([milli(before?.value.v ?? ""), milli(now?.value.v ?? "")]).toEqual([
      milli("2,190"),
      milli("2,310"),
    ]);
    const box1 = now?.references.find((r) => r.kind === "document")?.detail ?? "";
    expect(milli(box1.split(": ")[1] ?? "")).toBe(milli("2,310"));
    expect(SHL09.a.ticks[0]?.stale).toBe(SHL09.a.ticks[0]?.content_hash !== SHL09.a.content_hash);
    expect(`${String(SHL09.a.versions.length)} versions`).toBe("2 versions");
    for (const field of ["versions", "flags"]) {
      expect(cls("FieldProvenanceOut", field), field).toBe("restricted");
    }
    expect([cls("FieldValueOut", "v"), cls("FieldVersionOut", "citation")]).toEqual([
      "restricted",
      "restricted",
    ]);
    const tick: FieldTickIn = { level: "L2_reviewer", seen_hash: FIELD_V2 };
    expect(validateSchema("FieldTickIn", tick)).toEqual([]);
  });

  it("b: ≈ 48,000 is four vouchers of 12,000 and links its open issue", () => {
    const [estimate] = SHL09.b.versions;
    expect(estimate?.value_kind).toBe("estimate");
    expect(milli(estimate?.value.v ?? "")).toBe(4n * milli("12,000"));
    expect(estimate?.issue_id).not.toBeNull();
  });

  it("c: a person's edit carries its citation note", () => {
    const edit: FieldEditIn = {
      value: { t: "decimal", v: "2310" },
      value_kind: "exact",
      citation_note: "Per client email Sep 9",
      seen_seq: 2,
    };
    expect(validateSchema("FieldEditIn", edit)).toEqual([]);
    expect(validateSchema("FieldEditIn", { ...edit, citation_note: undefined })).not.toEqual([]);
    expect(SHL09.c.versions[0]?.actor_name).toBe("Kevin Osei");
  });

  it("d: both ticks are on the current hash", () => {
    expect(SHL09.d.ticks.map((t) => [t.initials, t.stale])).toEqual([
      ["KO", false],
      ["SI", false],
    ]);
  });

  it("e: an uncited agent value is Unsupported and cannot be ticked", () => {
    expect(SHL09.e.versions[0]?.unsupported).toBe(true);
    expect(SHL09.e.allowed_actions).not.toContain("field.sign_off");
    const add: FieldReferenceIn = { document_id: id(204), page: 4, seen_seq: 1 };
    expect(validateSchema("FieldReferenceIn", add)).toEqual([]);
  });
});

// SHL-16 a–f: checkpoint drawer -----------------------------------------------------------------

const checkpoint = (seq: number, over: Partial<CheckpointItemOut>): CheckpointItemOut => ({
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
const approval = (by: string, name: string, at: string): CheckpointDecisionOut => ({
  id: id(230),
  decision: "approved",
  reason: null,
  decided_by_user_id: by,
  decided_by_name: name,
  decided_at: at,
  proposal_decision_id: id(231),
});
const cp6 = checkpoint(6, {
  status: "proposed",
  summary: "K-1 treatment: Ridgeline",
  content_hash: CP6_HASH,
  proposal_id: k1.ref,
  agent_run_id: id(31),
  allowed_actions: ["checkpoint.approve", "checkpoint.reject", "checkpoint.rename"],
});
const cards: CheckpointItemOut[] = [
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
const history = (items: CheckpointItemOut[]): CheckpointHistoryOut => ({
  target_type: "tax_return",
  target_id: FELD_1040,
  filter: "all",
  items,
  current_checkpoint_id: items.find((c) => c.current)?.id ?? null,
  total: items.length,
  allowed_actions: ["checkpoint.create"],
});
const diffRow = (
  field_key: string,
  label: string,
  old: string | null,
  next: string | null,
  cause: string,
): CheckpointDiffRowOut => ({ field_key, label, old, new: next, cause, citation_ids: [id(33)] });
const cp6Detail: CheckpointDetailOut = {
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
const SHL16 = {
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

describe("SHL-16 a–f (stub 3)", () => {
  it("every history frame is the GET /v1/checkpoints shape", () => {
    for (const [key, frame] of Object.entries(SHL16)) {
      expect(validateResponse("GET", "/v1/checkpoints", frame), key).toEqual([]);
    }
    expect(validateResponse("GET", "/v1/checkpoints/{checkpoint_id}", cp6Detail)).toEqual([]);
  });

  it("a: Checkpoint 6 is the SHL-10 a proposal; the net change to total income ties at 0", () => {
    expect(cp6Detail.checkpoint.proposal_id).toBe(k1.ref);
    expect(cp6Detail.diff.map((r) => [r.field_key, r.old, r.new])).toEqual(
      k1.rows.map((r) => [r.field_key, r.before, r.after]),
    );
    const income = cp6Detail.diff.filter((r) => r.field_key.startsWith("sch_e."));
    const net = sum(income.map((r) => milli(r.new ?? "0") - milli(r.old ?? "0")));
    expect(net).toBe(milli(cp6Detail.totals[0]?.value ?? ""));
    expect(net).toBe(0n);
    expect(SHL16.a.items.filter((c) => c.current).map((c) => c.seq)).toEqual([5]);
    for (const field of ["summary", "decision"]) {
      expect(cls("CheckpointItemOut", field), field).toBe("restricted");
    }
    const approve: CheckpointApproveIn = { seen_hash: CP6_HASH };
    expect(validateSchema("CheckpointApproveIn", approve)).toEqual([]);
  });

  it("b: approving moves Current to Checkpoint 6", () => {
    const current = SHL16.b.items.filter((c) => c.current);
    expect(current.map((c) => c.seq)).toEqual([6]);
    expect(SHL16.b.current_checkpoint_id).toBe(cp6.id);
    expect(current[0]?.decision?.decided_by_name).toBe("Samuel Ito");
  });

  it("c: restoring Checkpoint 3 creates Checkpoint 7 as a copy", () => {
    const three = cards.find((c) => c.seq === 3);
    const seven = checkpoint(7, {
      cause: "restore",
      status: "saved",
      restored_from_id: three?.id ?? null,
    });
    expect(validateSchema("CheckpointItemOut", seven)).toEqual([]);
    const restore: CheckpointRestoreIn = { seen_hash: three?.content_hash ?? "" };
    expect(validateSchema("CheckpointRestoreIn", restore)).toEqual([]);
    expect(
      validateResponse("GET", "/v1/checkpoints/{checkpoint_id}", {
        ...cp6Detail,
        compare: "current",
      }),
    ).toEqual([]);
  });

  it("d: rename and star change only name and starred", () => {
    const rename: CheckpointRenameIn = { name: "Before K-1 treatment", starred: true };
    expect(validateSchema("CheckpointRenameIn", rename)).toEqual([]);
    expect(SHL16.d.items.find((c) => c.seq === 5)).toMatchObject(rename);
  });

  it("e: rejected with a reason", () => {
    const reject: CheckpointRejectIn = { seen_hash: CP6_HASH, reason: "Wait for final K-1" };
    expect(validateSchema("CheckpointRejectIn", reject)).toEqual([]);
    const d = SHL16.e.items[0]?.decision;
    expect(`${d?.decided_by_name ?? ""} · reason: ${d?.reason ?? ""}`).toBe(
      "Samuel Ito · reason: Wait for final K-1",
    );
  });

  it("f: an empty return offers Save checkpoint…", () => {
    expect([SHL16.f.total, SHL16.f.items.length, SHL16.f.current_checkpoint_id]).toEqual([
      0,
      0,
      null,
    ]);
    expect(SHL16.f.allowed_actions).toEqual(["checkpoint.create"]);
    const save: CheckpointCreateIn = { target_type: "tax_return", target_id: id(240), name: null };
    expect(validateSchema("CheckpointCreateIn", save)).toEqual([]);
  });
});

// SHL-15 a–e: issue composer and fix instructions -----------------------------------------------

const SUGGESTION =
  "Add 1,550 from the draft Ridgeline K-1 box 18A to Form 1040 line 2a. Check the K-1 statement for the state of the bonds and add any non-New York portion to IT-201 line 20. Mark both values as draft until Ridgeline releases final K-1s.";
const issueRow: IssueItemOut = {
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
const issue18a: IssueDetailOut = {
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
const INSTRUCTIONS = `${SUGGESTION}\nDon't change taxable interest on line 2b (6,910).`;
const fixing: IssueDetailOut = {
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
const NOTE =
  "The plan is a QACA with 6% default deferral. Four eligible participants had no 2025 deferrals and no opt-out election on file. If none exists, this is a missed-deferral failure to correct under EPCRS (start the correct deferrals, notify the participants and fund any missed QACA safe-harbor match; a QNEC for the missed deferrals may be 0% under the auto-enrollment safe harbor if corrected in time); evaluate as a control exception in AUD-15.";
const WORDING =
  "Four employees were automatically enrolled in the 401(k) but had no contributions in 2025. Please upload their signed opt-out forms, or let us know if none exist. The list is attached.";
const optOuts: IssueCreateIn = {
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
const SHL15 = {
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

describe("SHL-15 a–e (stub 3)", () => {
  it("every issue frame is the GET /v1/issues/{issue_id} shape", () => {
    for (const [key, frame] of Object.entries(SHL15)) {
      expect(validateResponse("GET", "/v1/issues/{issue_id}", frame), key).toEqual([]);
    }
    const page: ListPageIssueItemOut = {
      items: [issueRow],
      next_cursor: null,
      total: 4,
      total_capped: false,
      counts: { open: 4 },
      facets: {},
    };
    expect(validateResponse("GET", "/v1/issues", page)).toEqual([]);
  });

  it("a: Use suggestion plus one constraint; runs always propose", () => {
    const body: FixInstructionsIn = { seen_version: 1, text: INSTRUCTIONS, scope: "this_issue" };
    expect(validateSchema("FixInstructionsIn", body)).toEqual([]);
    expect(body.text.split("\n")[0]).toBe(SHL15.a.suggestion?.text);
    const accepted: FixInstructionsAcceptedOut = {
      issue_id: issueRow.id,
      agent_run_id: id(259),
      status: "in_progress",
    };
    expect(validateSchema("FixInstructionsAcceptedOut", accepted)).toEqual([]);
    for (const field of ["title", "suggestion", "fix_instructions", "fix_run", "explanations"]) {
      expect(cls("IssueDetailOut", field), field).toBe("restricted");
    }
    expect(cls("IssueItemOut", "title")).toBeUndefined();
  });

  it("a′, a″: the run adds the same 1,550 the line 2a suggestion adopts, then proposes", () => {
    const amount = /(\d{1,3}(?:,\d{3})+)/.exec(SHL15.a_prime.fix_run?.label ?? "")?.[1] ?? "";
    expect(milli(amount)).toBe(milli("1,550"));
    expect(SHL15.a_prime.issue.status).toBe("in_progress");
    expect(SHL15.a_double_prime.fix_run.proposal_id).toBe(k1.ref);
  });

  it("b: four cells, four participants; only the client wording goes to the client", () => {
    expect(validateSchema("IssueCreateIn", optOuts)).toEqual([]);
    const [, first, last] =
      /^[A-Z]+(\d+):[A-Z]+(\d+)$/.exec(optOuts.links?.[0]?.anchor ?? "") ?? [];
    expect(Number(last) - Number(first) + 1).toBe(4);
    for (const word of ["EPCRS", "QACA", "QNEC", "AUD-15"]) {
      expect(NOTE, word).toContain(word);
      expect(WORDING, word).not.toContain(word);
    }
    const send: IssueSendToClientIn = {
      seen_version: 1,
      client_wording: WORDING,
      contact_id: DANA,
      due_on: null,
    };
    expect(validateSchema("IssueSendToClientIn", send)).toEqual([]);
    expect(SHL15.b.request_item_id).not.toBeNull();
  });

  it("c: a field flag raises a Review point; Feld Issues 4 → 5", () => {
    const flag: IssueCreateIn = {
      record_type: "tax_return",
      record_id: FELD_1040,
      kind: "review_point",
      title: "Confirm Ridgeline K-1 amounts against the final K-1 before export",
      assignee_user_id: KEVIN,
      assignee_agent: false,
      links: [
        {
          kind: "form_field",
          target_type: "tax_return",
          target_id: FELD_1040,
          anchor: "f1040.l2b",
        },
      ],
    };
    expect(validateSchema("IssueCreateIn", flag)).toEqual([]);
    expect(validateSchema("IssueCreateIn", { ...flag, kind: "urgent" })).not.toEqual([]);
    const four: ListPageIssueItemOut = {
      items: [issueRow, issueRow, issueRow, issueRow],
      next_cursor: null,
      total: 4,
      total_capped: false,
      counts: { open: 4 },
      facets: {},
    };
    const five: ListPageIssueItemOut = {
      ...four,
      items: [...four.items, issueRow],
      total: 5,
      counts: { open: 5 },
    };
    expect([four.total, five.total]).toEqual([4, 5]);
    expect(validateResponse("GET", "/v1/issues", five)).toEqual([]);
  });

  it("d: Explain is read-only agent text with three citations", () => {
    const [explanation] = SHL15.d.explanations;
    expect(explanation?.citations.map((c) => c.label)).toEqual([
      "K-1 box 18A",
      "K-1 statement p. 3",
      "IT-201 instructions, line 20",
    ]);
    const accepted: ExplainAcceptedOut = { issue_id: issueRow.id, agent_run_id: id(255) };
    expect(validateSchema("ExplainAcceptedOut", accepted)).toEqual([]);
  });

  it("e: bulk instructions for the 2 Missing information issues", () => {
    const bulk: BulkFixInstructionsIn = {
      issues: [
        { issue_id: id(209), seen_version: 1 },
        { issue_id: issueRow.id, seen_version: 1 },
      ],
      text: "Obtain the confirmations",
    };
    expect(validateSchema("BulkFixInstructionsIn", bulk)).toEqual([]);
    const out: BulkFixInstructionsOut = {
      results: bulk.issues.map((i) => ({
        issue_id: i.issue_id,
        ok: true,
        agent_run_id: id(270),
        detail: null,
      })),
      accepted: 2,
      excluded: 0,
    };
    expect(validateSchema("BulkFixInstructionsOut", out)).toEqual([]);
    expect(out.accepted + out.excluded).toBe(out.results.length);
    expect(`Set Fix Instructions for ${String(bulk.issues.length)}`).toBe(
      "Set Fix Instructions for 2",
    );
  });
});
