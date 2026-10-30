// CLI-05 a and b: the Whitleys' transcripts as `GET /v1/client-entities/{id}/transcripts` and
// `GET /v1/transcripts/{id}/comparison` answer them (T-01-T50; T-01-T43's routes; DEC-1652). The
// register is the spec's four pulls (Kevin Osei, Sep 14, 9:05 and 9:06 AM, under the Form 8821);
// the comparison is the TY2024 Wage & Income transcript against the return as filed, computed by
// code on the server: Front Range Bank 1,870.00 and Lakeview Credit Union 1,250.00 not on the
// return (3,120.00), four other information returns agreeing. Amounts are decimal strings.
import type { TranscriptComparisonOut, TranscriptOut } from "@abacus/api-client";
import { stableId } from "./prng";
import { WHITLEY_DIFFERENCES, WHITLEY_TOTAL_CENTS } from "./tax-compliance";

const cents = (n: number): string =>
  `${String(Math.trunc(n / 100))}.${String(n % 100).padStart(2, "0")}`;

export const WI_2024 = stableId("transcript:whitley-wi-2024");
export const ACCOUNT_2024 = stableId("transcript:whitley-account-2024");
export const WI_2025 = stableId("transcript:whitley-wi-2025");
export const ACCOUNT_2025 = stableId("transcript:whitley-account-2025");
export const WHITLEY_2024_RETURN = stableId("tax-return:whitley-2024-1040");

const pulled = (minute: string): Pick<TranscriptOut, "pulled_at" | "pulled_by_name"> => ({
  pulled_at: `2026-09-14T09:${minute}:00-05:00`,
  pulled_by_name: "Kevin Osei",
});

export const WHITLEY_TRANSCRIPTS: readonly TranscriptOut[] = [
  {
    id: WI_2024,
    kind: "wage_income",
    tax_year: 2024,
    ...pulled("05"),
    parse_status: "parsed",
    authorization_form: "8821",
    result: "differences",
    difference_count: WHITLEY_DIFFERENCES.length,
    key_transaction: null,
    account_balance: null,
  },
  {
    id: ACCOUNT_2024,
    kind: "account",
    tax_year: 2024,
    ...pulled("05"),
    parse_status: "parsed",
    authorization_form: "8821",
    result: null,
    difference_count: null,
    key_transaction: { code: "922", posted_on: "2026-08-24" },
    account_balance: "0.00",
  },
  {
    id: WI_2025,
    kind: "wage_income",
    tax_year: 2025,
    ...pulled("06"),
    parse_status: "parsed",
    authorization_form: "8821",
    result: "agrees",
    difference_count: 0,
    key_transaction: null,
    account_balance: null,
  },
  {
    id: ACCOUNT_2025,
    kind: "account",
    tax_year: 2025,
    ...pulled("06"),
    parse_status: "parsed",
    authorization_form: "8821",
    result: null,
    difference_count: null,
    key_transaction: { code: "150", posted_on: "2026-04-10" },
    account_balance: "0.00",
  },
];

const PAYERS = ["Front Range Bank", "Lakeview Credit Union"] as const;

export const WHITLEY_COMPARISON_2024: TranscriptComparisonOut = {
  id: stableId("transcript-comparison:whitley-wi-2024"),
  transcript_id: WI_2024,
  return_id: WHITLEY_2024_RETURN,
  result: "differences",
  difference_total: cents(WHITLEY_TOTAL_CENTS),
  lines: WHITLEY_DIFFERENCES.map((d, i) => ({
    form: d.form,
    payer_name: PAYERS[i] ?? null,
    transcript_amount: cents(d.cents),
    return_amount: null,
    matched: false,
    line_no: 36 + i * 7,
    difference: cents(d.cents),
    status: "not_on_return",
  })),
  agreeing: [
    { form: "W-2", count: 2 },
    { form: "1098", count: 1 },
    { form: "1099-INT", count: 1 },
  ],
  checkpoint_id: stableId("checkpoint:whitley-2024-engine-import"),
  engine_version: "transcripts-v1",
  computed_at: "2026-09-14T09:07:00-05:00",
};
