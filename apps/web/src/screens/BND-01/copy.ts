// BND-01 copy, verbatim from the handoff spec.md (docs/screens/BND-01.md, Copy). Row text is data.

export const COPY = {
  title: "Binders",
  noun: "binders",
  chips: {
    service: "Service",
    season: "Season",
    office: "Office",
    officeAll: "All offices",
    preparer: "Preparer",
    preparerAll: "All",
    activity: "Client activity",
  },
  activity: { any: "Any", none_30_days: "None in 30 days" },
  /** "241 TY2025 binders · 224 returns · 17 second-part binders" */
  summary: (total: string, season: string, returns: string, parts: string) =>
    `${total} ${season} binders · ${returns} returns · ${parts} second-part binders`,
  /** "+ New binder" in spec.md: the plus is the button's icon, and an opener of a sheet ends in
   * "…" (plan 04 rule 9; DV-12 in docs/screens/BND-01.md). */
  newBinder: "New binder…",
  /** The pane header's "Send reminders…"; with a row selected, the bulk bar's "Send reminder…"
   * (spec.md layout and state b). UI words stay "reminder"; identifiers say follow_up (DV-7). */
  sendReminders: "Send reminders…",
  sendReminder: "Send reminder…",
  columns: {
    binder: "Binder",
    client: "Client",
    workItem: "Work item",
    requests: "Requests",
    status: "Status",
    activity: "Last client activity",
    prep: "Prep",
    menu: "Actions",
  },
  /** "5 of 7" */
  progress: (done: string, total: string) => `${done} of ${total}`,
  /** The Ferris tag, "§7216 consents 1 of 2": opens CLI-05's Consents (DEC-1288). */
  consentsTag: (signed: number, total: number) =>
    `§7216 consents ${String(signed)} of ${String(total)}`,
  /** "Unpublished Sep 2 by Remy Vidal — fixing 2 requests" */
  unpublished: (date: string, person: string, reason: string) =>
    `Unpublished ${date} by ${person} — ${reason}`,
  yesterday: "Yesterday",
  empty: {
    title: (season: string) => `No ${season} binders yet.`,
    body: (prior: string) => `Season setup creates binders from each client's ${prior} return.`,
    action: "Open season setup",
    actionHint: "Opens ENG-07 · season setup and roll-forward",
  },
  menu: {
    label: (binder: string, client: string) => `${binder} · ${client} actions`,
    publish: "Publish",
    unpublish: "Unpublish…",
    duplicate: (part: number) => `Duplicate as pt ${String(part)}`,
    files: "Open in Files",
  },
  unpublishDialog: {
    title: "Unpublish binder",
    reason: "Reason",
    placeholder: "fixing 2 requests",
    confirm: "Unpublish",
  },
  toasts: {
    published: (binder: string, client: string) => `Published ${binder} · ${client}`,
    unpublished: (binder: string, client: string) => `Unpublished ${binder} · ${client}`,
    duplicated: (binder: string) => `Created ${binder} as a Draft`,
    created: "Created the binder as a Draft",
    gate: "Not published: the engagement letter is not signed yet",
    failed: "Couldn’t update the binder",
  },
  sheet: {
    title: "New binder",
    engagement: "Client",
    workItem: "Work item",
    template: "Template",
    blank: "Blank",
    choose: "Choose",
    create: "Create",
  },
} as const;
