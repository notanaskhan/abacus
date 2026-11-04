// EBP-04 Contributions & remittance timeliness (A-05-T31): Northwind PY2025 as A-05-T30's reads return
// it. Card A and the late remittance are verbatim from the handoff spec: 878,400 + 392,100 =
// 1,270,500; − 48,600 = 1,221,900; + 96,400 = 1,318,300; + 48,600 = 1,366,900. Dec 26, 2025 →
// Jan 9, 2026 is 9 business days; lost earnings 33,540.00 × [(1 + 7%/365)^10 − 1] = 64.38. The 26
// payrolls run every 14 days from Jan 10, 2025; the handoff gives the first 20 only as totals
// (675,200 deferrals, 301,100 match), so each carries an equal share (33,760 / 15,055), and the
// pre-tax / Roth split is not drawn per payroll. f is the correction a person recorded on Sep 30.
// Dev and test only.

import type { FiguresOut, LateRemittanceOut, PayrollOut, TestGridOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type Ebp04Variant = "a" | "e" | "f";

// pay date, deferrals, match, deposited, total (the handoff's last five on-time payrolls)
const LAST: readonly (readonly [string, string, string, string, string])[] = [
  ["2025-10-17", "33780.00", "15120.00", "2025-10-21", "48900.00"],
  ["2025-10-31", "33910.00", "15180.00", "2025-11-04", "49090.00"],
  ["2025-11-14", "33650.00", "15050.00", "2025-11-18", "48700.00"],
  ["2025-11-28", "33720.00", "15090.00", "2025-12-02", "48810.00"],
  ["2025-12-12", "34600.00", "15500.00", "2025-12-16", "50100.00"],
];

function day(iso: string, plus: number): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + plus);
  return d.toISOString().slice(0, 10);
}

function payroll(
  on: string,
  deferrals: string,
  match: string,
  deposited: string,
  lag: number,
  calendar: number,
  late: boolean,
  total: string,
): PayrollOut {
  return {
    id: stableId(`payroll:northwind:${on}`),
    pay_date: on,
    deposit_date: deposited,
    deferrals_pretax: deferrals,
    deferrals_roth: "0.00",
    deferrals,
    match,
    total,
    business_day_lag: lag,
    calendar_lag: calendar,
    late,
  };
}

export function ebp04Payrolls(): PayrollOut[] {
  const first = Array.from({ length: 20 }, (_, i) => {
    const on = day("2025-01-10", i * 14);
    return payroll(on, "33760.00", "15055.00", day(on, 4), 2, 4, false, "48815.00");
  });
  const last = LAST.map(([on, d, m, dep, total]) => payroll(on, d, m, dep, 2, 4, false, total));
  return [
    ...first,
    ...last,
    payroll("2025-12-26", "33540.00", "15060.00", "2026-01-09", 9, 14, true, "48600.00"),
  ];
}

export function ebp04Late(variant: Ebp04Variant = "a"): LateRemittanceOut[] {
  return [
    {
      id: stableId("late-remittance:northwind:2025-12-26"),
      payroll_date: "2025-12-26",
      deposited_on: "2026-01-09",
      amount: "33540.00",
      business_days: 9,
      calendar_days: 10,
      established_practice_days: 2,
      lost_earnings: "64.38",
      status: variant === "f" ? "corrected" : "found",
      form_5330: variant === "f" ? "not_required" : "exposure",
    },
  ];
}

export function ebp04Figures(variant: Ebp04Variant = "a"): FiguresOut {
  const row = (key: string, label: string, amount: string | null, note: string | null = null) => ({
    key,
    label,
    amount,
    note,
    status: null,
  });
  return {
    title: "Contributions per financial statements",
    rows: [
      {
        key: "tie.payroll_trust",
        label: "Payroll → trust",
        amount: null,
        note: null,
        status: "tie",
      },
      { key: "tie.trust_fs", label: "Trust → FS", amount: null, note: null, status: "tie" },
      { key: "tie.w3", label: "W-3 Box 12", amount: null, note: null, status: "tie" },
      row(
        "deferrals",
        "Participant deferrals per PayGrid register (26 payrolls)",
        "878400.00",
        "pre-tax $746,600.00 · Roth $131,800.00 = W-3 Box 12 D / AA",
      ),
      row("match", "Employer QACA match per payroll calculation", "392100.00"),
      row("total_payroll", "Total per payroll", "1270500.00"),
      row("less_late", "Less Dec 26, 2025 payroll deposited Jan 9, 2026", "-48600.00"),
      row("trust_receipts", "Payroll-sourced receipts per trust, 2025", "1221900.00"),
      row("rollovers", "Rollover contributions", "96400.00"),
      row("total_trust", "Contributions per trust report", "1318300.00"),
      row(
        "receivable_aje1",
        "Contributions receivable at Dec 31, 2025 (AJE-1)",
        "48600.00",
        variant === "a" ? "Proposed to client" : "Client approved",
      ),
    ],
    total: "1366900.00",
    allowed_actions: ["ebp_correction.record", "ebp_schedule.draft"],
  };
}

export function ebp04Schedule(variant: Ebp04Variant = "a"): FiguresOut {
  const corrected = variant === "f";
  return {
    title: "Schedule H line 4a",
    rows: [
      {
        key: "transferred_late",
        label: "Participant contributions transferred late to plan",
        amount: "33540.00",
        note: null,
        status: null,
      },
      {
        key: "late_loans",
        label: "Late loan repayments included · No",
        amount: null,
        note: null,
        status: null,
      },
      {
        key: "not_corrected",
        label: "Contributions not corrected",
        amount: null,
        note: null,
        status: null,
      },
      {
        key: "outside_vfcp",
        label: "Contributions corrected outside VFCP",
        amount: null,
        note: null,
        status: null,
      },
      {
        key: "pending_vfcp",
        label: "Contributions pending correction in VFCP",
        amount: corrected ? null : "33540.00",
        note: null,
        status: null,
      },
      {
        key: "fully_corrected",
        label: "Total fully corrected under VFCP and PTE 2002-51",
        amount: corrected ? "33540.00" : null,
        note: null,
        status: null,
      },
    ],
    total: null,
    allowed_actions: ["ebp_schedule.draft"],
  };
}

/** c (A-05-T32): the 25 EBP-03 sample participants' deferral and match recalculation. Compensation
 * is synthetic (the handoff gives none): 52,000 + 1,850 per position; code's recalculated deferral
 * is 6% and the QACA match 3.5% of compensation (100% of 1% + 50% of the next 5%). Rows 8 and 15
 * missed deferrals after a late entry and trace to their EBP-03 items. Seed arithmetic only. */
export function ebp04Test(): TestGridOut {
  const rows = Array.from({ length: 25 }, (_, i) => {
    const position = i + 1;
    const comp = 52000 + position * 1850;
    const flagged = position === 8 || position === 15;
    // Integer cents, written as decimal strings (the API's shape).
    const text = (cents: number): string =>
      `${String(Math.floor(cents / 100))}.${String(cents % 100).padStart(2, "0")}`;
    const cell = (key: string, value: number, expected: number, exception = false) => ({
      attribute_key: key,
      result: exception ? ("exception" as const) : ("pass" as const),
      by: "system" as const,
      citation_ids: [],
      value: text(Math.round(value)),
      expected: text(Math.round(expected)),
    });
    const deferral = comp * 6; // cents: 6% of compensation
    const match = comp * 3.5; // cents: 3.5% of compensation
    return {
      position,
      item_id: stableId(`test:northwind:contributions:${String(position)}`),
      record_key: `NW-${String(1183 + position)}`,
      state: flagged ? "exception" : "pass",
      cells: [
        cell("compensation", comp * 100, comp * 100),
        cell("deferral", flagged ? deferral * 0.75 : deferral, deferral, flagged),
        cell("match", flagged ? match * 0.75 : match, match, flagged),
      ],
      linked_item_id: flagged
        ? stableId(`sample:northwind:eligibility:${String(position)}`)
        : null,
    };
  });
  return {
    test_id: stableId("test:northwind:contributions"),
    variant: "contributions_recalc",
    attributes: ["compensation", "deferral", "match"],
    rows,
    counts: { pass: 23, exception: 2 },
    version_no: 1,
  };
}
