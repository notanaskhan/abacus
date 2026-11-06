// NOT-02 Notice workspace (N-04-T14): N1, the Whitley CP2000 for TY2024, at Mon Sep 14, 2026, as the
// N-04-T11 analysis and the `notice_position` card return it. Figures verbatim from the handoff
// (goldens in N-04-T04): 1,870 + 1,250 = 3,120; 22% × 3,120 = 686.40; interest 66.61 from the
// notice; total 753.01. The card is reserved to Daniel Reyes (signer). All names are fictional. Dev
// and test only.

import type {
  ActivityItemOut,
  AnalysisOut,
  DecisionCardOut,
  ListPageActivityItemOut,
  NoticeOut,
} from "@abacus/api-client";
import { noticeId, noticeRow } from "../handlers/notices";
import { NOTICES } from "./notices";
import { stableId } from "./prng";

export type Not02Variant = "a" | "b" | "c" | "e" | "f";

const N1 = NOTICES.find((n) => n.key === "N1");
const N3 = NOTICES.find((n) => n.key === "N3"); // e: Collins, Disagree, Awaiting IRS
const N5 = NOTICES.find((n) => n.key === "N5"); // f: Santos, no authorization
export const NOT02_NOTICE = noticeId("N1");
export const NOT02_CARD = stableId("decision-card:notice:N1:position");
const DANIEL = stableId("user:daniel-reyes");
const DOCS = [
  stableId("evidence-version:N1:1099-int:front-range"),
  stableId("evidence-version:N1:1099-int:lakeview"),
];

export function not02Notice(variant: Not02Variant = "a", persona = "kevin-osei"): NoticeOut {
  const shown = variant === "e" ? N3 : variant === "f" ? N5 : N1;
  if (shown === undefined) throw new Error("notice");
  const row = noticeRow(shown);
  return {
    row,
    notice_date: "2026-08-24",
    taxpayer_tin: { kind: "ssn", last4: "6631", presence: "on_file" },
    related_return_id: stableId("return:whitley:2024"),
    related_return_label: "2024 Form 1040",
    respond_by_source: "extracted",
    readiness: [],
    partner_owned: false,
    signer: { user_id: DANIEL, name: "Daniel Reyes", initials: "DR" },
    decision_id: variant === "c" ? stableId("decision:N1:position") : null,
    decided_by: variant === "c" ? { user_id: DANIEL, name: "Daniel Reyes", initials: "DR" } : null,
    decided_at: variant === "c" ? "2026-09-14T14:51:00Z" : null,
    escalated_reason: null,
    follow_up_on: null,
    closed_on: null,
    client_visible: false,
    allowed_actions:
      persona === "daniel-reyes"
        ? ["notice.note", "notice.request_decision", "notice_response.draft"]
        : ["notice.note", "notice.request_decision", "notice_response.draft", "notice.analyze"],
  };
}

const WHY =
  "The notice agrees with the return except for interest on two 1099-INTs issued after filing. 3,120.00 at the 22% bracket = 686.40; the taxable income stays inside the 22% bracket (94,300–201,050, MFJ 2024). No penalty is proposed. The IRS figured interest of 66.61 to the notice date (Aug 24, 2026); it keeps accruing until paid.";

// N-04-T22, verbatim from the handoff's artboard e.
const COLLINS_WHY =
  "The IRS taxed 13,200.00 of 1099-B proceeds as gain (15% = 1,980.00) because the broker reported no basis (noncovered shares); the sale is on an aggregated Form 8949 line as filed, with a basis of 13,200.00, so the gain is zero";

export function not02Analysis(variant: Not02Variant = "a"): AnalysisOut {
  const base = analysisOfN1(variant);
  if (variant === "e") {
    return {
      ...base,
      rows: [
        row("capital_gain", "Capital gain", "0.00", "13200.00", "13200.00"),
        row("tax", "Tax", null, "1980.00", "1980.00"),
        row("total_due", "Total due", null, null, "1980.00"),
      ],
      information_returns: [info("Form 1099-B", "", "13200.00", false, false, null)],
      checks: null,
      sources: [],
      agent: {
        ...base.agent,
        explanation: COLLINS_WHY,
        recommended_position: "disagree",
        run_id: stableId("agent-run:N3:analysis"),
      },
      decision_card_id: null,
    };
  }
  if (variant === "f") {
    return {
      ...base,
      analysis_kind: "balance_due",
      rows: [row("total_due", "Total due", null, null, "1106.00")],
      information_returns: [],
      checks: null,
      sources: [],
      agent: {
        ...base.agent,
        explanation: null,
        recommended_position: null,
        run_id: stableId("agent-run:N5:analysis"),
      },
      decision_card_id: null,
    };
  }
  return base;
}

function analysisOfN1(variant: Not02Variant): AnalysisOut {
  const running = variant === "b";
  return {
    analysis_kind: "underreporter_comparison",
    status: running ? "running" : "ready",
    progress_label: running ? "Comparing 6 information returns with the 2024 return…" : null,
    version: 1,
    engine_name: "notices.compute.underreporter",
    engine_version: "1",
    inputs_hash: "0".repeat(64),
    rows: [
      row("taxable_interest", "Taxable interest", "412.00", "3532.00", "3120.00"),
      row("taxable_income", "Taxable income", "148600.00", "151720.00", "3120.00"),
      row("tax", "Tax", "22798.00", "23484.40", "686.40"),
      row("interest", "Interest (to Aug 24, 2026)", null, "66.61", "66.61"),
      row("penalty", "Accuracy-related penalty", null, "0.00", null),
      row("total_due", "Total due", null, null, "753.01"),
    ],
    transcript_rows: [],
    information_returns: [
      info("Form 1099-INT", "Front Range Bank", "1870.00", false, true, 0),
      info("Form 1099-INT", "Lakeview Credit Union", "1250.00", false, true, 1),
      // The four that agree: the handoff names only their forms (and the 412.00 1099-INT), so the
      // payers stay blank rather than invented; the screen shows the forms alone.
      info("W-2", "", "0.00", true, false, null),
      info("W-2", "", "0.00", true, false, null),
      info("Form 1098", "", "0.00", true, false, null),
      info("Form 1099-INT", "", "412.00", true, false, null),
    ],
    checks: running
      ? null
      : {
          difference_explained: true,
          total_foots: true,
          bracket_check: {
            agrees: true,
            expected: "686.40",
            notice: "686.40",
            rate: "0.22",
            reason: null,
          },
        },
    sources: [
      {
        label: "1099 corrections",
        document_ids: DOCS,
        citation_ids: [1, 2, 3, 4].map((n) => stableId(`citation:N1:1099:${String(n)}`)),
      },
    ],
    agent: {
      stage: "live",
      explanation: running ? null : WHY,
      recommended_position: running ? null : "agree",
      refusal: null,
      run_id: stableId("agent-run:N1:analysis"),
      citation_ids: [],
    },
    decision_card_id: running ? null : NOT02_CARD,
  };
}

function row(
  key: string,
  label: string,
  asFiled: string | null,
  irs: string | null,
  difference: string | null,
): AnalysisOut["rows"][number] {
  return {
    key,
    label,
    as_filed: asFiled,
    irs,
    difference,
    information_returns: null,
    citation_ids: [],
  };
}

function info(
  form: string,
  payer: string,
  amount: string,
  onReturn: boolean,
  after: boolean,
  doc: number | null,
): AnalysisOut["information_returns"][number] {
  return {
    form,
    payer_name: payer,
    amount,
    on_return: onReturn,
    issued_after_filing: after,
    document_id: doc === null ? null : (DOCS[doc] ?? null),
    citation_id: null,
  };
}

export function not02Card(variant: Not02Variant, persona: string): DecisionCardOut {
  const decided = variant === "c";
  return {
    card: {
      id: NOT02_CARD,
      kind: "notice_position",
      engagement_id: stableId("engagement:whitley:2024"),
      work_item_id: null,
      requested_at: "2026-09-14T14:20:00Z",
      reserved_role: "signer",
      reserved_user_id: DANIEL,
      reserved_user_name: "Daniel Reyes",
      status: decided ? "decided" : "awaiting_role",
      version_no: 1,
      superseded_by_version: null,
      blocking_count: 0,
      allowed_actions: persona === "daniel-reyes" && !decided ? ["decision.decide"] : [],
    },
    question: "Position on the CP2000",
    options: [
      {
        key: "agree",
        label: "Agree — pay $753.01",
        detail: "both forms are valid and unreported",
        recommended: true,
        figures: {},
      },
      {
        key: "partially_agree",
        label: "Partially agree",
        detail: null,
        recommended: false,
        figures: {},
      },
      { key: "disagree", label: "Disagree", detail: null, recommended: false, figures: {} },
    ],
    recommendation: {
      option_key: "agree",
      reasons: [],
      suggestion_id: stableId("suggestion:N1:position"),
    },
    decision: decided
      ? {
          id: stableId("decision:N1:position"),
          option_key: "agree",
          decided_by_name: "Daniel Reyes",
          decided_by_user_id: DANIEL,
          decided_at: "2026-09-14T14:51:00Z",
          rationale: "Both 1099-INTs are valid and were not reported.",
          factors: [],
          seen_card_version: 1,
        }
      : null,
    context: [],
    factors: [],
    history: [],
    note: null,
    citation_ids: [],
    blocking_refs: [],
  };
}

const ACTIVITY: readonly ActivityItemOut[] = [
  { at: "2026-08-24T14:00:00Z", event: "received", label: "Received", actor_label: null },
  {
    at: "2026-08-25T15:10:00Z",
    event: "uploaded",
    label: "Uploaded via portal",
    actor_label: "Dana Whitley",
  },
  { at: "2026-08-25T15:11:00Z", event: "classified", label: "Classified", actor_label: null },
  { at: "2026-09-14T14:10:00Z", event: "analyzed", label: "Analyzed", actor_label: null },
  {
    at: "2026-09-14T14:20:00Z",
    event: "decision_requested",
    label: "Decision requested",
    actor_label: "Kevin Osei",
  },
];

export function not02Activity(): ListPageActivityItemOut {
  return { items: [...ACTIVITY], total: ACTIVITY.length };
}
