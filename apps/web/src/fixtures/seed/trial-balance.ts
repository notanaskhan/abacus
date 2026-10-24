// A-02-T03 (TASK-1186): Northwind's AUD-06 trial balance in C9 v1's view-by-layer shape
// (docs/contracts/c09-ledger.md), typed with the generated client, for fixture mode and the C9
// consumer tests. Seed-derived: the lines are the seed's trust-basis trial balance
// (`SPECIMEN_SEED.NORTHWIND_TB`, from documents.py `_TB_LINES`, blueprint §9.4) and the BOY column
// is the Harborline Trust Company report's 1/1/2025 column (documents.py `_NET_ASSETS`). The
// fixture stands in for the server, so it computes the subtotals and totals here, in integer
// cents; a screen never sums a column (A-02 AC-2.1). The AUD-06 a–h scenarios are A-02-T05's.

import type {
  TbGroupOut,
  TbLayerLineOut,
  TbLayerViewOut,
  TbNamedTotalOut,
  TbTickOut,
} from "@abacus/api-client";
import { SPECIMEN_SEED } from "@abacus/ui/specimens";
import { stableId } from "./prng";

/** Harborline's 1/1/2025 column, per account (documents.py `_NET_ASSETS`). */
const BOY: Readonly<Record<string, string>> = {
  "1110": "5102300.00",
  "1120": "2011640.00",
  "1130": "2388970.00",
  "1140": "1276090.00",
  "1150": "868000.00",
  "1160": "1036000.00",
  "1200": "1257000.00",
  "1300": "288500.00",
};
const FUNDS = ["1110", "1120", "1130", "1140", "1150", "1160"] as const;
const INVESTMENTS = [...FUNDS, "1200"] as const;
const LOANS = ["1300"] as const;

// The E0 day (Mon Sep 14, 2026, CDT): pulled 9:26 AM, adopted 10:02 AM, fund lines reviewed 2:05 PM.
const PULLED_AT = "2026-09-14T09:26:00-05:00";
const ADOPTED_AT = "2026-09-14T10:02:00-05:00";
const AGREED_AT = "2026-09-14T11:40:00-05:00";
const REVIEWED_AT = "2026-09-14T14:05:00-05:00";
const MARCUS = { id: stableId("user:marcus-delaney"), name: "Marcus Delaney", initials: "MD" };
const HANNAH = { id: stableId("user:hannah-leclerc"), name: "Hannah Leclerc", initials: "HL" };

/** A decimal string ("6120450.00", "-17800.00") as integer cents. */
export function cents(value: string): bigint {
  const negative = value.startsWith("-");
  const [whole = "0", fraction = ""] = (negative ? value.slice(1) : value).split(".");
  const magnitude = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0").slice(0, 2));
  return negative ? -magnitude : magnitude;
}

/** Integer cents as the server's decimal string. */
export function money(value: bigint): string {
  const negative = value < 0n;
  const magnitude = negative ? -value : value;
  const fraction = String(magnitude % 100n).padStart(2, "0");
  return `${negative ? "-" : ""}${String(magnitude / 100n)}.${fraction}`;
}

const sum = (values: readonly string[]): bigint => values.reduce((a, v) => a + cents(v), 0n);

function ticks(code: string): TbTickOut[] {
  if (!(FUNDS as readonly string[]).includes(code)) return [];
  const citation = stableId(`citation:northwind:harborline:${code}`);
  return [
    {
      level: 1,
      kind: "agreed",
      actor_kind: "human",
      by_user_id: MARCUS.id,
      by_name: MARCUS.name,
      initials: MARCUS.initials,
      at: AGREED_AT,
      citation_id: citation,
      verified: true,
    },
    {
      level: 2,
      kind: "reviewed",
      actor_kind: "human",
      by_user_id: HANNAH.id,
      by_name: HANNAH.name,
      initials: HANNAH.initials,
      at: REVIEWED_AT,
      citation_id: null,
      verified: true,
    },
  ];
}

function lines(): TbLayerLineOut[] {
  return SPECIMEN_SEED.NORTHWIND_TB.map(([code, name, debit, credit]) => {
    const eoy = (debit === "" ? 0n : cents(debit)) - (credit === "" ? 0n : cents(credit));
    const boy = BOY[code];
    const tick = ticks(code);
    return {
      account_code: code,
      account_name: name,
      area: (INVESTMENTS as readonly string[]).includes(code) ? "Investments" : null,
      wp_ref: null,
      boy: boy ?? null,
      eoy: money(eoy),
      aje: null,
      rje: null,
      final: null,
      adjustment_refs: [],
      ticks: tick,
      citation_ids: tick.flatMap((t) => (t.citation_id === null ? [] : [t.citation_id])),
      flags: [],
    };
  });
}

function group(key: string, label: string, of: readonly TbLayerLineOut[]): TbGroupOut {
  const boys = of.map((l) => l.boy);
  return {
    key,
    label,
    lines: [...of],
    boy: boys.every((b) => b !== null) ? money(sum(boys)) : null,
    eoy: money(sum(of.map((l) => l.eoy))),
  };
}

function total(key: string, label: string, of: readonly TbLayerLineOut[]): TbNamedTotalOut {
  return {
    key,
    label,
    boy: money(sum(of.map((l) => l.boy ?? "0.00"))),
    eoy: money(sum(of.map((l) => l.eoy))),
  };
}

/** AUD-06's Unadjusted view of Northwind's PY2025 trial balance, version 1, at E0. */
export function northwindTbView(engagementId: string): TbLayerViewOut {
  const all = lines();
  const pick = (codes: readonly string[]) => all.filter((l) => codes.includes(l.account_code));
  const investments = pick(INVESTMENTS);
  const loans = pick(LOANS);
  const changes = all.filter((l) => !investments.includes(l) && !loans.includes(l));
  const debit = sum(SPECIMEN_SEED.NORTHWIND_TB.flatMap(([, , d]) => (d === "" ? [] : [d])));
  const credit = sum(SPECIMEN_SEED.NORTHWIND_TB.flatMap(([, , , c]) => (c === "" ? [] : [c])));
  return {
    trial_balance_id: stableId("trial-balance:northwind:2025:standard"),
    engagement_id: engagementId,
    label: "standard",
    layer: "unadjusted",
    layers_available: ["unadjusted"],
    display_unit: "cents",
    period_start: "2025-01-01",
    period_end: "2025-12-31",
    prior_period_end: "2024-12-31",
    version_no: 1,
    current_version_no: 1,
    provenance: {
      source_kind: "import",
      source: "import_accrued_template",
      pulled_at: PULLED_AT,
      adopted_by_user_id: MARCUS.id,
      adopted_by_name: MARCUS.name,
      adopted_at: ADOPTED_AT,
    },
    groups: [
      group("investments", "Investments at fair value", investments),
      group("participant_loans", "Notes receivable from participants", loans),
      group("net_assets_and_changes", "Net assets and changes in net assets", changes),
    ],
    totals: [
      total("mutual_funds", "Total mutual funds & CITs", pick(FUNDS)),
      total("investments", "Total investments at fair value", investments),
      total("net_assets", "Net assets available for benefits", [...investments, ...loans]),
    ],
    balance: {
      layer: "unadjusted",
      debit: money(debit),
      credit: money(credit),
      difference: money(debit - credit),
      balanced: debit === credit,
    },
    checks: { tie: 3, off: 0, pending: 0, worst: "tie" },
    newer_snapshots: 0,
    allowed_actions: [
      "trial_balance.annotate",
      "trial_balance.export",
      "tie_out_check.define",
      "sign_off.review",
    ],
  };
}
