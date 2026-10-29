// T-02's six screens on fixtures (T-02-T08; docs/screens/{TAX-01,TAX-02,TAX-03,TXP-12,POR-05,
// POR-13}.md): TAX-01's summary as the plan states it (T-02 §3: 79 open, 145 done, 224 TY2025
// returns, 161 extended; offices Chicago 98/35/63, Denver 64/22/42, New York 62/22/40), typed
// against the tax-returns stub. The designed rows of each screen arrive with its build (T-02-T09
// onward), from its spec, extending F-06-T02's tax-season specimen data.
import type { TaxReturnSummaryOut } from "@abacus/api-client";
import { stableId } from "./prng";

const office = (name: string): string => stableId(`office:${name.toLowerCase()}`);

export const TY2025_SUMMARY: TaxReturnSummaryOut = {
  tax_year: 2025,
  total: 224,
  open: 79,
  done: 145,
  extended: 161,
  tiles: [
    { status: "not_started", count: 2 },
    { status: "gathering", count: 8 },
    { status: "preparing", count: 9 },
    { status: "prepared", count: 17 },
    { status: "in_review", count: 15 },
    { status: "action_required", count: 11 },
    { status: "approved", count: 7 },
    { status: "awaiting_signature", count: 10 },
    { status: "filed", count: 6 },
    { status: "accepted", count: 139 },
  ],
  offices: [
    { office_id: office("Chicago"), open: 35, done: 63 },
    { office_id: office("Denver"), open: 22, done: 42 },
    { office_id: office("New York"), open: 22, done: 40 },
  ],
};

/** The open statuses (TAX-01's tiles); the rest are done. */
export const OPEN_STATUSES: ReadonlySet<string> = new Set([
  "not_started",
  "gathering",
  "preparing",
  "prepared",
  "in_review",
  "action_required",
  "approved",
  "awaiting_signature",
]);
