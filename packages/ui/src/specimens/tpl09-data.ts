import type { FieldItem } from "../data/fields";
import type { IssueDetailView, IssueGroup, IssueKind, IssueState } from "../issues/issue-kit";
import { matchIdOf } from "../tracing/match-store";
import type { MatchId } from "../tracing/types";
import {
  COPPERLEAF_BANK_REC,
  FELD_1040_LINES,
  FELD_HALVARD,
  FELD_K1,
  STAFF,
} from "./seed-figures";
import { K1_BOXES, K1_FILE } from "./tpl03";

// TPL-09's issue lists (F-05-T57), word for word from the TPL-09 spec and the Wave 0 Templates
// canvas (`#tpl09`, `TP9`): the Feld 2025 Form 1040 for Kevin Osei (4 = 2 missing information + 1
// action required + 1 review point), the Copperleaf August close review for Priya Raman (7 = 2
// medium + 5 low, the Close rail's count) and the Ridgeline 2025 Form 1065 for Samuel Ito (11 = 5
// waiting on the client + 6 review points, as TXP-10). Counts are the server's strings; the seed
// test foots the ••4410 reconciliation (seed-figures COPPERLEAF_BANK_REC).

export const AGENT = "Accrued Agent";

/** Who an issue can be assigned to on these records: the agent first, then the people. */
export const TPL09_PEOPLE = [
  AGENT,
  STAFF.kevin,
  STAFF.samuel,
  STAFF.priya,
  STAFF.raj,
  STAFF.hannah,
] as const;

export interface Tpl09Issue {
  view: IssueDetailView;
  kind: IssueKind;
  /** The mini run row while the agent fixes it. */
  run?: string;
}

/** "**18A Tax-exempt interest = 1,550**": the canvas marks its figures with double asterisks. */
const parts = (s: string): readonly { text: string; figure: boolean }[] =>
  s
    .split("**")
    .map((text, n) => ({ text, figure: n % 2 === 1 }))
    .filter((p) => p.text !== "");

const linked = (name: string): MatchId =>
  matchIdOf({
    kind: "record_field",
    record_type: "linked_entity",
    record_id: name,
    field: "file",
  });

const base = (
  id: string,
  title: string,
  rest: Partial<IssueDetailView> & Pick<IssueDetailView, "facts">,
): IssueDetailView => ({
  id,
  title,
  state: "open",
  assignee: AGENT,
  priority: "",
  severity: { label: "" },
  status: "Open",
  createdBy: AGENT,
  blocks: [],
  cells: [],
  why: "",
  links: [],
  ...rest,
});

// ---- TPL-09a, d, e: Feld 2025 Form 1040 (tree) ----------------------------------------------------

const KIND = {
  missing: "Missing Information",
  action: "Action Required",
  review: "Review Point",
} as const;

type FeldKind = keyof typeof KIND;

interface FeldRow {
  id: string;
  title: string;
  kind: FeldKind;
  fix?: boolean;
}

const FELD_BANDS: readonly { id: string; label: string; sub: string; rows: readonly FeldRow[] }[] =
  [
    {
      id: "general",
      label: "General",
      sub: "Payments, Penalties & Estimates",
      rows: [
        {
          id: "est",
          title: "Obtain 2025 federal and NY estimated tax payment confirmations",
          kind: "missing",
        },
      ],
    },
    {
      id: "income",
      label: "Income",
      sub: "Sch E, p 2 - Partnership Passthrough (K-1 1065)",
      rows: [
        {
          id: "k1d",
          title: "Ridgeline K-1 is a draft — final approval blocked until Ridgeline is approved",
          kind: "action",
        },
        {
          id: "k18",
          title: "Source K-1 box 18A ‘Tax-exempt interest’ is not on the worksheet",
          kind: "missing",
          fix: true,
        },
      ],
    },
    {
      id: "state",
      label: "State",
      sub: "New York",
      rows: [
        {
          id: "nyc",
          title: "Confirm full-year NYC residency for the IT-201 resident tax",
          kind: "review",
        },
      ],
    },
  ];

/** The tree: General, Income and State bands with their form sections. */
export function feldGroups(states: Readonly<Record<string, IssueState>>): readonly IssueGroup[] {
  return FELD_BANDS.map((b) => ({
    id: b.id,
    label: b.label,
    count: "",
    sub: b.sub,
    items: b.rows.map((r) => {
      const st = states[r.id] ?? "open";
      const done = st === "resolved" || st === "na";
      return {
        id: r.id,
        title: r.title,
        sub: done ? "Resolved" : KIND[r.kind],
        subTone: r.kind === "action" ? ("amber" as const) : ("muted" as const),
        flag: r.kind === "missing" ? ("red" as const) : ("amber" as const),
        ...(r.fix === true ? { agentFixable: true } : {}),
        state: st,
      };
    }),
  }));
}

/** The Feld issue counts the Issues tab and the acceptance read: 2 / 1 / 1 = 4. */
export const FELD_COUNTS = {
  missing: FELD_BANDS.flatMap((b) => b.rows).filter((r) => r.kind === "missing").length,
  action: FELD_BANDS.flatMap((b) => b.rows).filter((r) => r.kind === "action").length,
  review: FELD_BANDS.flatMap((b) => b.rows).filter((r) => r.kind === "review").length,
} as const;

const feldFacts = (assignee: string, priority: string, createdBy: string) => ({
  assignee,
  createdBy,
  priority,
  facts: [
    { label: "Priority", value: priority },
    { label: "Created by", value: createdBy },
  ],
});

/** The K-1 box 18A match: the chip, the page region and the worksheet's line 2a share it. */
export const K18_MATCH: MatchId = K1_BOXES.box18a.match;

export const FELD_ISSUES: Readonly<Record<string, Tpl09Issue>> = {
  k18: {
    kind: "agent",
    run: "Adding 1,550 to Form 1040 line 2a",
    view: base("k18", "Source K-1 box 18A ‘Tax-exempt interest’ is not on the worksheet", {
      ...feldFacts(AGENT, "High", AGENT),
      summary: parts(
        "The draft Ridgeline Property Partners, LP K-1 reports **18A Tax-exempt interest = 1,550**, but no worksheet field carries that amount. Form 1040 line 2a should show 1,550. Confirm the box was intentionally omitted, or add it before export.",
      ),
      entities: [
        {
          name: "2025 K-1 (Form 1065) — Ridgeline Property Partners, LP · Draft K-1 · pre-release",
        },
      ],
      links: [{ name: K1_FILE, icon: "file", match: K18_MATCH }],
      explain:
        "I compared each box on the draft K-1 with the worksheet fields. Box 18A carries 1,550 and no field maps to it, so Form 1040 line 2a is blank.",
    }),
  },
  est: {
    kind: "client",
    view: base("est", "Obtain 2025 federal and NY estimated tax payment confirmations", {
      ...feldFacts(AGENT, "Medium", AGENT),
      summary: parts(
        "Jonah and Claire made 2025 federal and New York estimated payments, but no confirmations are in Intake. **Form 1040 line 26** stays blank until they arrive.",
      ),
      entities: [{ name: "2025 Form 1040 · Line 26 Estimated tax payments" }],
      explain:
        "Last year’s return shows four federal estimates, and the 2025 organizer says they were paid again. I need the IRS and New York confirmations to enter the amounts.",
    }),
  },
  k1d: {
    kind: "agent",
    view: base(
      "k1d",
      "Ridgeline K-1 is a draft — final approval blocked until Ridgeline is approved",
      {
        ...feldFacts(AGENT, "Medium", AGENT),
        summary: parts(
          "Ridgeline Property Partners, LP has issued a pre-release K-1 only. Final approval of this return waits until the Ridgeline 1065 is approved and its K-1s are released.",
        ),
        entities: [
          { name: "2025 Form 1065 — Ridgeline Property Partners, LP · In review · Partner" },
        ],
      },
    ),
  },
  nyc: {
    kind: "agent",
    view: base("nyc", "Confirm full-year NYC residency for the IT-201 resident tax", {
      ...feldFacts(STAFF.kevin, "Low", STAFF.samuel),
      summary: parts(
        "The return treats Jonah and Claire as full-year New York City residents. Confirm they lived in Brooklyn for all of 2025 before the IT-201 resident tax is final.",
      ),
      entities: [{ name: "2025 IT-201 · NYC resident tax worksheet — Feld" }],
    }),
  },
};

/** The worksheet beside the K-1: Interest and Dividends, and Schedule E Part II (the seed's Feld
 * figures, blueprint 01 §9.4). Line 2a is the agent's proposed value until a person accepts it. */
export function feldSheet(line2a: "proposed" | "accepted" | "rejected"): readonly {
  title: string;
  rows: readonly FieldItem[];
}[] {
  return [
    {
      title: "Interest and Dividends",
      rows: [
        {
          id: "int-halvard",
          label: "Taxable interest — Halvard Securities",
          value: FELD_HALVARD.interest,
          format: "whole",
        },
        {
          id: "int-k1",
          label: "Taxable interest — Ridgeline K-1 box 5",
          value: FELD_K1.box5,
          format: "whole",
          match: K1_BOXES.box5.match,
        },
        {
          id: "line2a",
          label: "Tax-exempt interest (Form 1040 line 2a)",
          value: line2a === "rejected" ? null : FELD_1040_LINES.line2a,
          format: "whole",
          match: K18_MATCH,
          ...(line2a === "proposed" ? { proposed: true } : {}),
        },
        {
          id: "qual",
          label: "Qualified dividends",
          value: FELD_HALVARD.qualifiedDividends,
          format: "whole",
        },
        {
          id: "ord",
          label: "Ordinary dividends",
          value: FELD_HALVARD.ordinaryDividends,
          format: "whole",
        },
      ],
    },
    {
      title: "Schedule E Part II",
      rows: [
        {
          id: "sche",
          label: "Net rental real estate income — Ridgeline (passive)",
          value: FELD_K1.box2,
          format: "whole",
          match: K1_BOXES.box2.match,
        },
      ],
    },
  ];
}

/** The K-1's supporting-schedule lines under the page (masked as the page masks them). */
export const K1_SUPPORT: readonly (readonly [string, string])[] = [
  ["Entity", "Ridgeline Property Partners, LP"],
  ["EIN", "••-•••0287"],
  ["Recipient", "Jonah Feld"],
  ["Recipient TIN", "•••-••-4417"],
  ["Tax year", "2025"],
];

// ---- TPL-09b, g: Copperleaf August close review (severity) ----------------------------------------

interface CloseRow {
  id: string;
  title: string;
  account: string;
}

const CLOSE_BANDS: readonly { id: string; label: string; rows: readonly CloseRow[] }[] = [
  {
    id: "med",
    label: "Medium",
    rows: [
      {
        id: "se",
        title: "Sound Electric $3,200.00 booked to Repairs & Maintenance — up 400% on July",
        account: "Repairs & Maintenance",
      },
      {
        id: "acc",
        title: "Accrued expenses entry $14,900.00 is above the $10,000 other-accruals threshold",
        account: "Accrued Expenses",
      },
    ],
  },
  {
    id: "low",
    label: "Low",
    rows: [
      {
        id: "ck",
        title: "Outstanding check #2281 dated Feb 2026 has not cleared",
        account: "Operating Checking (Front Range Bank) ••4410",
      },
      {
        id: "ref",
        title: "Vendor refund $380.00 on the Aug 27 statement is not recorded in the books",
        account: "Operating Checking ••4410",
      },
      {
        id: "pp",
        title: "Prepaid insurance ties once the $700 August amortization posts",
        account: "Prepaid Insurance",
      },
      {
        id: "pay",
        title: "Payroll up 12.5% on July — new hires, merit increases and overtime",
        account: "Payroll Expenses",
      },
      {
        id: "amex",
        title: "Amex statement cycle ends Aug 22, not on the calendar month",
        account: "Amex Business Card ••1009",
      },
    ],
  },
];

/** The severity bands; a resolved issue leaves its band unless Show resolved is on. */
export function closeGroups(
  states: Readonly<Record<string, IssueState>>,
  showResolved: boolean,
): readonly IssueGroup[] {
  return CLOSE_BANDS.map((b) => {
    const rows = b.rows.filter((r) => {
      const st = states[r.id] ?? "open";
      return showResolved || (st !== "resolved" && st !== "na");
    });
    return {
      id: b.id,
      label: b.label,
      count: String(rows.length),
      items: rows.map((r) => {
        const st = states[r.id] ?? "open";
        const done = st === "resolved" || st === "na";
        return {
          id: r.id,
          title: r.title,
          sub: `${done ? "Resolved" : "Open"} · ${r.account}`,
          flag: "amber" as const,
          state: st,
        };
      }),
    };
  });
}

export const CLOSE_COUNTS = {
  medium: CLOSE_BANDS[0]?.rows.length ?? 0,
  low: CLOSE_BANDS[1]?.rows.length ?? 0,
} as const;

const CK_WHY =
  "Check #2281 for $1,240.00, dated Feb 19, 2026, is still outstanding on the Aug 31, 2026 statement — more than six months after issue — while every other outstanding check cleared within 12 days. Confirm with Ben Ashby whether it was lost, voided or should be reissued; a stale check may need to be written back to cash or reported as unclaimed property.";

/** A close issue's detail: Severity, Status and Account after Assigned to; the account is the
 * linked entity (#2281 carries its reason, as the canvas draws only that one). */
export function closeIssue(id: string): Tpl09Issue | null {
  const band = CLOSE_BANDS.find((b) => b.rows.some((r) => r.id === id));
  const row = band?.rows.find((r) => r.id === id);
  if (band === undefined || row === undefined) return null;
  return {
    kind: "review",
    view: base(row.id, row.title, {
      severity: { label: band.label },
      facts: [
        { label: "Severity", value: band.label },
        { label: "Status", value: "Open" },
        { label: "Account", value: row.account },
      ],
      why: row.id === "ck" ? CK_WHY : "",
      entities: [
        {
          name: row.account,
          flag: true,
          ...(row.id === "ck" ? { sub: "1 reconciling item" } : {}),
        },
      ],
    }),
  };
}

export interface RecLine {
  id: string;
  label: string;
  /** A decimal string; negative for the outstanding checks. */
  amount?: string;
  kind: "line" | "group" | "check" | "total" | "band";
  flag?: boolean;
  /** "Statement p. 2": the refund's match chip to the statement line. */
  chip?: string;
  tie?: boolean;
}

const R = COPPERLEAF_BANK_REC;

/** The ••4410 Reconciliation view beside the close review, in the canvas's order. */
export const BANK_REC: readonly RecLine[] = [
  { id: "bank", label: "Balance per bank statement, Aug 31, 2026", amount: R.bank, kind: "line" },
  {
    id: "dit",
    label: "Deposit in transit — Square payout, Aug 31",
    amount: R.depositInTransit,
    kind: "line",
  },
  { id: "oc", label: "OUTSTANDING CHECKS", kind: "group" },
  ...R.outstandingChecks.map((c): RecLine => ({
    id: `ck${c.id}`,
    label: c.label,
    amount: c.amount,
    kind: "check",
    ...(c.stale ? { flag: true } : {}),
  })),
  {
    id: "toc",
    label: "Total outstanding checks",
    amount: R.totalOutstanding,
    kind: "total",
  },
  { id: "adjbank", label: "Adjusted bank balance", amount: R.adjustedBank, kind: "band" },
  { id: "book", label: "Balance per books", amount: R.book, kind: "line" },
  {
    id: "refund",
    label: "Unrecorded vendor refund — statement line Aug 27",
    amount: R.unrecordedRefund,
    kind: "line",
    chip: "Statement p. 2",
  },
  { id: "adjbook", label: "Adjusted book balance", amount: R.adjustedBook, kind: "band" },
  { id: "diff", label: "Difference", amount: R.difference, kind: "total", tie: true },
];

/** The refund's statement match: the row, its chip and the refund issue share it. */
export const REFUND_MATCH: MatchId = linked("Copperleaf ••4410 statement Aug 27");

// ---- TPL-09c, f: Ridgeline 2025 Form 1065 (radio) -------------------------------------------------

const RIDGELINE_BANDS: readonly {
  id: string;
  label: string;
  rows: readonly { id: string; title: string }[];
}[] = [
  {
    id: "wait",
    label: "Waiting on the client",
    rows: [
      {
        id: "754",
        title:
          "§754 election: partners’ decision and support for Pell Street II’s $360,000 purchase price",
      },
      {
        id: "pell",
        title: "Pell Street transfer (6/30/2025): assignment agreement and transfer-date balances",
      },
      {
        id: "roof",
        title: "Elm Street roof replacement: contractor invoice and placed-in-service date",
      },
      { id: "dep", title: "Bergen Street tenant security deposit ledger supporting 121,800" },
      {
        id: "rtx",
        title: "December real estate tax installment: county bill supporting the 18,500 accrual",
      },
    ],
  },
  {
    id: "rev",
    label: "Review points",
    rows: [
      { id: "tei", title: "Tax-exempt interest 6,200 omitted from the capital rollforward" },
      {
        id: "lot",
        title: "Larimer parking lot: 100% bonus requires acquisition after Jan 19, 2025",
      },
      { id: "743", title: "§743(b) placeholder 28,595 pending the §754 decision" },
      { id: "app", title: "Apportionment by property: IL 46.0% · CO 31.5% · NY 22.5%" },
      {
        id: "752",
        title: "Nonrecourse mortgage shared by year-end profit percentages under §752",
      },
      { id: "k23", title: "Schedules K-2/K-3 required — domestic filing exception unavailable" },
    ],
  },
];

/** The radio bands; a resolved issue keeps its place with the olive disc, as the canvas does. */
export function ridgelineGroups(
  states: Readonly<Record<string, IssueState>>,
): readonly IssueGroup[] {
  return RIDGELINE_BANDS.map((b) => ({
    id: b.id,
    label: b.label,
    count: "",
    items: b.rows.map((r) => ({ id: r.id, title: r.title, state: states[r.id] ?? "open" })),
  }));
}

export const RIDGELINE_COUNTS = {
  waiting: RIDGELINE_BANDS[0]?.rows.length ?? 0,
  review: RIDGELINE_BANDS[1]?.rows.length ?? 0,
} as const;

const TEI_CELLS = [
  "05 Capital!H8",
  "05 Capital!H9",
  "05 Capital!H10",
  "05 Capital!H11",
  "05 Capital!H12",
  "06 Schedule K!C31",
  "07 M-2!C9",
] as const;

/** A Ridgeline issue: the M-2 issue carries What it blocks and its workbook cells. */
export function ridgelineIssue(id: string): Tpl09Issue | null {
  const band = RIDGELINE_BANDS.find((b) => b.rows.some((r) => r.id === id));
  const row = band?.rows.find((r) => r.id === id);
  if (band === undefined || row === undefined) return null;
  const severity = band.id === "wait" ? "Waiting on the client" : "Review point";
  return {
    kind: band.id === "wait" ? "client" : "review",
    ...(row.id === "tei" ? { run: "Adding 6,200 to M-2 other increases" } : {}),
    view: base(row.id, row.title, {
      severity: { label: severity },
      facts: [
        { label: "Severity", value: severity },
        { label: "Status", value: "Open" },
        { label: "Created by", value: AGENT },
      ],
      ...(row.id === "tei"
        ? {
            blocks: [
              {
                text: "Schedule M-2 and every partner’s Item L sum to 6,860,000, but Schedule L line 21 shows partners’ capital of 6,866,200. Tax-exempt interest of 6,200 from the municipal bond fund (Schedule K line 18A) is allocated on the K-1s but missing from ‘Other increases’. Final approval and K-1 release are blocked until M-2 ties.",
              },
            ],
            cells: TEI_CELLS.map((ref) => ({
              ref,
              value: "",
              match: matchIdOf({
                kind: "record_field",
                record_type: "workbook_cell",
                record_id: "ridgeline",
                field: ref,
              }),
            })),
          }
        : {}),
    }),
  };
}
