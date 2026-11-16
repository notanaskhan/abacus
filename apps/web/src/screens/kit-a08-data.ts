// The fieldwork kit's gallery figures (A-08-T26), verbatim from the handoff (AUD-12 a, b, f to h;
// AUD-14 d, e; AUD-26 b, c) and A-08's typed fixtures (fieldwork.ts). Nothing here is summed: the
// kit renders what it is given, and the screens (A-08-T27 on) take the same shapes from the API.
import type { ConfirmationDetailOut, ScoredEntryOut, TestGridOut } from "@abacus/api-client";
import type { MatchId } from "@abacus/ui";
import type { AttributeRow, SelectedEntry, SsarsStep } from "../domain/fieldwork";

type Reason = ScoredEntryOut["reason_codes"][number];
const entry = (
  ref: string,
  on: string,
  amount: string,
  reasons: Reason[],
  score: number,
): ScoredEntryOut => ({
  entry_ref: ref,
  posted_on: on,
  amount,
  account_last4: null,
  description: "",
  score,
  reason_codes: reasons,
  selected: true,
});

/** AUD-12 a: the first page of the 40 selected entries (the handoff's ten rows). */
export const SELECTED_PAGE: SelectedEntry[] = [
  {
    position: 1,
    entry: entry(
      "JE-26-18391",
      "2026-07-08",
      "74000.00",
      ["post_close", "manual_by_role", "round_amount"],
      94,
    ),
    user: "lferrante",
    drcr: "Dr 5000 COGS / Cr 1450 Inventory reserve",
    result: "pass",
  },
  {
    position: 2,
    entry: entry("JE-26-18377", "2026-07-06", "128450.00", ["post_close"], 91),
    user: "gl.controller",
    drcr: "Dr 1200 AR / Cr 4000 Revenue",
    result: "pass",
  },
  {
    position: 3,
    entry: entry(
      "JE-26-17950",
      "2026-06-28",
      "50000.00",
      ["weekend", "round_amount", "manual_by_role", "keyword"],
      89,
    ),
    user: "lferrante",
    drcr: "Dr 2100 Accrued expenses / Cr 6400 Bonus expense",
    result: "needs_human",
  },
  {
    position: 4,
    entry: entry(
      "JE-26-16022",
      "2026-05-31",
      "85000.00",
      ["weekend", "round_amount", "manual_by_role"],
      88,
    ),
    user: "lferrante",
    drcr: "Dr 1500 PP&E / Cr 6100 Repairs",
    result: "pass",
  },
  {
    position: 5,
    entry: entry("JE-26-17994", "2026-06-30", "100000.00", ["round_amount", "keyword"], 86),
    user: "gl.controller",
    drcr: "Dr 6500 Interest expense / Cr 2150 Accrued interest",
    result: "agent_tested",
  },
  {
    position: 6,
    entry: entry("JE-26-18402", "2026-07-10", "52500.00", ["post_close", "keyword"], 83),
    user: "gl.controller",
    drcr: "Dr 2100 Accrued expenses / Cr 5000 COGS",
    result: "pass",
  },
  {
    position: 7,
    entry: entry(
      "JE-26-12877",
      "2026-03-31",
      "1075000.00",
      ["round_amount", "manual_by_role"],
      80,
    ),
    user: "lferrante",
    drcr: "Dr 3100 Dividends / Cr 2050 Dividends payable",
    result: "pass",
  },
  {
    position: 8,
    entry: entry("JE-26-17401", "2026-06-13", "61800.00", ["weekend"], 77),
    user: "ap.clerk2",
    drcr: "Dr 6200 Freight / Cr 2000 AP",
    result: "pass",
  },
  {
    position: 9,
    entry: entry("JE-26-18366", "2026-07-02", "47900.00", ["post_close"], 75),
    user: "gl.controller",
    drcr: "Dr 1300 Inventory / Cr 5000 COGS",
    result: "not_started",
  },
  {
    position: 10,
    entry: entry("JE-26-15530", "2026-05-16", "212400.00", ["weekend"], 72),
    user: "ap.clerk2",
    drcr: "Dr 1300 Inventory / Cr 2000 AP",
    result: "not_started",
  },
]; // fmt: skip

export const INTEREST_MATCH = "ev:front-range-q4#p1:340,402,560,418" as MatchId;

/** AUD-12 a: the attributes for JE-26-17994. */
export const ATTRIBUTES_17994: AttributeRow[] = [
  {
    key: "support",
    label: "Support agrees",
    value: "$100,000.00",
    match: INTEREST_MATCH,
    agreed: true,
  },
  {
    key: "rationale",
    label: "Business rationale",
    value: "Q4 revolver interest accrual per Front Range Bank notice",
    agreed: true,
  },
  {
    key: "authorized",
    label: "Authorized",
    value: "Approved by L. Ferrante, Jun 30",
    agreed: true,
  },
  { key: "period", label: "Posted to correct period", value: "FY2026 P12", agreed: true },
  {
    key: "keyword",
    label: "Keyword reviewed",
    value: "plug to bank interest",
    agreed: true,
    agentNote:
      "Agent: actual Q4 interest per bank notice $101,246.85; difference $1,246.85 is below CT $7,750",
  },
]; // fmt: skip

/** AUD-12 b: Northwind's contribution test, the handoff's first rows and the flagged 8 and 15. */
export const NORTHWIND_GRID: TestGridOut = {
  test_id: "northwind-contributions-2025-12-12",
  variant: "details",
  version_no: 1,
  attributes: ["compensation", "elected_rate", "deferral", "match"],
  counts: {},
  rows: [
    ["Alicia Brennan", "2412.31", "8%", "192.98", "84.43", "pass"],
    ["Tomás Ibarra", "3250.00", "10%", "325.00", "113.75", "pass"],
    ["Priyanka Desai", "1903.85", "6%", "114.23", "66.63", "pass"],
    ["Gordon Whitfield", "6730.77", "15%", "1009.62", "235.58", "pass"],
    ["Mei Tanaka", "2115.38", "6%", "126.92", "74.04", "pass"],
  ].map(([name, comp, rate, deferral, match, state], i) => ({
    item_id: `nw-${String(i + 1)}`,
    position: i + 1,
    record_key: name ?? "",
    state: state as "pass",
    cells: [
      {
        attribute_key: "compensation",
        value: comp ?? null,
        result: "pass" as const,
        by: "agent" as const,
        citation_ids: [],
      },
      {
        attribute_key: "elected_rate",
        value: rate ?? null,
        result: "pass" as const,
        by: "agent" as const,
        citation_ids: [],
      },
      {
        attribute_key: "deferral",
        value: deferral ?? null,
        result: "pass" as const,
        by: "system" as const,
        citation_ids: [],
      },
      {
        attribute_key: "match",
        value: match ?? null,
        result: "pass" as const,
        by: "system" as const,
        citation_ids: [],
      },
    ],
  })),
};

export const NORTHWIND_HEADERS = {
  compensation: "Compensation",
  elected_rate: "Elected rate",
  deferral: "Deferral recalculated",
  match: "QACA match recalculated",
};

/** AUD-14 a: C3 Alpine Ridge Sports with the drawer open (the handoff's DRAWER). */
export const ALPINE_RIDGE_DETAIL: ConfirmationDetailOut = {
  row: {
    id: "c3",
    number: "C3",
    type: "accounts_receivable",
    channel: "accrued_link",
    status: "exception",
    respondent_org: "Alpine Ridge Sports",
    book_total: "286900.00",
    address_independent: true,
    authorization_on_file: true,
    sample_item_ref: null,
    sent_at: "2026-09-18T14:00:00Z",
    viewed_at: null,
    second_request_at: null,
    responded_at: "2026-09-24T16:00:00Z",
    allowed_actions: ["confirmation.accept_reconciliation", "finding.create"],
  },
  lines: [],
  address_verifications: [],
  response: {
    agrees: false,
    attachment_version_ids: [],
    attested: true,
    explanation: null,
    respondent_name: "Alpine Ridge Sports, accounts payable",
    respondent_title: null,
    submitted_at: "2026-09-24T16:00:00Z",
    via: "respondent_page",
  },
  reconciliation: {
    accepted_at: null,
    accepted_by_name: null,
    balance_per_books: "286900.00",
    balance_per_respondent: "282600.00",
    below_clearly_trivial: true,
    classification: "factual",
    items: [
      {
        id: "cm-6281",
        description: "Credit memo CM-6281 dated Jun 28, recorded Jul 2, 2026",
        amount: "-4300.00",
        item_date: "2026-06-28",
        recorded_on: "2026-07-02",
        proposed_by_agent: true,
        citation_ids: [],
      },
    ],
    unreconciled: "0.00",
  },
  why_surfaced_suggestion_id: null,
  finding_id: null,
  misstatement_id: null,
};

export const ALPINE_RIDGE_WHY =
  "The respondent's statement lists credit memo CM-6281 dated June 28. Granite Peak recorded it on July 2, so receivables and revenue at June 30 are overstated by $4,300.";

/** AUD-26 a, c, d: the rail rows for each mode (Lakeshore, Fenwick, Juniper & Oak). */
export const SSARS_STEPS: Record<"review" | "compilation" | "preparation", SsarsStep[]> = {
  review: [
    {
      key: "inquiries",
      label: "Inquiry program",
      state: "in_progress",
      meta: "11 of 14 answered",
    },
    {
      key: "analytics",
      label: "Analytical procedures",
      state: "in_progress",
      meta: "1 over threshold · explained",
    },
    { key: "fs", label: "Financial statements", state: "not_started", meta: "Not started" },
    { key: "report", label: "Review report", state: "not_started", meta: "Not started" },
  ],
  compilation: [
    { key: "read", label: "Read the FS for obvious material misstatements", state: "in_progress" },
    { key: "fs", label: "Financial statements", state: "not_started", meta: "Not started" },
    {
      key: "report",
      label: "Compilation report (AR-C 80)",
      state: "not_started",
      meta: "Not started",
    },
  ],
  preparation: [
    { key: "fs", label: "Financial statements", state: "done" },
    { key: "approval", label: "Approved by Carla Juniper (POR-08)", state: "done" },
    { key: "report", label: "No report — AR-C 70", state: "not_started" },
  ],
}; // fmt: skip
