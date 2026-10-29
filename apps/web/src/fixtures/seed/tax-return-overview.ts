// TAX-02's records and overviews (T-02-T14): artboards a–e, verbatim from the handoff's spec.md
// and screenshots (docs/screens/TAX-02.md). a and e are the Feld 2025 Form 1040 at E0 and on
// Sep 19; c is the same return on Feb 3 (gathering, pro forma only); b is Rafael Quintero (not
// started, binder not published); d is Juliet Okonjo (prepared, not yet exported). Every return
// the board holds also answers, from its row alone (no invented overview rows), so a TAX-01 row
// always opens. T-02-T13's read model replaces these once the routes go live.
import type {
  EngineSummaryLineOut,
  FilingRowOut,
  LadderStepOut,
  PipelineStepOut,
  RecordLinkOut,
  TaxPlanRowOut,
  TaxReturnOverviewOut,
  TaxReturnRecordOut,
  TwoYearStatOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type OverviewVariant = "a" | "b" | "c" | "d" | "e";

/** What a variant changes on the return's board row. */
export interface RowPatch {
  client: string;
  status: TaxReturnRecordOut["row"]["status"];
  review_level: TaxReturnRecordOut["row"]["review_level"];
  sync: TaxReturnRecordOut["row"]["sync"];
}

export interface OverviewSeed {
  row: RowPatch;
  record: Pick<TaxReturnRecordOut, "tabs" | "card_detail" | "engine_return_id" | "allowed_actions">;
  overview: Omit<TaxReturnOverviewOut, "return_id">;
}

const DELIVER: PipelineStepOut = {
  step: "deliver",
  state: "not_started",
  sub: "Export · 8879 · e-file · client copy",
};

const FELD_LINKS = (binder: string): RecordLinkOut[] => [
  { key: "client", sub: "Jonah & Claire Feld · Household" },
  { key: "engagement", sub: "TY2025 Individual Tax · Feld" },
  { key: "binder", sub: binder },
  { key: "files", sub: "41 documents" },
  { key: "relationships", sub: "Ridgeline Property Partners, LP · LP 25% (Jonah)" },
];

const FELD_FILING: FilingRowOut[] = [
  { key: "due", value: "Oct 15, 2026 (extended)" },
  { key: "extension", value: "Form 4868 + IT-370 · filed Apr 14, 2026 · Accepted" },
  { key: "jurisdictions", value: "Federal · NY + NYC · IL (NR) · CO (NR)" },
  { key: "engine", value: "CCH Axcess · 2025I:FeldJ:V3" },
  {
    key: "consents",
    value: "",
    pill: "Signed · expires Dec 31 2026",
    detail: "Use · AI disclosure (2 consents) · signed Feb 2, 2026",
  },
  { key: "office", value: "New York" },
];

const line = (
  ref: string,
  label: string,
  amount: string | null,
  more: Partial<EngineSummaryLineOut> = {},
): EngineSummaryLineOut => ({
  line_key: `f1040.${ref.replaceAll(" ", "_").toLowerCase()}`,
  line_ref: ref,
  label,
  amount,
  ...more,
});

/** The federal estimate (spec C); `blocked` adds a's two ⚑ notes and leaves 2a blank. */
function estimate(blocked: boolean): EngineSummaryLineOut[] {
  return [
    line("1a", "Wages", "268400"),
    blocked
      ? line("2a", "Tax-exempt interest", null, {
          note: "K-1 box 18A 1,550 not yet carried (Issue)",
          issue: true,
        })
      : line("2a", "Tax-exempt interest", "1550"),
    line("2b", "Taxable interest", "6910"),
    line("3b", "Ordinary dividends", "14820"),
    line("3a", "Qualified dividends", "11960", { indent: true }),
    line("Sch 1 line 5", "Schedule E, Ridgeline (passive)", "307900"),
    line("11", "Adjusted gross income", "598030", { total: "total" }),
    line(
      "12",
      "Itemized deductions (SALT 10,591 after phase-down · mortgage interest 18,240 · gifts 12,500)",
      "41331",
    ),
    line("13", "Qualified business income deduction", "61580"),
    line("15", "Taxable income", "495119", { total: "total" }),
    line("16", "Tax", "110531"),
    line("23", "Other taxes (NIIT 12,526 · Additional Medicare 166)", "12692"),
    line("24", "Total tax", "123223", { total: "total" }),
    line("25d", "Withholding", "53476"),
    blocked
      ? line("26", "Estimated payments", "60000", {
          note: "per organizer — confirmations requested",
        })
      : line("26", "Estimated payments", "60000"),
    line("Sch 3 line 10", "Paid with extension", "10000"),
    line("33", "Total payments", "123476", { total: "total" }),
    line("35a", "Refund", "253", { total: "grand" }),
  ];
}

const FOOTNOTE =
  "Effective rate 20.6% · AMT none · Form 2210 not required (timely payments 113,476 ≥ 90% of 123,223)";

function plan(stage: "a" | "c" | "e"): TaxPlanRowOut[] {
  const s = stage === "c" ? "not_started" : "done";
  const d = (detail: string): { detail: string } | Record<string, never> =>
    stage === "c" ? {} : { detail };
  return [
    { label: "Form 1040 with Schedules 1, 2, 3", state: s },
    { label: "Schedule A", state: s, ...d("itemized 41,331 > standard 31,500") },
    { label: "Schedule B", state: s },
    { label: "Schedule E p 2", state: s, detail: "Ridgeline (passive, not a PTP)" },
    { label: "Form 8995-A", state: s, ...d("QBI 61,580 (UBIA limit 98,450)") },
    { label: "Form 8959 · Form 8960", state: s },
    { label: "Form 4868", state: s, detail: stage === "c" ? "due Apr 15, 2026" : "filed Apr 14" },
    stage === "a"
      ? {
          label: "NY IT-201 + NYC resident tax",
          state: "in_progress",
          detail: "residency review point open",
        }
      : { label: "NY IT-201 + NYC resident tax", state: s },
    { label: "IT-112-R · IT-653", state: s, ...d("PTET credit 4,746") },
    { label: "IL-1040 Sch NR", state: s, ...d("PTET credit 7,011") },
    { label: "CO DR 0104PN", state: s, ...d("PTET credit 4,268") },
  ];
}

const CARRYFORWARDS =
  "None — no capital loss, passive loss, charitable or AMT credit carryforwards on the 2024 return.";

const TWO_YEAR: TwoYearStatOut[] = [
  { key: "agi", prior: "551940", current: "598030", change_pct: "8.4" },
  { key: "total_tax", prior: "110826", current: "123223", change_pct: "11.2" },
  { key: "refund", prior: "1174", current: "253", change_pct: "-78.4" },
];

const RIDGELINE = (pill: string, tone: "state" | "green") => [
  {
    issuer_name: "Ridgeline Property Partners, LP",
    tags: ["Passive", "§199A eligible", "IL · CO · NY"],
    pill,
    pill_tone: tone,
  },
];

// The rung's sub-line is the read model's words (`note`); the fixture carries no person chip.
const ladder = (
  rows: [NonNullable<LadderStepOut["step"]>, NonNullable<LadderStepOut["state"]>, string | null][],
): LadderStepOut[] =>
  rows.map(([step, state, note]) => ({
    role: step === "preparer" ? "preparer" : step === "final_approval" ? "signer" : "reviewer",
    step,
    state,
    note,
    person: null,
    signed_off_at: null,
  }));

const ASSIGN = ["tax_return.read", "tax_return.assign"];

export const OVERVIEWS: Readonly<Record<OverviewVariant, OverviewSeed>> = {
  a: {
    row: {
      client: "Jonah & Claire Feld",
      status: "in_review",
      review_level: "manager",
      sync: "synced",
    },
    record: {
      tabs: [
        { tab: "overview", count: null },
        { tab: "intake", count: 2 },
        { tab: "review", count: 37 },
        { tab: "issues", count: 4 },
        { tab: "activity", count: null },
      ],
      card_detail: "Married filing jointly",
      engine_return_id: "2025I:FeldJ:V3",
      allowed_actions: ASSIGN,
    },
    overview: {
      ladder: ladder([
        ["preparer", "done", "Kevin Osei · submitted Sep 8"],
        ["detail_review", "done", "Olivia Brandt · signed off Sep 9"],
        ["manager_review", "in_progress", "Samuel Ito · in progress"],
        ["final_approval", "not_started", "Daniel Reyes · BH-TAX-02 signer"],
      ]).map((s) =>
        s.step === "final_approval" ? { ...s, blocked_by: "Draft K-1 · pre-release" } : s,
      ),
      engine_version: "2025I:FeldJ:V3",
      engine_synced_on: "2026-09-10",
      engine_summary: estimate(true),
      engine_footnote: FOOTNOTE,
      open_issues: 4,
      k1_dependencies: [
        {
          source_return_id: null,
          issuer_name: "Ridgeline Property Partners, LP",
          status: "awaiting",
          source_label: "Ridgeline 1065",
          short_name: "Ridgeline",
          source_due_on: "2026-09-15",
          blocking: true,
        },
      ],
      consent_ok: true,
      allowed_actions: ASSIGN,
      record_links: FELD_LINKS("2025 Binder · 5 of 7 requests satisfied"),
      filing: FELD_FILING,
      pipeline: [
        { step: "gather", state: "done", sub: "5 of 7 requests · 2 open" },
        { step: "prepare", state: "done", sub: "Aug 25 – Sep 8 · Kevin Osei" },
        {
          step: "review",
          state: "in_progress",
          sub: "Detail ✓ Sep 9 · Manager in progress · Partner",
        },
        DELIVER,
      ],
      plan: plan("a"),
      k1_classifications: RIDGELINE("Draft K-1 · pre-release", "state"),
      carryforwards: CARRYFORWARDS,
      issues: [
        {
          id: stableId("issue:feld:k1-18a"),
          title: "Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet",
          kind: "missing_information",
          severity: "high",
        },
        {
          id: stableId("issue:feld:ridgeline-draft"),
          title: "Ridgeline K-1 is a draft — final approval blocked until Ridgeline is approved",
          kind: "action_required",
          severity: "high",
        },
        {
          id: stableId("issue:feld:estimates"),
          title: "Obtain 2025 federal and NY estimated tax payment confirmations",
          kind: "missing_information",
          severity: "medium",
        },
        {
          id: stableId("issue:feld:nyc-residency"),
          title: "Confirm full-year NYC residency for the IT-201 resident tax",
          kind: "review_point",
          severity: "medium",
        },
      ],
      two_year: TWO_YEAR,
      pro_forma: [],
      pro_forma_label: null,
    },
  },
  b: {
    row: {
      client: "Rafael Quintero",
      status: "not_started",
      review_level: null,
      sync: "not_yet_exported",
    },
    record: {
      tabs: ["overview", "intake", "review", "issues", "activity"].map((tab) => ({
        tab,
        count: null,
      })),
      card_detail: "Denver",
      engine_return_id: null,
      allowed_actions: ASSIGN,
    },
    overview: {
      ladder: ladder([
        ["preparer", "not_started", "LW · not started"],
        ["detail_review", "not_started", "Olivia Brandt · not started"],
        ["manager_review", "not_started", null],
        ["final_approval", "not_started", null],
      ]),
      engine_version: null,
      engine_synced_on: null,
      engine_summary: [],
      engine_footnote: null,
      open_issues: 0,
      k1_dependencies: [],
      consent_ok: null,
      allowed_actions: ASSIGN,
      record_links: [
        { key: "client", sub: "Rafael Quintero" },
        { key: "engagement", sub: "TY2025 Individual Tax · Quintero" },
        { key: "binder", sub: "2025 Binder · Draft · not published" },
      ],
      filing: [
        { key: "due", value: "Oct 15, 2026 (extended)" },
        { key: "engine", value: "CCH Axcess · not yet exported" },
        { key: "office", value: "Denver" },
      ],
      pipeline: [
        { step: "gather", state: "not_started", sub: "Binder not published" },
        { step: "prepare", state: "not_started", sub: "Not started · LW" },
        { step: "review", state: "not_started", sub: "Not started" },
        DELIVER,
      ],
      plan: [],
      k1_classifications: [],
      carryforwards: null,
      issues: [],
      two_year: [],
      pro_forma: [],
      pro_forma_label: null,
    },
  },
  c: {
    row: {
      client: "Jonah & Claire Feld",
      status: "gathering",
      review_level: null,
      sync: "not_yet_exported",
    },
    record: {
      tabs: [
        { tab: "overview", count: null },
        { tab: "intake", count: 7 },
        { tab: "review", count: null },
        { tab: "issues", count: null },
        { tab: "activity", count: null },
      ],
      card_detail: "Married filing jointly",
      engine_return_id: "2025I:FeldJ:V1",
      allowed_actions: ASSIGN,
    },
    overview: {
      ladder: ladder([
        ["preparer", "in_progress", "Kevin Osei · gathering"],
        ["detail_review", "not_started", "Olivia Brandt · not started"],
        ["manager_review", "not_started", "Samuel Ito · not started"],
        ["final_approval", "not_started", "Daniel Reyes · BH-TAX-02 signer"],
      ]),
      engine_version: "2025I:FeldJ:V1",
      engine_synced_on: null,
      engine_summary: [],
      engine_footnote: null,
      open_issues: 0,
      k1_dependencies: [
        {
          source_return_id: null,
          issuer_name: "Ridgeline Property Partners, LP",
          status: "awaiting",
          source_label: "Ridgeline 1065",
          short_name: "Ridgeline",
          source_due_on: "2026-09-15",
          blocking: false,
        },
      ],
      consent_ok: null,
      allowed_actions: ASSIGN,
      record_links: FELD_LINKS("2025 Binder · 0 of 7 requests satisfied"),
      filing: [{ key: "due", value: "Apr 15, 2026" }],
      pipeline: [
        { step: "gather", state: "in_progress", sub: "0 of 7 requests" },
        { step: "prepare", state: "not_started", sub: "Not started · Kevin Osei" },
        { step: "review", state: "not_started", sub: "Not started" },
        DELIVER,
      ],
      plan: plan("c"),
      k1_classifications: RIDGELINE("Waiting on K-1", "state"),
      carryforwards: CARRYFORWARDS,
      issues: [],
      two_year: [],
      pro_forma_label: "Pro forma 2025I:FeldJ:V1 imported Feb 3",
      pro_forma: [
        { label: "Source", value: "CCH Axcess · TY2024 return rolled forward" },
        { label: "Filing status", value: "Married filing jointly" },
        { label: "2024 AGI", value: "551,940" },
        { label: "2024 total tax", value: "110,826" },
        { label: "2024 refund", value: "1,174" },
        { label: "Carryforwards", value: "None" },
        { label: "Expected K-1s", value: "Ridgeline Property Partners, LP" },
        { label: "States", value: "NY + NYC · IL (NR) · CO (NR)" },
      ],
    },
  },
  d: {
    row: {
      client: "Juliet Okonjo",
      status: "prepared",
      review_level: null,
      sync: "not_yet_exported",
    },
    record: {
      tabs: ["overview", "intake", "review", "issues", "activity"].map((tab) => ({
        tab,
        count: null,
      })),
      card_detail: "Chicago",
      engine_return_id: null,
      allowed_actions: ASSIGN,
    },
    overview: {
      ladder: ladder([
        ["preparer", "done", "BN · submitted"],
        ["detail_review", "not_started", "YK · not started"],
        ["manager_review", "not_started", null],
        ["final_approval", "not_started", null],
      ]),
      engine_version: null,
      engine_synced_on: null,
      engine_summary: [],
      engine_footnote: null,
      open_issues: 0,
      k1_dependencies: [],
      consent_ok: null,
      allowed_actions: ASSIGN,
      record_links: [
        { key: "client", sub: "Juliet Okonjo" },
        { key: "engagement", sub: "TY2025 Individual Tax · Okonjo" },
        { key: "binder", sub: "2025 Binder" },
      ],
      filing: [
        { key: "due", value: "Oct 15, 2026 (extended)" },
        { key: "engine", value: "CCH Axcess · not yet exported" },
        { key: "office", value: "Chicago" },
      ],
      pipeline: [
        { step: "gather", state: "done", sub: "Binder complete" },
        { step: "prepare", state: "done", sub: "BN · prepared" },
        { step: "review", state: "not_started", sub: "Detail review not started" },
        DELIVER,
      ],
      plan: [],
      k1_classifications: [],
      carryforwards: null,
      issues: [],
      two_year: [],
      pro_forma: [],
      pro_forma_label: null,
    },
  },
  e: {
    row: {
      client: "Jonah & Claire Feld",
      status: "accepted",
      review_level: null,
      sync: "synced",
    },
    record: {
      tabs: ["overview", "intake", "review", "issues", "activity"].map((tab) => ({
        tab,
        count: null,
      })),
      card_detail: "Married filing jointly",
      engine_return_id: "2025I:FeldJ:V3",
      allowed_actions: ASSIGN,
    },
    overview: {
      ladder: ladder([
        ["preparer", "done", "Kevin Osei · submitted Sep 8"],
        ["detail_review", "done", "Olivia Brandt · signed off Sep 9"],
        ["manager_review", "done", "Samuel Ito · signed off"],
        ["final_approval", "done", "Daniel Reyes · Sep 16"],
      ]),
      engine_version: "2025I:FeldJ:V3",
      engine_synced_on: "2026-09-16",
      engine_summary: estimate(false),
      engine_footnote: FOOTNOTE,
      open_issues: 0,
      k1_dependencies: [],
      consent_ok: true,
      allowed_actions: ASSIGN,
      record_links: FELD_LINKS("2025 Binder · 7 of 7 requests satisfied"),
      filing: FELD_FILING,
      pipeline: [
        { step: "gather", state: "done", sub: "7 of 7 requests" },
        { step: "prepare", state: "done", sub: "Aug 25 – Sep 8 · Kevin Osei" },
        { step: "review", state: "done", sub: "Detail Sep 9 · Manager · Partner Sep 16" },
        { step: "deliver", state: "done", sub: "Accepted Sep 18 (federal) · Sep 19 (NY)" },
      ],
      plan: plan("e"),
      k1_classifications: RIDGELINE("Released Sep 15", "green"),
      carryforwards: CARRYFORWARDS,
      issues: [],
      two_year: TWO_YEAR,
      pro_forma: [],
      pro_forma_label: null,
    },
  },
};
