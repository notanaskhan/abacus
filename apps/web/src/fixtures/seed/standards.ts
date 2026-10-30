// KNW-04 Firm standards & thresholds, Brightwater Hale at E0 (Mon Sep 14, 2026, 9:24 AM CT;
// K-02-T13; docs/screens/KNW-04.md). Copy, names and figures are the handoff's (spec.md and the
// nine artboards); ids are stable. In the product these rows arrive through the import endpoints
// (K-02-T11, T18), never a constant; this file feeds fixture mode only.
//
// Owners (handoff): Priya Raman the CAS thresholds and SSARS & CAS; Daniel Reyes the tax
// checklists, review levels and BH-TAX-02; Margaret Okonkwo materiality and document confidence.
// Every version in effect was published Jan 20, 2026 (the artboards' pills); AJE thresholds v1
// was published Jan 5, 2025 and is superseded.

import type {
  StandardDetailOut,
  StandardExampleRowOut,
  StandardExamplesOut,
  StandardOut,
  StandardPersonOut,
  StandardVersionOut,
  StandardVersionSummaryOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

type Payload = StandardVersionOut["payload"];
type Kind = StandardOut["kind"];

const person = (name: string): StandardPersonOut => ({
  user_id: stableId(`user:${name.toLowerCase().replace(/[^a-z]+/g, "-")}`),
  name,
});
export const PRIYA = person("Priya Raman");
export const DANIEL = person("Daniel Reyes");
export const MARGARET = person("Margaret Okonkwo");

/** The partners who see drafts (K-02 US-3.4); everyone else reads published versions only. */
export const DRAFT_READERS: ReadonlySet<string> = new Set([
  "priya-raman",
  "daniel-reyes",
  "margaret-okonkwo",
  "thomas-whitcombe",
]);

const PUBLISHED_AT = "2026-01-20T15:00:00Z";
const EFFECTIVE = "2026-01-20";
const HASH = `sha256:${"0".repeat(64)}`;

/** A stable id per client name. */
const client = (name: string): string =>
  stableId(`client:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`);

export interface Def {
  key: string;
  kind: Kind;
  name: string;
  /** The fieldset title ("BH AJE thresholds v2"); `{v}` is the version. */
  title: string;
  owner: StandardPersonOut;
  version: number;
  payload: Payload;
  usage?: number;
  /** Checks, rows or tiers the version holds. */
  entries?: number;
  taxYear?: number;
  draft?: { version: number; taxYear?: number };
  history?: { version: number; publishedAt: string; effective: string }[];
}

function items(n: number, form: string): Extract<Payload, { kind: "review_checklist" }>["items"] {
  // The checklist's text is firm content (ADR-056); KNW-04 b shows only the count, so the
  // fixture holds keyed placeholders, never invented review steps.
  return Array.from({ length: n }, (_, i) => ({
    key: `${form.toLowerCase()}-${String(i + 1).padStart(2, "0")}`,
    section: "Checks",
    text: `Check ${String(i + 1)}`,
  }));
}

type AjeRow = Extract<Payload, { kind: "aje_thresholds" }>["rows"][number];

const limit = (account_class: string, limit_usd: number): AjeRow => ({
  account_class,
  rule: "limit",
  limit_usd,
  approver_level: "senior_or_above",
  batch: true,
});

function checklist(form: string, version: number, n: number, usage: number): Def {
  return {
    key: `bh-${form.toLowerCase()}-review-checklist`,
    kind: "review_checklist",
    name: `${form} Review Checklist`,
    title: `${form} Review Checklist v{v}`,
    owner: DANIEL,
    version,
    payload: {
      kind: "review_checklist",
      applies_to: { form, tax_year: 2025 },
      items: items(n, form),
    },
    usage,
    entries: n,
    taxYear: 2025,
  };
}

export const STANDARDS: readonly Def[] = [
  {
    ...checklist("1040", 6, 38, 162),
    draft: { version: 7, taxYear: 2026 },
  },
  checklist("1065", 4, 42, 38),
  checklist("1120-S", 3, 36, 12),
  checklist("1120", 2, 33, 5),
  checklist("1041", 2, 31, 6),
  checklist("990", 1, 29, 1),
  {
    key: "bh-review-levels",
    kind: "review_levels",
    name: "Review levels",
    title: "BH review levels v{v}",
    owner: DANIEL,
    version: 2,
    entries: 3,
    payload: {
      kind: "review_levels",
      tiers: [
        {
          tier: 1,
          name: "Standard",
          required_levels: ["L1", "L2"],
          second_partner_review: false,
          criteria: "The return meets no Tier 2 or Tier 3 criterion",
        },
        {
          tier: 2,
          name: "Elevated",
          required_levels: ["L1", "L2", "L3"],
          second_partner_review: false,
          criteria: "Entity returns, multi-state returns and returns with an open IRS notice",
        },
        {
          tier: 3,
          name: "High",
          required_levels: ["L1", "L2", "L3", "L4"],
          second_partner_review: true,
          criteria:
            "Positions needing Form 8275 disclosure, first-year complex entities, returns with K-1s to other Brightwater clients",
        },
      ],
    },
  },
  {
    key: "bh-tax-02",
    kind: "return_approval_policy",
    name: "Return approval",
    title: "BH-TAX-02",
    owner: DANIEL,
    version: 1,
    payload: {
      kind: "return_approval_policy",
      code: "BH-TAX-02",
      rule: "signing_partner_final_approval",
      applies_to: [
        "Jonah & Claire Feld",
        "Ridgeline Property Partners, LP",
        "Calloway Family Trust",
        "Marcus & Dana Whitley",
      ].map((name) => ({ client_id: client(name), approver_user_id: DANIEL.user_id })),
      export_condition: "after_final_approval",
    },
  },
  {
    key: "bh-aje-thresholds",
    kind: "aje_thresholds",
    name: "AJE thresholds",
    title: "BH AJE thresholds v{v}",
    owner: PRIYA,
    version: 2,
    entries: 7,
    history: [{ version: 1, publishedAt: "2025-01-05T15:00:00Z", effective: "2025-01-05" }],
    payload: {
      kind: "aje_thresholds",
      rows: [
        limit("Payroll accruals", 15000),
        limit("Other accrued expenses", 10000),
        limit("Prepaid expenses", 10000),
        limit("Depreciation", 10000),
        limit("Deferred revenue", 10000),
        {
          account_class: "All other classes",
          rule: "review_required",
          limit_usd: null,
          approver_level: "manager_or_partner",
          batch: false,
        },
        {
          account_class: "Attest clients",
          rule: "always_held",
          limit_usd: null,
          approver_level: "partner",
          batch: false,
        },
      ],
    },
  },
  {
    key: "bh-variance-thresholds",
    kind: "variance_thresholds",
    name: "Variance thresholds",
    title: "BH variance thresholds v{v}",
    owner: PRIYA,
    version: 3,
    entries: 3,
    payload: {
      kind: "variance_thresholds",
      rows: [
        { context: "close_flux", pct: "10", amount_usd: 2500 },
        { context: "ssars_review_analytics", pct: "10", amount_usd: 50000 },
        { context: "tax_two_year", pct: "10", amount_usd: 5000 },
      ],
    },
  },
  {
    key: "bh-materiality-ranges",
    kind: "materiality_ranges",
    name: "Materiality ranges",
    title: "BH materiality ranges v{v}",
    owner: MARGARET,
    version: 2,
    entries: 3,
    payload: {
      kind: "materiality_ranges",
      rows: [
        {
          engagement_kind: "EBP (defined contribution)",
          benchmark: "Net assets available for benefits",
          low_pct: "1.0",
          high_pct: "2.0",
        },
        {
          engagement_kind: "For-profit FS audit",
          benchmark: "Pre-tax income",
          low_pct: "3",
          high_pct: "7",
        },
        {
          engagement_kind: "Not-for-profit",
          benchmark: "Total expenses",
          low_pct: "1",
          high_pct: "2",
        },
      ],
      performance_materiality: { low_pct: "50", high_pct: "75" },
      clearly_trivial_pct: "5",
    },
  },
  {
    key: "bh-document-confidence",
    kind: "document_confidence",
    name: "Document confidence",
    title: "BH document confidence v{v}",
    owner: MARGARET,
    version: 1,
    payload: {
      kind: "document_confidence",
      hold_below_pct: "90",
      auto_accept_above_pct: "98",
      auto_accept_enabled: false,
    },
  },
  {
    key: "bh-ssars-cas",
    kind: "ssars_cas_settings",
    name: "SSARS & CAS",
    title: "SSARS & CAS",
    owner: PRIYA,
    version: 1,
    payload: { kind: "ssars_cas_settings", early_adopt_ssars27: false },
  },
] as const;

export const standardId = (key: string): string => stableId(`standard:${key}`);
export const versionId = (key: string, version: number): string =>
  stableId(`standard-version:${key}:${String(version)}`);

export function summary(
  def: Def,
  version: number,
  status: StandardVersionSummaryOut["status"],
  at: { publishedAt: string; effective: string } | null,
  current: boolean,
  taxYear?: number,
): StandardVersionSummaryOut {
  return {
    id: versionId(def.key, version),
    version,
    status,
    effective_from: at?.effective ?? null,
    published_at: at?.publishedAt ?? null,
    published_by: at === null ? null : def.owner,
    current,
    tax_year: taxYear ?? null,
  };
}

const ACTIONS_READ = ["firm_standard.read"];

/** What a persona may do with a standard: the owner drafts and publishes (`owner_of_target`). */
export function actionsFor(def: Def, persona: string): string[] {
  const owner = def.owner.name.toLowerCase().replace(/[^a-z]+/g, "-") === persona;
  return owner
    ? [...ACTIONS_READ, "firm_standard.draft", "firm_standard.import", "firm_standard.publish"]
    : ACTIONS_READ;
}

export function standardOut(def: Def, persona: string): StandardOut {
  const current = summary(
    def,
    def.version,
    "published",
    { publishedAt: PUBLISHED_AT, effective: EFFECTIVE },
    true,
    def.taxYear,
  );
  const draft =
    def.draft !== undefined && DRAFT_READERS.has(persona)
      ? summary(def, def.draft.version, "draft", null, false, def.draft.taxYear)
      : null;
  return {
    id: standardId(def.key),
    kind: def.kind,
    key: def.key,
    name: def.name,
    owner: def.owner,
    current_version: current,
    draft_version: draft,
    usage_count: def.usage ?? null,
    entries: def.entries ?? null,
    allowed_actions: actionsFor(def, persona),
  };
}

const CLIENT_NAMES: Readonly<Record<string, string>> = Object.fromEntries(
  [
    "Jonah & Claire Feld",
    "Ridgeline Property Partners, LP",
    "Calloway Family Trust",
    "Marcus & Dana Whitley",
  ].map((name) => [client(name), name]),
);

export function standardDetail(def: Def, persona: string): StandardDetailOut {
  const standard = standardOut(def, persona);
  const version: StandardVersionOut = {
    id: versionId(def.key, def.version),
    standard_id: standard.id,
    version: def.version,
    status: "published",
    effective_from: EFFECTIVE,
    payload_schema_version: 1,
    payload_hash: HASH,
    change_summary: null,
    drafted_from_version_id: def.version > 1 ? versionId(def.key, def.version - 1) : null,
    drafted_by: def.owner,
    published_by: def.owner,
    published_at: PUBLISHED_AT,
    row_version: 1,
    payload: def.payload,
  };
  // Superseded is computed, never served: an older published version is `published` and not
  // `current` (the registry's derived code, DEC-1154).
  const older = (def.history ?? []).map((h) => summary(def, h.version, "published", h, false));
  const labels: Record<string, string> =
    def.kind === "return_approval_policy"
      ? { ...CLIENT_NAMES, [DANIEL.user_id]: DANIEL.name }
      : {};
  return {
    standard,
    version,
    timeline: [
      ...(standard.draft_version === null ? [] : [standard.draft_version]),
      standard.current_version as StandardVersionSummaryOut,
      ...older,
    ],
    labels,
  };
}

const row = (r: Partial<StandardExampleRowOut> & { label: string; outcome: string }) =>
  ({
    client_id: null,
    client_name: null,
    amount_usd: null,
    detail: null,
    route: null,
    approver_name: null,
    cells: {},
    ...r,
  }) satisfies StandardExampleRowOut;

const COPPERLEAF = "Copperleaf Coffee Roasters, Inc.";

/** The example providers' rows for August 2026 (C-01, A-04, T-08 and P-03 register them later;
 * the live product shows the designed empty state until they do). */
export const EXAMPLES: Readonly<Record<string, Omit<StandardExamplesOut, "standard_id">>> = {
  "bh-aje-thresholds": {
    period: "2026-08",
    provider_registered: true,
    caption: COPPERLEAF,
    rows: [
      ["AJE-01 · Payroll accrual", 11860, "≤ $15,000 payroll accruals"],
      ["AJE-02 · Prepaid insurance", 700, "≤ $10,000 prepaid expenses"],
      ["AJE-03 · Depreciation", 2140, "≤ $10,000 depreciation"],
      ["AJE-04 · Deferred revenue (subscriptions)", 5320, "≤ $10,000 deferred revenue"],
    ]
      .map(([label, amount, detail]) =>
        row({
          client_name: COPPERLEAF,
          label: label as string,
          amount_usd: amount as number,
          outcome: "within_threshold",
          detail: detail as string,
          approver_name: "Raj Malhotra",
        }),
      )
      .concat([
        row({
          client_name: COPPERLEAF,
          label: "AJE-05 · Accrued expenses",
          amount_usd: 14900,
          outcome: "review_required",
          detail: "> $10,000",
          approver_name: "Priya Raman",
        }),
      ]),
  },
  "bh-1065-review-checklist": {
    period: "2025",
    provider_registered: true,
    caption: "1065 Review Checklist v4 · last run started 9:18 AM · Samuel Ito",
    rows: [
      row({ label: "Kestrel Ventures Fund I, LP", outcome: "passed", detail: "42 of 42" }),
      row({ label: "Bramble & Finch Design, LLC", outcome: "passed" }),
      row({ label: "Harborview Dental Properties, LP", outcome: "passed" }),
      row({ label: "Ridgeline Property Partners, LP", outcome: "exceptions", detail: "2" }),
      row({ label: "Marlowe Street Holdings, LP", outcome: "exceptions", detail: "3" }),
      row({ label: "Northgate Medical Partners, LLP", outcome: "running", detail: "31 of 42" }),
    ],
  },
  "bh-variance-thresholds": {
    period: "2026-08",
    provider_registered: true,
    caption: null,
    rows: [
      row({
        client_name: COPPERLEAF,
        label: "Copperleaf repairs & maintenance 3,200 vs 640 (+400%)",
        outcome: "over_threshold",
        detail: "over threshold, unexplained → client question",
      }),
    ],
  },
  "bh-materiality-ranges": {
    period: null,
    provider_registered: true,
    caption: null,
    rows: [
      row({
        label: "Northwind Robotics 401(k) Plan",
        amount_usd: 252200,
        outcome: "decided",
        detail: "1.5% of unadjusted net assets $16,812,400",
        approver_name: "Margaret Okonkwo",
        cells: {
          performance: "75% · $189,150",
          clearly_trivial: "5% · $12,610",
          decided_at: "Sep 14, 11:12 AM",
        },
      }),
      row({
        label: "Granite Peak Outdoor Supply",
        amount_usd: 155000,
        outcome: "blocked",
        detail: "5% of pre-tax income $3,100,000 · proposed by Accrued Agent",
        approver_name: "Margaret Okonkwo",
        cells: { performance: "75% · $116,250", clearly_trivial: "5% · $7,750" },
      }),
    ],
  },
  "bh-document-confidence": {
    period: null,
    provider_registered: true,
    caption: null,
    rows: [
      row({
        label: "Schedule of Account Balances ← BrokerWindow detail 62%",
        outcome: "held",
        detail: "held for staff",
      }),
    ],
  },
  "bh-ssars-cas": {
    period: "2026-08",
    provider_registered: true,
    caption: null,
    rows: [row({ label: "Copperleaf August 2026", outcome: "ar_c_70_preparation" })],
  },
};
