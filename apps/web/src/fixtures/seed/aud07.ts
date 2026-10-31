// AUD-07 Materiality (A-04-T10; docs/screens/AUD-07.md; the AUD-07 handoff spec.md and R2): the
// Northwind Robotics 401(k) Plan PY2025 record and its `planning_materiality` card, in the shapes
// of the A-04 stub (`MaterialityRecordOut`, `ThresholdsOut`) and C3 (`DecisionCardOut`).
//
// Figures are the materiality engine's (A-04-T08) as the AUD-07 acceptance writes them, and the
// preview handler below stands in for the server: it is the fixture's arithmetic, never the
// screen's. 16,812,400 x 1.5% = 252,186 -> 252,200; PM 75% = 189,150; CT 5% = 12,610; 1.0% =
// 168,100 / 126,075 / 8,405; final basis 16,861,000 -> 252,900, +700 (0.3%).

import type {
  BenchmarkOut,
  DecisionCardOut,
  MaterialityPreviewIn,
  MaterialityRecordOut,
  PlanningMaterialityVersionOut,
  QualitativeFactorOut,
  ThresholdsOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Aud07Variant = "a" | "b" | "c" | "d" | "e";

const MARGARET = stableId("user:margaret-okonkwo");
export const AUD07_CARD = stableId("decision-card:northwind:planning_materiality");
const DECISION = stableId("decision:northwind:planning_materiality:v2");
const AT_0926 = "2026-09-14T09:26:00-05:00";
const AT_0927 = "2026-09-14T09:27:00-05:00";
const AT_1112 = "2026-09-14T11:12:00-05:00";
const AT_OCT6 = "2026-10-06T11:20:00-05:00";
const NET_ASSETS = "16812400";
const FINAL_NET_ASSETS = "16861000";
const POLICY = { low: "1.0", high: "2.0", pmLow: 50n, pmHigh: 75n, ct: 5n } as const;

// ---- the fixture's stand-in for the engine (hundredths of a percent, whole dollars) -----------

const hundredths = (pct: string): bigint => {
  const [whole, frac = ""] = pct.split(".");
  return BigInt(whole ?? "0") * 100n + BigInt((frac + "00").slice(0, 2));
};
const half = (n: bigint, d: bigint): bigint => (n * 2n + d) / (d * 2n);
const money = (n: bigint): string => `${String(n)}.00`;
const pct4 = (h: bigint): string => `${String(h / 100n)}.${String(h % 100n).padStart(2, "0")}00`;

/** Engine figures for a benchmark, a rate and PM/CT; `null` outside the firm's policy. */
export function computeThresholds(
  body: MaterialityPreviewIn,
  amount: string = NET_ASSETS,
  at: string = AT_0927,
): ThresholdsOut | null {
  const rate = hundredths(String(body.rate_pct));
  const pm = hundredths(String(body.pm_pct));
  const ct = hundredths(String(body.ct_pct));
  if (rate < hundredths(POLICY.low) || rate > hundredths(POLICY.high)) return null;
  if (pm < POLICY.pmLow * 100n || pm > POLICY.pmHigh * 100n || ct !== POLICY.ct * 100n)
    return null;
  const overall = half(BigInt(amount) * rate, 10_000n * 100n) * 100n;
  return {
    basis: body.basis ?? "unadjusted",
    benchmark_key: body.benchmark_key,
    benchmark_amount: money(BigInt(amount)),
    rate_pct: pct4(rate),
    overall: money(overall),
    pm_pct: pct4(pm),
    pm: money(half(overall * pm, 10_000n)),
    ct_pct: pct4(ct),
    ct: money(half(overall * ct, 10_000n)),
    policy_low_pct: "1.0000",
    policy_high_pct: "2.0000",
    stamp: {
      engine_name: "materiality",
      engine_version: "1",
      inputs_hash: `${rate.toString(16)}${pm.toString(16)}`.padStart(64, "0"),
      computed_at: at,
    },
  };
}

const at = (rate: string, amount: string = NET_ASSETS, when: string = AT_0927): ThresholdsOut => {
  const t = computeThresholds(
    { benchmark_key: "net_assets", rate_pct: rate, pm_pct: "75", ct_pct: "5" },
    amount,
    when,
  );
  if (t === null) throw new Error("outside the fixture policy");
  return t;
};

// ---- the record --------------------------------------------------------------------------------

const BENCHMARKS: BenchmarkOut[] = [
  {
    key: "net_assets",
    label: "Net assets available for benefits",
    amount: "16812400.00",
    range_low_pct: "1.0000",
    range_high_pct: "2.0000",
    low: "168100.00",
    high: "336200.00",
    use: "overall",
    prior_years: [
      {
        year: "PY2024",
        amount: "14228500.00",
        overall_used: "213400.00",
        rate_used_pct: "1.5000",
      },
      {
        year: "PY2023",
        amount: "11902700.00",
        overall_used: "178500.00",
        rate_used_pct: "1.5000",
      },
    ],
    growth_pct: "18.2",
  },
  {
    key: "contributions",
    label: "Contributions (participant, employer, rollovers)",
    amount: "1318300.00",
    range_low_pct: "3.0000",
    range_high_pct: "5.0000",
    low: "39500.00",
    high: "65900.00",
    use: "considered_for_specific",
    prior_years: [
      { year: "PY2024", amount: "1142600.00", overall_used: null, rate_used_pct: null },
      { year: "PY2023", amount: "1016800.00", overall_used: null, rate_used_pct: null },
    ],
    growth_pct: "15.4",
  },
  {
    key: "benefit_payments",
    label: "Benefit payments to participants",
    amount: "812650.00",
    range_low_pct: "3.0000",
    range_high_pct: "5.0000",
    low: "24400.00",
    high: "40600.00",
    use: "considered_for_specific",
    prior_years: [
      { year: "PY2024", amount: "694300.00", overall_used: null, rate_used_pct: null },
      { year: "PY2023", amount: "588900.00", overall_used: null, rate_used_pct: null },
    ],
    growth_pct: "17.0",
  },
];

const FACTORS: QualitativeFactorOut[] = [
  ["Users are participants, the plan administrator and the DOL (Form 5500)", true],
  ["ERISA §103(a)(3)(C) election; investment information certified by Harborline", true],
  ["Participant-directed, with a self-directed brokerage window ($1,605,000)", true],
  [
    "QACA automatic enrollment (6% default, +1% a year to 15%) raises operational-error risk",
    true,
  ],
  ["Remittance timing is sensitive (Schedule H line 4a)", true],
  ["First-year engagement — No", false],
  ["Uncorrected misstatements in PY2024 — None", false],
  ["Significant deficiencies reported in PY2024 — None", false],
].map(([text, applies]) => ({
  text: text as string,
  applies: applies as boolean,
  citation_ids: [],
}));

const CAPTION = [
  "Unadjusted: the 48,600 contributions receivable (Dec 26 payroll) is not yet recorded. Net assets = investments 16,500,000 + notes receivable 312,400 (Trial Balance, Harborline net trust assets).",
  "Prior years from the PY2024 and PY2023 audited statements; net assets grew 18.2% on PY2024 with market returns and QACA escalation from 2025.",
];
const SPECIFIC =
  "Contributions and benefit payments are tested at performance materiality; no user group expects a lower threshold.";

function version(
  n: number,
  status: PlanningMaterialityVersionOut["status"],
  over: Partial<PlanningMaterialityVersionOut>,
): PlanningMaterialityVersionOut {
  return {
    version_no: n,
    status,
    current: false,
    superseded: false,
    thresholds: at("1.5"),
    decision_card_id: AUD07_CARD,
    decision_id: null,
    reassessment: null,
    impact: [],
    created_by_name: "Marcus Delaney via Agent",
    created_at: AT_0927,
    ...over,
  };
}

const V1 = version(1, "proposed", {});
const V2 = version(2, "decided", {
  thresholds: at("1.5", NET_ASSETS, AT_1112),
  decision_id: DECISION,
  created_by_name: "Margaret Okonkwo",
  created_at: AT_1112,
});
const V3_REASSESSED = version(3, "reassessed", {
  thresholds: V2.thresholds,
  decision_id: DECISION,
  reassessment: {
    final_amount: "16861000.00",
    at_rate: "252900.00",
    difference: "700.00",
    difference_pct: "0.3",
    conclusion: "no_change",
  },
  created_by_name: "Margaret Okonkwo",
  created_at: AT_OCT6,
});
const V3_REVISED = version(3, "revised", {
  thresholds: at("1.5", FINAL_NET_ASSETS, AT_OCT6),
  decision_id: DECISION,
  reassessment: {
    final_amount: "16861000.00",
    at_rate: "252900.00",
    difference: "700.00",
    difference_pct: "0.3",
    conclusion: "revised",
  },
  impact: [
    {
      workpaper_code: "AUD-11",
      title: "Sample Selection",
      reason: "depends_on_step",
      preparer_name: "Marcus Delaney",
    },
  ],
  created_by_name: "Margaret Okonkwo",
  created_at: AT_OCT6,
});

const mark = (
  vs: PlanningMaterialityVersionOut[],
  currentNo: number,
  superseded: readonly number[],
): PlanningMaterialityVersionOut[] =>
  vs.map((v) => ({
    ...v,
    current: v.version_no === currentNo,
    superseded: superseded.includes(v.version_no),
  }));

export function aud07Record(variant: Aud07Variant): MaterialityRecordOut {
  const partner = variant !== "b";
  const pending = variant === "a" || variant === "b";
  const versions =
    variant === "a" || variant === "b"
      ? mark([V1], 1, [])
      : variant === "c"
        ? mark([V1, V2], 2, [1])
        : mark([V1, V2, variant === "d" ? V3_REASSESSED : V3_REVISED], 3, [1]);
  return {
    current: versions.find((v) => v.current) ?? null,
    versions: [...versions].reverse(),
    benchmarks: BENCHMARKS,
    qualitative_factors: FACTORS,
    policy_version_id: stableId("standard:materiality_ranges:v2"),
    pending_card_id: pending ? AUD07_CARD : null,
    allowed_actions: partner
      ? pending
        ? ["decision.decide"]
        : []
      : ["materiality.propose", "materiality.reassess", "decision.notify"],
    period_end: "2025-12-31",
    benchmark_caption: CAPTION,
    specific_note: SPECIFIC,
  };
}

// ---- the planning_materiality card -------------------------------------------------------------

const figures = (t: ThresholdsOut): Record<string, string> => ({
  rate_pct: t.rate_pct,
  overall: t.overall,
  pm_pct: t.pm_pct,
  pm: t.pm,
  ct_pct: t.ct_pct,
  ct: t.ct,
});

const REASONS = [
  "I computed three benchmarks from the unadjusted trial balance. Net assets available for benefits is the firm's default benchmark for a defined contribution plan (BH-EBP-110 step 7).",
  "1.5% sits mid-range. Nothing in the file points to the bottom of the range: the engagement is recurring, PY2024 had no uncorrected misstatements, and Harborline certifies the investments.",
  "1.5% keeps planning materiality in line with the rate used in both prior years.",
];

const PROPOSED: DecisionCardOut = {
  card: {
    id: AUD07_CARD,
    engagement_id: stableId("engagement:northwind-py2025"),
    work_item_id: stableId("work-item:northwind-py2025"),
    kind: "planning_materiality",
    version_no: 1,
    status: "awaiting_role",
    reserved_role: "engagement_partner",
    reserved_user_id: MARGARET,
    reserved_user_name: "Margaret Okonkwo",
    requested_at: AT_0927,
    blocking_count: 3,
    superseded_by_version: null,
    allowed_actions: ["decision.decide", "decision.request_analysis"],
  },
  question: "Which planning materiality should this audit use?",
  // AUD-07's card draws its context as the citation chips (DEC-1851).
  context: [
    { key: "step", label: "BH-EBP-110 step 7", value: "BH-EBP-110 step 7", citation_id: null },
    { key: "au_c_320", label: "AU-C 320", value: "AU-C 320", citation_id: null },
    { key: "au_c_450", label: "AU-C 450", value: "AU-C 450", citation_id: null },
    { key: "tb", label: "Trial Balance · 9:26 AM", value: AT_0926, citation_id: null },
  ],
  options: [
    {
      key: "rate_1_0",
      label: "1.0% of net assets — $168,100",
      detail:
        "PM 75% $126,075 · CT 5% $8,405. Bottom of the firm range; for a first-year audit or known control problems.",
      figures: figures(at("1.0")),
      recommended: false,
    },
    {
      key: "rate_1_5",
      label: "1.5% of net assets — $252,200",
      detail:
        "PM 75% $189,150 · CT 5% $12,610. Recurring engagement, no uncorrected misstatements or significant deficiencies in PY2024, investments certified.",
      figures: figures(at("1.5")),
      recommended: true,
    },
    {
      key: "custom",
      label: "Another rate within 1.0%–2.0%…",
      detail: "PM and CT recompute as you type.",
      figures: {},
      recommended: false,
    },
  ],
  factors: [],
  citation_ids: [],
  note: null,
  recommendation: {
    suggestion_id: stableId("suggestion:northwind:materiality"),
    option_key: "rate_1_5",
    reasons: REASONS,
  },
  blocking_refs: [],
  decision: null,
  history: [
    {
      version_no: 1,
      event: "proposed",
      actor_kind: "agent",
      actor_user_id: null,
      actor_initials: null,
      at: AT_0927,
      option_key: "rate_1_5",
      changed: null,
      figures: {},
    },
  ],
};

export function aud07Card(variant: Aud07Variant): DecisionCardOut {
  if (variant === "a") return PROPOSED;
  if (variant === "b") {
    return {
      ...PROPOSED,
      card: {
        ...PROPOSED.card,
        allowed_actions: ["decision.notify", "decision.request_analysis"],
      },
    };
  }
  return {
    ...PROPOSED,
    card: { ...PROPOSED.card, status: "decided", version_no: 2, allowed_actions: [] },
    decision: {
      id: DECISION,
      option_key: "rate_1_5",
      factors: [],
      rationale: "Recurring plan, clean PY2024, certified investments; mid-range rate.",
      seen_card_version: 1,
      decided_by_user_id: MARGARET,
      decided_by_name: "Margaret Okonkwo",
      decided_at: AT_1112,
    },
    history: [
      ...PROPOSED.history,
      {
        version_no: 2,
        event: "decided",
        actor_kind: "human",
        actor_user_id: MARGARET,
        actor_initials: "MO",
        at: AT_1112,
        option_key: "rate_1_5",
        changed: null,
        figures: {},
      },
    ],
  };
}
