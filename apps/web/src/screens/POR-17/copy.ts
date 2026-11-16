// POR-17 words, verbatim from the handoff (spec.md and the POR-17a–f artboards). Names, figures and
// the client's authorization come from the API; never from here.

export const COPY = {
  secure: (reference: string) => `Secure confirmation · reference ${reference}`,
  from: (firm: string, client: string) => `From ${firm}, independent auditors of ${client}`,
  heading: {
    receivable: (client: string, asOf: string) =>
      `Please confirm the amount you owed ${client} at ${asOf}`,
    bank: (client: string, asOf: string) =>
      `Please confirm ${client}’s accounts with you at ${asOf}`,
  },
  authorized: (by: string, client: string, on: string) => `— ${by}, ${client} · authorized ${on}`,
  balanceTitle: (client: string) => `Balance per ${client}’s records`,
  balancesTitle: (client: string) => `Balances per ${client}’s records`,
  perClient: (description: string, client: string) => `${description} — balance per ${client}`,
  table: { invoice: "Invoice", date: "Date", amount: "Amount", total: "Total" },
  listEvery: (client: string, asOf: string) =>
    `Please list every deposit and loan account in ${client}’s name at ${asOf}, with its balance, including any not shown above.`,
  accounts: {
    account: "Account",
    type: "Type",
    balanceAt: (asOf: string) => `Balance at ${asOf}`,
    accountPlaceholder: "Account name and number",
    typePlaceholder: "Deposit or loan",
    add: "Add account",
    remove: "Remove account",
  },
  response: {
    title: "Your response",
    agrees: "The balance agrees with our records",
    differs: "The balance does not agree",
    agreesMany: "The balances agree with our records",
    differsMany: "The balances do not agree",
    perOurRecords: "Balance per our records $",
    difference: "Difference $",
    explain: "Explain the difference",
    attachSupport: "Attach a statement or support",
    attachStatement: "Attach your AP statement (optional)",
    attachBankStatement: "Attach your statement (optional)",
    chooseFile: "Choose file",
  },
  who: {
    title: "Who is responding",
    name: "Name",
    namePlaceholder: "Full name",
    title_: "Title",
    company: "Company",
    email: "Email",
    sendCode: "Send code",
    code: "6-digit code",
    attest: "I confirm this response is accurate and that I'm authorized to give it.",
  },
  submitNote: (firm: string, client: string) =>
    `Your response goes only to ${firm}. ${client} won't see it before the auditors do.`,
  submit: "Submit response",
  footer: "Questions: reply to the email this link came in, or call the number on our website.",
  done: {
    title: (firm: string) => `Thank you — your response was sent to ${firm}`,
    response: "Response",
    agrees: (amount: string) => `Agrees · ${amount}`,
    differs: (amount: string) => `Does not agree · ${amount}`,
    submitted: "Submitted",
    verified: "Verified email",
    reference: "Reference",
    close: "You can close this page. This link no longer accepts changes.",
  },
  expired: {
    title: "This confirmation link has expired",
    // DV-7: an expired link gets the uniform answer, so the firm is not named (TASK-8355).
    body: "Contact the firm using the phone number on its website — not the number in this email — to get a new link.",
  },
  answered: (on: string) => `This confirmation was already answered on ${on}.`,
} as const;
