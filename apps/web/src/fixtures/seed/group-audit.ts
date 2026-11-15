// Harlow & Pike FY2026 group audit (A-09-T06/T07; SPEC-658; A-09 §5.4), typed with the generated
// shapes of the A-09 stubs. Figures are the handoff's (AUD-31 to AUD-35, POR-23 spec.md) and the
// backend's `assurance/group_fixtures.py`; every total here is computed in whole cents from the
// entity columns and the eliminations, never typed (the contract test foots them). The live values
// come from the consolidation engine (A-09-T13) once the services land.
import type {
  ComponentRoomOut,
  ConsolidatedTbOut,
  ConsolidationOut,
  EliminationOut,
  EliminationsOut,
  GroupScopingOut,
  TbRowOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const ENTITY_KEYS = [
  "holdings",
  "operating",
  "manufacturing",
  "distribution",
  "real_estate",
] as const;
export type EntityKey = (typeof ENTITY_KEYS)[number];
export const ENTITY_NAMES: Record<EntityKey, string> = {
  holdings: "Harlow & Pike Holdings, Inc.",
  operating: "Harlow & Pike Operating Co.",
  manufacturing: "Harlow & Pike Manufacturing, Inc.",
  distribution: "Harlow & Pike Distribution, Inc.",
  real_estate: "Harlow & Pike Real Estate, LLC",
};
const ids = (label: string) => stableId(`group:harlow-pike:${label}`);
export const GROUP_IDS = {
  consolidation: ids("consolidation"),
  workItem: ids("work-item:a28"),
  room: ids("component-room:distribution"),
} as const;

type Section = TbRowOut["section"];
type Amounts = readonly [number, number, number, number, number]; // whole dollars, debit positive
// AUD-33 a: (caption, section, Holdings, Operating Co., Manufacturing, Distribution, Real Estate)
export const TB_ROWS: readonly [string, Section, Amounts][] = [
  ["Cash", "assets", [2_600_000, 0, 1_800_000, 1_400_000, 300_000]],
  ["Accounts receivable", "assets", [0, 0, 7_200_000, 4_100_000, 0]],
  ["Intercompany receivable", "assets", [0, 0, 2_400_000, 0, 0]],
  ["Inventory", "assets", [0, 0, 9_600_000, 6_300_000, 0]],
  ["Property, plant & equipment, net", "assets", [0, 0, 8_400_000, 1_200_000, 8_100_000]],
  ["Investment in Operating Co.", "assets", [20_000_000, 0, 0, 0, 0]],
  ["Investment in Real Estate", "assets", [6_000_000, 0, 0, 0, 0]],
  ["Investment in Manufacturing", "assets", [0, 14_000_000, 0, 0, 0]],
  ["Investment in Distribution", "assets", [0, 6_000_000, 0, 0, 0]],
  ["Accounts payable", "liabilities_equity", [0, 0, -4_600_000, -2_300_000, 0]],
  ["Intercompany payable", "liabilities_equity", [0, 0, 0, -2_400_000, 0]],
  ["Accrued liabilities", "liabilities_equity", [-400_000, 0, -1_500_000, -600_000, 0]],
  ["Mortgage note", "liabilities_equity", [0, 0, 0, 0, -1_200_000]],
  ["Term loan", "liabilities_equity", [-9_000_000, 0, 0, 0, 0]],
  [
    "Common stock / contributed capital",
    "liabilities_equity",
    [-12_000_000, -20_000_000, -14_000_000, -6_000_000, -6_000_000],
  ],
  [
    "Retained earnings 1/1/2026",
    "liabilities_equity",
    [-9_360_000, 0, -5_900_000, -100_000, -300_000],
  ],
  ["Net sales — third party", "income", [0, 0, -42_000_000, -31_000_000, 0]],
  ["Net sales — intercompany", "income", [0, 0, -18_000_000, 0, 0]],
  ["Rental income — intercompany", "income", [0, 0, 0, 0, -1_200_000]],
  ["Cost of goods sold", "income", [0, 0, 45_600_000, 24_800_000, 0]],
  ["Rent expense — intercompany", "income", [0, 0, 1_200_000, 0, 0]],
  ["Operating expenses", "income", [1_800_000, 0, 9_800_000, 4_600_000, 260_000]],
  ["Interest expense", "income", [360_000, 0, 0, 0, 40_000]],
];

type ElimLine = [caption: string, debit: number, credit: number];
export const ELIMINATION_SPECS: readonly [string, number, string, ElimLine[]][] = [
  [
    "E1a",
    2,
    "Investment in subsidiaries vs contributed capital",
    [
      ["Common stock / contributed capital", 20_000_000, 0],
      ["Investment in Manufacturing", 0, 14_000_000],
      ["Investment in Distribution", 0, 6_000_000],
    ],
  ],
  [
    "E1b",
    1,
    "Investment in subsidiaries vs contributed capital",
    [
      ["Common stock / contributed capital", 26_000_000, 0],
      ["Investment in Operating Co.", 0, 20_000_000],
      ["Investment in Real Estate", 0, 6_000_000],
    ],
  ],
  [
    "E2",
    2,
    "Intercompany sales, Manufacturing → Distribution",
    [
      ["Net sales — intercompany", 18_000_000, 0],
      ["Cost of goods sold", 0, 18_000_000],
    ],
  ],
  [
    "E3",
    2,
    "Unrealized profit in Distribution's ending inventory",
    [
      ["Cost of goods sold", 240_000, 0],
      ["Inventory", 0, 240_000],
    ],
  ],
  [
    "E4",
    2,
    "Intercompany balances",
    [
      ["Intercompany payable", 2_400_000, 0],
      ["Intercompany receivable", 0, 2_400_000],
    ],
  ],
  [
    "E5",
    1,
    "Intercompany rent, Real Estate → Manufacturing",
    [
      ["Rental income — intercompany", 1_200_000, 0],
      ["Rent expense — intercompany", 0, 1_200_000],
    ],
  ],
];

const money = (dollars: number): string => `${String(dollars)}.00`;

/** Net debit per caption of the eliminations at `level` (all when undefined). */
function eliminations(level?: number): Map<string, number> {
  const out = new Map<string, number>();
  for (const [, lvl, , lines] of ELIMINATION_SPECS) {
    if (level !== undefined && lvl !== level) continue;
    for (const [caption, debit, credit] of lines) {
      out.set(caption, (out.get(caption) ?? 0) + debit - credit);
    }
  }
  return out;
}

function codesFor(caption: string, level?: number): string[] {
  return ELIMINATION_SPECS.filter(
    ([, lvl, , lines]) =>
      (level === undefined || lvl === level) && lines.some(([c]) => c === caption),
  ).map(([code]) => code);
}

const LEVEL2: readonly EntityKey[] = ["operating", "manufacturing", "distribution"];

function rows(level: 1 | 2): TbRowOut[] {
  const members = level === 1 ? ENTITY_KEYS : LEVEL2;
  const elim = eliminations(level === 1 ? undefined : 2);
  return TB_ROWS.map(([caption, section, amounts]) => {
    const own = members.map((key) => amounts[ENTITY_KEYS.indexOf(key)] ?? 0);
    const e = elim.get(caption) ?? 0;
    const consolidated = own.reduce((a, b) => a + b, 0) + e;
    return {
      caption,
      section,
      cells: [
        ...members.map((key, i) => ({
          column: key,
          amount: money(own[i] ?? 0),
          elimination_codes: [],
        })),
        {
          column: "eliminations",
          amount: money(e),
          elimination_codes: codesFor(caption, level === 1 ? undefined : 2),
        },
        { column: "consolidated", amount: money(consolidated), elimination_codes: [] },
      ],
    };
  });
}

function cell(row: TbRowOut, column: string): number {
  const found = row.cells.find((c) => c.column === column);
  return found === undefined ? 0 : Number(found.amount);
}

export function sumSection(tbRows: TbRowOut[], section: Section, column: string): number {
  return tbRows.filter((r) => r.section === section).reduce((a, r) => a + cell(r, column), 0);
}

function tb(level: 1 | 2): ConsolidatedTbOut {
  const body = rows(level);
  const totalAssets = sumSection(body, "assets", "consolidated");
  const netIncome = -sumSection(body, "income", "consolidated");
  return {
    level,
    view: "consolidated",
    columns: [...(level === 1 ? ENTITY_KEYS : LEVEL2), "eliminations", "consolidated"],
    rows: body,
    tallies: {
      total_assets: money(totalAssets),
      net_income: money(netIncome),
      balanced: "tie",
      off_by: null,
      intercompany: "tie",
      intercompany_off_by: null,
      eliminations_posted: level === 1 ? 6 : 4,
      mapped: 244,
      accounts: 244,
    },
    engine_version: "fixture",
  };
}

/** AUD-33 a (Level 1) and d (Level 2 · Operating Co.). */
export const CONSOLIDATED_TB_L1: ConsolidatedTbOut = tb(1);
export const CONSOLIDATED_TB_L2: ConsolidatedTbOut = tb(2);

function elimination([
  code,
  level,
  description,
  lines,
]: (typeof ELIMINATION_SPECS)[number]): EliminationOut {
  const debit = lines.reduce((a, [, d]) => a + d, 0);
  const credit = lines.reduce((a, [, , c]) => a + c, 0);
  return {
    id: ids(`elimination:${code}`),
    display_code: code,
    consolidation_level: level,
    description,
    status: "posted",
    posting_target: "consolidation_layer",
    lines: lines.map(([caption, d, c]) => ({
      caption,
      client_entity_id: null,
      debit: money(d),
      credit: money(c),
    })),
    total_debit: money(debit),
    total_credit: money(credit),
    off_by: money(debit - credit),
    computation:
      code === "E3"
        ? "1,000,000 of Distribution's 8/31 inventory was bought from Manufacturing × Manufacturing's 2026 gross margin 24.0% (14,400,000 ÷ 60,000,000) = 240,000"
        : null,
    citation_ids: [],
    proposed_by_run_id: null,
    approved_by_name: "Omar Haddad",
    posted_at: "2026-09-14T14:01:00-05:00",
  };
}

export const ELIMINATIONS: EliminationsOut = (() => {
  const items = ELIMINATION_SPECS.map(elimination);
  const debit = items.reduce((a, e) => a + Number(e.total_debit), 0);
  const credit = items.reduce((a, e) => a + Number(e.total_credit), 0);
  return { items, total_debit: money(debit), total_credit: money(credit) };
})();

/** AUD-32 d: interim total debits per entity (the debit side of each interim TB). */
export function interimDebits(key: EntityKey): number {
  const i = ENTITY_KEYS.indexOf(key);
  return TB_ROWS.reduce((a, [, , amounts]) => a + Math.max(0, amounts[i] ?? 0), 0);
}

const LEVELS: Record<EntityKey, [number, EntityKey | null]> = {
  holdings: [1, null],
  operating: [2, "holdings"],
  manufacturing: [3, "operating"],
  distribution: [3, "operating"],
  real_estate: [2, "holdings"],
};

export const CONSOLIDATION_REVIEW: ConsolidationOut = {
  id: GROUP_IDS.consolidation,
  name: "FY2026 group consolidation",
  status: "draft",
  lock_state: "open",
  year_end: "2026-12-31",
  reporting_currency: "USD",
  interim_period_end: "2026-08-31",
  prior_period_end: "2025-12-31",
  entities: ENTITY_KEYS.map((key) => {
    const [level, parent] = LEVELS[key];
    return {
      id: ids(`entity:${key}`),
      client_entity_id: ids(`client-entity:${key}`),
      name: ENTITY_NAMES[key],
      level,
      parent_id: parent === null ? null : ids(`entity:${parent}`),
      ownership_pct: "100.000000",
      city: null,
      component_auditor_name: key === "distribution" ? "Pruett & Lang LLP" : null,
      trial_balances: [
        {
          id: ids(`tb:${key}:interim`),
          label: "interim",
          period_kind: "current",
          period_start: "2026-01-01",
          period_end: "2026-08-31",
          state: "attached",
          file_name: null,
          total_debits: money(interimDebits(key)),
          not_needed_reason: null,
        },
      ],
    };
  }),
  tiers: 3,
  interim_total_debits: money(ENTITY_KEYS.reduce((a, k) => a + interimDebits(k), 0)),
  all_balanced: true,
  missing: [],
  finalized_by_name: null,
  finalized_at: null,
  row_version: 3,
  allowed_actions: ["consolidation.edit", "consolidation.finalize"],
};

export const ACCOUNTS_BY_ENTITY: Record<EntityKey, number> = {
  holdings: 32,
  operating: 8,
  manufacturing: 98,
  distribution: 76,
  real_estate: 30,
};

const PMS: [EntityKey, "full_scope" | "specific_procedures", number][] = [
  ["manufacturing", "full_scope", 135_000],
  ["distribution", "full_scope", 105_000],
  ["real_estate", "specific_procedures", 54_000],
  ["holdings", "specific_procedures", 90_000],
];

/** AUD-34 c: decided (240,000 · 180,000 · 12,000) with the component PMs. */
export const GROUP_SCOPING_DECIDED: GroupScopingOut = {
  decision_card_id: ids("decision:group-materiality"),
  decided: true,
  group_materiality: "240000.00",
  performance_materiality: "180000.00",
  clearly_trivial: "12000.00",
  decided_by_name: "Margaret Okonkwo",
  decided_at: "2026-09-14T15:40:00-05:00",
  options: [
    {
      key: "pbt_5",
      benchmark: "Forecast income before taxes",
      base: "4800000.00",
      rate_pct: "5",
      amount: "240000.00",
      recommended: true,
      citation_ids: [],
    },
    {
      key: "pbt_4",
      benchmark: "Forecast income before taxes",
      base: "4800000.00",
      rate_pct: "4",
      amount: "192000.00",
      recommended: false,
      citation_ids: [],
    },
  ],
  components: PMS.map(([key, planned, pm]) => ({
    id: ids(`component:${key}`),
    entity_name: ENTITY_NAMES[key],
    planned_work: planned,
    scope_areas: [],
    performed_by: key === "distribution" ? "component_auditor" : "group_team",
    component_pm: money(pm),
    pm_pct_of_group: String(Math.round((pm * 100) / 180_000)),
    suggestion_id: null,
  })),
  component_pm_total: money(PMS.reduce((a, [, , pm]) => a + pm, 0)),
  coverage: [
    {
      measure: "total_assets",
      total: "50760000.00",
      full_scope: money(27_000_000 + 12_760_000),
      specific_procedures: money(8_400_000 + 2_600_000),
      full_scope_pct: "78",
      specific_procedures_pct: "22",
    },
    {
      measure: "third_party_sales",
      total: "73000000.00",
      full_scope: "73000000.00",
      specific_procedures: "0.00",
      full_scope_pct: "100",
      specific_procedures_pct: "0",
    },
  ],
  allowed_actions: ["component.edit"],
};

/** POR-23 a: Renee Pruett's room on Wed Sep 23, 9:40 AM (0 of 4; client words only). */
export const COMPONENT_ROOM_INVITED: ComponentRoomOut = {
  id: GROUP_IDS.room,
  group_name: "Harlow & Pike Holdings, Inc. · FY2026 group audit",
  component_name: "Harlow & Pike Distribution, Inc.",
  firm_name: "Brightwater Hale LLP",
  acknowledged_on: null,
  uploaded: 0,
  expected: 4,
  deliverables: [
    {
      id: ids("deliverable:interim-memo"),
      title: "Interim memo",
      due_on: "2026-11-30",
      word: "due",
      uploaded_on: null,
      return_note: null,
    },
    {
      id: ids("deliverable:clearance"),
      title: "Clearance letter",
      due_on: "2027-02-12",
      word: "due",
      uploaded_on: null,
      return_note: null,
    },
    {
      id: ids("deliverable:summary"),
      title: "Summary of uncorrected misstatements",
      due_on: "2027-02-12",
      word: "due",
      uploaded_on: null,
      return_note: null,
    },
    {
      id: ids("deliverable:representations"),
      title: "Representation letter",
      due_on: "2027-02-12",
      word: "due",
      uploaded_on: null,
      return_note: null,
    },
  ],
};
