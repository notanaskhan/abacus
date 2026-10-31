// AUD-31 in fixture mode (A-03-T12; docs/screens/AUD-31.md; the AUD-31 handoff f and the composed
// a′–e′): Granite Peak Outdoor Supply's FY2026 mapping set over the TB lines AUD-06's fixture
// already carries (blueprint §9.8; seed/aud06.ts GRANITE_FY2026), in C9 v2's shapes. The 128
// accounts and BH FS groupings v1's own lines are client and firm content A-03-T16 loads through
// the import endpoints (DEC-1555): until then each Granite TB line stands for its accounts and
// each grouping carries one FS line named as the TB line, so nothing is invented. The summary's
// tallies are granitePeakMapping()'s (128 of 128, TB balanced 1 of 1). The fixture stands in for
// the server, so it computes the subtotals (integer cents); the screen sums nothing.

import type {
  AccountMappingOut,
  FsLineOptionOut,
  GroupSubtotalOut,
  GroupingLinesOut,
  GroupingSetSummaryOut,
  MappingRunOut,
  MappingSetOut,
  MappingSetSummaryOut,
} from "@abacus/api-client";
import { GRANITE_FY2026, GRANITE_TB } from "./aud06";
import { stableId } from "./prng";
import { granitePeakMapping } from "./sampling";
import { cents, money } from "./trial-balance";

type Klass = FsLineOptionOut["class"];

/** BH FS groupings v1's groupings the Granite lines fall in, in the statement's order. */
export const GROUPINGS: readonly { key: string; label: string; class: Klass }[] = [
  { key: "cash", label: "Cash", class: "assets" },
  { key: "accounts_receivable", label: "Accounts receivable", class: "assets" },
  { key: "inventory", label: "Inventory", class: "assets" },
  { key: "ppe", label: "Property, plant & equipment", class: "assets" },
  { key: "other_assets", label: "Other assets", class: "assets" },
  { key: "accounts_payable", label: "Accounts payable", class: "liabilities" },
  { key: "accrued_liabilities", label: "Accrued liabilities", class: "liabilities" },
  { key: "debt", label: "Debt", class: "liabilities" },
  { key: "equity", label: "Equity", class: "equity" },
  { key: "revenue", label: "Revenue", class: "revenue" },
  { key: "cogs", label: "Cost of goods sold", class: "expenses" },
  { key: "operating_expenses", label: "Operating expenses", class: "expenses" },
  { key: "interest", label: "Interest", class: "expenses" },
];

/** Which grouping each Granite TB line maps to (the handoff's grouping words). */
const GROUPING_OF: Readonly<Record<string, string>> = {
  Cash: "cash",
  "Accounts receivable": "accounts_receivable",
  Inventory: "inventory",
  "PP&E, net": "ppe",
  "Other assets": "other_assets",
  "Accounts payable": "accounts_payable",
  "Accrued liabilities": "accrued_liabilities",
  "Revolver — Front Range Bank": "debt",
  "Term loan": "debt",
  "Equity, July 1, 2025": "equity",
  Revenue: "revenue",
  "Cost of goods sold": "cogs",
  "Operating expenses": "operating_expenses",
  "Interest expense": "interest",
};

const slug = (name: string): string =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");

/** One FS line per Granite TB line, under its grouping. */
export const FS_LINES: readonly FsLineOptionOut[] = GRANITE_FY2026.map(([name]) => {
  const g = GROUPINGS.find((x) => x.key === GROUPING_OF[name]) ?? GROUPINGS[0];
  return {
    id: stableId(`fs-line:bh-fs-groupings:1:${slug(name)}`),
    key: slug(name),
    label: name,
    class: g?.class ?? "assets",
    grouping_key: g?.key ?? "cash",
    grouping_label: g?.label ?? "Cash",
    normal_balance: g?.class === "assets" || g?.class === "expenses" ? "debit" : "credit",
  };
});

export const GRANITE_MAPPING = granitePeakMapping().id;
export const GROUPING_SET = stableId("grouping-set:bh-fs-groupings");
const CALEB = stableId("user:caleb-dunn");
const CONFIRMED_SEP_11 = "2026-09-11T16:20:00Z";

export type Aud31Variant = "f" | "a2" | "b2" | "c2" | "d2" | "e2";

/** The account a′ leaves for review (no TB mapper: no suggestion), and c′ maps by hand. */
export const REVIEW_ACCOUNT = slug("Other assets");

function row(name: string, amount: string, variant: Aud31Variant): AccountMappingOut {
  const line = FS_LINES.find((l) => l.label === name);
  const code = slug(name);
  const pending = code === REVIEW_ACCOUNT && variant === "a2";
  const edited = code === REVIEW_ACCOUNT && (variant === "c2" || variant === "d2");
  return {
    account_code: code,
    account_name: name,
    balance: amount,
    citation_match_id: `ev:${GRANITE_TB}#row:${code}`,
    state: pending ? "unmapped" : edited ? "edited" : "rule",
    fs_line_id: pending ? null : (line?.id ?? null),
    fs_line_label: pending ? null : (line?.label ?? null),
    grouping_label: pending ? null : (line?.grouping_label ?? null),
    method: pending
      ? null
      : edited
        ? "manual"
        : code === REVIEW_ACCOUNT
          ? "number_range"
          : "prior_year_match",
    confidence: pending || edited ? null : code === REVIEW_ACCOUNT ? "medium" : "high",
    edited_at: edited ? "2026-09-14T16:44:00Z" : null,
    edited_by_initials: edited ? "CD" : null,
    was_fs_line_label: null,
    seen_version: edited ? 2 : 1,
  };
}

function subtotals(rows: readonly AccountMappingOut[]): GroupSubtotalOut[] {
  return GROUPINGS.flatMap((g) => {
    const mine = rows.filter((r) => r.grouping_label === g.label);
    if (mine.length === 0) return [];
    const total = money(mine.reduce((s, r) => s + cents(r.balance), 0n));
    // Each Granite TB line is its own source line here, so every grouping ties.
    return [
      {
        grouping_key: g.key,
        grouping_label: g.label,
        subtotal: total,
        source_total: total,
        off: null,
      },
    ];
  });
}

export function aud31Summary(variant: Aud31Variant): MappingSetSummaryOut {
  const base = granitePeakMapping();
  const review = variant === "a2" ? 1 : 0;
  const status: MappingSetSummaryOut["status"] =
    variant === "e2"
      ? "changed_after_sign_off"
      : variant === "f" || variant === "d2"
        ? "prepared"
        : "in_progress";
  const signed = variant === "f" || variant === "e2";
  return {
    ...base,
    trial_balance_id: GRANITE_TB,
    run_status: variant === "b2" ? "running" : "ready",
    status,
    tallies: {
      ...base.tallies,
      mapped: base.tallies.accounts - review,
      need_review: review,
      edited: variant === "c2" || variant === "d2" ? 1 : null,
    },
    sign_offs:
      variant === "d2"
        ? [
            {
              level: 1,
              initials: "CD",
              name: "Caleb Dunn",
              at: "2026-09-14T16:58:00Z",
              stale: false,
            },
          ]
        : signed
          ? [
              {
                level: 1,
                initials: "CD",
                name: "Caleb Dunn",
                at: CONFIRMED_SEP_11,
                stale: variant === "e2",
              },
            ]
          : [],
  };
}

export function aud31Set(variant: Aud31Variant): MappingSetOut {
  const rows = GRANITE_FY2026.map(([name, amount]) => row(name, amount, variant));
  const confirmed = variant === "f" || variant === "d2";
  return {
    summary: aud31Summary(variant),
    rows,
    subtotals: subtotals(rows),
    allowed_actions: confirmed
      ? ["sign_off.review"]
      : ["mapping_set.run", "mapping_set.confirm", "account_mapping.edit"],
  };
}

/** b′: the rules running (10:50 AM), 78 of 128 (61%). */
export function aud31Run(variant: Aud31Variant): MappingRunOut {
  return variant === "b2"
    ? {
        mapping_set_id: GRANITE_MAPPING,
        run_status: "running",
        run_done: 78,
        run_total: 128,
        failure_code: null,
      }
    : {
        mapping_set_id: GRANITE_MAPPING,
        run_status: "ready",
        run_done: 128,
        run_total: 128,
        failure_code: null,
      };
}

export function groupingCatalogue(): GroupingSetSummaryOut[] {
  return [
    {
      id: GROUPING_SET,
      key: "bh_fs_groupings",
      name: "BH FS groupings",
      current_version_no: 1,
      versions: [
        {
          id: granitePeakMapping().grouping_set_version_id,
          version_no: 1,
          status: "published",
          effective_from: "2026-07-01",
          published_at: "2026-08-03T15:00:00Z",
          published_by_name: "Margaret Okonkwo",
          problems: 0,
        },
      ],
    },
  ];
}

/** The Change picker's lines: by class, then grouping, with Caleb's recently used. */
export function groupingLines(): GroupingLinesOut {
  const classes: Klass[] = ["assets", "liabilities", "equity", "revenue", "expenses"];
  return {
    grouping_set_id: GROUPING_SET,
    version_id: granitePeakMapping().grouping_set_version_id,
    version_no: 1,
    classes: classes.map((k) => ({
      class: k,
      groupings: GROUPINGS.filter((g) => g.class === k).map((g) => ({
        key: g.key,
        label: g.label,
        lines: FS_LINES.filter((l) => l.grouping_key === g.key),
      })),
    })),
    recently_used: FS_LINES.filter(
      (l) => l.grouping_key === "ppe" || l.grouping_key === "other_assets",
    ),
  };
}

export { CALEB };
