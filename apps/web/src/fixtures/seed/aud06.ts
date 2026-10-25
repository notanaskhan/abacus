// A-02-T05 (TASK-1215): AUD-06's artboard data in C9 v1's shapes (docs/contracts/c09-ledger.md),
// typed with the generated client. Northwind's E0 views extend A-02-T03's `northwindTbView`; Harlow
// & Pike Manufacturing's Interim TB (g) is AUD-06 revision.md verbatim; Granite Peak's FY2026 TB (h,
// empty, newer) is blueprint §9.8 with the accounts the A-02 epic §5.3 lists (inferred there). The
// fixtures stand in for the server, so they compute subtotals, ties and leadsheet changes here, in
// integer cents; a screen never sums a column (A-02 AC-2.1). The Python scenario export (F-04-T31)
// replaces these once it renders Granite Peak and Harlow & Pike.

import type {
  SnapshotOut,
  TbGroupOut,
  TbLayerLineOut,
  TbLayerViewOut,
  TbLeadsheetAreaOut,
  TbLeadsheetRowOut,
  TbNamedTotalOut,
  TbTickOut,
  TieOutCheckOut,
  TrialBalanceOut,
} from "@abacus/api-client";
import { stableId } from "./prng";
import { cents, money, northwindTbView } from "./trial-balance";

const MARCUS = { id: stableId("user:marcus-delaney"), name: "Marcus Delaney" };
const HANNAH = { id: stableId("user:hannah-leclerc"), name: "Hannah Leclerc", initials: "HL" };
const CALEB = { id: stableId("user:caleb-dunn"), name: "Caleb Dunn" };
const SIMONE = { id: stableId("user:simone-baptiste"), name: "Simone Baptiste" };

const PULLED_AT = "2026-09-14T09:26:00-05:00";
const ADOPTED_AT = "2026-09-14T10:02:00-05:00";
const OCT6_REVIEWED_AT = "2026-10-06T14:05:00-05:00";

const FUNDS = ["1110", "1120", "1130", "1140", "1150", "1160"] as const;
const NET_ASSET_ACCOUNTS = [...FUNDS, "1200", "1300"] as const;
const BROKERWINDOW = "1200";

const sum = (values: readonly (string | null)[]): bigint =>
  values.reduce((a, v) => a + (v === null ? 0n : cents(v)), 0n);

/** "1234567.89" as "1,234,567.89" (the tie formula's grammar). */
function grouped(value: bigint): string {
  const text = money(value < 0n ? -value : value);
  const [whole = "0", fraction = "00"] = text.split(".");
  return `${value < 0n ? "-" : ""}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction}`;
}

/** Δ% to 0.1 %, half-even (A-02 AC-5.1), as the server's decimal string ("20.0"). */
export function changePct(py: bigint, change: bigint): string | null {
  if (py === 0n) return null;
  const scaled = change * 1000n; // tenths of a percent, before division
  let q = scaled / py;
  const r = scaled % py;
  const twice = (r < 0n ? -r : r) * 2n;
  const den = py < 0n ? -py : py;
  if (twice > den || (twice === den && q % 2n !== 0n)) q += scaled < 0n !== py < 0n ? -1n : 1n;
  const neg = q < 0n;
  const m = neg ? -q : q;
  return `${neg ? "-" : ""}${String(m / 10n)}.${String(m % 10n)}`;
}

function lines(view: TbLayerViewOut): TbLayerLineOut[] {
  return view.groups.flatMap((g) => g.lines);
}

function regroup(
  view: TbLayerViewOut,
  edit: (line: TbLayerLineOut) => TbLayerLineOut,
  column: "eoy" | "final" = "eoy",
): TbLayerViewOut {
  const groups: TbGroupOut[] = view.groups.map((g) => {
    const of = g.lines.map(edit);
    return {
      ...g,
      lines: of,
      eoy: money(sum(of.map((l) => (column === "final" ? (l.final ?? l.eoy) : l.eoy)))),
    };
  });
  const all = groups.flatMap((g) => g.lines);
  const pick = (codes: readonly string[]) => all.filter((l) => codes.includes(l.account_code));
  const value = (l: TbLayerLineOut) => (column === "final" ? (l.final ?? l.eoy) : l.eoy);
  const totals: TbNamedTotalOut[] = view.totals.map((t) => {
    const codes =
      t.key === "mutual_funds"
        ? FUNDS
        : t.key === "investments"
          ? [...FUNDS, BROKERWINDOW]
          : [...NET_ASSET_ACCOUNTS, RECEIVABLE];
    return { ...t, eoy: money(sum(pick(codes).map(value))) };
  });
  const debit = sum(all.map(value).filter((v) => !v.startsWith("-")));
  const credit = -sum(all.map(value).filter((v) => v.startsWith("-")));
  return {
    ...view,
    groups,
    totals,
    balance: {
      layer: view.layer,
      debit: money(debit),
      credit: money(credit),
      difference: money(debit - credit),
      balanced: debit === credit,
    },
  };
}

// --- Northwind (a–f) ------------------------------------------------------------------------------

/** AUD-06a: Northwind PY2025 TB v1, adopted 10:02 AM by Marcus Delaney, three ties. */
export function aud06a(engagementId: string): TbLayerViewOut {
  return northwindTbView(engagementId);
}

/** AUD-06b: the agent's draft (9:26 AM): every agreement an outlined agent tick, no initials and
 * no review yet. C9 v1 has no pre-adoption draft shape, so provenance stays v1's (DEC-342). */
export function aud06b(engagementId: string): TbLayerViewOut {
  const view = northwindTbView(engagementId);
  return regroup(view, (l) => {
    const agreed: TbTickOut[] = (l.ticks ?? [])
      .filter((t) => t.kind === "agreed")
      .map((t) => ({
        ...t,
        actor_kind: "agent",
        by_user_id: stableId("agent:accrued"),
        by_name: "Accrued Agent",
        initials: null,
        at: PULLED_AT,
        verified: false,
      }));
    return { ...l, ticks: agreed };
  });
}

const OFF_CHECK = stableId("tie-out-check:northwind:net-assets-trust");
const OFF_ISSUE = stableId("issue:northwind:brokerwindow-eoy");

/** AUD-06c: the BrokerWindow EOY line pulled at 1,606,560.00 against the trust report's
 * 1,605,000.00 ("off 1,560.00"), flagged and linked to an issue. The pull stays balanced: the
 * 1,560.00 sits in net appreciation (DEC-342). */
export function aud06c(engagementId: string): TbLayerViewOut {
  const view = regroup(northwindTbView(engagementId), (l) => {
    if (l.account_code === BROKERWINDOW) {
      return {
        ...l,
        eoy: "1606560.00",
        flags: [{ kind: "does_not_tie", check_id: OFF_CHECK, issue_id: OFF_ISSUE }],
      };
    }
    if (l.account_code === "4200") return { ...l, eoy: money(cents(l.eoy) - 156000n) };
    return l;
  });
  return { ...view, checks: { tie: 2, off: 1, pending: 0, worst: "off" } };
}

/** The account AJE-1 debits (blueprint §9.4: contributions receivable 48,600 = 33,540 + 15,060).
 * The PY2025 TB has no such account, so the Final layer adds it (DEC-342). */
export const RECEIVABLE = "contributions_receivable";
const AJE1_PARTICIPANT = "33540.00";
const AJE1_EMPLOYER = "15060.00";

/** AUD-06d: the Final layer at Oct 6 with AJE-1 from fixture adjustments (C8 shape, A-06). */
export function aud06d(engagementId: string): TbLayerViewOut {
  const base = northwindTbView(engagementId);
  const aje1 = cents(AJE1_PARTICIPANT) + cents(AJE1_EMPLOYER);
  const reviewed = (l: TbLayerLineOut): TbTickOut[] => [
    ...(l.ticks ?? []).filter((t) => t.kind === "agreed"),
    {
      level: 2,
      kind: "reviewed",
      actor_kind: "human",
      by_user_id: HANNAH.id,
      by_name: HANNAH.name,
      initials: HANNAH.initials,
      at: OCT6_REVIEWED_AT,
      citation_id: null,
      verified: true,
    },
  ];
  const final = (l: TbLayerLineOut, aje: bigint | null): TbLayerLineOut => ({
    ...l,
    aje: aje === null ? null : money(aje),
    rje: null,
    final: money(cents(l.eoy) + (aje ?? 0n)),
    adjustment_refs: aje === null ? [] : ["AJE-1"],
    ticks: reviewed(l),
  });
  const receivable: TbLayerLineOut = {
    account_code: RECEIVABLE,
    account_name: "Contributions receivable",
    area: null,
    wp_ref: null,
    boy: null,
    eoy: "0.00",
    aje: null,
    rje: null,
    final: null,
    adjustment_refs: [],
    ticks: [],
    citation_ids: [],
    flags: [],
  };
  const at = base.groups.findIndex((g) => g.key === "participant_loans") + 1;
  const withReceivable: TbLayerViewOut = {
    ...base,
    groups: [
      ...base.groups.slice(0, at),
      {
        key: RECEIVABLE,
        label: "Contributions receivable",
        lines: [receivable],
        boy: null,
        eoy: "0.00",
      },
      ...base.groups.slice(at),
    ],
  };
  const view = regroup(
    { ...withReceivable, layer: "final", layers_available: ["unadjusted", "aje", "rje", "final"] },
    (l) => {
      if (l.account_code === RECEIVABLE) return final(l, aje1);
      if (l.account_code === "4100") return final(l, -aje1);
      return final(l, null);
    },
    "final",
  );
  return { ...view, newer_snapshots: 0 };
}

/** The AJE-1 entry the Final layer carries (Dr receivable; Cr participant and employer). */
export const AJE1 = {
  ref: "AJE-1",
  debit: { account: "Contributions receivable", amount: "48600.00" },
  credits: [
    { account: "Participant contributions", amount: AJE1_PARTICIPANT },
    { account: "Employer contributions", amount: AJE1_EMPLOYER },
  ],
} as const;

/** AUD-06e: the Investments leadsheet (statement grammar; the server's Δ and Δ%). */
export function aud06e(trialBalanceId: string): TbLeadsheetAreaOut {
  const view = northwindTbView(stableId("engagement:aud06:northwind"));
  const rows: TbLeadsheetRowOut[] = lines(view)
    .filter((l) => l.area === "Investments")
    .map((l) => {
      const py = cents(l.boy ?? "0.00");
      const cy = cents(l.eoy);
      return {
        account_code: l.account_code,
        account_name: l.account_name,
        py: l.boy,
        cy: l.eoy,
        change: money(cy - py),
        change_pct: changePct(py, cy - py),
      };
    });
  const py = sum(rows.map((r) => r.py));
  const cy = sum(rows.map((r) => r.cy));
  return {
    trial_balance_id: trialBalanceId,
    area: "Investments",
    layer: "unadjusted",
    display_unit: "cents",
    version_no: 1,
    unassigned: false,
    rows,
    py: money(py),
    cy: money(cy),
    change: money(cy - py),
    change_pct: changePct(py, cy - py),
  };
}

function check(
  key: string,
  label: string,
  kind: TieOutCheckOut["kind"],
  column: "eoy" | "boy",
  accounts: readonly string[],
  expected: string | null,
  actual: string | null,
  extra: Partial<TieOutCheckOut> = {},
): TieOutCheckOut {
  const difference = expected === null || actual === null ? null : cents(actual) - cents(expected);
  return {
    id: stableId(`tie-out-check:northwind:${key}`),
    key,
    label,
    kind,
    column,
    accounts: [...accounts],
    expected,
    negate: false,
    tolerance: "0.00",
    citation_ids: [stableId(`citation:northwind:${key}`)],
    components: [],
    defined_at: ADOPTED_AT,
    defined_by_name: MARCUS.name,
    version_no: 1,
    result: {
      status: difference === null ? "pending" : difference === 0n ? "tie" : "off",
      expected,
      actual,
      difference: difference === null ? null : money(difference < 0n ? -difference : difference),
      formula: null,
      missing: [],
    },
    ...extra,
  };
}

/** AUD-06a and c's check strip: net assets to the trust report, BOY to the PY2024 FS, loans. */
export function aud06Checks(view: TbLayerViewOut): TieOutCheckOut[] {
  const all = lines(view);
  const pick = (column: "eoy" | "boy") =>
    money(
      sum(
        all
          .filter((l) => (NET_ASSET_ACCOUNTS as readonly string[]).includes(l.account_code))
          .map((l) => l[column]),
      ),
    );
  const parts = [
    { label: "Beginning", sign: 1, value: "288500.00" },
    { label: "Draws", sign: 1, value: "96200.00" },
    { label: "Repayments", sign: -1, value: "57450.00" },
    { label: "Forgiven", sign: -1, value: "14850.00" },
  ];
  const rolled = parts.reduce((a, p) => a + BigInt(p.sign) * cents(p.value), 0n);
  const formula = `${parts
    .map((p, i) => `${i === 0 ? "" : p.sign < 0 ? " − " : " + "}${grouped(cents(p.value))}`)
    .join("")} = ${grouped(rolled)}`;
  const loans = all.find((l) => l.account_code === "1300")?.eoy ?? null;
  return [
    check(
      "net-assets-trust",
      "Net assets ↔ trust report",
      "tie",
      "eoy",
      NET_ASSET_ACCOUNTS,
      "16812400.00",
      pick("eoy"),
    ),
    check(
      "boy-py2024-fs",
      "BOY ↔ PY2024 audited FS",
      "tie",
      "boy",
      NET_ASSET_ACCOUNTS,
      "14228500.00",
      pick("boy"),
    ),
    check(
      "loan-rollforward",
      "Loan rollforward",
      "rollforward",
      "eoy",
      ["1300"],
      money(rolled),
      loans,
      {
        components: parts,
        result: {
          status: loans !== null && cents(loans) === rolled ? "tie" : "off",
          expected: money(rolled),
          actual: loans,
          difference: loans === null ? null : money(cents(loans) - rolled),
          formula,
          missing: [],
        },
      },
    ),
  ];
}

// --- Single-column TBs (g, h, empty, newer) -------------------------------------------------------

type Row = readonly [name: string, amount: string];

function slug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

function plainLine(name: string, amount: string): TbLayerLineOut {
  return {
    account_code: slug(name),
    account_name: name,
    area: null,
    wp_ref: null,
    boy: null,
    eoy: amount,
    aje: null,
    rje: null,
    final: null,
    adjustment_refs: [],
    ticks: [],
    citation_ids: [],
    flags: [],
  };
}

interface Plain {
  trialBalanceId: string;
  engagementId: string;
  label: TbLayerViewOut["label"];
  layer: TbLayerViewOut["layer"];
  periodStart: string;
  periodEnd: string;
  priorPeriodEnd: string | null;
  displayUnit: TbLayerViewOut["display_unit"];
  rows: readonly Row[];
  /** The rows the balance sheet total covers ("Total assets"). */
  assets: number;
  adopted: { at: string; by: { id: string; name: string }; pulledAt: string; source: string };
  newer?: number;
}

function plainView(p: Plain): TbLayerViewOut {
  const all = p.rows.map(([name, amount]) => plainLine(name, amount));
  const final = p.layer === "final";
  const shown = final ? all.map((l) => ({ ...l, aje: "0.00", rje: "0.00", final: l.eoy })) : all;
  const debit = sum(all.map((l) => l.eoy).filter((v) => !v.startsWith("-")));
  const credit = -sum(all.map((l) => l.eoy).filter((v) => v.startsWith("-")));
  const assets = sum(all.slice(0, p.assets).map((l) => l.eoy));
  const income = -sum(
    all
      .slice(p.assets)
      .filter((l) => isIncome(l.account_name))
      .map((l) => l.eoy),
  );
  return {
    trial_balance_id: p.trialBalanceId,
    engagement_id: p.engagementId,
    label: p.label,
    layer: p.layer,
    layers_available: final ? ["unadjusted", "aje", "rje", "final"] : ["unadjusted"],
    display_unit: p.displayUnit,
    period_start: p.periodStart,
    period_end: p.periodEnd,
    prior_period_end: p.priorPeriodEnd,
    version_no: 1,
    current_version_no: 1,
    provenance: {
      source_kind: "import",
      source: p.adopted.source,
      pulled_at: p.adopted.pulledAt,
      adopted_by_user_id: p.adopted.by.id,
      adopted_by_name: p.adopted.by.name,
      adopted_at: p.adopted.at,
    },
    groups: [
      {
        key: "all",
        label: "Accounts",
        lines: shown,
        boy: null,
        eoy: money(sum(all.map((l) => l.eoy))),
      },
    ],
    totals: [
      { key: "total_assets", label: "Total assets", boy: null, eoy: money(assets) },
      { key: "net_income", label: "Net income", boy: null, eoy: money(income) },
    ],
    balance: {
      layer: p.layer,
      debit: money(debit),
      credit: money(credit),
      difference: money(debit - credit),
      balanced: debit === credit,
    },
    checks: { tie: 1, off: 0, pending: 0, worst: "tie" },
    newer_snapshots: p.newer ?? 0,
    allowed_actions: ["trial_balance.annotate", "trial_balance.export", "tie_out_check.define"],
  };
}

/** Income-statement lines (their sum, negated, is net income). */
function isIncome(name: string): boolean {
  return /sales|revenue|cost of goods|expense|interest/iu.test(name);
}

/** AUD-06g: Harlow & Pike Manufacturing, Interim 8/31/2026, whole dollars (revision.md g). */
export const HARLOW_MANUFACTURING: readonly Row[] = [
  ["Cash", "1800000.00"],
  ["Accounts receivable", "7200000.00"],
  ["Intercompany receivable", "2400000.00"],
  ["Inventory", "9600000.00"],
  ["PP&E, net", "8400000.00"],
  ["Accounts payable", "-4600000.00"],
  ["Accrued liabilities", "-1500000.00"],
  ["Contributed capital", "-14000000.00"],
  ["Retained earnings 1/1/2026", "-5900000.00"],
  ["Net sales — third party", "-42000000.00"],
  ["Net sales — intercompany", "-18000000.00"],
  ["Cost of goods sold", "45600000.00"],
  ["Rent expense — intercompany", "1200000.00"],
  ["Operating expenses", "9800000.00"],
];

export const HARLOW_ENGAGEMENT = stableId("engagement:harlow-pike:fy2026");
export const HARLOW_TB = stableId("trial-balance:harlow-pike:manufacturing:interim:2026-08-31");

export function aud06g(): TbLayerViewOut {
  return plainView({
    trialBalanceId: HARLOW_TB,
    engagementId: HARLOW_ENGAGEMENT,
    label: "interim",
    layer: "unadjusted",
    periodStart: "2026-01-01",
    periodEnd: "2026-08-31",
    priorPeriodEnd: null,
    displayUnit: "whole_dollars",
    rows: HARLOW_MANUFACTURING,
    assets: 5,
    adopted: {
      at: "2026-09-14T15:40:00-05:00",
      by: CALEB,
      pulledAt: "2026-09-14T15:30:00-05:00",
      source: "import_accrued_template",
    },
  });
}

/** Granite Peak FY2026 (blueprint §9.8; A-02 §5.3, inferred there). */
export const GRANITE_FY2026: readonly Row[] = [
  ["Cash", "2140000.00"],
  ["Accounts receivable", "5860000.00"],
  ["Inventory", "11420000.00"],
  ["PP&E, net", "6380000.00"],
  ["Other assets", "610000.00"],
  ["Accounts payable", "-4180000.00"],
  ["Accrued liabilities", "-1630000.00"],
  ["Revolver — Front Range Bank", "-6500000.00"],
  ["Term loan", "-3200000.00"],
  ["Equity, July 1, 2025", "-7800000.00"],
  ["Revenue", "-48600000.00"],
  ["Cost of goods sold", "29160000.00"],
  ["Operating expenses", "15820000.00"],
  ["Interest expense", "520000.00"],
];

/** The re-pull after the Alpine Ridge Sports credit memo (dated 6/28, recorded 7/2; §9.8): AR
 * and revenue each 4,300.00 lower, so two lines change and the net change is 0 (DEC-342). */
export const GRANITE_FY2026_REPULL: readonly Row[] = GRANITE_FY2026.map(([name, amount]) => {
  if (name === "Accounts receivable") return [name, money(cents(amount) - 430000n)] as const;
  if (name === "Revenue") return [name, money(cents(amount) + 430000n)] as const;
  return [name, amount] as const;
});

export const GRANITE_TB = stableId("trial-balance:granite-peak:fy2026:standard");

function granite(engagementId: string, layer: "unadjusted" | "final", newer = 0): TbLayerViewOut {
  return plainView({
    trialBalanceId: GRANITE_TB,
    engagementId,
    label: "standard",
    layer,
    periodStart: "2025-07-01",
    periodEnd: "2026-06-30",
    priorPeriodEnd: "2025-06-30",
    displayUnit: "cents",
    rows: GRANITE_FY2026,
    assets: 5,
    adopted: {
      at: "2026-09-14T09:10:00-05:00",
      by: SIMONE,
      pulledAt: "2026-09-14T09:00:00-05:00",
      source: "import_netsuite_csv",
    },
    newer,
  });
}

/** AUD-06h: Granite Peak FY2026, Final layer (Nov 9, 10:15 AM CST). */
export function aud06h(engagementId: string): TbLayerViewOut {
  return granite(engagementId, "final");
}

/** The newer-TB state: v1 adopted, one adoptable newer pull. */
export function aud06Newer(engagementId: string): TbLayerViewOut {
  return granite(engagementId, "unadjusted", 1);
}

export function graniteTrialBalance(): TrialBalanceOut {
  return {
    id: GRANITE_TB,
    label: "standard",
    display_unit: "cents",
    period_start: "2025-07-01",
    period_end: "2026-06-30",
    current_version_no: 1,
  };
}

/** A pulled snapshot as the list and candidates read it; `against` counts the changed lines. */
export function snapshotOf(
  id: string,
  rows: readonly Row[],
  pulledAt: string,
  against?: readonly Row[],
): SnapshotOut {
  const debit = sum(rows.map(([, a]) => a).filter((a) => !a.startsWith("-")));
  const credit = -sum(rows.map(([, a]) => a).filter((a) => a.startsWith("-")));
  const before = new Map(against?.map(([n, a]) => [n, a]));
  const changed = against === undefined ? null : rows.filter(([n, a]) => before.get(n) !== a);
  return {
    id,
    period_start: "2025-07-01",
    period_end: "2026-06-30",
    pulled_at: pulledAt,
    source: "import_netsuite_csv",
    line_count: rows.length,
    total_debit: money(debit),
    total_credit: money(credit),
    lines_changed: changed === null ? null : changed.length,
    net_change:
      changed === null
        ? null
        : money(sum(changed.map(([n, a]) => money(cents(a) - cents(before.get(n) ?? "0.00"))))),
  };
}
