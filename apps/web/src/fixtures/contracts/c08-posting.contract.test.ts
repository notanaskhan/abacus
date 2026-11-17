// C-02-T08 (DEC-5507): C8 v2 posting consumer fixtures for CLS-07 (docs/contracts/adjustments.md
// v2; SPEC-700 AC-3, AC-4). Typed with the generated client, so a breaking change fails `tsc`,
// and checked against the OpenAPI document at run time. Copperleaf, August 2026: AJE-01..05 with
// BH AJE thresholds v2, then batch 2026-08-A (QBO 48213-48218). The pytest half is
// backend/tests/contracts/c08_adjustments/test_c02t08_posting_consumer.py.
import type { PostingCloseEntriesOut, PostingCloseEntryRowOut, PostingBatchOut } from "@abacus/api-client";
import { STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { validateResponse } from "../schema-check";

const LIST = "/v1/work-items/{work_item_id}/proposed-entries:close";
const UNDO = "/v1/posting-batches/{batch_id}/undo";
const id = (n: number): string => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
type Entry = { label: string };
const ENTRY = STATUS_REGISTRY.proposed_entry as Record<string, Entry>;
const BATCH = STATUS_REGISTRY.posting_batch as Record<string, Entry>;

const ROWS: readonly [string, string, string, string, PostingCloseEntryRowOut["status"]][] = [
  ["AJE-01", "11860.00", "payroll_accruals", "15000.00", "within_threshold"],
  ["AJE-02", "700.00", "prepaids", "10000.00", "within_threshold"],
  ["AJE-03", "2140.00", "depreciation", "10000.00", "within_threshold"],
  ["AJE-04", "5320.00", "deferred_revenue", "10000.00", "within_threshold"],
  ["AJE-05", "14900.00", "other_accruals", "10000.00", "review_required"],
];

function cents(amount: string): number {
  return Math.round(Number(amount) * 100);
}

function cls07a(): PostingCloseEntriesOut {
  const items: PostingCloseEntryRowOut[] = ROWS.map(([ref, amount, cls, limit, status], i) => ({
    entry_id: id(i + 1),
    ref,
    amount,
    status,
    class_limit: { account_class: cls, limit },
    version: 1,
    allowed_actions: [],
  }));
  const sum = (rows: PostingCloseEntryRowOut[]): string =>
    (rows.reduce((t, r) => t + cents(r.amount), 0) / 100).toFixed(2);
  const within = items.filter((r) => r.status === "within_threshold");
  const review = items.filter((r) => r.status === "review_required");
  return {
    items,
    total: items.length,
    tallies: {
      proposed: { count: items.length, amount: sum(items) },
      within_threshold: { count: within.length, amount: sum(within) },
      review_required: { count: review.length, amount: sum(review) },
      approved: 0,
      of: items.length,
    },
    approver: {
      user_id: id(90),
      display_name: "Raj Malhotra",
      role_label: "CAS Senior",
      policy_label: "BH AJE thresholds v2",
      policy_version_id: id(91),
      may_batch_within_threshold: true,
    },
    posting_enabled: true,
    is_attest_client: false,
  };
}

describe("C8 v2 fixtures for CLS-07", () => {
  it("a: the tally strip foots 5 · $34,920.00 = 4 · $20,020.00 + 1 · $14,900.00", () => {
    const page = cls07a();
    expect(page.tallies.proposed).toEqual({ count: 5, amount: "34920.00" });
    expect(page.tallies.within_threshold).toEqual({ count: 4, amount: "20020.00" });
    expect(page.tallies.review_required).toEqual({ count: 1, amount: "14900.00" });
    expect(validateResponse("GET", LIST, page)).toEqual([]);
  });

  it("g: an attest client's rows offer no Post control", () => {
    const page = { ...cls07a(), is_attest_client: true, posting_enabled: false };
    expect(page.items.flatMap((r) => r.allowed_actions ?? [])).not.toContain("posting_batch.post");
  });

  it("d: batch 2026-08-A reads Posted · QBO 48213 to 48218 and $35,300.00", () => {
    const batch: PostingBatchOut = {
      batch_id: id(800),
      batch_code: "2026-08-A",
      period: "2026-08",
      status: "posted",
      entry_count: 6,
      total_amount: "35300.00",
      first_external_ref: "48213",
      last_external_ref: "48218",
      closing_date_target: "2026-08-31",
      failure_count: 0,
      resolved_failure_count: 0,
      entries: Array.from({ length: 6 }, (_, i) => ({
        entry_id: id(i + 1),
        ref: `AJE-0${i + 1}`,
        status: "posted" as const,
        external_txn_ref: String(48213 + i),
      })),
      version: 3,
    };
    expect(cents("20020.00") + cents("14900.00") + cents("380.00")).toBe(cents("35300.00"));
    expect(validateResponse("POST", UNDO, batch)).toEqual([]);
  });

  it("speaks the registry's words for entries and batches", () => {
    expect(ENTRY.recorded_externally?.label).toBe("Recorded in ledger");
    expect(ENTRY.failed_post?.label).toBe("Failed post");
    expect(BATCH.posted?.label).toBe("Posted");
  });
});
