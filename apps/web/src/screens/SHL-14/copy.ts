// SHL-14 copy, verbatim from the handoff spec.md and revision.md R2 (docs/screens/SHL-14.md,
// Copy). Field values (titles, descriptions, due dates, people) are data, never copy.

export const COPY = {
  title: { new: "New request", existing: "Request" },
  tabs: {
    label: "Request sections",
    details: "Details",
    comments: "Comments",
    activity: "Activity",
  },
  pill: { draft: "Draft" },
  card: {
    documentRequest: "Document request",
    people: "People",
    links: "Links",
    preview: (name: string) => `Preview — what ${name} sees`,
  },
  keys: {
    request: "Request",
    category: "Category",
    description: "Description",
    due: "Due",
    wave: "Wave",
    clientAssignee: "Client assignee",
    thirdParty: "Request from a third party",
    delegate: "Third party",
    firmOwner: "Firm owner",
    visibility: "Visibility",
    reminders: "Reminders",
    linkedWorkpaper: "Linked workpaper",
    supports: "Supports",
    relatedRows: "Related rows",
    controls: "Controls",
    attachments: "Attachments",
  },
  wave: { planning: "Planning", year_end: "Year-end", sample: "Sample" },
  visibility: { owners: "Owners only", client: "Client" },
  visibilityDraftHelp: "Becomes Client when sent",
  reminders: (n: number) => `Every ${String(n)} days until received`,
  remindersHelp: "Sent from the pre-approved reminder template",
  thirdPartyHelp: (delegate: string, assignee: string) =>
    `${delegate} sees only this request (POR-14). ${assignee} is copied.`,
  attachmentsEmpty: "No attachments",
  controlsNone: "—",
  choose: "Choose",
  datePlaceholder: "YYYY-MM-DD",
  preview: {
    upload: "Upload…",
    ignore: "Ignore",
    due: (date: string) => `Due ${date}`,
  },
  footer: {
    adds: (done: string, total: string) =>
      `Adds 1 request · Source Documents will read ${done} of ${total} received`,
    saveDraft: "Save draft",
    saveSend: "Save & send",
    sendTo: (name: string) => `Save & send to ${name}`,
    approveSend: "Approve & send",
    approveSendTo: (name: string) => `Approve & send to ${name}`,
    modelText: "Edit the client wording before sending",
  },
  validation: { due: "Add a due date to send", date: "Enter a date as YYYY-MM-DD." },
  toast: {
    sent: (name: string) => `Request sent to ${name}`,
    saved: "Draft saved",
    failed: "Couldn’t save the request.",
  },
  activity: {
    drafted: "Drafted by Accrued Agent in the BH-FS-430 procedure session",
    sent: (who: string) => `Sent by ${who}`,
    empty: "No activity yet.",
  },
  comments: { empty: "No comments yet." },
  // The close variant (d, P-06-T24), verbatim from spec.md state 4 with R2 item 3 (the "Visible to
  // client" toggle reads as the Visibility row, Client).
  close: {
    documentRequest: "Document Request",
    uploadCard: "Uploaded Document",
    keys: {
      requestedBy: "Requested by",
      status: "Status",
      file: "File",
      uploadedBy: "Uploaded by",
    },
    markIncorporated: "Mark incorporated",
    return: "Return…",
  },
} as const;
