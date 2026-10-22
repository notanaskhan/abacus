// P-04-T09: C3 v1 consumer fixture assertions for stubs 1 and 2. One typed frame per SHL-10 a–g,
// SHL-11 a–h and SHL-12 a–h artboard, built against the generated client's types (a removed or
// renamed field fails tsc) and checked against the OpenAPI document at run time (a field the schema
// no longer has fails here). Figures foot with bigint decimals, never floats. Copy and figures come
// from docs/contracts/review-grammar.md §8 and the P-04 epic's artboard rows; ids are placeholders.
// The UI tasks (P-04 S16–S24) build their scenarios from these shapes.
import type {
  AgentProposalOut as ProposalOut,
  AgentSuggestionOut as SuggestionOut,
  CardDecideIn as DecideIn,
  CardDecisionOut as DecisionOut,
  ReviewNoteDetailOut as ReviewNoteOut,
  ApproveProposalIn,
  BulkSignOffOut,
  DecisionCardOut,
  DecisionCardVersionOut,
  EligibilityCheckOut,
  LadderLevelOut,
  ListPageDecisionCardItemOut,
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
