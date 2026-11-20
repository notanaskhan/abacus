// T-06-T32 (TASK-8835): Ridgeline's states and PTET in fixture mode, as `GET /v1/tax-returns/{id}/
// states` answers it (TXP-09 a–e). Every figure is the handoff's (spec ACCEPTANCE): 566,536 +
// 387,954 + 277,110 = 1,231,600; PTET 28,044 + 17,070 + 18,982 = 64,096; Jonah Feld's credits
// 7,011 + 4,268 + 4,746 = 16,025. tax-depth-states.foot.test.ts re-adds them (ADR-050).
import type { TaxDepthStateOut, TaxDepthStatesOut } from "@abacus/api-client";
import { PARTNER_ID } from "./tax-depth-basis";
import { stableId } from "./prng";

export type StatesVariant = "e0" | "missingFactor" | "paymentGap" | "approved";

const BASE = "1231600";
const PAID_ON = "2026-03-12";

type S = readonly [
  code: string,
  name: string,
  property: string,
  numerator: string,
  share: string,
  rate: string,
  ptet: string,
  form: string,
];

const STATES: readonly S[] = [
  [
    "IL",
    "Illinois",
    "Elm Street, Chicago",
    "566536",
    "46.0",
    "4.95",
    "28044",
    "IL-1065 (PTE tax)",
  ],
  [
    "CO",
    "Colorado",
    "Larimer Lofts, Denver",
    "387954",
    "31.5",
    "4.40",
    "17070",
    "DR 0106 (SALT parity)",
  ],
  [
    "NY",
    "New York",
    "Bergen Street, Brooklyn",
    "277110",
    "22.5",
    "6.85",
    "18982",
    "PTET annual return (online)",
  ],
];

function state(s: S, variant: StatesVariant): TaxDepthStateOut {
  const [code, name, property, numerator, share, rate, ptet, form] = s;
  const unpaid = variant === "paymentGap" && code === "NY";
  const unmapped = variant === "missingFactor" && code === "CO";
  return {
    state: code,
    name,
    property_name: property,
    numerator: unmapped ? null : numerator,
    denominator: BASE,
    apportionment_pct: share,
    nexus_basis: "Real property in state",
    ptet: "elected",
    rate_pct: rate,
    ptet_amount: ptet,
    ptet_paid: unpaid ? null : ptet,
    ptet_paid_on: unpaid ? null : PAID_ON,
    return_form: form,
    mapped: !unmapped,
    status: variant === "approved" ? "approved" : "in_review",
    approved_by_initials: variant === "approved" ? "SI" : null,
    approved_on: variant === "approved" ? "2026-09-14" : null,
    nexus_conclusion: `Files ${form.split(" ")[0] ?? form}`,
  };
}

type C = readonly [
  key: string,
  name: string,
  note: string | null,
  il: string,
  co: string,
  ny: string,
  total: string,
];

const CREDITS: readonly C[] = [
  ["gp", "Ridgeline GP LLC", null, "561", "341", "380", "1282"],
  ["shah", "Meera Shah", null, "10657", "6486", "7213", "24356"],
  ["psv", "Pell Street Ventures LLC", "35% → 30%", "9114", "5548", "6169", "20831"],
  ["ps2", "Pell Street II LLC", "7/1–12/31", "701", "427", "474", "1602"],
  ["feld", "Jonah Feld", null, "7011", "4268", "4746", "16025"],
];

const NEXUS = [
  ["IL", "Owns Elm Street building", "Elm_Street_Deed_2018.pdf", "Files IL-1065"],
  ["CO", "Owns Larimer Lofts building", "Larimer_Lofts_Deed_2019.pdf", "Files DR 0106"],
  ["NY", "Owns Bergen Street building", "Bergen_Street_Deed_2020.pdf", "Files PTET annual return"],
  ["NYC", "Rental of real property is exempt from NYC UBT", null, "No UBT return"],
] as const;

export function states(variant: StatesVariant = "e0"): TaxDepthStatesOut {
  const rows = STATES.map((s) => state(s, variant));
  const paid = rows.filter((r) => r.ptet_paid !== null).length;
  return {
    view: "apportionment",
    states: rows,
    apportionment_tally: variant === "missingFactor" ? "check" : "tie",
    sourcing: variant === "approved" ? "approved" : "proposed",
    paid_count: paid,
    payable_count: rows.length,
    base: BASE,
    ptet_total: "64096",
    credits: CREDITS.map(([key, name, note, il, co, ny, total]) => ({
      partner_id: PARTNER_ID(key),
      name,
      note,
      by_state: { IL: il, CO: co, NY: ny },
      total,
    })),
    nexus: NEXUS.map(([code, fact, file, conclusion]) => ({
      state: code,
      fact,
      evidence_name: file,
      evidence_version_id: file === null ? null : stableId(`evidence:ridgeline:${code}:deed`),
      conclusion,
      owner_initials: "SI",
    })),
    opportunities: [
      {
        jurisdiction: "New York City",
        subject: "Jonah Feld (NYC resident)",
        basis: "Resident member",
        deadline_note: "NYC PTET election by Mar 15, 2027 for TY2027",
      },
    ],
  };
}
