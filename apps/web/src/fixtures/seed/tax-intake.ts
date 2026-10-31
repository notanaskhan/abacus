// TAX-03's intake reads (T-02-T19): `GET /v1/tax-returns/{id}/intake` for artboards a–f, verbatim
// from the handoff's spec.md (`TAX-03 Return - Intake - Feld 2025 Form 1040/`). The Feld 2025
// Binder's seven requests (5 of 7 satisfied, "Intake 2"), the two 1095-C forms waiting in the Inbox
// (one for 2024) and Ridgeline's draft K-1 hand-off; Meera Shah's return has no binder (f).
import type {
  IntakeCategoryOut,
  IntakeQuestionnaireOut,
  IntakeRequestOut,
  IntakeWaitingFileOut,
  LiveItemOut,
  TaxReturnIntakeOut,
} from "@abacus/api-client";
import { stableId } from "./prng";
import { K1_STATEMENT, W2_CLAIRE } from "./trust";

export type IntakeVariant = "a" | "b" | "c" | "d" | "e" | "f";

export const FELD_BINDER_ID = stableId("binder:feld:2025");
const at = (day: string, time: string): string => `2026-${day}T${time}:00-05:00`;

const CATEGORY = {
  personal: { key: stableId("category:personal"), label: "Personal & Household Information" },
  income: { key: stableId("category:income"), label: "Income Sources" },
  home: { key: stableId("category:home"), label: "Home & Property" },
  health: { key: stableId("category:health"), label: "Health & Medical" },
  charity: { key: stableId("category:charity"), label: "Charitable & Donations" },
  other: { key: stableId("category:other"), label: "Other Activity" },
} as const;
type CategoryKey = keyof typeof CATEGORY;

export const REQUEST = {
  w2: stableId("request:feld:2025:w2-mercer-hill"),
  b1099: stableId("request:feld:2025:1099-halvard"),
  k1: stableId("request:feld:2025:k1-ridgeline"),
  f1098: stableId("request:feld:2025:1098-hudson"),
  donations: stableId("request:feld:2025:donations"),
  f1095c: stableId("request:feld:2025:1095c-mercer-hill"),
  estimates: stableId("request:feld:2025:estimates"),
} as const;

export const ATTACHMENT = {
  c2025: stableId("attachment:feld:1095c-2025"),
  c2024: stableId("attachment:feld:1095c-2024"),
} as const;
const THREAD = stableId("thread:feld:2025-tax-documents");
const MESSAGE = stableId("message:feld:2025-tax-documents:0912");
export const DUPLICATE_VERSION = stableId("evidence-version:feld:w2-mercer-hill-claire:dup");
export const RIDGELINE_RETURN = stableId("tax-return:ridgeline:2025:1065");

function row(
  id: string,
  category: CategoryKey,
  title: string,
  patch: Partial<IntakeRequestOut>,
): IntakeRequestOut {
  return {
    id,
    binder_id: FELD_BINDER_ID,
    category: CATEGORY[category].key,
    title,
    status: "requested",
    overdue: false,
    requested_at: at("02-03", "09:00"),
    due_on: null,
    latest_version_id: null,
    file_name: null,
    uploaded_on: null,
    channel: null,
    linked_count: null,
    owed_by: null,
    duplicate: null,
    ...patch,
  };
}

const received = (file: string, day: string, channel: string, version: string) => ({
  status: "received",
  file_name: file,
  uploaded_on: `2026-${day}`,
  channel,
  latest_version_id: version,
});

const W2 = row(REQUEST.w2, "income", "2025 W-2 From Mercer Hill Health", {
  ...received("Claire_Feld_2025_W2_MercerHill.pdf", "08-03", "firm", W2_CLAIRE),
  linked_count: 1,
});
const B1099 = row(
  REQUEST.b1099,
  "income",
  "2025 Consolidated 1099 From Halvard Securities (Acct ••3318)",
  received(
    "Jonah_Feld_2025_1099_Composite_Halvard.pdf",
    "08-05",
    "client",
    stableId("evidence-version:feld:halvard-1099-portal"),
  ),
);
const K1 = row(REQUEST.k1, "income", "Schedule K-1 from Ridgeline Property Partners, LP", {
  ...received(
    "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
    "08-24",
    "firm",
    stableId("evidence-version:feld:ridgeline-k1-draft"),
  ),
  linked_count: 5,
});
const F1098 = row(
  REQUEST.f1098,
  "home",
  "2025 Form 1098 From Hudson Mutual Savings (co-op loan)",
  received(
    "Claire_Feld_2025_1098_HudsonMutual.pdf",
    "08-03",
    "firm",
    stableId("evidence-version:feld:1098-hudson"),
  ),
);
const DONATIONS = row(
  REQUEST.donations,
  "charity",
  "2025 donation receipts and acknowledgment letters",
  received(
    "Feld_2025_Donations.pdf",
    "08-07",
    "client",
    stableId("evidence-version:feld:donations"),
  ),
);
const F1095C = row(REQUEST.f1095c, "health", "Form 1095-C From Mercer Hill Health", {});
const ESTIMATES = row(
  REQUEST.estimates,
  "other",
  "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
  { requested_at: at("09-01", "09:00") },
);

function categories(rows: readonly IntakeRequestOut[]): IntakeCategoryOut[] {
  return (Object.keys(CATEGORY) as CategoryKey[]).map((k) => {
    const mine = rows.filter((r) => r.category === CATEGORY[k].key);
    return {
      key: CATEGORY[k].key,
      label: CATEGORY[k].label,
      requested: mine.length,
      received: mine.filter((r) => r.status === "received" || r.status === "accepted").length,
    };
  });
}

const QUESTIONS: IntakeQuestionnaireOut[] = [
  {
    id: stableId("questionnaire:feld:2025:organizer"),
    kind: "organizer",
    title: "2025 organizer",
    status: "submitted",
    answered: 22,
    total: 24,
    submitted_at: at("08-20", "18:10"),
    submitted_by_name: "Claire Feld",
  },
  {
    id: stableId("questionnaire:feld:2025:digital-asset"),
    kind: "team_questions",
    title: "Digital asset question",
    status: "submitted",
    answered: 1,
    total: 1,
    submitted_at: at("08-27", "10:02"),
    submitted_by_name: null,
  },
  {
    id: stableId("questionnaire:feld:2025:residency"),
    kind: "team_questions",
    title: "Residency facts",
    status: "submitted",
    answered: 3,
    total: 3,
    submitted_at: at("09-09", "16:40"),
    submitted_by_name: null,
  },
];

function waiting(year: 2025 | 2024): IntakeWaitingFileOut {
  const current = year === 2025;
  return {
    attachment_id: current ? ATTACHMENT.c2025 : ATTACHMENT.c2024,
    thread_id: THREAD,
    message_id: MESSAGE,
    file_name: `Feld_1095C_${String(year)}.pdf`,
    media_type: "application/pdf",
    size_bytes: current ? 412 * 1024 : 398 * 1024,
    channel: "email",
    sender: "claire.feld@gmail.com",
    subject: "Re: 2025 tax documents",
    received_at: at("09-14", "09:12"),
    tax_year: year,
    wrong_year: !current,
    duplicate: false,
    flags: current ? [] : ["wrong_year"],
    suggestion: current
      ? {
          request_id: REQUEST.f1095c,
          label: "Health & Medical › Form 1095-C From Mercer Hill Health",
          confidence: 96,
        }
      : null,
  };
}

const K1_DRAFT = {
  source_return_id: RIDGELINE_RETURN,
  issuer_name: "Ridgeline Property Partners, LP",
  source_label: "Ridgeline 1065",
  short_name: "Ridgeline",
  source_due_on: "2026-09-15",
  status: "awaiting" as const,
  blocking: true,
};

const BINDER = {
  id: FELD_BINDER_ID,
  name: "2025 Binder",
  status: "published",
  published_at: at("02-03", "10:15"),
  published_by_name: "Kevin Osei",
  marked_done_at: null,
  marked_done_by_name: null,
  last_upload_at: at("09-14", "09:12"),
};

const ACTIONS = [
  "evidence.accept",
  "inbox.file",
  "inbox.triage",
  "questionnaire.ask",
  "request_item.create",
];

function intake(
  returnId: string,
  rows: IntakeRequestOut[],
  patch: Partial<TaxReturnIntakeOut> = {},
): TaxReturnIntakeOut {
  const done = rows.filter((r) => r.status === "received" || r.status === "accepted").length;
  const files = patch.waiting ?? [];
  return {
    return_id: returnId,
    binder_id: FELD_BINDER_ID,
    binder: BINDER,
    categories: categories(rows),
    requests: rows,
    requests_total: rows.length,
    requests_received: done,
    waiting: files,
    waiting_files: files.length,
    suggestions: "shown",
    tax_year: 2025,
    questionnaire_ids: QUESTIONS.map((q) => q.id),
    questionnaires: QUESTIONS,
    k1_handoffs: [K1_DRAFT],
    allowed_actions: ACTIONS,
    ...patch,
  };
}

const ROWS_A = [W2, B1099, K1, F1098, DONATIONS, F1095C, ESTIMATES];
const FILED_1095C = {
  ...F1095C,
  ...received(
    "Feld_1095C_2025.pdf",
    "09-14",
    "firm",
    stableId("evidence-version:feld:1095c-2025"),
  ),
};
const FILED_ESTIMATES = {
  ...ESTIMATES,
  ...received(
    "Feld_2025_Estimated_Payments.pdf",
    "09-15",
    "client",
    stableId("evidence-version:feld:estimates"),
  ),
  linked_count: null,
};

/** TAX-03's read for an artboard of the Feld return (f is Meera Shah's, with no binder). */
export function intakeFor(variant: IntakeVariant, returnId: string): TaxReturnIntakeOut {
  switch (variant) {
    case "a":
      return intake(returnId, ROWS_A, { waiting: [waiting(2025), waiting(2024)] });
    case "b":
      return intake(returnId, [W2, B1099, K1, F1098, DONATIONS, FILED_1095C, ESTIMATES]);
    case "c":
      return intake(returnId, [W2, B1099, K1, F1098, DONATIONS, FILED_1095C, FILED_ESTIMATES], {
        binder: {
          ...BINDER,
          status: "complete",
          marked_done_at: at("09-15", "09:02"),
          marked_done_by_name: "Claire Feld",
          last_upload_at: at("09-15", "09:01"),
        },
      });
    case "d":
      return intake(
        returnId,
        [
          W2,
          B1099,
          {
            ...K1,
            ...received("Ridgeline 2025 K-1 statement.pdf", "09-15", "firm", K1_STATEMENT),
            linked_count: 5,
          },
          F1098,
          DONATIONS,
          FILED_1095C,
          FILED_ESTIMATES,
        ],
        { k1_handoffs: [{ ...K1_DRAFT, status: "received", blocking: false }] },
      );
    case "e":
      return intake(
        returnId,
        [
          {
            ...W2,
            duplicate: {
              version_id: DUPLICATE_VERSION,
              file_name: "Claire_Feld_2025_W2_MercerHill (1).pdf",
            },
          },
          B1099,
          K1,
          F1098,
          DONATIONS,
          F1095C,
          ESTIMATES,
        ],
        { waiting: [waiting(2025), waiting(2024)] },
      );
    case "f":
      return {
        return_id: returnId,
        binder_id: null,
        binder: null,
        categories: [],
        requests: [],
        requests_total: 0,
        requests_received: 0,
        waiting: [],
        waiting_files: 0,
        suggestions: "agents_off",
        tax_year: 2025,
        questionnaire_ids: [],
        questionnaires: [],
        k1_handoffs: [],
        allowed_actions: ACTIONS,
      };
  }
}

/** BND-02's live poll for the Feld binder: Claire uploading the estimates in a (POR-03), the two
 * 1095-C forms waiting in the Inbox. */
export function liveFor(variant: IntakeVariant): LiveItemOut[] {
  const open = variant === "a" || variant === "e";
  return [
    {
      request_item_id: REQUEST.f1095c,
      inbox_waiting: open ? 2 : 0,
      uploading_files: 0,
      screening_running: false,
    },
    {
      request_item_id: REQUEST.estimates,
      inbox_waiting: 0,
      uploading_files: open ? 2 : 0,
      screening_running: false,
    },
  ];
}
