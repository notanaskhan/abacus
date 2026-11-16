// TXT-02's read model for the Calloway Family Trust's 2025 Form 1041 (T-07-T17): the calc tree,
// the by-character table and the tally strip, verbatim from the handoff (trust-calculation.png;
// TXT-02 A–E). Base: FAI 430,000 · DNI 400,000 · distributions 240,000 · deduction 240,000 ·
// retained 160,000 · taxable 159,900. Changed (d): Theo's Dec 15 distribution 80,000 → 100,000
// gives 260,000 / 140,000 / 139,900 with struck priors. Every figure is the engine's (T-07-T09).
import type {
  FiduciaryCharacterRowOut,
  FiduciaryComputationOut,
  FiduciaryTreeNodeOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type CalcState = "base" | "changed" | "signed";

type Row = [
  key: string,
  parent: string | null,
  label: string,
  value: string | null,
  clause?: string | undefined,
  box?: string,
];

const NORA = "nora";
const THEO = "theo";

function rows(state: CalcState): Row[] {
  const changed = state === "changed";
  const theo = changed ? "100,000" : "80,000";
  return [
    ["fai", null, "Trust accounting income", "430000.00"],
    ["income", "fai", "Income", null],
    ["interest", "income", "Interest — Harborline custodial account", "107500.00"],
    ["dividends", "income", "Ordinary dividends (qualified 258,000)", "322500.00"],
    ["adjustments", "fai", "Adjustments", null],
    [
      "trustee_fees",
      "adjustments",
      "Trustee fees charged to principal — deductible",
      "-30000.00",
      "V(c)",
    ],
    [
      "gains",
      "adjustments",
      "Capital gains allocated to principal — no sales in 2025",
      null,
      "II",
    ],
    ["dni", "fai", "Distributable net income", "400000.00"],
    ["distributions", null, "Distributions and deduction", null],
    [
      "paid",
      "distributions",
      "Distributions paid in 2025 (discretionary, Art. III(a))",
      changed ? "260000.00" : "240000.00",
      "III(a)",
    ],
    [
      "idd",
      "distributions",
      "Income distribution deduction (§661) — lesser of distributions and DNI",
      changed ? "260000.00" : "240000.00",
    ],
    ["allocation", null, "Beneficiary Allocation", null],
    [NORA, "allocation", "Nora Calloway", null],
    ["nora_paid", NORA, "Distributions (Jun 30 80,000 · Dec 15 80,000)", "160000.00"],
    ["nora_share", NORA, `Beneficiary share ${changed ? "61.5%" : "66.7%"}`, null],
    ["nora_dni", NORA, "DNI allocated", "160000.00"],
    ["nora_k1", NORA, "Schedule K-1 / Form 1041", null],
    ["nora_box1", "nora_k1", "Interest income", "40000.00", undefined, "Box 1"],
    ["nora_box2a", "nora_k1", "Ordinary dividends", "120000.00", undefined, "Box 2a"],
    ["nora_box2b", "nora_k1", "Qualified dividends", "96000.00", undefined, "Box 2b"],
    [THEO, "allocation", "Theo Calloway", null],
    ["theo_paid", THEO, `Distributions (Dec 15 ${theo})`, changed ? "100000.00" : "80000.00"],
    ["theo_share", THEO, `Beneficiary share ${changed ? "38.5%" : "33.3%"}`, null],
    ["theo_dni", THEO, "DNI allocated", changed ? "100000.00" : "80000.00"],
    ["theo_k1", THEO, "Schedule K-1 / Form 1041", null],
    [
      "theo_box1",
      "theo_k1",
      "Interest income",
      changed ? "25000.00" : "20000.00",
      undefined,
      "Box 1",
    ],
    [
      "theo_box2a",
      "theo_k1",
      "Ordinary dividends",
      changed ? "75000.00" : "60000.00",
      undefined,
      "Box 2a",
    ],
    [
      "theo_box2b",
      "theo_k1",
      "Qualified dividends",
      changed ? "60000.00" : "48000.00",
      undefined,
      "Box 2b",
    ],
    ["retained", null, "Retained by the trust", null],
    [
      "undistributed",
      "retained",
      "Undistributed DNI (accumulated under Art. IV(a))",
      changed ? "140000.00" : "160000.00",
      "IV(a)",
    ],
    ["exemption", "retained", "Personal exemption (§642(b))", "-100.00"],
    ["taxable", "retained", "Trust taxable income", changed ? "139900.00" : "159900.00"],
  ];
}

const BASE: Record<string, string | null> = Object.fromEntries(
  rows("base").map((r) => [r[0], r[3]]),
);

function levelOf(all: Row[], key: string): number {
  const parent = all.find((r) => r[0] === key)?.[1] ?? null;
  return parent === null ? 0 : levelOf(all, parent) + 1;
}

function nodes(state: CalcState): FiduciaryTreeNodeOut[] {
  const all = rows(state);
  return all.map(([key, parent, label, value, clause, box]) => {
    const prior = BASE[key] ?? null;
    const changed = state === "changed" && prior !== value;
    return {
      key,
      parent_key: parent,
      level: levelOf(all, key),
      label,
      value,
      box_label: box ?? null,
      clause_labels: clause ? [clause] : [],
      provenance_id: box ? stableId(`provenance:calloway:${key}`) : null,
      changed,
      prior_value: changed ? prior : null,
      highlighted: key === "nora_dni",
    };
  });
}

function byCharacter(state: CalcState): FiduciaryCharacterRowOut[] {
  const c = state === "changed";
  const row = (
    kind: FiduciaryCharacterRowOut["kind"],
    total: string,
    n: string,
    t: string,
    trust: string,
  ) => ({
    kind,
    total,
    by_party: [
      { party: "Nora Calloway", amount: n },
      { party: "Theo Calloway", amount: t },
      { party: "Trust", amount: trust },
    ],
  });
  return c
    ? [
        row("interest", "100000.00", "40000.00", "25000.00", "35000.00"),
        row("ordinary_dividends", "300000.00", "120000.00", "75000.00", "105000.00"),
        row("qualified_dividends", "240000.00", "96000.00", "60000.00", "84000.00"),
        row("total", "400000.00", "160000.00", "100000.00", "140000.00"),
      ]
    : [
        row("interest", "100000.00", "40000.00", "20000.00", "40000.00"),
        row("ordinary_dividends", "300000.00", "120000.00", "60000.00", "120000.00"),
        row("qualified_dividends", "240000.00", "96000.00", "48000.00", "96000.00"),
        row("total", "400000.00", "160000.00", "80000.00", "160000.00"),
      ];
}

export function callowayComputation(
  returnId: string,
  state: CalcState = "base",
): FiduciaryComputationOut {
  const changed = state === "changed";
  return {
    return_id: returnId,
    computation_id: stableId(`fiduciary-computation:calloway:${state}`),
    version_no: changed ? 2 : 1,
    view: "tree",
    engine_name: "fiduciary",
    engine_version: "1.0.0",
    inputs_hash: changed ? "b".repeat(64) : "a".repeat(64),
    parameter_set: "ty2025.v1",
    computed_at: "2026-09-14T14:24:00Z",
    nodes: nodes(state),
    by_character: byCharacter(state),
    tallies: [
      { key: "fai", label: "FAI", value: "430000.00", state: null },
      { key: "dni", label: "DNI", value: "400000.00", state: null },
      {
        key: "distributions",
        label: "Distributions",
        value: changed ? "260000.00" : "240000.00",
        state: null,
      },
      {
        key: "idd",
        label: "Distribution deduction",
        value: changed ? "260000.00" : "240000.00",
        state: null,
      },
      {
        key: "retained",
        label: "Retained DNI",
        value: changed ? "140000.00" : "160000.00",
        state: null,
      },
      { key: "k1_tie", label: "Σ K-1s = deduction", value: null, state: "tie" },
      {
        key: "taxable",
        label: "Taxable income",
        value: changed ? "139900.00" : "159900.00",
        state: null,
      },
    ],
    notes: [
      changed
        ? "FAI not distributed: 430,000 − 260,000 = 170,000 added to principal under Art. IV(a)."
        : "FAI not distributed: 430,000 − 240,000 = 190,000 added to principal under Art. IV(a).",
    ],
    banner: changed ? "Theo's Dec 15 distribution edited · re-approval needed" : null,
    signed_by_initials: state === "signed" || changed ? "SI" : null,
    sign_off_stale: changed,
    allowed_actions: [
      "fai_line.edit",
      "trust_distribution.edit",
      "fiduciary_computation.export",
      "sign_off.l2",
    ],
  };
}
