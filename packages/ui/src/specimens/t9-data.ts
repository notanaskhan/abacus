import type { TableColumn, TableRow } from "../data/types";
import type { IssueDetailView, IssueGroup, IssueKind } from "../issues/issue-kit";
import { matchIdOf } from "../tracing/match-store";
import type { MatchId } from "../tracing/types";
import { feldBox } from "./feld-t3";
import { STAFF } from "./seed-figures";

// The T9 frame's issues, word for word from the T9 handoff's boards (Wave 0 Foundations `#t9`):
// the Feld 2025 Form 1040 review (T9a, T9d), the Copperleaf August close (T9b) and the Ridgeline
// 2025 Form 1065 (T9c, T9e). Where the boards name a Ridgeline party the blueprint's seed does not
// have, the seed's wins (DEC-354): the 6/30/2025 transfer is Pell Street Ventures LLC to Pell Street
// II LLC (01 §9.4), and the partner on the 704(b) and Section 752 points is Pell Street Ventures
// LLC. TPL-09 (F-05-T57) draws the seed's own issue lists. Counts are the server's strings.

export const AGENT = "Accrued Agent";

/** Who an issue can be assigned to: the agent first, then the people on the record. */
export const T9_PEOPLE = [
  AGENT,
  STAFF.hannah,
  STAFF.samuel,
  STAFF.olivia,
  STAFF.daniel,
  STAFF.raj,
  STAFF.priya,
] as const;

const cell = (sheet: string, ref: string): MatchId =>
  matchIdOf({ kind: "record_field", record_type: "workbook_cell", record_id: sheet, field: ref });
const file = (name: string): MatchId =>
  matchIdOf({
    kind: "record_field",
    record_type: "linked_entity",
    record_id: name,
    field: "file",
  });

const parts = (s: string): IssueDetailView["blocks"] =>
  s
    .split("*")
    .map((text, n) => ({ text, figure: n % 2 === 1 }))
    .filter((p) => p.text !== "");

export interface T9Issue {
  view: IssueDetailView;
  kind: IssueKind;
}

// ---- T9a, T9d: Feld 2025 Form 1040 (tree) ---------------------------------------------------------

/** Line 3b's mismatch: the workbook cell lights 1099-DIV box 1a on the page and line 3b. */
export const DIV3B_MATCH = feldBox("1099:div-1a");

export const FELD_GROUPS: readonly IssueGroup[] = [
  {
    id: "schb",
    label: "Schedule B · Interest and dividends",
    count: "1 open",
    items: [
      {
        id: "div3b",
        title: "Ordinary dividends on line 3b read 4,182 against 4,812 on the composite 1099",
        sub: "Action required",
        subTone: "amber",
        flag: "red",
        agentFixable: true,
      },
    ],
  },
  {
    id: "schd",
    label: "Schedule D and Form 8949",
    count: "1 open",
    items: [
      {
        id: "basis",
        title: "Three lots with no reported basis on the composite 1099-B",
        sub: "Missing information",
        flag: "red",
      },
    ],
  },
  {
    id: "scha",
    label: "Schedule A · Itemized deductions",
    count: "2 open",
    items: [
      {
        id: "ptax",
        title: "Cook County property tax bill is still outstanding",
        sub: "Missing information",
        flag: "red",
      },
      {
        id: "char",
        title: "Charitable receipts for gifts of $250 or more are still outstanding",
        sub: "Missing information",
        flag: "red",
      },
    ],
  },
];

const COMPOSITE = "2025 Composite 1099 — Brokerage.pdf";

const feldIssue = (
  id: string,
  title: string,
  severity: string,
  kind: IssueKind,
  rest: Pick<IssueDetailView, "blocks" | "cells" | "why" | "links"> & { explain?: string },
): T9Issue => ({
  kind,
  view: {
    id,
    title,
    state: "open",
    assignee: AGENT,
    priority: kind === "client" ? "Before filing" : "This review",
    severity: { label: severity, flag: "red" },
    status: "Open",
    createdBy: AGENT,
    ...rest,
  },
});

export const FELD_ISSUES: Readonly<Record<string, T9Issue>> = {
  div3b: feldIssue(
    "div3b",
    "Ordinary dividends on line 3b read 4,182 against 4,812 on the composite 1099",
    "Action required",
    "agent",
    {
      blocks: parts(
        "Line 3b is *630* short of the 1099, so ordinary dividends and the tax on them are understated.",
      ),
      cells: [{ ref: "Leadsheet!C14", value: "4,182", match: DIV3B_MATCH }],
      why: "Box 1a of the 1099-DIV reports 4,812.37. The worksheet value reads like a transposition.",
      links: [{ name: COMPOSITE, icon: "file", match: file(COMPOSITE) }],
      explain: "I can replace 4,182 with 4,812 from box 1a. Nothing else on the return changes.",
    },
  ),
  basis: feldIssue(
    "basis",
    "Three lots with no reported basis on the composite 1099-B",
    "Missing information",
    "client",
    {
      blocks: parts(
        "Foreign tax paid of *$214.60* is not claimed, so the credit on Schedule 3 line 1 is *$0*.",
      ),
      cells: [{ ref: "1116!B9", value: "214.60", match: cell("feld", "1116!B9") }],
      why: "The composite 1099 reports foreign tax paid in box 7, and no Form 1116 or direct credit election is on the return.",
      links: [{ name: COMPOSITE, icon: "file", match: file(COMPOSITE) }],
    },
  ),
  ptax: feldIssue(
    "ptax",
    "Cook County property tax bill is still outstanding",
    "Missing information",
    "client",
    {
      blocks: parts(
        "Schedule A line 5b stays at *—* until the bill arrives. The 2024 return deducted *9,840*.",
      ),
      cells: [{ ref: "Schedule A!C5b", value: "—", match: cell("feld", "Schedule A!C5b") }],
      why: "Property tax was deducted on the 2024 return and no 2025 bill is in Intake.",
      links: [
        {
          name: "2024 Form 1040 · Schedule A.pdf",
          icon: "file",
          match: file("2024 Form 1040 · Schedule A.pdf"),
        },
      ],
    },
  ),
  char: feldIssue(
    "char",
    "Charitable receipts for gifts of $250 or more are still outstanding",
    "Missing information",
    "client",
    {
      blocks: parts(
        "Foreign tax paid of *$214.60* is not claimed, so the credit on Schedule 3 line 1 is *$0*.",
      ),
      cells: [{ ref: "1116!B9", value: "214.60", match: cell("feld", "1116!B9") }],
      why: "The composite 1099 reports foreign tax paid in box 7, and no Form 1116 or direct credit election is on the return.",
      links: [{ name: COMPOSITE, icon: "file", match: file(COMPOSITE) }],
    },
  ),
};

// ---- T9b: Copperleaf August close (severity) -----------------------------------------------------

export const COPPERLEAF_GROUPS = (showResolved: boolean): readonly IssueGroup[] => [
  {
    id: "high",
    label: "High",
    count: "2",
    items: [
      {
        id: "amex",
        title: "Amex ••1009 August statement missing",
        sub: "Open · Amex Business Card ••1009",
        flag: "red",
      },
      {
        id: "dup",
        title: "Duplicate vendor payment to Front Range Roasting Supply",
        sub: "Open · Operating Checking (Front Range Bank) ••4410",
        flag: "red",
      },
    ],
  },
  {
    id: "medium",
    label: "Medium",
    count: "2",
    items: [
      {
        id: "tr",
        title: "Transfer to savings posted to the wrong period",
        sub: "Open · Business Savings (Front Range Bank) ••7731",
        flag: "amber",
      },
      {
        id: "pay",
        title: "Payroll clearing has a $1,240.00 unreconciled balance",
        sub: "Open · Payroll Clearing ••5208",
        flag: "amber",
      },
    ],
  },
  {
    id: "low",
    label: "Low",
    count: "3",
    items: [
      {
        id: "fee",
        title: "Card processing fees coded to cost of goods sold",
        sub: "Open · Operating Checking (Front Range Bank) ••4410",
        flag: "amber",
      },
      {
        id: "ins",
        title: "Prepaid insurance amortization off by $3.42",
        sub: "Open · Corporate Card ••1186",
        flag: "amber",
      },
      {
        id: "sub",
        title: "Two software subscriptions renewed at a higher rate",
        sub: "Open · Corporate Card ••1186",
        flag: "amber",
      },
      ...(showResolved
        ? [
            {
              id: "old",
              title: "Uncashed check from June still outstanding",
              sub: "Resolved · Operating Checking (Front Range Bank) ••4410",
              flag: "amber" as const,
              state: "resolved" as const,
            },
          ]
        : []),
    ],
  },
];

/** The register rows the duplicate's workbook cells point at (E212 is Aug 12, E219 is Aug 14). */
export const DUP_ROWS = { e212: "aug12", e219: "aug14" } as const;
const regMatch = (row: string): MatchId => cell("operating-4410", row);

const closeIssue = (
  id: string,
  title: string,
  sev: "High" | "Medium" | "Low",
  assignee: string,
  kind: IssueKind,
  rest: Pick<IssueDetailView, "blocks" | "cells" | "why" | "links"> & { explain?: string },
): T9Issue => ({
  kind,
  view: {
    id,
    title,
    state: "open",
    assignee,
    priority: sev === "High" ? "Before close" : "This close",
    severity: { label: sev, flag: sev === "High" ? "red" : "amber" },
    status: "Open",
    createdBy: kind === "review" && assignee !== AGENT ? assignee : AGENT,
    ...rest,
  },
});

const DUP = {
  blocks: parts(
    "Two payments of *$4,180.00* to Front Range Roasting Supply cleared on Aug 12 and Aug 14 against one invoice.",
  ),
  cells: [
    { ref: "Operating ••4410!E212", value: "4,180.00", match: regMatch(DUP_ROWS.e212) },
    { ref: "Operating ••4410!E219", value: "4,180.00", match: regMatch(DUP_ROWS.e219) },
  ],
  why: "The invoice number, amount and vendor match on both payments, two days apart.",
  links: [
    { name: "Invoice FR-20931.pdf", icon: "file" as const, match: file("Invoice FR-20931.pdf") },
  ],
  explain:
    "I can draft a vendor credit request and an entry to a receivable for the duplicate, both for your approval.",
};

const AMEX = {
  blocks: parts(
    "Amex Business Card *••1009* cannot be reconciled, so the August close stays at *4 of 24* accounts.",
  ),
  cells: [],
  why: "No statement for August has arrived and the card feed stops at July 31.",
  links: [
    {
      name: "August bank statements",
      icon: "folder" as const,
      match: file("August bank statements"),
    },
  ],
};

export const COPPERLEAF_ISSUES: Readonly<Record<string, T9Issue>> = {
  amex: closeIssue(
    "amex",
    "Amex ••1009 August statement missing",
    "High",
    STAFF.raj,
    "client",
    AMEX,
  ),
  dup: closeIssue(
    "dup",
    "Duplicate vendor payment to Front Range Roasting Supply",
    "High",
    AGENT,
    "agent",
    DUP,
  ),
  tr: closeIssue(
    "tr",
    "Transfer to savings posted to the wrong period",
    "Medium",
    AGENT,
    "agent",
    DUP,
  ),
  pay: closeIssue(
    "pay",
    "Payroll clearing has a $1,240.00 unreconciled balance",
    "Medium",
    STAFF.raj,
    "review",
    DUP,
  ),
  fee: closeIssue(
    "fee",
    "Card processing fees coded to cost of goods sold",
    "Low",
    AGENT,
    "agent",
    DUP,
  ),
  ins: closeIssue(
    "ins",
    "Prepaid insurance amortization off by $3.42",
    "Low",
    AGENT,
    "agent",
    DUP,
  ),
  sub: closeIssue(
    "sub",
    "Two software subscriptions renewed at a higher rate",
    "Low",
    AGENT,
    "review",
    DUP,
  ),
  old: {
    ...closeIssue(
      "old",
      "Uncashed check from June still outstanding",
      "Low",
      STAFF.raj,
      "review",
      DUP,
    ),
  },
};

/** The Operating ••4410 August register beside the close review (T9b), as the server sends it. */
export const REGISTER_COLUMNS: readonly TableColumn[] = [
  { key: "date", header: "Date", type: "text", width: 72 },
  { key: "desc", header: "Description", type: "label" },
  { key: "ref", header: "Reference", type: "text", width: 104 },
  { key: "amount", header: "Amount", type: "num", width: 120, format: "cents" },
];

const reg = (id: string, date: string, desc: string, ref: string, amount: string): TableRow => ({
  id,
  label: desc,
  cells: { date: { value: date }, ref: { value: ref }, amount: { value: amount } },
});

export const REGISTER_ROWS: readonly TableRow[] = [
  reg("aug01", "Aug 1", "Wholesale receipts", "DEP 0801", "18240.50"),
  reg("aug03", "Aug 3", "Larimer Square Properties · rent", "ACH 0803", "-18500.00"),
  reg("aug05", "Aug 5", "Payroll", "ACH 0805", "-22610.84"),
  reg("aug07", "Aug 7", "Card settlement", "DEP 0807", "9412.30"),
  reg("aug09", "Aug 9", "Front Range Roasting Supply", "CHK 10471", "-2960.00"),
  reg("aug12", "Aug 12", "Front Range Roasting Supply", "ACH 0812", "-4180.00"),
  reg("aug13", "Aug 13", "Santos Cooperative · green coffee", "WIRE 0813", "-31206.40"),
  reg("aug14", "Aug 14", "Front Range Roasting Supply", "ACH 0814", "-4180.00"),
  reg("aug16", "Aug 16", "Card settlement", "DEP 0816", "11086.75"),
  reg("aug20", "Aug 20", "Peak Logistics · freight", "ACH 0820", "-3940.12"),
  reg("aug22", "Aug 22", "Wholesale receipts", "DEP 0822", "21904.00"),
  reg("aug27", "Aug 27", "Check", "#10482", "-2180.00"),
  reg("aug28", "Aug 28", "Check", "#10489", "-810.00"),
  reg("aug29", "Aug 29", "Ridgeway Utilities", "ACH 0829", "-1346.22"),
];

export const registerMatch = (row: TableRow): MatchId | undefined =>
  row.id === DUP_ROWS.e212 || row.id === DUP_ROWS.e219 ? regMatch(row.id) : undefined;

// ---- T9c, T9e: Ridgeline 2025 Form 1065 (radio) --------------------------------------------------

interface RidgelineRow {
  id: string;
  band: "client" | "review" | "resolved";
  title: string;
  assignee: string;
  kind: IssueKind;
}

const RIDGELINE_ROWS: readonly RidgelineRow[] = [
  {
    id: "acc",
    band: "client",
    title: "Composition of accrued expenses, accrued sales and payroll liabilities",
    assignee: AGENT,
    kind: "client",
  },
  {
    id: "754",
    band: "client",
    title: "Section 754 election: partners’ decision, statement and Section 755 inputs",
    assignee: AGENT,
    kind: "client",
  },
  {
    id: "k3",
    band: "client",
    title: "Schedules K-2/K-3 domestic filing exception: partner notification and K-3 requests",
    assignee: AGENT,
    kind: "client",
  },
  {
    id: "rp",
    band: "client",
    title: "Related-party balances: counterparties, terms and Section 7872 interest",
    assignee: AGENT,
    kind: "client",
  },
  {
    id: "state",
    band: "client",
    title: "State filing decisions: Colorado, Utah and Arizona composite returns",
    assignee: AGENT,
    kind: "client",
  },
  {
    id: "fa",
    band: "client",
    title: "Fixed asset register: locations, listed-property use and real property ownership",
    assignee: AGENT,
    kind: "client",
  },
  {
    id: "xfer",
    band: "client",
    title:
      "Pell Street Ventures to Pell Street II transfer (6/30/2025): varying-interest data and transfer-date balances",
    assignee: AGENT,
    kind: "client",
  },
  {
    id: "704b",
    band: "review",
    title:
      "704(b) capital for Pell Street Ventures LLC is off by $8,500 against the tax basis roll-forward",
    assignee: STAFF.daniel,
    kind: "review",
  },
  {
    id: "co",
    band: "review",
    title: "Colorado apportionment: payroll factor uses a draft wage file",
    assignee: AGENT,
    kind: "agent",
  },
  {
    id: "ded",
    band: "resolved",
    title: "Guaranteed payments to Ridgeline GP LLC classified as deductions",
    assignee: STAFF.hannah,
    kind: "review",
  },
];

const BANDS = [
  { id: "client", label: "Waiting on the client" },
  { id: "review", label: "Review points" },
  { id: "resolved", label: "Resolved" },
] as const;

/** The radio queue: an issue the agent is fixing stays in its band; a resolved one moves down. */
export function ridgelineGroups(states: Readonly<Record<string, string>>): readonly IssueGroup[] {
  const done = (id: string, band: string): boolean =>
    band === "resolved" || states[id] === "resolved" || states[id] === "na";
  return BANDS.map((b) => {
    const items = RIDGELINE_ROWS.filter((r) =>
      b.id === "resolved" ? done(r.id, r.band) : r.band === b.id && !done(r.id, r.band),
    ).map((r) => ({
      id: r.id,
      title: r.title,
      state: done(r.id, r.band) ? ("resolved" as const) : ("open" as const),
    }));
    return {
      id: b.id,
      label: b.label,
      count: String(items.length),
      items,
      ...(b.id === "resolved" ? { defaultOpen: false } : {}),
    };
  });
}

const RP = {
  blocks: parts(
    "Due from related party *$1,379,849*, due to related party *$206,652* (shown as “payable to partner” on the 2024 return), due from other company *$20,000* and loans to others *$1,750* have no identified counterparty, note or stated rate. Book interest income of *$8,500* on *$1.4 million* of receivables implies a below-AFR rate. The Section 752 recourse allocation of the payable to Pell Street Ventures LLC follows the 2024 Item K pattern and needs the underlying agreement.",
  ),
  cells: [
    { ref: "03 Liabilities!C29", value: "206,652" },
    { ref: "04 GP & Partner Txns!D59", value: "1,379,849" },
    { ref: "04 GP & Partner Txns!E59", value: "20,000" },
    { ref: "04 GP & Partner Txns!H59", value: "1,750" },
    { ref: "04 GP & Partner Txns!D60", value: "8,500" },
  ].map((c) => ({ ...c, match: cell("ridgeline", c.ref) })),
  why: "The balance sheet carries related-party receivables of $1.4 million with no note on file, and the interest booked is below the applicable federal rate. Without counterparties and terms, Schedule L, Item K liabilities and any Section 7872 imputed interest cannot be finished.",
  links: [
    "2025 Ridgeline trial balance.xlsx",
    "2024 Form 1065 · Schedule K-1 (Pell Street Ventures LLC).pdf",
    "Partnership agreement · amended 2023.pdf",
  ].map((name) => ({
    name,
    icon: name.endsWith(".xlsx") ? ("sheet" as const) : ("file" as const),
    match: file(name),
  })),
};

const P704B = {
  blocks: parts(
    "Pell Street Ventures LLC’s 704(b) ending capital is *$8,500* higher than the tax basis roll-forward. Four of the five K-1s are ready; Pell Street Ventures LLC’s waits on this.",
  ),
  cells: [
    { ref: "05 Capital!F14", value: "412,380" },
    { ref: "05 Capital!G14", value: "403,880" },
  ].map((c) => ({ ...c, match: cell("ridgeline", c.ref) })),
  why: "The 704(b) and tax capital roll-forwards disagree by more than the $1,000 review threshold for a single partner.",
  links: [
    {
      name: "Capital account roll-forward.xlsx",
      icon: "sheet" as const,
      match: file("Capital account roll-forward.xlsx"),
    },
  ],
};

export const CO_EXPLAIN =
  "I can replace the draft wage total with the W-3 total and recompute the Colorado factor. Nothing else on the return changes.";

const CO = {
  blocks: parts(
    "The Colorado payroll factor uses *$2,184,300* from a draft wage file; the final W-3 shows *$2,201,950*. Apportionment moves by *0.4%*.",
  ),
  cells: [
    {
      ref: "07 State Apportionment!C12",
      value: "2,184,300",
      match: cell("ridgeline", "07 State Apportionment!C12"),
    },
  ],
  why: "The payroll factor source is a file marked draft by the client, and a final W-3 arrived later.",
  links: [
    {
      name: "Colorado wages · draft.xlsx",
      icon: "sheet" as const,
      match: file("Colorado wages · draft.xlsx"),
    },
    { name: "2025 Form W-3.pdf", icon: "file" as const, match: file("2025 Form W-3.pdf") },
  ],
  explain: CO_EXPLAIN,
};

const KIND_LABEL: Record<IssueKind, string> = {
  client: "Waiting on the client",
  review: "Review point",
  agent: "The agent can fix this",
};

/** The detail of a Ridgeline issue; issues the boards don't open show the related-party detail,
 * as the handoff's kit does. */
export function ridgelineIssue(id: string): T9Issue {
  const row = RIDGELINE_ROWS.find((r) => r.id === id) ?? RIDGELINE_ROWS[3];
  if (row === undefined) throw new Error(`no issue ${id}`);
  const detail = row.id === "704b" ? P704B : row.id === "co" ? CO : RP;
  return {
    kind: row.kind,
    view: {
      id: row.id,
      title: row.title,
      state: row.band === "resolved" ? "resolved" : "open",
      assignee: row.assignee,
      priority: row.kind === "client" ? "Before filing" : "This review",
      severity: { label: KIND_LABEL[row.kind] },
      status: row.band === "resolved" ? "Resolved" : "Open",
      createdBy: row.kind === "review" && row.assignee !== AGENT ? row.assignee : AGENT,
      ...detail,
    },
  };
}
