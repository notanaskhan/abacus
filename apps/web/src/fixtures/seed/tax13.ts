// TAX-13 (T-03-T11): the named rows at Mon Sep 14, 2026, verbatim from the handoff. 79 + 82 = 161 with
// 2 likely; TY2026 Q3: Paid 2 · Scheduled 1 · Awaiting 2 = 5 due, Not required 2. Fictional names. Dev
// and test only.

import type {
  EstimateRowOut,
  EvidenceVersionOut,
  ExtensionRowOut,
  ListPageEstimateRowOut,
  ListPageExtensionRowOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

type Row = ExtensionRowOut;

function ext(
  name: string,
  form: string,
  extForm: string,
  due: string,
  options: Partial<Row> & { filed?: string; paid?: readonly [string, string][]; by?: string } = {},
): Row {
  const { filed, paid = [], by, ...rest } = options;
  const id = stableId(`extension:${name}:${extForm}`);
  return {
    allowed_actions: [],
    client_name: name,
    extended_due_on: due,
    likely_reasons: [],
    likely_to_extend: false,
    lines: [
      {
        extension_id: id,
        form: extForm,
        jurisdiction: "federal",
        status: filed === undefined ? "not_filed" : "accepted",
        ...(filed === undefined ? {} : { filed_on: filed }),
      },
    ],
    original_due_on: "2026-04-15",
    payments: paid.map(([jurisdiction, amount], i) => ({
      amount,
      id: `${id}:${String(i)}`,
      jurisdiction,
      kind: "extension_payment" as const,
      proposed_by_name: "Samuel Ito",
    })),
    return_form: form,
    row_version: 1,
    tax_return_id: stableId(`tax-return:${name}`),
    tax_year: 2025,
    work_item_id: id,
    ...(by === undefined ? {} : { confirmation: { confirmed: true, contact_name: by } }),
    ...rest,
  };
}

const OPEN: Row[] = [
  ext("Ridgeline Property Partners, LP", "1065", "7004", "2026-09-15", {
    filed: "2026-03-12",
    by: "Owen Calder",
    days_to_extended_due: 1,
    projected_liability_note: "pass-through",
    paid: [
      ["IL", "28044"],
      ["CO", "17070"],
      ["NY", "18982"],
    ],
  }),
  ext("Harborview Dental Properties, LP", "1065", "7004", "2026-09-15", {
    filed: "2026-03-12",
    by: "Dr. Sofia Lindqvist",
    days_to_extended_due: 1,
  }),
  ext("Calloway Family Trust", "1041", "7004", "2026-09-30", {
    filed: "2026-04-13",
    by: "Eleanor Calloway",
    days_to_extended_due: 16,
    projected_liability: "46300",
    withholding_plus_estimates: "42000",
    safe_harbor_target: "46300",
    safe_harbor_pct: "100",
    paid: [["federal", "5000"]],
  }),
  ext("Ashford Manufacturing Co.", "1120", "7004", "2026-10-15", {
    filed: "2026-04-14",
    by: "Gwen Talbot",
    days_to_extended_due: 31,
    projected_liability: "1572900",
    withholding_plus_estimates: "1560000",
    safe_harbor_target: "1572900",
    safe_harbor_pct: "100",
    paid: [["federal", "12900"]],
  }),
  ext("Jonah & Claire Feld", "1040", "4868 + IT-370", "2026-10-15", {
    filed: "2026-04-14",
    by: "Claire Feld",
    days_to_extended_due: 31,
    projected_liability: "122500",
    withholding_plus_estimates: "113476",
    safe_harbor_target: "110250",
    safe_harbor_pct: "90",
    paid: [
      ["federal", "10000"],
      ["NY", "6000"],
    ],
  }),
  ext("Meera Shah", "1040", "4868", "2026-10-15", {
    filed: "2026-04-13",
    by: "Meera Shah",
    days_to_extended_due: 31,
    projected_liability: "148000",
    withholding_plus_estimates: "128000",
    safe_harbor_target: "133200",
    safe_harbor_pct: "90",
    paid: [["federal", "20000"]],
  }),
  ext("Estate of Walter Thornbury (Walter's 2025 Form 1040)", "1040", "4868", "2026-10-15", {
    filed: "2026-04-15",
    by: "Paul Thornbury (executor)",
    days_to_extended_due: 31,
    projected_liability: "212000",
    withholding_plus_estimates: "188000",
    safe_harbor_target: "190800",
    safe_harbor_pct: "90",
    paid: [["federal", "24000"]],
  }),
  ext("Elena Varga", "1040", "4868", "2026-10-15", {
    filed: "2026-04-14",
    by: "Elena Varga",
    days_to_extended_due: 31,
    projected_liability: "3900",
    withholding_plus_estimates: "3400",
    safe_harbor_target: "3510",
    safe_harbor_pct: "90",
    paid: [["federal", "500"]],
  }),
];

const LIKELY: Row[] = [
  ext("Lakeshore Literacy Alliance", "2025 Form 990 (FYE Jun 30, 2026)", "8868", "2027-05-17", {
    likely_to_extend: true,
    likely_reasons: ["binder_incomplete"],
    original_due_on: "2026-11-16",
    days_to_extended_due: 245,
  }),
  ext("Estate of Walter Thornbury", "706", "4768", "2027-05-03", {
    likely_to_extend: true,
    likely_reasons: ["engagement_not_accepted"],
    original_due_on: "2026-11-02",
    days_to_extended_due: 231,
    client_id: stableId("client:estate-of-walter-thornbury"),
    engagement_id: stableId("engagement:thornbury-acceptance"),
    prepare_blocked_reason: "Engagement pending acceptance (CLI-07): G1 and G3 are not met",
    likely_note: "4768 extends time to file only; estate tax is still due Nov 2",
  }),
];

const COUNTS = { extended: 161, open: 79, filed: 82, likely: 2, acks_pending: 0 };

export function tax13Extensions(segment: string | null): ListPageExtensionRowOut {
  const items = segment === "likely" ? LIKELY : OPEN;
  return { items, total: segment === "likely" ? 2 : 163, counts: COUNTS };
}

// T-03-T16: the April timeline. d, Fri Apr 10: 38 extended, 123 likely, the six unfiled rows still
// to extend. e, Tue Apr 14, 4:05 PM: 149 extended, Feld Filed (ack pending), Varga Rejected.
const REVIEWER_ACTIONS: Row["allowed_actions"] = [
  "filing_extension.prepare",
  "filing_extension.approve_payment",
  "filing_extension.mark_filed",
  "filing_extension.confirmation_send",
];
const PREPARER_ACTIONS: Row["allowed_actions"] = [
  "filing_extension.prepare",
  "filing_extension.mark_filed",
];
const NAMED = ["Ridgeline", "Harborview"];
const ENGAGEMENT = stableId("engagement:tax13-season");

export function tax13SeasonD(
  returnIds: readonly string[],
  reviewer = true,
): ListPageExtensionRowOut {
  const items = OPEN.map((row): Row => {
    if (NAMED.some((n) => row.client_name.startsWith(n))) {
      return { ...row, days_to_extended_due: null };
    }
    return {
      ...row,
      allowed_actions: reviewer ? REVIEWER_ACTIONS : PREPARER_ACTIONS,
      engagement_id: ENGAGEMENT,
      confirmation: null,
      days_to_extended_due: null,
      likely_to_extend: true,
      lines: row.lines.map((l) => ({ ...l, filed_on: null, status: "not_filed" as const })),
    };
  });
  return {
    items:
      returnIds.length === 0 ? items : items.filter((r) => returnIds.includes(r.tax_return_id)),
    total: returnIds.length === 0 ? 161 : returnIds.length,
    counts: { extended: 38, open: 38, filed: 0, likely: 123, acks_pending: 0 },
  };
}

const ACK_ON_APR_14: Readonly<Record<string, Row["lines"][number]["status"]>> = {
  "Jonah & Claire Feld": "filed",
  "Elena Varga": "rejected",
};

export function tax13SeasonE(): ListPageExtensionRowOut {
  const items = OPEN.map((row): Row => {
    if (row.client_name.startsWith("Estate of Walter Thornbury")) {
      return {
        ...row,
        allowed_actions: REVIEWER_ACTIONS,
        engagement_id: ENGAGEMENT,
        days_to_extended_due: null,
        likely_to_extend: true,
        lines: row.lines.map((l) => ({ ...l, filed_on: null, status: "prepared" as const })),
      };
    }
    const status = ACK_ON_APR_14[row.client_name];
    return {
      ...row,
      days_to_extended_due: null,
      lines: row.lines.map((l) => ({
        ...l,
        ...(status === undefined ? {} : { status }),
        ...(status === "rejected" ? { reject_code: "IND-031-04" } : {}),
      })),
    };
  });
  return {
    items,
    total: 161,
    counts: { extended: 149, open: 149, filed: 0, likely: 12, acks_pending: 1 },
  };
}

export const tax13FiledForm: EvidenceVersionOut = {
  created_at: "2026-04-14T14:00:00-05:00",
  evidence_item_id: stableId("evidence-item:tax13-filed-form"),
  id: stableId("evidence-version:tax13-filed-form"),
  method: "uploaded",
  period_end: null,
  period_start: null,
  pulled_at: null,
  source: "Form 4868 confirmation.pdf",
  version_no: 1,
};

/** The three returns on artboard d's sheet: Feld, Shah, Varga. */
export const TAX13_SHEET_IDS: readonly string[] = [
  "Jonah & Claire Feld",
  "Meera Shah",
  "Elena Varga",
].map((name) => stableId(`tax-return:${name}`));

function estimate(
  name: string,
  status: NonNullable<EstimateRowOut["installment"]>["status"],
  annual: string | null,
  amount: string | null,
  method: EstimateRowOut["method"] = "prior_year_110",
): EstimateRowOut {
  return {
    allowed_actions: [],
    annual_required: annual,
    client_entity_id: stableId(`client-entity:${name}`),
    client_name: name,
    forms: ["1040-ES"],
    installment: { amount, due_on: "2026-09-15", quarter: 3, status },
    method,
    payment_method_labels: ["irs_direct_pay"],
    row_version: 1,
    schedule_id: stableId(`estimate-schedule:${name}`),
    tax_year: 2026,
  };
}

export function tax13Estimates(): ListPageEstimateRowOut {
  return {
    items: [
      estimate("Jonah & Claire Feld", "paid", "134750", "33688"),
      estimate("Meera Shah", "paid", "162800", "40700"),
      estimate("Calloway Family Trust", "scheduled", "50930", "12733"),
      estimate("Elena Varga", "confirmation_requested", "4290", "1073"),
      estimate("Marcus & Dana Whitley", "confirmation_requested", "18200", "4550"),
      estimate("Aurelio Santos", "not_required", null, null, "not_required_withholding"),
      estimate(
        "Estate of Walter Thornbury",
        "not_required",
        null,
        null,
        "not_required_estate_first_years",
      ),
    ],
    total: 7,
    counts: { due: 5, paid: 2, scheduled: 1, confirmation_requested: 2, not_required: 2 },
  };
}
