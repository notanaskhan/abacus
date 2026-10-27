// HOME-01 copy, verbatim from the handoff spec.md and revision.md R2 (docs/screens/HOME-01.md,
// Copy). Names, clients, figures and row text are data, never copy. Strings with no handoff source
// are marked "undesigned" (I-01 §5.5).

export const COPY = {
  greeting: {
    morning: (name: string) => `Good morning, ${name}`,
    afternoon: (name: string) => `Good afternoon, ${name}`,
  },
  openToday: "Open Today",
  office: { label: "Office", all: "All offices" },
  running: (n: number) => `${String(n)} running`,
  tiles: {
    taxCaption: (n: number) => `Tax returns · TY2025 · ${String(n)} open`,
    taxOfficeCaption: (office: string, n: number) => `${office} · ${String(n)} returns`,
    /** The four tax tile words, in the demo order: Prepared · In review · Issues · Ready. */
    tax: {
      prepared: "Prepared",
      in_review: "In review",
      action_required: "Issues",
      approved: "Ready",
    },
    audits: (n: number) => `Audits & assurance · ${String(n)}`,
    auditPhases: {
      planning: "Planning",
      fieldwork: "Fieldwork",
      in_review: "In review",
      ready_to_release: "Ready to release",
      released: "Released",
    },
    closesPill: "In progress",
    closesCaption: (total: number) => `of ${String(total)} · August 2026`,
    noticesCaption: "Notices open",
    noticesNew: (n: number) => `${String(n)} New`,
    admin: {
      signatures_out: "Signatures out",
      inbox_waiting: "Inbox waiting",
      portal_invites_pending: "Portal invites pending",
      binders: "Binders",
    },
  },
  pane: { title: "Waiting on you", openQueue: "Open queue" },
  yourWork: {
    "home.your_work.returns": "Your returns",
    "home.your_work.engagements": "Your engagements",
    "home.your_work.mine": "My work",
  } as Record<string, string>,
  empty: {
    title: "Nothing waiting on you.",
    body: "Decisions, sign-offs and approvals that need you appear here.",
  },
  deadlines: { title: "Your deadlines · next 14 days", calendar: "Calendar" },
  next: (on: string, client: string, filing: string) => `Next: ${on} · ${client} · ${filing}`,
  activity: { title: "Client activity" },
  /** Undesigned (I-01-T11): the tile popover's name and its office rows. */
  byOffice: {
    label: (tile: string) => `${tile} by office`,
    row: (office: string, n: number) => `${office} · ${String(n)}`,
    unnamed: "Office",
  },
  /** Undesigned: the region names screen readers announce. */
  error: { tiles: "home", queue: "what waits on you" },
} as const;
