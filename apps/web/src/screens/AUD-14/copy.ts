// AUD-14 copy (A-08-T29): verbatim from the handoff spec (#aud14). Keys aud14.<state>.<element>.
export const AUD14_COPY = {
  title: "Confirmations",
  back: "‹ Back to cockpit",
  search: "Search",
  newConfirmation: "+ New confirmation",
  filters: {
    type: "Type",
    respondent: "Respondent",
    status: "Status",
    channel: "Channel",
    all: "All",
  },
  tilesLabel: "Confirmations by status",
  columns: [
    "#",
    "Item",
    "Respondent",
    "Address verification",
    "Channel",
    "Sent",
    "Response",
    "Book",
    "Confirmed",
    "Difference",
    "Status",
  ],
  coverage: (
    sent: string,
    population: string,
    pct: string,
    confirmed: string,
    differences: string,
    ct: string,
  ) =>
    `AR sent for confirmation ${sent} of ${population} (${pct}%) · confirmed ${confirmed} · differences ${differences} · CT ${ct}`,
  clientNote:
    "Requests and responses travel only between Brightwater Hale and the respondent. Granite Peak sees only the authorization it signs.",
  waitingOn: "Waiting on Luis Ferrante (SIG-02)",
  viewed: "Viewed Sep 19",
  secondRequest: "2nd request Sep 28",
  authorizationLink: "Authorization (SIG-02)",
  previewLink: "Preview respondent page (POR-17)",
  // A-08-T32 (DEC-5530): the live log's words, from the handoff's rows (C1 to C4) with the dates
  // and people the API answers.
  items: {
    bank: "Bank balances & debt",
    accounts_receivable: "Accounts receivable",
    accounts_payable: "Accounts payable",
    other: "Other",
  },
  channels: {
    network_recorded: "Bank confirmation network",
    accrued_link: "Accrued link (POR-17)",
    mail_recorded: "Mail",
  },
  noResponse: "No response",
  addressCheck: (method: string, initials: string, on: string) => `${method} (${initials}, ${on})`,
  viewedOn: (on: string) => `Viewed ${on}`,
  secondRequestOn: (on: string) => `2nd request ${on}`,
} as const; // fmt: skip
