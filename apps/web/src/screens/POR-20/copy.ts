// POR-20 copy (R-01-T25; docs/screens/POR-20.md "Copy"). Chrome and fixed strings only: template
// subjects, blocks and buttons are firm content from the server, never here (AGENTS 16). The
// strings the handoff reserved without copy (flag off, stale draft, lint words, the second band,
// Reply-To, not published) are written here by R-01-T25 inside the copy bans (DEC-567).

import type { LintFindingOut } from "@abacus/api-client";

export const COPY = {
  subbar: {
    back: "Firm settings",
    title: "Email templates",
    context: "Portal & client experience",
  },
  structureHeader: "Portal › Email templates",
  band: {
    templates: "Templates",
    registered: "Templates other areas add",
    schedule: "Reminder schedule",
    variables: "Variables",
    rules: "Rules",
  },
  usedBy: (label: string): string => `Used by ${label}`,
  pill: {
    published: (n: number): string => `Published · v${String(n)}`,
    draft: (n: number): string => `Draft changes · v${String(n)}`,
    publishedBy: (n: number, date: string, person: string): string =>
      `Published · v${String(n)} · ${date} by ${person}`,
    notPublished: "Not published yet",
  },
  schedule: {
    cadence: "Cadence",
    cadenceValue: (n: number): string => `Every ${String(n)} days until done`,
    max: "Maximum reminders",
    sendAt: "Send at",
    sendAtValue: (time: string, weekdays: boolean): string =>
      `${weekdays ? "Weekdays · " : ""}${time} recipient's time`,
    stopWhenDone: "Stop when the client marks the binder done",
    copyPreparer: "Copy the assigned preparer",
  },
  rulesBody:
    "Emails never include account numbers, SSNs, tax amounts or attachments. Everything sensitive stays in the portal.",
  paper: {
    widthLabel: "Preview width",
    w600: "600",
    w390: "390",
    phone: "Phone",
    sendTest: "Send test…",
    discard: "Discard",
    publish: (n: number | null): string => (n === null ? "Publish" : `Publish v${String(n)}`),
  },
  meta: {
    from: "From",
    recipient: "To",
    subject: "Subject",
    replyTo: "Reply-To",
    sampleClient: "Sample client",
  },
  editing: {
    bar: "Editing · choose a variable on the left to insert it at the cursor",
    done: "Done",
    blockLabel: (id: string): string => `Block ${id}`,
    subject: "Subject",
  },
  phone: { back: "Inbox", toMe: "to me" },
  testSheet: {
    title: "Send a test email",
    sendTo: "Send to",
    email: "Email",
    sample: "Sample recipient",
    note: "The test fills in this person's details and goes only to you.",
    cancel: "Cancel",
    send: "Send test",
  },
  toastTestSent: (email: string): string => `Test sent to ${email}`,
  flagOffNote: "Template editing is off for your firm. Published templates are shown read-only.",
  staleDraft: "This draft changed since you opened it. The latest draft is shown.",
  findingsTitle: "Fix these before you send a test or publish",
  previewTitle: "Email preview",
  showText: "Show plain text",
  hideText: "Hide plain text",
  stepUpTitle: "Confirm it's you to publish",
  stepUpBody: "Publishing a template needs a recent second sign-in step.",
  signInAgain: "Sign in again",
  loadError: "email templates",
  on: "On",
  off: "Off",
} as const;

/** What each lint finding asks of the editor (`lint.<code>`; the codes are R-01-T23's). */
export const LINT: Readonly<Record<LintFindingOut["code"], string>> = {
  amount: "Remove the amount: emails never include tax amounts.",
  tin_shape: "Remove the SSN or TIN: it stays in the portal.",
  account_number: "Remove the account number: it stays in the portal.",
  attachment: "Emails never carry attachments: point to the portal instead.",
  second_button: "Keep to one button: remove the extra call to action.",
  unregistered_variable: "This variable isn't available in this template.",
  foreign_link: "The only link is the portal button: remove this link.",
  platform_name: "Client emails show only your firm's name: remove the platform's name.",
  banned_word: "Use the words clients see: this word isn't used in client email.",
};

/** Where a finding is: a block's id, or the subject, preheader or button. */
export function whereOf(blockId: string | null | undefined, variable?: string | null): string {
  if (variable !== null && variable !== undefined) return `{${variable}}`;
  if (blockId === "subject") return COPY.meta.subject;
  if (blockId === "preheader") return "Preheader";
  if (blockId === "cta_label") return "Button";
  return blockId ?? "";
}
