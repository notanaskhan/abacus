// ADM-08 copy, verbatim from the handoff (screens/ADM-08 spec.md). Accrued records and mirrors;
// the ERO transmits in CCH Axcess (R-04): no phrase here has Accrued or the agent export, post,
// transmit or file a return.

export const COPY = {
  title: "Integrations",
  back: "Settings",
  navTitle: "Settings",
  segments: { tax: "Tax engine", ledgers: "Ledgers", mailboxes: "Mailboxes" },
  test: "Test connection",
  discard: "Discard",
  save: "Save",
  engine: {
    title: "CCH Axcess Tax",
    connected: "✓ Connected",
    rows: {
      connection: "Connection",
      last_sync: "Last sync",
      return_id_template: "Return ID convention",
      client_code_rule: "Client code rule",
      new_version_on_import: "New version on each import",
    },
    returnIdHelp:
      "Examples: 2025I:FeldJ:V3 · 2025P:Ridgeline:V2 · 2025P:Harborview:V3 · 2025F:Calloway:V1. Type letters: I 1040 · P 1065 · S 1120-S · C 1120 · F 1041 · X 990.",
    clientCodeHelp:
      "FeldJ = Feld, Jonah · Ridgeline = Ridgeline Property Partners, LP · Harborview = Harborview Dental Properties, LP · Calloway = Calloway Family Trust.",
    rulesTitle: "Export & import rules",
    rules: {
      export_after_final_approval: "Export only after final approval",
      who_may_export: "Who may export",
      import_requires_approval: "Import requires approval",
      read_diagnostics: "Read diagnostics back after export",
      efile_status_every: "Read e-file status",
    },
    usersTitle: "User mapping",
    usersMapped: (n: number, total: number) =>
      `Tax team — ${String(n)} of ${String(total)} mapped to CCH staff IDs`,
    unmapped: (n: number) => `Unmapped — ${String(n)}`,
    editMapping: "Edit mapping ›",
    officesTitle: "Office mapping",
  },
  mirror: {
    title: "Workflow status mirror",
    on: "Mirror on",
    help: "Accrued pushes return status and due dates to CCH Axcess workflow projects. Assignments flow back.",
    columns: ["Accrued status", "→", "Workflow status", "Direction"] as const,
    oneWay: "one-way",
    twoWay: "two-way",
    footer: "Last mirror 9:22 AM · 79 open TY2025 returns in sync · 0 conflicts",
    conflict: "Each workflow status may map from one Accrued status.",
  },
  connected: {
    band: (n: number) => `Connected · ${String(n)}`,
    footer: "Workbench › Connect ›",
  },
  ledgers: {
    title: "General ledger posting",
    rows: {
      post_only_approved: "Post only human-approved batches",
      attest_clients: "Attest clients",
      journal_memo: "Journal memo",
      journal_prefix: "Journal number prefix",
      post_as: "Post as",
    },
    help: "Client-ledger OAuth is granted by the client in the portal (POR-16).",
    needsReauth: "Needs reauth",
    failedHelp:
      "The Sage Intacct user lacks permission to create journal entries. Ask Arjun Mehta to grant 'GL journal: add' and reconnect in the portal (POR-16).",
    reconnect: "Send reconnect request",
  },
  mailboxes: {
    rows: {
      mailbox: "Mailbox",
      auto_classify: "Auto-classify attachments",
      match_sender: "Match sender to client by contacts and domains",
      unmatched_senders: "Unmatched senders",
      route_upload_something_else: "Route portal “Upload something else” to Inbox",
      notices_intake: "Notices to Notices intake",
    },
  },
  testPassed: (n: number) => `Test passed · ${String(n)} returns read · 412 ms`,
  testPassedToast: "CCH Axcess Tax test passed",
  testFailed: (problem: string) => `Test failed · ${problem}`,
  drawer: { title: "Edit mapping", staffId: "CCH staff ID" },
  saved: "Integration settings saved",
} as const;
