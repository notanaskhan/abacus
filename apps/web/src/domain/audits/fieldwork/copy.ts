// The fieldwork kit's words (A-08-T26), verbatim from the handoff (AUD-12, AUD-13, AUD-14, AUD-26
// spec.md and the AUD-12 revision). Screens pass figures; the kit never computes a financial one.
import type { CriterionOut, ScoredEntryOut } from "@abacus/api-client";

export const FIELDWORK_COPY = {
  population: {
    title: "Population",
    source: "Source",
    entries: "Entries",
    lines: "Lines",
    period: "Period",
    completeness: "Completeness",
    difference: "Difference",
    tie: (tied: number, total: number) =>
      `Opening TB + JE activity = closing TB for ${String(tied)} of ${String(total)} accounts`,
    postClose: (through: string) => ` + post-close to ${through}`,
  },
  criteria: {
    title: "Risk criteria",
    count: "Count",
    unique: "Unique entries flagged",
    unavailable: "Not available from this ledger",
    filterAll: "Show all",
    footer: (selected: number, byScore: number, floor: number, unpredictable: number) =>
      `Selected ${String(selected)} = ${String(byScore)} highest scores (≥ ${String(floor)}) + ${String(unpredictable)} unpredictable picks.`,
    approved: (initials: string, on: string) => ` Approved by ${initials} ${on}.`,
    label: {
      weekend_holiday: "Weekend or holiday posting",
      round_amount: "Round dollar",
      post_close: "Post-close",
      manual_by_role: "Manual by senior management",
      keywords: "Keywords",
    } satisfies Record<CriterionOut["key"], string>,
  },
  reasons: {
    weekend: "Weekend",
    holiday: "Holiday",
    round_amount: "Round",
    post_close: "Post-close",
    manual_by_role: "Sr mgmt",
    keyword: "Keyword",
  } satisfies Record<ScoredEntryOut["reason_codes"][number], string>,
  selected: {
    title: (n: number) => `Selected entries · ${String(n)}`,
    pending: (n: number, add: number, initials: string) =>
      `Selected entries · ${String(n)} + ${String(add)} pending approval (${initials})`,
    page: (from: number, to: number, total: number) =>
      `${String(from)}–${String(to)} of ${String(total)}`,
    previous: "Previous page",
    next: "Next page",
    review: "Review in package",
    columns: ["#", "Entry", "Date", "User", "Dr / Cr", "Amount", "Criteria", "Score", "Result"],
    result: {
      pass: "MS",
      needs_human: "Needs human",
      agent_tested: "Agent-tested",
      not_started: "Not started",
      exception: "Exception",
      running: "Testing",
    },
  },
  attributes: {
    title: (ref: string) => `Attributes for ${ref}`,
    agreed: "Agreed",
    open: "Open",
  },
  footer: {
    adopt: "Adopt results (L1)…",
    expand: "Expand testing…",
    raise: "Raise exception…",
    waiting: (name: string) => `Waiting on ${name}`,
  },
  expand: {
    title: "Expand testing",
    byScore: "Add the next entries by score",
    participants: "Add participants",
    unpredictable: "Add unpredictable picks",
    becomes: (n: number) => `Selected becomes ${String(n)} · code recomputes coverage`,
    rationaleLabel: "Rationale",
    rationaleHelp: "Required. A person sends the request; the agent may draft the rationale.",
    approver: "Approver",
    request: "Request approval",
    less: "Fewer",
    more: "More",
  },
  grid: {
    deviations: "Deviation log",
    none: (udl: string, tolerable: string) =>
      `0 deviations · upper deviation limit ${udl} < tolerable ${tolerable}`,
    pass: "Agreed",
    exception: "Exception",
  },
  analytics: {
    columns: ["Line", "Current year", "Prior year", "Change", "Change %", "Status"],
    status: {
      within: "Within threshold",
      unexplained: "Unexplained",
      explained: "Explained",
      accepted: "Accepted",
    } as Record<string, string>,
  },
  runs: { title: "Runs" },
  confirmations: {
    response: "Response",
    reconciliation: "Reconciliation",
    classification: "Classification",
    why: "Why this was surfaced",
    accept: "Accept reconciliation",
    unreconciled: "Unreconciled",
    agrees: "Agrees",
    differs: "Difference",
    noResponse: "No response yet",
    book: "Balance per books",
    confirmed: "Balance per respondent",
    newTitle: "New confirmation",
    type: "Type",
    respondent: "Respondent",
    organisation: "Organisation",
    address: "Address",
    verification: "How you verified the address",
    sources: "Sources",
    send: "Send",
    notVerified:
      "Verify the address before sending. Accrued will not send to an address supplied only by the client.",
    types: {
      bank: "Bank",
      accounts_receivable: "Accounts receivable",
      accounts_payable: "Accounts payable",
      other: "Other",
    },
    sourceNames: {
      client_supplied: "Client-supplied",
      prior_year: "Prior year",
      website: "Website",
      phone: "Phone",
      public_register: "Public register",
      bank_published: "Bank published",
    },
  },
  ssars: {
    modes: { review: "Review", compilation: "Compilation", preparation: "Preparation" },
    rail: "Engagement steps",
  },
} as const;

/** "Jun 28, 2026 (Sun)": a weekend posting date carries its day (AUD-12 acceptance). */
export function postedOn(iso: string, formatted: string): string {
  const day = new Date(`${iso}T12:00:00Z`).getUTCDay();
  if (day === 0) return `${formatted} (Sun)`;
  if (day === 6) return `${formatted} (Sat)`;
  return formatted;
}
