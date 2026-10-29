// INB-02 · Attachment triage & File-to (N-01-T15; docs/screens/INB-02.md "Copy"; handoff INB-02
// spec). Verbatim; templated strings take their values from the triage bundle.
export const COPY = {
  title: "File attachments",
  subtitle: (subject: string, sender: string): string => `${subject} · ${sender}`,
  apply: (n: number): string => `Apply ${String(n)}`,
  destination: "Suggested destination",
  openRequest: (date: string): string => `Open request · Requested ${date}`,
  alreadyOnFile: "Already on file",
  candidates: "Choose where this goes",
  flags: "Flags",
  noFlags: "No flags.",
  flag: {
    wrongYear: (year: number, open: number): string =>
      `Tax year ${String(year)} ≠ ${String(open)} (the open return).`,
    duplicate: (file: string, date: string): string =>
      `Duplicate of ${file} (identical hash, received ${date}).`,
    duplicateOfNotice: "Duplicate of notice on file",
    tinMismatch: (form: string, record: string): string =>
      `SSN differs from the client record (last four ${form} vs ${record})`,
    ambiguous: "Two charges match this amount; the receipt date is not legible.",
    replacement: (file: string, channel: string, date: string): string =>
      `Possible replacement for ${file} (${channel} ${date})`,
  },
  rows: {
    form: "Form",
    taxYear: "Tax year",
    issuer: "Issuer",
    taxpayer: "Taxpayer",
    matches: "matches client record",
    supersede: "Supersede earlier",
    supersedeNone: (year: number | null, form: string | null): string =>
      `No ${year === null ? "" : `${String(year)} `}Form ${form ?? ""} on file to replace.`,
    keepBoth: "Keep both versions",
    renameTo: "Rename to",
    decision: "Decision",
    reason: "Reason",
    tellClient: "Tell the client",
    tellClientOff: "Off: nothing is sent. Ignored attachments stay in the email record.",
  },
  decisions: { file: "File", ignore: "Ignore", hold: "Hold — ask client" },
  reasons: {
    wrong_year: "Wrong year",
    duplicate: "duplicate",
    not_ours: "Not ours",
    spam: "Spam",
    unreadable: "Unreadable",
    other: "Other",
  },
  holdPreview: "We received a W-2c whose SSN doesn't match our records. Please confirm…",
  formNames: {
    "1095-C": "Form 1095-C · Employer-Provided Health Insurance Offer and Coverage",
  } as Readonly<Record<string, string>>,
  strip: (pages: number | null, kb: number, sha: string): string =>
    `${pages === null ? "" : `${String(pages)} pages · `}${String(kb)} KB · SHA-256 ${sha.slice(0, 4)}…${sha.slice(-4)}`,
  footer: (time: string, viewer: string, notify: readonly string[]): string =>
    `Accrued Agent classified these attachments at ${time}. Filing is recorded as ${viewer}.` +
    (notify.length > 0 ? ` ${notify.join(", ")} (preparer) is notified.` : ""),
  toast: (filed: number, ignored: number, held: number, notified: readonly string[]): string =>
    [
      filed > 0 ? `Filed ${String(filed)}` : null,
      ignored > 0 ? `Ignored ${String(ignored)}` : null,
      held > 0 ? `Held ${String(held)}` : null,
      notified.length > 0 ? `${notified.join(", ")} notified` : null,
    ]
      .filter((p) => p !== null)
      .join(" · "),
  changed: "This changed while you were deciding. Review again.",
} as const;
