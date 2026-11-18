// ADM-14 copy (G-04-T18, DEC-5639): verbatim from the ADM-14 handoff spec and the docs/screens
// artboard table. Figures come from the reads, never from here.
export const COPY = {
  title: "Plan & usage",
  settings: "Settings",
  firmSettings: "Firm settings",
  back: "‹ Back",
  month: (from: string, to: string, day: number, of: number) =>
    `Usage month ${from} – ${to} · day ${String(day)} of ${String(of)}`,
  requestMore: "Request more…",
  readOnly: "Only firm admins can change alerts and billing contact.",
  minutes: {
    title: "Agent-minutes",
    of: (included: string) => ` of ${included} included`,
    nextAlert: (pct: number, at: string, away: string, reset: string) =>
      `Next alert at ${String(pct)}% (${at}) · ${away} agent-minutes away · included minutes reset ${reset}`,
    left: (left: string, reset: string) => `${left} left until ${reset}`,
    // ADM-14 b: the banner names the newest alert; the helper the one before it.
    sentBanner: (pct: number, at: string, to: string) =>
      `${String(pct)}% of included agent-minutes used · alert sent ${at} to ${to}`,
    sentEarlier: (pct: number, at: string) => ` · ${String(pct)}% alert sent ${at}`,
    resetTomorrow: (on: string) => `Included minutes reset tomorrow, ${on}`,
    and: " and ",
    over: (n: string) =>
      `${n} agent-minutes over included · agents keep running (setting: Keep agents running) · overage is billed on the next invoice at the order-form rate`,
    byLine: "By service line",
  },
  alerts: {
    title: "Budget alerts",
    chip: "Firm · engagement",
    rule: (pct: number, at: string, first: boolean) =>
      first ? `Firm · ${String(pct)}% of included (${at})` : `Firm · ${String(pct)}% (${at})`,
    groups: "Partners and firm admin",
    at100: "At 100%",
    keep: "Keep agents running · overage billed",
    pause: "Pause scheduled agents only",
    engagement: "Engagement",
    defaultBudget: "Default engagement budget",
    perMonth: (n: string) => `${n} agent-minutes per usage month`,
    defaultHelp: (pct: number) =>
      `Alert the engagement manager at ${String(pct)}%. Agent columns check their estimate against it before a run.`,
    budgetRow: (used: string, budget: string, pct: string) => `${used} of ${budget} (${pct}%)`,
    sent: (when: string, who: string) => `Alert sent ${when} · ${who}`,
  },
  seats: {
    title: "Plan & seats",
    term: "Term",
    annual: (from: string, to: string) => `Annual · ${from} – ${to}`,
    renewal: "Renewal",
    inDays: (on: string, n: number) => `${on} · in ${String(n)} days`,
    contact: "Billing contact",
    seats: "Seats",
    used: (used: number, total: number) => `${String(used)} of ${String(total)} used`,
    full: "Full",
    fullHelp: "Add seats from People or Request more.",
    workbench: "Workbench active, 30 days",
    active: (n: number, of: number) => `${String(n)} of ${String(of)} ›`,
  },
  rates: {
    title: "Billing rates",
    band: (label: string, people: number) => `${label} (${String(people)})`,
    perHour: (rate: string) => `${rate} / h`,
    nonChargeable: "Non-chargeable",
    effective: (on: string) =>
      `Effective ${on}. Read-only here; change rates in CCH Axcess Practice. Used for standard value and realization (Budget & effort, Insights).`,
    notConnected: "Billing rates are not connected",
  },
  modules: {
    title: "Modules",
    names: {
      tax_services: "Tax",
      audit_assurance: "Audit & assurance",
      client_accounting: "Client accounting",
      advisory: "Advisory",
      attest: "Attest (SOC & readiness)",
      internal_audit: "Internal audit",
    } as Readonly<Record<string, string>>,
    library: "Agent library",
    stable: "Stable channel · monthly releases",
    help: "Modules are set on the order form. Ask for changes with Request more…",
  },
  request: {
    title: "Request more",
    seats: "Seats",
    minutes: "Agent-minutes",
    reason: "Reason",
    approval: (name: string) => `Partner approval: ${name}`,
    send: "Send request",
  },
  saved: "Plan & usage saved",
  save: "Save",
  discard: "Discard",
  unsaved: "Unsaved changes",
} as const;
