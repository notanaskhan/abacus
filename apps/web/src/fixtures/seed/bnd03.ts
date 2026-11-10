// BND-03 Questionnaire editor (T-03-T09): the Feld 2025 Binder's organizer (template 1040 organizer
// v6) at Mon Sep 14, 2026, as T-03-T05's editor read and client preview return it. Questions and
// answers verbatim from the handoff spec: 9 questions, 8 answered (Q9 open), 4 conditional
// follow-ups, 1 review point raised (Q2) and the request "estimated payment confirmations" (Q5).
// Variant e adds the empty section Health coverage. All names are fictional. Dev and test only.

import type {
  ClientPreviewOut,
  EditorQuestionOut,
  QuestionnaireEditorOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Bnd03Variant = "a" | "d" | "e";
export const BND03_QUESTIONNAIRE = stableId("questionnaire:feld:2025");

type Q = EditorQuestionOut;

function q(
  key: string,
  section: string,
  position: number,
  wording: string,
  type: Q["type"],
  answer: { value: unknown; on: string } | null,
  extra: Partial<Q> = {},
): Q {
  return {
    id: stableId(`question:feld:${key}`),
    key,
    section_key: section,
    position,
    client_wording: wording,
    type,
    required: false,
    answered: answer !== null,
    answer:
      answer === null
        ? null
        : {
            answer_id: stableId(`answer:feld:${key}`),
            answered_on: answer.on,
            contact_name: "Claire Feld",
            value: answer.value,
            note: null,
          },
    parent_key: null,
    show_when: null,
    triggered: null,
    internal_helper: null,
    effects: [],
    effect_rules: [],
    choices: [],
    amount_parts: [],
    ...extra,
  };
}

const QUESTIONS: readonly Q[] = [
  q(
    "q1",
    "household",
    1,
    "Did your filing status, address or dependents change in 2025?",
    "yes_no",
    { value: "No", on: "2026-08-20" },
  ),
  q(
    "q2",
    "household",
    2,
    "Did you live or keep a home anywhere other than New York City in 2025?",
    "yes_no",
    { value: "Yes", on: "2026-09-09" },
    {
      effects: [
        {
          id: stableId("effect:feld:q2:review"),
          kind: "review_point_raised",
          rule_key: "q2_yes_residency",
          title: "Confirm full-year NYC residency for the IT-201 resident tax",
          actor_kind: "system",
          actor_name: null,
          created_at: "2026-09-09T15:00:00Z",
          target_type: "issue",
          target_id: stableId("issue:feld:residency"),
        },
      ],
    },
  ),
  q(
    "q2a",
    "household",
    3,
    "Days in New York City · elsewhere · traveling",
    "amount",
    { value: "281 · 72 (Rhinebeck, NY) · 12", on: "2026-09-09" },
    {
      parent_key: "q2",
      show_when: { parent_key: "q2", equals: "Yes" },
      triggered: true,
    },
  ),
  q(
    "q3",
    "income",
    4,
    "At any time during 2025, did you (a) receive (as a reward, award or payment for property or services) or (b) sell, exchange or otherwise dispose of a digital asset (or a financial interest in a digital asset)?",
    "yes_no",
    { value: "No", on: "2026-08-27" },
    { required: true },
  ),
  q("q3a", "income", 5, "Upload Form 1099-DA or exchange reports", "upload_if_yes", null, {
    parent_key: "q3",
    required: true,
    show_when: { parent_key: "q3", equals: "Yes" },
    triggered: false,
  }),
  q(
    "q4",
    "income",
    6,
    "Did either of you receive income not reported on a W-2, 1099 or K-1 (for example gig, rental or foreign income)?",
    "yes_no",
    { value: "No", on: "2026-08-20" },
  ),
  q(
    "q5",
    "payments",
    7,
    "Did you make 2025 estimated tax payments?",
    "yes_no",
    { value: "Yes", on: "2026-08-20" },
    { required: true },
  ),
  q(
    "q5a",
    "payments",
    8,
    "Amounts paid",
    "amount",
    { value: "Federal 60,000 (4 × 15,000) · New York 14,000 (4 × 3,500)", on: "2026-08-20" },
    {
      parent_key: "q5",
      show_when: { parent_key: "q5", equals: "Yes" },
      triggered: true,
      amount_parts: ["Federal", "New York"],
    },
  ),
  q("q5b", "payments", 9, "Upload payment confirmations", "upload_if_yes", null, {
    parent_key: "q5",
    show_when: { parent_key: "q5", equals: "Yes" },
    triggered: true,
    effects: [
      {
        id: stableId("effect:feld:q5:request"),
        kind: "request_item_created",
        rule_key: "q5_yes_confirmations",
        title: "estimated payment confirmations",
        actor_kind: "system",
        actor_name: null,
        created_at: "2026-09-01T14:00:00Z",
        target_type: "request_item",
        target_id: stableId("request-item:feld:estimates"),
      },
    ],
  }),
  q(
    "q6",
    "payments",
    10,
    "How should we handle a 2025 refund?",
    "choice",
    { value: "Direct deposit", on: "2026-08-28" },
    {
      choices: ["Direct deposit", "Apply to 2026 estimates"],
      internal_helper: "Paper refund checks ended Sep 30, 2025",
    },
  ),
  q("q7", "deductions", 11, "Did you make charitable gifts of $250 or more?", "upload_if_yes", {
    value: "Yes",
    on: "2026-08-07",
  }),
  q(
    "q8",
    "notices",
    12,
    "Did you receive any letters from the IRS or a state in 2025?",
    "upload_if_yes",
    { value: "No", on: "2026-08-20" },
    {
      internal_helper: "Uploads route to Notices (NOT-01)",
    },
  ),
  q(
    "q9",
    "notices",
    13,
    "Did you give more than $19,000 to any one person in 2025?",
    "yes_no",
    null,
    {
      internal_helper: "Yes flags a Form 709 review (internal only)",
    },
  ),
];

const SECTIONS = [
  ["household", "Household", 2],
  ["income", "Income", 2],
  ["payments", "Payments & refunds", 2],
  ["deductions", "Deductions", 1],
  ["notices", "Notices & gifts", 2],
] as const;

export function bnd03Editor(variant: Bnd03Variant = "a"): QuestionnaireEditorOut {
  const sections = [
    ...SECTIONS,
    ...(variant === "e" ? ([["health", "Health coverage", 0]] as const) : []),
  ].map(([key, title, count], i) => ({
    id: stableId(`section:feld:${key}`),
    key,
    title,
    position: i + 1,
    question_count: count,
  }));
  return {
    id: BND03_QUESTIONNAIRE,
    title: "Jonah & Claire Feld · 2025 Form 1040",
    owner_kind: variant === "d" ? "template_version" : "binder",
    binder_id: variant === "d" ? null : stableId("binder:feld:2025"),
    banner:
      variant === "d"
        ? "Editing template 1040 organizer v6 — changes apply to TY2026 binders"
        : null,
    row_version: 6,
    template: {
      template_id: stableId("template:1040-organizer"),
      name: "1040 organizer",
      version: 6,
      version_id: stableId("template:1040-organizer:v6"),
      applies_to_tax_year: 2025,
    },
    counts: {
      questions: 9,
      answered: 8,
      conditional_follow_ups: 4,
      review_points_raised: 1,
      requests_created: 1,
      last_answer_by: "Claire Feld",
      last_answer_on: "2026-09-09",
    },
    sections,
    questions:
      variant === "d"
        ? QUESTIONS.map((x) => ({ ...x, answered: false, answer: null, effects: [] }))
        : [...QUESTIONS],
    allowed_actions: ["questionnaire.edit"],
  };
}

export function bnd03Preview(): ClientPreviewOut {
  return {
    firm_name: "Brightwater Hale",
    questions: QUESTIONS.map((x) => ({
      key: x.key,
      client_wording: x.client_wording,
      type: x.type,
      required: x.required,
      parent_key: x.parent_key ?? null,
      visible: x.triggered !== false,
      choices: x.choices ?? [],
      amount_parts: x.amount_parts ?? [],
      answer:
        x.key === "q5a" ? { Federal: "60,000", "New York": "14,000" } : (x.answer?.value ?? null),
    })),
  };
}
