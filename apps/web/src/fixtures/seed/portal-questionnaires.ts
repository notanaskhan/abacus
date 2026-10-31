// POR-05 · Questions on fixtures (T-02-T24; docs/screens/POR-05.md; handoff spec "POR-05"): the
// Feld 2025 Tax Organizer (Claire Feld; 22 of 24 answered at E0), Northwind's fraud inquiries
// (Dana Kowalski) and Granite Peak's analytics questions (Luis Ferrante), as T-02-T22's portal
// routes answer them (`QuestionnaireOut`). The handoff words the three open questions, the three
// answered rows it shows and the inquiries; the other 18 answered organizer questions are fixture
// placeholders that carry only their section (DEC-1569), so the rail's counts foot to the
// handoff's 4 + 5 + 2 + 2 + 1 + 2 + 2 + 2 + 4 = 24.
import type { QuestionOut, QuestionnaireOut } from "@abacus/api-client";
import { stableId } from "./prng";

export const FELD_ORGANIZER = stableId("questionnaire:feld-2025-organizer");
export const NORTHWIND_INQUIRIES = stableId("questionnaire:northwind-py2025-fraud-inquiries");
export const GRANITE_QUESTIONS = stableId("questionnaire:granite-peak-fy2026-questions");
export const TEAM_SECTION = "Questions from your team";
export const SECTIONS: readonly [string, number][] = [
  ["Personal & Household Information", 4],
  ["Income Sources", 5],
  ["Home & Property", 2],
  ["Health & Medical", 2],
  ["Education & Student", 1],
  ["Retirement", 2],
  ["Charitable & Donations", 2],
  ["Business & Self-Employment", 2],
  ["Other Activity", 4],
];

function q(
  id: string,
  section: string,
  type: QuestionOut["type"],
  wording: string,
  extra: Partial<QuestionOut> = {},
): QuestionOut {
  return {
    id: stableId(`question:${id}`),
    section,
    type,
    client_wording: wording,
    help_text: null,
    conditional_on_question_id: null,
    prior_year_value: null,
    answer: null,
    answer_version: null,
    linked_request_item_id: null,
    sent_at: null,
    ...extra,
  };
}

export const CRYPTO = q(
  "feld:digital-assets",
  TEAM_SECTION,
  "yes_no",
  "Did either of you sell, exchange or receive any digital assets (such as cryptocurrency) in 2025?",
  {
    help_text:
      "Your 2024 return answered Yes to this question. Exchanges send Form 1099-DA for the first time for 2025.",
    prior_year_value: "yes",
    sent_at: "2026-09-11T10:00:00-05:00",
    linked_request_item_id: stableId("request-item:feld:1099-da"),
  },
);
export const RETIREMENT = q(
  "feld:ira-hsa-529",
  "Retirement",
  "amount_group",
  "Did you or Jonah contribute to an IRA, HSA or 529 plan for 2025?",
  {
    help_text:
      "IRA and HSA contributions for 2025 could be made until April 15, 2026. 529 contributions count for the year you made them.",
  },
);
export const FOREIGN = q(
  "feld:foreign-accounts",
  "Other Activity",
  "yes_no",
  "At any time in 2025, did either of you have a financial interest in, or signature authority over, a bank or brokerage account outside the United States?",
  { help_text: "If yes, we'll also check whether an FBAR (FinCEN 114) is required." },
);
const ANSWERED_SHOWN: readonly [string, string, string, string][] = [
  [
    "feld:filing-status",
    "Personal & Household Information",
    "Did your filing status change in 2025?",
    "no",
  ],
  ["feld:home", "Home & Property", "Did you buy, sell or refinance a home?", "no"],
  [
    "feld:estimates",
    "Income Sources",
    "Did you make 2025 estimated tax payments?",
    "Yes · confirmations in Documents",
  ],
];

/** The organizer's 24 questions; `answered` flips the three open ones (c). */
function organizer(allAnswered: boolean, uploaded: boolean): QuestionOut[] {
  const shown = ANSWERED_SHOWN.map(([id, section, wording, answer]) =>
    q(id, section, "yes_no", wording, { answer, answer_version: 1 }),
  );
  const placeholders: QuestionOut[] = [];
  for (const [section, total] of SECTIONS) {
    const used =
      shown.filter((s) => s.section === section).length +
      [CRYPTO, RETIREMENT, FOREIGN].filter((o) => o.section === section).length;
    for (let n = used; n < total; n += 1) {
      placeholders.push(
        q(
          `feld:${section}:${String(n)}`,
          section,
          "yes_no",
          `${section} · question ${String(n + 1)}`,
          {
            answer: "no",
            answer_version: 1,
          },
        ),
      );
    }
  }
  const open = [CRYPTO, RETIREMENT, FOREIGN].map((o) =>
    allAnswered
      ? { ...o, answer: o === RETIREMENT ? { answer: "no" } : "no", answer_version: 2 }
      : uploaded && o === CRYPTO
        ? { ...o, answer: "yes", answer_version: 2 }
        : o,
  );
  return [...open, ...shown, ...placeholders];
}

export const FELD_UPLOAD = "2025_gains_losses_report.pdf";

export function feldOrganizer(state: string): QuestionnaireOut {
  const done = state === "c";
  const questions = organizer(done, state === "b");
  // The organizer's progress counts its own 24 (the team's question is asked beside it).
  const organizerOnly = questions.filter((x) => x.section !== TEAM_SECTION);
  const answered = organizerOnly.filter((x) => x.answer !== null).length;
  return {
    id: FELD_ORGANIZER,
    kind: "organizer",
    title: "2025 Tax Organizer",
    status: done ? "complete" : "open",
    due_on: null,
    answered,
    total: organizerOnly.length,
    addressed_to_contact_id: null,
    questions,
  };
}

export const NORTHWIND_QUESTIONS: readonly string[] = [
  "Are you aware of any actual, suspected or alleged fraud affecting the Northwind Robotics 401(k) Plan since January 1, 2025?",
  "How do you identify and respond to risks such as unauthorized distributions, loans or changes to participant data?",
  "Were any participant contributions sent to the trust late in 2025 or 2026, or corrected through the DOL's Voluntary Fiduciary Correction Program?",
  "Have you told the people who handle plan transactions what's expected of them on ethics and conduct, and how?",
];

export function northwindInquiries(): QuestionnaireOut {
  return {
    id: NORTHWIND_INQUIRIES,
    kind: "inquiry",
    title: "PY2025 audit — fraud risk inquiries",
    status: "open",
    due_on: "2026-09-18",
    answered: 0,
    total: NORTHWIND_QUESTIONS.length,
    addressed_to_contact_id: stableId("contact:dana-kowalski"),
    questions: NORTHWIND_QUESTIONS.map((wording, n) =>
      q(`northwind:fraud:${String(n)}`, "Fraud risk inquiries", "long_text", wording),
    ),
  };
}

export const GRANITE_PEAK_QUESTIONS: readonly string[] = [
  "Inventory rose $2,240,000 (24.4%) to $11,420,000 at June 30, 2026. What drove the increase, and how much relates to products discontinued during the year?",
  "Gross margin fell from 41.0% to 40.0%. Which cost changes (freight, product mix, markdowns) explain it?",
];

export function graniteQuestions(): QuestionnaireOut {
  return {
    id: GRANITE_QUESTIONS,
    kind: "inquiry",
    title: "FY2026 audit — questions",
    status: "open",
    due_on: null,
    answered: 0,
    total: GRANITE_PEAK_QUESTIONS.length,
    addressed_to_contact_id: stableId("contact:luis-ferrante"),
    questions: GRANITE_PEAK_QUESTIONS.map((wording, n) =>
      q(`granite:analytics:${String(n)}`, "Questions from your team", "long_text", wording, {
        sent_at: "2026-09-11T10:00:00-05:00",
      }),
    ),
  };
}

/** The questionnaires the viewer of each artboard sees (f: none). */
export function questionnairesOf(state: string): QuestionnaireOut[] {
  if (state === "f") return [];
  if (state === "d") return [northwindInquiries()];
  if (state === "e") return [graniteQuestions()];
  return [feldOrganizer(state)];
}
