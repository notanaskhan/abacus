// BND-02 copy, verbatim from the handoff spec.md (docs/screens/BND-02.md, Copy). Request titles,
// file names, rail values and client wording are data, never these strings.

export const COPY = {
  back: "All Binders",
  backHint: "Opens BND-01 · all binders",
  openReturn: "Open return",
  openReturnHint: "Opens TAX-03 · return intake",
  tabs: {
    requests: "Requests",
    questions: "Questions",
    activity: "Activity",
    label: "Binder sections",
  },
  rail: {
    title: "Binder",
    published: "Published",
    createdFrom: "Created from",
    visibleTo: "Visible to",
    markedDone: "Marked done",
    reminders: "Reminders",
    template: "Template",
    categories: "Categories",
    notYet: "Not yet",
    /** "Not yet · 2 open" */
    notYetOpen: (open: string) => `Not yet · ${open} open`,
    /** "Every 7 days" */
    every: (days: string) => `Every ${days} days`,
    open: (n: string) => `${n} open`,
    nothing: "Nothing requested",
  },
  canvas: {
    title: "Requests",
    preview: "Preview as client",
    previewHint: "Opens POR-03 as the client sees it, in a 1400 preview sheet",
    sendReminder: "Send reminder…",
    sendReminderHint: "The follow-up sheet comes with P-06-T16",
    newRequest: "Request",
    newRequestHint: "Opens SHL-14 · request composer",
    sectionCount: (done: string, total: string) => `${done} of ${total}`,
  },
  bar: {
    /** "Published Feb 3 · 5 of 7 satisfied · 2 open" (+ " (1 ignored)") */
    published: (date: string, done: string, total: string, open: string, ignored: string | null) =>
      `Published ${date} · ${done} of ${total} satisfied · ${open} open${
        ignored === null ? "" : ` (${ignored} ignored)`
      }`,
    unpublish: "Unpublish…",
    /** "Draft · 7 requests from the 2025 return" */
    draft: (n: string, from: string | null) =>
      from === null ? `Draft · ${n} requests` : `Draft · ${n} requests from the ${from}`,
    publish: "Publish to client…",
    /** "Marked done by Claire Feld · Sep 15, 9:02 AM · 7 of 7" */
    complete: (person: string, when: string, done: string, total: string) =>
      `Marked done by ${person} · ${when} · ${done} of ${total}`,
    unpublished: (date: string, reason: string) => `Unpublished ${date} — ${reason}`,
    closed: (date: string) => `Closed ${date}`,
    overdue: (n: string) => `${n} overdue`,
    progress: (done: string, total: string) => `${done} of ${total} satisfied`,
  },
  row: {
    /** "From 2024 return" */
    fromPriorYear: (year: string) => `From ${year} return`,
    requested: "Requested",
    /** "Requested Feb 3" */
    requestedOn: (date: string) => `Requested ${date}`,
    notPublished: "Not published",
    k1Draft: "Draft K-1 · pre-release",
    /** "Waiting 2" */
    waiting: (n: string) => `Waiting ${n}`,
    waitingHint: "Opens INB-02 · filing for Claire’s 9:12 AM email",
    /** "Uploading 2 files…" */
    uploading: (n: number) => (n === 1 ? "Uploading 1 file…" : `Uploading ${String(n)} files…`),
    /** "Due Aug 31 · 14 days late" */
    late: (date: string, days: number) =>
      `Due ${date} · ${String(days)} ${days === 1 ? "day" : "days"} late`,
    ignored: "Ignored",
    internalOnly: "Internal only — the client won't see this request.",
    visibleOn: (title: string) => `${title}: visible to client`,
    visibleOff: (title: string) => `${title}: hidden from client`,
    menu: (title: string) => `${title} actions`,
    edit: "Edit",
    editHint: "Opens SHL-14 to edit this request",
    waive: "Waive (Not applicable)…",
    returnToClient: "Return to client…",
    delete: "Delete",
  },
  /** The client's Ignore reasons (SPEC-042 codes), in the client's words. */
  ignoreReasons: {
    not_this_year: "Not applicable this year",
    sent_another_way: "Sent another way",
    dont_have: "Don't have it",
  },
  dock: {
    title: "Request",
    requestCard: "Document Request",
    request: "Request",
    category: "Category",
    visible: "Visible to client",
    requestedBy: "Requested by",
    source: "Source",
    wording: "Client wording",
    uploadCard: "Uploaded Document",
    status: "Status",
    file: "File",
    uploadedBy: "Uploaded by",
    /** "1 of 5 files" */
    ofFiles: (n: string) => `1 of ${n} files`,
    clientReason: "Client’s reason",
    openViewer: "Open in viewer",
    openViewerHint: "Opens SHL-08 · source viewer",
    replaceK1: "Replace with final K-1",
    replaceK1Hint: "Enabled after the TXP-12 release",
    waive: "Waive (Not applicable)",
    returnToClient: "Return to client…",
    remind: "Send reminder for this request",
    empty: "Select a request to see it here.",
  },
  preview: {
    title: "Preview as client",
    todo: "To do",
    done: "Done",
    ignored: "Ignored",
    close: "Close",
  },
  activity: {
    empty: "No activity yet.",
    events: {
      "binder.created": "Created the binder",
      "binder.published": "Published the binder",
      "binder.publish_undone": "Undid the publish",
      "binder.unpublished": "Unpublished the binder",
      "binder.marked_done": "Marked the binder done",
      "request_item.sent": "Sent a request",
      "request_item.ignored_by_client": "Ignored a request",
      "request_item.returned_to_client": "Returned a request to the client",
      "request_item.waived": "Waived a request",
      "request_item.visibility_changed": "Changed a request's visibility",
    } as Readonly<Record<string, string>>,
  },
  dialogs: {
    publishTitle: "Publish to client",
    publishTo: (people: string) => `Visible to ${people}`,
    publish: "Publish",
    unpublishTitle: "Unpublish binder",
    reason: "Reason",
    unpublish: "Unpublish",
    waiveTitle: "Waive as not applicable",
    waiveReason: "Reason",
    waiveNote: "Note",
    waive: "Waive",
    returnTitle: "Return to client",
    returnNote: "Note to the client",
    returnIt: "Return",
    cancel: "Cancel",
  },
  waiveReasons: {
    not_applicable_this_year: "Not applicable this year",
    already_sent: "Already sent",
    dont_have: "Client doesn't have it",
    firm_waived: "Waived by the firm",
  },
  toasts: {
    published: (binder: string) => `Published ${binder}`,
    unpublished: (binder: string) => `Unpublished ${binder}`,
    gate: "Not published: the engagement letter is not signed yet",
    hidden: "Hidden from the client",
    shown: "Visible to the client",
    waived: "Waived as not applicable",
    returned: "Returned to client with your reason",
    deleted: "Request deleted",
    failed: "Couldn’t update the binder",
  },
} as const;
