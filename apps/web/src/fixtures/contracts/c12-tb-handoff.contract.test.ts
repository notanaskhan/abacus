// T-06-T06 (DEC-5515): C12 v1 consumer fixtures for AUD-38 (audit_release) and CLS-12 (close_lock)
// (docs/contracts/c12-tb-handoff.md; SPEC-702 AC-27 to AC-31). Typed with the generated client and
// validated against the OpenAPI document. Granite Peak FY2026 and Copperleaf's December close.
// The pytest half is backend/tests/contracts/c12_tb_handoff/.
import type { TbHandoffLandingOut, TbHandoffPreviewOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { validateResponse } from "../schema-check";

const PREVIEW = "/v1/engagements/{engagement_id}/tax-handoff/preview";
const LANDING = "/v1/tax-returns/{return_id}/handoff";

const aud38a: TbHandoffPreviewOut = {
  source_kind: "audit_release",
  source_snapshot_id: "00000000-0000-4000-8000-0000000c1201",
  gate: "released",
  status: "ready",
  counts: { mapped: 121, suggested: 5, review: 2, total: 128 },
  review_accounts: [
    {
      account_ref: "2255",
      account_name: "Accrued customer loyalty rewards",
      balance: "-84600.00",
      choice: "send_blank",
      source: "tb_mapper",
    },
    {
      account_ref: "6875",
      account_name: "Small equipment expensed",
      balance: "41200.00",
      choice: "send_blank",
      source: "tb_mapper",
    },
  ],
  book_income: { pretax: "3100000.00", income_tax_expense: "750000.00", net_income: "2350000.00" },
  schedules: ["fixed_assets", "accrued_liabilities", "passed_adjustments"],
  tax_items: [],
  preview_hash: "0".repeat(63) + "1",
};

const cls12c2: TbHandoffLandingOut = {
  handoff_id: "00000000-0000-4000-8000-0000000c1202",
  source_kind: "close_lock",
  locked_close_id: "00000000-0000-4000-8000-0000000c1203",
  source_label: "TB from the December 2026 close, locked Jan 11, 2027",
  handed_off_at: "2027-01-12T20:15:00Z",
  handed_off_by: "Priya Raman",
  source_link_allowed: true,
  superseded: false,
};

describe("C12 v1 fixtures for AUD-38 and CLS-12", () => {
  it("AUD-38 a foots 121 + 5 + 2 = 128 and 3,100,000 - 750,000 = 2,350,000", () => {
    const c = aud38a.counts;
    expect(c.mapped + c.suggested + c.review).toBe(c.total);
    const cents = (s: string): number => Math.round(Number(s) * 100);
    const b = aud38a.book_income;
    expect(cents(b.pretax) - cents(b.income_tax_expense)).toBe(cents(b.net_income));
    expect(validateResponse("GET", PREVIEW, aud38a)).toEqual([]);
  });

  it("every account choice names its source", () => {
    const { source: _dropped, ...unsourced } = aud38a.review_accounts[0]!;
    const broken = { ...aud38a, review_accounts: [unsourced] };
    expect(validateResponse("GET", PREVIEW, broken)).not.toEqual([]);
  });

  it("CLS-12's close_lock landing names its locked close", () => {
    expect(validateResponse("GET", LANDING, cls12c2)).toEqual([]);
    expect(cls12c2.locked_close_id).toBeTruthy();
  });
});
