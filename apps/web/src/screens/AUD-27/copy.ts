// AUD-27 · Estimates, related parties & parties in interest (A-05-T57): every word verbatim from
// the handoff (`AUD-27 Estimates- related parties and parties in interest/spec.md`).

export const COPY = {
  title: "Estimates & Related Parties",
  edit: "Edit",
  signOff: "Sign off…",
  sourceDocs: "Source Docs",
  openInExcel: "Open in Excel",
  tabs: {
    estimates: "Estimates",
    related_parties: "Related parties",
    parties_in_interest: "Parties in interest / PT",
  },
  estimates: {
    card: "Estimates",
    columns: ["Estimate", "Balance", "Method", "Retrospective", "Auditor range", "Status"],
    significantRisk: "Significant risk",
    over: (difference: string, percent: string) => `over by ${difference}, ${percent}%`,
    under: (difference: string, percent: string) => `under by ${difference}, ${percent}%`,
    vs: (prior: string, outcome: string) => `${prior} vs ${outcome}`,
    range: (low: string, high: string) => `${low} – ${high}`,
    none: "—",
  },
  method: {
    card: (name: string) => `${name} — method`,
    total: "Total",
    tieTo: (account: string) => `tie to TB ${account}`,
    // The handoff's line with the period dates read from the rollforward's own labels.
    rollforward: (opening: string, usage: string, additions: string, closing: string) =>
      `Opening ${opening} − write-offs ${usage} + provision ${additions} = closing ${closing}`,
    // S31 close (DV-AUD-27-3): the handoff's line, its dates the work item's period.
    rollforwardDated: (
      openOn: string,
      opening: string,
      usage: string,
      additions: string,
      closeOn: string,
      closing: string,
    ) =>
      `${openOn} ${opening} − write-offs ${usage} + provision ${additions} = ${closeOn} ${closing}`,
  },
  bias: {
    card: "Bias indicators",
    // Composed from code's figures: the handoff's sentence, with its numbers the server's.
    none: (count: number, ceiling: string) =>
      `None. ${count === 2 ? "Both" : String(count)} prior-year estimates exceeded outcomes by less than ${ceiling}%; management's point sits inside the auditor's range.`,
    possible:
      "Possible bias: every prior-year estimate differed from its outcome in the same direction.",
  },
  disclosure: { card: "Disclosure", linked: "Linked" },
  requestConclusion: "Request partner conclusion…",
  citations: (n: number) => `Citations (${String(n)})`,
  procedures: (n: number) => `Procedures (${String(n)})`,
  related: {
    columns: ["Party", "Relationship", "Source", "FY2026 transactions", "Disclosure", "Status"],
    source: {
      client_list: "Client list",
      agent_search: "Agent search",
      manual: "Added by the team",
    } as Record<string, string>,
    askManagement: "Ask management (POR-05)",
    finding: "Finding F-3 → AUD-15",
    raise: "Raise exception…",
  },
  pii: {
    columns: ["Party", "ERISA relationship", "2025 transactions", "Exemption", "Reporting"],
    // S31 close (DV-AUD-27-6): the handoff's Form 5330 line, its figures the server's.
    excise: (lostEarnings: string, excise: string) =>
      `Excise tax 15% × ${lostEarnings} = ${excise} unless PTE 2002-51 relief applies`,
    card: "Late remittance as a prohibited transaction",
    lostEarnings: "Lost earnings",
    correction: "Correction",
    form5330: "Form 5330",
    scheduleG: "Schedule G",
    scheduleGNote: "Part III not required — late contributions are reported on line 4a only",
  },
  run: "Run",
};
