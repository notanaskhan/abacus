// TAX-13 (T-03-T11): the named rows at Mon Sep 14, 2026, verbatim from the handoff. 79 + 82 = 161 with
// 2 likely; TY2026 Q3: Paid 2 · Scheduled 1 · Awaiting 2 = 5 due, Not required 2. Fictional names. Dev
// and test only.

import type { EstimateRowOut, ExtensionRowOut, ListPageEstimateRowOut, ListPageExtensionRowOut } from "@abacus/api-client";
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
      id: `${id}:${i}`,
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
  ext("Ridgeline Property Partners, LP", "1065", "7004", "2026-09-15", { filed: "2026-03-12", by: "Owen Calder", days_to_extended_due: 1, projected_liability_note: "pass-through", paid: [["IL", "28044"], ["CO", "17070"], ["NY", "18982"]] }),
  ext("Harborview Dental Properties, LP", "1065", "7004", "2026-09-15", { filed: "2026-03-12", by: "Dr. Sofia Lindqvist", days_to_extended_due: 1 }),
  ext("Calloway Family Trust", "1041", "7004", "2026-09-30", { filed: "2026-04-13", by: "Eleanor Calloway", days_to_extended_due: 16, projected_liability: "46300", withholding_plus_estimates: "42000", safe_harbor_target: "46300", safe_harbor_pct: "100", paid: [["federal", "5000"]] }),
  ext("Ashford Manufacturing Co.", "1120", "7004", "2026-10-15", { filed: "2026-04-14", by: "Gwen Talbot", days_to_extended_due: 31, projected_liability: "1572900", withholding_plus_estimates: "1560000", safe_harbor_target: "1572900", safe_harbor_pct: "100", paid: [["federal", "12900"]] }),
  ext("Jonah & Claire Feld", "1040", "4868 + IT-370", "2026-10-15", { filed: "2026-04-14", by: "Claire Feld", days_to_extended_due: 31, projected_liability: "122500", withholding_plus_estimates: "113476", safe_harbor_target: "110250", safe_harbor_pct: "90", paid: [["federal", "10000"], ["NY", "6000"]] }),
  ext("Meera Shah", "1040", "4868", "2026-10-15", { filed: "2026-04-13", by: "Meera Shah", days_to_extended_due: 31, projected_liability: "148000", withholding_plus_estimates: "128000", safe_harbor_target: "133200", safe_harbor_pct: "90", paid: [["federal", "20000"]] }),
  ext("Estate of Walter Thornbury (Walter's 2025 Form 1040)", "1040", "4868", "2026-10-15", { filed: "2026-04-15", by: "Paul Thornbury (executor)", days_to_extended_due: 31, projected_liability: "212000", withholding_plus_estimates: "188000", safe_harbor_target: "190800", safe_harbor_pct: "90", paid: [["federal", "24000"]] }),
  ext("Elena Varga", "1040", "4868", "2026-10-15", { filed: "2026-04-14", by: "Elena Varga", days_to_extended_due: 31, projected_liability: "3900", withholding_plus_estimates: "3400", safe_harbor_target: "3510", safe_harbor_pct: "90", paid: [["federal", "500"]] }),
];

const LIKELY: Row[] = [
  ext("Lakeshore Literacy Alliance", "2025 Form 990 (FYE Jun 30, 2026)", "8868", "2027-05-17", { likely_to_extend: true, likely_reasons: ["binder_incomplete"], original_due_on: "2026-11-16", days_to_extended_due: 245 }),
  ext("Estate of Walter Thornbury", "706", "4768", "2027-05-03", { likely_to_extend: true, likely_reasons: ["engagement_not_accepted"], original_due_on: "2026-11-02", days_to_extended_due: 231, prepare_blocked_reason: "Engagement pending acceptance (CLI-07): G1 and G3 are not met", likely_note: "4768 extends time to file only; estate tax is still due Nov 2" }),
];

const COUNTS = { extended: 161, open: 79, filed: 82, likely: 2, acks_pending: 0 };

export function tax13Extensions(segment: string | null): ListPageExtensionRowOut {
  const items = segment === "likely" ? LIKELY : OPEN;
  return { items, total: segment === "likely" ? 2 : 163, counts: COUNTS };
}

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
      estimate("Estate of Walter Thornbury", "not_required", null, null, "not_required_estate_first_years"),
    ],
    total: 7,
    counts: { due: 5, paid: 2, scheduled: 1, confirmation_requested: 2, not_required: 2 },
  };
}
