// T-05-T43 (TASK-7704; handoff TXP-05 A–D; docs/screens/TXP-05.md): Schedule K, its Form 8825
// breakdown, the capital accounts behind Item L and the allocation structure's status, as the
// server's workbook v1 routes answer them in fixture mode. Figures are whole-dollar decimal
// strings, verbatim from the handoff (every row crossfoots exactly; the screen sums nothing).
// Synthetic only.
import type {
  WorkbookAllocationStructureOut,
  WorkbookBreakdownOut,
  WorkbookCapitalAccountsOut,
  WorkbookScheduleKLineOut,
  WorkbookScheduleKOut,
} from "@abacus/api-client";
import { stableId } from "./prng";
import { ridgeline } from "./tax-entity-allocation";
import type { Snapshot } from "./tax-entity";

const KEYS = ["gp", "shah", "psv", "ps2", "feld"] as const;
export const PARTNER_IDS = KEYS.map((k) => stableId(`partner:ridgeline:${k}`));

type Five = readonly [string, string, string, string, string];

function line(
  no: string,
  label: string,
  total: string,
  shares: Five | null,
): WorkbookScheduleKLineOut {
  return {
    line: no,
    label,
    total,
    by_partner:
      shares === null
        ? []
        : shares.map((amount, i) => ({ partner_id: PARTNER_IDS[i] ?? "", amount })),
    tie: "tie",
  };
}

const FEDERAL: readonly WorkbookScheduleKLineOut[] = [
  line("1", "Ordinary business income (loss)", "0", null),
  line("2", "Net rental real estate income (loss) — Form 8825", "1231600", [
    "24632",
    "468008",
    "400270",
    "30790",
    "307900",
  ]),
  line("3c", "Other net rental income (loss)", "0", null),
  line("4c", "Guaranteed payments — total", "0", null),
  line("5", "Interest income", "18400", ["368", "6992", "5980", "460", "4600"]),
  line("18a", "Tax-exempt interest income", "6200", ["124", "2356", "2015", "155", "1550"]),
  line("19a", "Distributions of cash and marketable securities", "600000", [
    "12000",
    "228000",
    "180000",
    "30000",
    "150000",
  ]),
  line("20a", "Investment income", "18400", ["368", "6992", "5980", "460", "4600"]),
];

const ANALYSIS = line("analysis_1", "Net income (loss)", "1250000", [
  "25000",
  "475000",
  "406250",
  "31250",
  "312500",
]);

/** B: the state view (sheet 08's imported schedule): the apportionment rows as the handoff names
 * them (no amounts drawn) and each state's PTET credit with its partner splits (TXP-09's). */
const STATE: readonly WorkbookScheduleKLineOut[] = [
  line("IL", "IL 46.0% · line 2 share", "0", null),
  line("CO", "CO 31.5%", "0", null),
  line("NY", "NY 22.5%", "0", null),
  line("ptet_il", "PTET credit IL", "28044", ["561", "10657", "9114", "701", "7011"]),
  line("ptet_co", "PTET credit CO", "17070", ["341", "6486", "5548", "427", "4268"]),
  line("ptet_ny", "PTET credit NY", "18982", ["380", "7213", "6169", "474", "4746"]),
];

export function scheduleK(view: "federal" | "state"): WorkbookScheduleKOut {
  return view === "state"
    ? { view, lines: [...STATE] }
    : { view, lines: [...FEDERAL], analysis: ANALYSIS };
}

/** A2: Form 8825 → line 2, the three properties behind 1,231,600. */
export function breakdown(lineNo: string): WorkbookBreakdownOut {
  return {
    line: lineNo,
    rows:
      lineNo === "2"
        ? [
            { property_name: "Elm Street", amount: "566536" },
            { property_name: "Larimer Lofts", amount: "387954" },
            { property_name: "Bergen Street", amount: "277110" },
          ]
        : [],
  };
}

const ENDING_DRAFTED: Five = ["93000", "2527000", "1994845", "332655", "1912500"];
const ENDING_FIXED: Five = ["93124", "2529356", "1996860", "332810", "1914050"];
const NAMES: Five = [
  "Ridgeline GP LLC",
  "Meera Shah",
  "Pell Street Ventures LLC",
  "Pell Street II LLC",
  "Jonah Feld",
];

/** Item L: the partners' ending capital against Schedule L's 6,866,200 (off 6,200 until the fix).
 * T-05-T55: each 05 row as TXP-07's panes draw it (handoff TXP-07 a, b, c): beginning,
 * contributions, allocated income, tax-exempt income (blank on the tax basis until the fix; 704(b)
 * and book carry it), transfers (−331,405 / +331,405 at 6/30/2025), distributions, and the
 * endings on both bases. Verbatim from the handoff; every pane crossfoots. */
const BEGINNING: Five = ["80000", "2280000", "2100000", "0", "1500000"];
const CONTRIBUTIONS: Five = ["0", "0", "0", "0", "250000"];
const INCOME: Five = ["25000", "475000", "406250", "31250", "312500"];
const TAX_EXEMPT: Five = ["124", "2356", "2015", "155", "1550"];
const TRANSFERS: readonly (string | null)[] = [null, null, "-331405", "331405", null];
const DISTRIBUTIONS: Five = ["12000", "228000", "180000", "30000", "150000"];

export function capitalAccounts(snapshot: Snapshot): WorkbookCapitalAccountsOut {
  const fixed = snapshot === "afterFix" || snapshot === "run3";
  const endings = fixed ? ENDING_FIXED : ENDING_DRAFTED;
  return {
    view: "by_partner",
    basis: "tax",
    rows: endings.map((ending, i) => ({
      partner_id: PARTNER_IDS[i] ?? "",
      name: NAMES[i] ?? null,
      row: i + 2,
      beginning: BEGINNING[i] ?? "0",
      contributions: CONTRIBUTIONS[i] ?? "0",
      income: INCOME[i] ?? "0",
      distributions: DISTRIBUTIONS[i] ?? "0",
      ending,
      tax_exempt: fixed ? (TAX_EXEMPT[i] ?? null) : null,
      tax_exempt_704b: TAX_EXEMPT[i] ?? null,
      nondeductible: null,
      transfers: TRANSFERS[i] ?? null,
      guaranteed_payments: null,
      ending_704b: ENDING_FIXED[i] ?? null,
    })),
    tie: fixed ? "tie" : "off",
    totals: {
      beginning: "5960000",
      contributions: "250000",
      income: "1250000",
      distributions: "600000",
      ending: fixed ? "6866200" : "6860000",
      tax_exempt: fixed ? "6200" : null,
      transfers: "0",
      ending_704b: "6866200",
    },
    item_l: {
      capital_ending: fixed ? "6866200" : "6860000",
      m2_ending: "6866200",
      tie: fixed ? "tie" : "off",
      difference: fixed ? "0" : "-6200",
    },
    book_tie: "tie",
    derives_tie: "tie",
  };
}

/** The tally strip's Allocation card: Ridgeline's approved structure (TXP-06 A's). */
export function allocationSummary(): WorkbookAllocationStructureOut {
  return ridgeline();
}
