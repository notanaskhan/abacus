// T-05-T44 (TASK-7707; handoff TXP-06 A–D; docs/screens/TXP-06.md): the allocation structure as
// `GET …/allocation-structure` and `POST …/preview` answer it in fixture mode. Ridgeline (straight
// percentage, two periods of 628,100; approved, or Pending approval on Sep 8 with the reader's two
// clause citations) and Harborview (targeted waterfall, 4,900,000, plugs 900,000). Every figure is
// verbatim from the handoff; prior tiers, available and remaining are the server's. Synthetic only.
import type {
  WorkbookAllocationPartnerOut,
  WorkbookAllocationResultOut,
  WorkbookAllocationStructureOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

const rid = (k: string) => stableId(`partner:ridgeline:${k}`);
const hid = (k: string) => stableId(`partner:harborview:${k}`);
export const CITATIONS = [stableId("citation:lpa-4.1"), stableId("citation:assignment-3")];

function results(
  ids: (k: string) => string,
  rows: readonly (readonly [string, string, number | null, string])[],
): WorkbookAllocationResultOut[] {
  return rows.map(([k, period, rung, amount]) => ({
    partner_id: ids(k),
    period_key: period,
    rung_priority: rung,
    amount,
  }));
}

function partner(
  id: string,
  name: string,
  kind: WorkbookAllocationPartnerOut["kind"],
  total: string,
  extra: Partial<WorkbookAllocationPartnerOut> = {},
): WorkbookAllocationPartnerOut {
  return { partner_id: id, name, kind, total, ...extra };
}

const RIDGELINE_RESULTS = results(rid, [
  ["gp", "p1", null, "12562"],
  ["shah", "p1", null, "238678"],
  ["psv", "p1", null, "219835"],
  ["feld", "p1", null, "157025"],
  ["gp", "p2", null, "12562"],
  ["shah", "p2", null, "238678"],
  ["psv", "p2", null, "188430"],
  ["ps2", "p2", null, "31405"],
  ["feld", "p2", null, "157025"],
]);

const RIDGELINE_PARTNERS = [
  partner(rid("gp"), "Ridgeline GP LLC", "gp", "25124"),
  partner(rid("shah"), "Meera Shah", "lp", "477356"),
  partner(rid("psv"), "Pell Street Ventures LLC", "lp", "408265"),
  partner(rid("ps2"), "Pell Street II LLC", "lp", "31405"),
  partner(rid("feld"), "Jonah Feld", "lp", "314050"),
];

export function ridgeline(pending = false): WorkbookAllocationStructureOut {
  return {
    version: pending ? 1 : 2,
    latest_version: pending ? 1 : 2,
    kind: "straight_percentage",
    status: pending ? "pending_approval" : "approved",
    method: "interim_closing",
    convention: "monthly",
    proposed_by: "agent",
    income: "1256200",
    rungs: [{ key: "straight_pct", label: "Straight pct", citation_ids: CITATIONS }],
    seen_hash: `sha256:${"a".repeat(64)}`,
    allowed_actions: ["allocation_structure.edit"],
    structure_id: stableId(`allocation:ridgeline:${pending ? "1" : "2"}`),
    sign_off_target_id: stableId("allocation:ridgeline:1"),
    periods: [
      { key: "p1", starts_on: "2025-01-01", ends_on: "2025-06-30", amount: "628100" },
      { key: "p2", starts_on: "2025-07-01", ends_on: "2025-12-31", amount: "628100" },
    ],
    partners: RIDGELINE_PARTNERS,
    results: RIDGELINE_RESULTS,
    checks: { periods_foot: true, partners_foot: true },
    citation_ids: CITATIONS,
  };
}

const HARBORVIEW_PARTNERS = [
  partner(hid("hgp"), "Harborview Property GP LLC", "gp", "180000", {
    beginning: "100000",
    target: "280000",
  }),
  partner(hid("lindqvist"), "Lindqvist Family Holdings LLC", "lp", "443077", {
    beginning: "2400000",
    target: "2843077",
  }),
  partner(hid("bayridge"), "Bayridge Capital LLC", "lp", "276923", {
    beginning: "1500000",
    target: "1776923",
  }),
];

export function harborview(
  rates = { pref: "8", catchUp: "20", gp: "20" },
): WorkbookAllocationStructureOut {
  return {
    version: 1,
    latest_version: 1,
    kind: "targeted_waterfall",
    status: "approved",
    method: "interim_closing",
    convention: "calendar_day",
    proposed_by: "human",
    income: "900000",
    distributable: "4900000",
    gp_profit_percent: "20.00",
    rungs: [
      { key: "return_of_capital", label: "Return of capital", citation_ids: [] },
      {
        key: "preferred_return",
        label: "Preferred return",
        percentage: rates.pref,
        citation_ids: [],
      },
      { key: "catch_up", label: "Catch up", percentage: rates.catchUp, citation_ids: [] },
      { key: "promote", label: "Promote", percentage: rates.gp, citation_ids: [] },
    ],
    seen_hash: `sha256:${"b".repeat(64)}`,
    allowed_actions: ["allocation_structure.edit"],
    structure_id: stableId("allocation:harborview:1"),
    sign_off_target_id: stableId("allocation:harborview:1"),
    periods: [
      { key: "r1", amount: "4000000", available: "4900000", remaining: "900000" },
      { key: "r2", amount: "312000", prior: "4000000", available: "900000", remaining: "588000" },
      { key: "r3", amount: "78000", prior: "4312000", available: "588000", remaining: "510000" },
      { key: "r4", amount: "510000", prior: "4390000", available: "510000", remaining: "0" },
    ],
    partners: HARBORVIEW_PARTNERS,
    results: results(hid, [
      ["hgp", "year", 1, "100000"],
      ["lindqvist", "year", 1, "2400000"],
      ["bayridge", "year", 1, "1500000"],
      ["lindqvist", "year", 2, "192000"],
      ["bayridge", "year", 2, "120000"],
      ["hgp", "year", 3, "78000"],
      ["hgp", "year", 4, "102000"],
      ["lindqvist", "year", 4, "251077"],
      ["bayridge", "year", 4, "156923"],
    ]),
    checks: { rungs_foot: true, targets_foot: true, plugs_foot: true },
    citation_ids: [],
  };
}
