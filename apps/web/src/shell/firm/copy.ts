// The firm shell's interim frames (P-01-T02). The shortcut list is SHL-03's ("Keyboard shortcuts
// → shortcuts dialog (560w) listing ⌘K Go…, G H Home, G T Tax Returns, G A Audits, G C Closes,
// G W Workbench, ? Help"); "Support" and "System status" are SHL-05's words. The rest is the
// undesigned interim copy of P-01 §2.2, reviewed by AY (DEC-32 pattern, recorded in TASK-396).

export const INTERIM_GO = {
  placeholder: "Go to an area",
  areas: "Areas",
  shortcutsTitle: "Shortcuts",
  shortcuts: [
    { keys: "⌘K", label: "Go…" },
    { keys: "G H", label: "Home" },
    { keys: "G T", label: "Tax Returns" },
    { keys: "G A", label: "Audits" },
    { keys: "G C", label: "Closes" },
    { keys: "G W", label: "Workbench" },
    { keys: "?", label: "Help" },
  ],
} as const;

export const INTERIM_SUPPORT = {
  title: "Support",
  contact: "Accrued Support",
  contactLine: (email: string) => `Write to ${email}`,
  status: "System status",
} as const;

// SHL-03, verbatim from the handoff (spec.md and the canvas's built frames, `shl3Vals`). The tray's
// accessible name and the profile drawer are undesigned (AC 2.1.5: "This state is undesigned and
// reviewed by AY"); their words are recorded in docs/screens/SHL-03.md.
export const FIRM_MENU = {
  label: "Firm and profile",
  firmHeader: "Firm",
  sandboxLine: "Sandbox · seeded demo data only",
  sandboxPill: "Sandbox",
  profile: "Your profile",
  office: "Default office filter",
  allOffices: "All offices",
  notificationPreferences: "Notification preferences",
  shortcuts: "Keyboard shortcuts",
  shortcutKeys: ["⌘", "/"],
  viewOnly: "View only",
  signOut: "Sign out",
  version: (v: string) => `Version ${v}`,
  seats: (n: number) => `${String(n)} seats`,
  switched: (firm: string) => `Switched to ${firm}`,
  admin: {
    firm_settings: "Firm settings",
    users_roles: "Users & roles",
    security_center: "Security center",
    developer_api: "Developer & API",
    audit_log: "Audit log",
  },
} as const;

// SHL-04, verbatim from spec.md (states 1–6) and the R2 revision. The tab track's accessible name
// is undesigned; the load error reuses the v1 drawer's words (SPEC-305).
export const NOTIFICATIONS = {
  title: "Notifications",
  markAllRead: "Mark all read",
  tabsLabel: "Notification kinds",
  tabs: {
    all: "All",
    approvals: "Approvals",
    mentions: "Mentions",
    client_activity: "Client activity",
  },
  openApprovals: "Open approvals queue →",
  emptyAll: {
    title: "You're all caught up.",
    body: "Approvals, mentions, client uploads and finished runs appear here.",
  },
  emptyApprovals: {
    title: "No approvals waiting on you.",
    body: "Decisions, sign-offs and agent proposals that need you appear here.",
  },
  showing: "Showing 30 days",
  unread: "Unread",
  loading: "Loading notifications",
  error: "Couldn't load notifications",
  retry: "Retry",
  // P-01-T10 follow-up: row d's inline pair, its receipt and Undo (SHL-04 spec frame 3).
  accept: "Accept",
  returnAction: "Return…",
  returnTitle: "Return",
  returnConfirm: "Return",
  reason: "Reason (required)",
  chooseReason: "Choose a reason",
  note: "Note",
  noteRequired: "Note (required)",
  noteToClient: "The client will see this note.",
  accepted: (name: string, time: string) => `✓ Accepted by ${name} · ${time}`,
  returned: (name: string, time: string) => `Returned by ${name} · ${time}`,
  undo: "Undo",
  failed: "That didn't work. Try again.",
  // R2: the footer menu, the four kinds with "In Accrued · Email".
  settings: "Notification settings",
  settingsChannels: "In Accrued · Email",
  inApp: "In Accrued",
  email: "Email",
  kinds: {
    mention: "Mention",
    todo_assigned: "To-do assigned",
    template_update_available: "Template update available",
    trigger_run_finished: "Trigger run finished",
  } as Record<string, string>,
} as const;

export const PROFILE = {
  title: "Your profile",
  note: "Ask your firm admin to change these",
  name: "Name",
  initials: "Initials",
  role: "Role",
  jobTitle: "Job title",
  office: "Office",
  email: "Email",
  timeZone: "Time zone",
  // G-01 AC6.1: the annual independence self-confirmation (the statement is the firm's text).
  annual: (year: number) => `Annual independence confirmation · ${String(year)}`,
  annualConfirmAction: "Confirm…",
  annualConfirmed: (date: string) => `Confirmed ${date}`,
  annualDeclined: (date: string) => `Declined ${date}`,
  annualTitle: (year: number) => `Annual independence confirmation · ${String(year)}`,
  annualConfirm: "Confirm",
  annualDecline: "Decline",
  annualNote: "Note (required to decline)",
  annualNoStatement: "Your firm hasn't published its independence statement yet.",
  annualFailed: "That didn't work. Try again.",
} as const;
