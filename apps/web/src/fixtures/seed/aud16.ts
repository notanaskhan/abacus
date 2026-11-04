// AUD-16 Misstatements & adjustments (A-06-T22): the A-06-T13 SUM view and C8's entries for
// Northwind PY2025, verbatim from the handoff spec. Materiality v2 (252,200 / PM 189,150 / CT
// 12,610); rollover 34,150 = 35,300 − 1,150 and iron curtain 22,250 = 35,300 − 13,050 are the
// server's figures here, never the browser's. Variant f is illustrative: the handoff states the
// rule (aggregate above 50% of PM turns the bar amber), not figures, so its aggregate is chosen to
// cross it. RJE-1's account codes are not in the handoff and stay blank. Dev and test only.

import type {
  AbacusModulesAssuranceFindingsContractMisstatementOut,
  EntryOut,
  ListPageEntryOut,
  ListPageMisstatementOut,
  SendPreviewOut,
  SumOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Aud16Variant = "a" | "b2" | "e" | "f";

const SUM_ACTIONS: NonNullable<SumOut["allowed_actions"]> = [
  "sum.update_factors",
  "sum.request_conclusion",
  "sum.snapshot",
  "sum.export",
];

export const AUD16_CARD = stableId("decision-card:northwind:sum-conclusion");

export function aud16Sum(variant: Aud16Variant = "a"): SumOut {
  const concluded = variant === "e";
  const approaching = variant === "f";
  return {
    column_set: "ebp_net_assets",
    rollover: approaching ? "104000.00" : "34150.00",
    iron_curtain: "22250.00",
    aggregate: approaching ? "104000.00" : "34150.00",
    aggregate_view: "rollover",
    pct_of_pm: approaching ? "55.0" : "18.1",
    fill_pct_of_overall: approaching ? "41.2" : "13.5",
    ct_tick_pct: "5.0",
    pm_tick_pct: "75.0",
    approaching_pm: approaching,
    above_pm: false,
    engine_version: "1",
    inputs_hash: "0".repeat(64),
    thresholds: { overall: "252200.00", pm: "189150.00", ct: "12610.00", label: "v2 · 1.5%" },
    rows: [
      {
        misstatement_id: stableId("misstatement:northwind:paje-1"),
        ref: "PAJE-1",
        group: "current",
        description: "Employer safe-harbor match on bonus pay (projected)",
        finding_ref: "F-07",
        workpaper_ref: "EBP-04",
        client_note:
          "Declined by Dana Kowalski · Sep 25 — sponsor will correct under EPCRS in 2026",
        type: "projected",
        assets: "35300.00",
        liabilities: null,
        net_assets: "35300.00",
        change_in_net_assets: "35300.00",
        carried_from_py: null,
      },
      {
        misstatement_id: stableId("misstatement:northwind:paje-2"),
        ref: "PAJE-2",
        group: "current",
        description:
          "Accrued administrative expenses — Q4 recordkeeping 6,150 · TPA 2,400 · audit fee 4,500",
        finding_ref: "F-08",
        workpaper_ref: "EBP-09",
        client_note: "Declined by Dana Kowalski · Sep 25 — recorded when invoiced",
        type: "judgmental",
        assets: null,
        liabilities: "13050.00",
        net_assets: "-13050.00",
        change_in_net_assets: "-1150.00",
        carried_from_py: "-11900.00",
      },
      {
        misstatement_id: null,
        ref: "PY-1",
        group: "prior_year",
        description: "Accrued administrative expenses at 12/31/2024 — reversed in 2025",
        finding_ref: null,
        workpaper_ref: null,
        client_note: null,
        type: "judgmental",
        assets: null,
        liabilities: "11900.00",
        net_assets: "-11900.00",
        change_in_net_assets: null,
        carried_from_py: null,
      },
    ],
    totals: {
      assets: "35300.00",
      liabilities: "13050.00",
      net_assets: "22250.00",
      change_in_net_assets: "34150.00",
      carried_from_py: "-11900.00",
    },
    footnote:
      "Rollover measures the 2025 effect on the change in net assets (PAJE-2: 13,050 − 11,900 = 1,150). Iron curtain measures the effect on net assets at 12/31/2025. Projected misstatements are not booked; the sponsor corrects the participant accounts.",
    below_ct_count: 1,
    below_ct_total: "4210.00",
    factors: [
      factor(
        "participant_balances",
        "Affects participant account balances",
        "Yes · 412 census records (PAJE-1)",
        true,
      ),
      factor(
        "plan_terms",
        "Affects compliance with plan terms",
        "Yes · AU-C 703 reportable finding",
        true,
      ),
      factor("trend", "Masks a change in trend", "No", false),
      factor("fraud", "Fraud or illegal act", "No", false),
      factor("comparatives", "Affects comparatives", "No · PY effect reverses", false),
      factor("approaches_pm", "Approaches PM", approaching ? "Yes" : "No", approaching),
    ],
    booked: [
      {
        ref: "AJE-1",
        description: "Contributions receivable",
        amount: "48600.00",
        approval_label: "Client approved · Sep 25",
      },
      {
        ref: "RJE-1",
        description: "Loan offsets to benefits paid",
        amount: "14850.00",
        approval_label: "Client approved · Sep 25",
      },
    ],
    conclusion: concluded
      ? {
          state: "concluded",
          decision_card_id: AUD16_CARD,
          reserved_user_name: "Margaret Okonkwo",
          outcome_label: "Immaterial individually and in aggregate",
          decided_by_name: "Margaret Okonkwo",
          decided_at: "2026-10-02T21:30:00Z",
        }
      : {
          state: "not_requested",
          decision_card_id: null,
          reserved_user_name: "Margaret Okonkwo",
          outcome_label: null,
          decided_by_name: null,
          decided_at: null,
        },
    sign_off: {
      prepared_label: "Prepared · HL Sep 28",
      partner_label: concluded ? "MO" : null,
      partner_signed: concluded,
    },
    counts: { proposed: 1, reclass: 1, passed: 2, below_ct: 1 },
    allowed_actions: concluded ? ["sum.export"] : SUM_ACTIONS,
  };
}

function factor(
  key: string,
  label: string,
  value: string,
  flagged: boolean,
): NonNullable<SumOut["factors"]>[number] {
  return { factor: key, label, value, flagged };
}

function entry(
  ref: string,
  kind: EntryOut["kind"],
  description: string,
  amount: string,
  status: EntryOut["status"],
  label: string | null,
  lines: readonly (readonly [string, string, string, string])[],
): EntryOut {
  return {
    id: stableId(`entry:northwind:${ref}`),
    ref,
    kind,
    description,
    amount,
    status,
    threshold_result: "review_required",
    is_attest_client: true,
    approval_label: label,
    version: 1,
    lines: lines.map(([code, name, debit, credit], i) => ({
      line_no: i + 1,
      account_code: code,
      account_name: name,
      fs_line_key: null,
      debit,
      credit,
    })),
    allowed_actions:
      status === "review_required"
        ? ["proposed_entry.update", "proposed_entry.send_to_client", "proposed_entry.reject"]
        : [],
  };
}

export function aud16Entries(kind: "aje" | "rje", variant: Aud16Variant = "a"): ListPageEntryOut {
  const items =
    kind === "aje"
      ? [
          entry(
            "AJE-1",
            "aje",
            "Contributions receivable — December 26, 2025 payroll",
            "48600.00",
            variant === "b2" ? "review_required" : "client_approved",
            variant === "b2" ? null : "Client approved · Dana Kowalski · Sep 25",
            [
              ["1250", "Employer & participant contributions receivable", "48600.00", "0.00"],
              ["4100", "Participant contributions", "0.00", "33540.00"],
              ["4200", "Employer contributions", "0.00", "15060.00"],
            ],
          ),
        ]
      : [
          entry(
            "RJE-1",
            "rje",
            "Loan offsets to benefits paid",
            "14850.00",
            "client_approved",
            "Client approved · Sep 25",
            [
              ["", "Benefits paid to participants", "14850.00", "0.00"],
              ["", "Deemed distributions of participant loans", "0.00", "14850.00"],
            ],
          ),
        ];
  return { items, total: items.length };
}

export function aud16BelowCt(): ListPageMisstatementOut {
  const item: AbacusModulesAssuranceFindingsContractMisstatementOut = {
    id: stableId("misstatement:northwind:bct-1"),
    ref: "BCT-1",
    origin_ref: null,
    description: "Rollover received Dec 31, 2025, recorded Jan 2, 2026",
    type: "factual",
    nature: "misstatement",
    status: "below_ct",
    amount: "4210.00",
    finding_ref: null,
    proposed_entry_ref: null,
    allowed_actions: [],
  };
  return { items: [item], total: 1 };
}

/** O3's preview for b2: the synthetic tenant's approval template (seed content, Brightwater Hale). */
export function aud16Preview(): SendPreviewOut {
  const aje = aud16Entries("aje", "b2").items[0];
  return {
    recipient_contact_id: stableId("contact:northwind:dana-kowalski"),
    recipient_name: "Dana Kowalski",
    wording_template_version_id: stableId("template:brightwater:entry-approval:v1"),
    template_label: "Entry approval · v1",
    entries:
      aje === undefined
        ? []
        : [
            {
              id: aje.id,
              ref: aje.ref,
              amount: aje.amount,
              client_wording:
                "Please record AJE-1: contributions receivable for the December 26, 2025 payroll, 48,600.",
            },
          ],
    seen_versions: aje === undefined ? {} : { [aje.id]: aje.version },
  };
}
