// CLS-11's words, verbatim from the handoff (screens/CLS-11 spec.md, artboards a, a2, c, d, d2)
// and the status vocabulary. Deviations (docs/screens/CLS-11.md): Write scope reads "Journal
// entries · closing date" (DEC-5509); the reconnect dialog names the owner, never a pronoun, since
// the owner varies by client (DEC-5924).
export const COPY = {
  title: "Ledger sync",
  back: (period: string) => `${period} Close`,
  filters: {
    period: "Period",
    status: "Status",
    type: "Type",
    all: "All",
    year: "2026",
    statuses: { posted: "Posted", proposed: "Proposed", failed_post: "Failed post" },
    types: { batches: "Batches", events: "Sync events" },
  },
  tiles: {
    posted: "Posted",
    proposed: "Proposed",
    failed: "Failed post",
    closingDate: "Closing date",
    resolvedCaption: (n: number, on: string) => `Failed post: ${String(n)} resolved ${on}`,
  },
  banner: {
    expired: (company: string, owner: string) =>
      `QuickBooks Online authorization for ${company} expired. ${owner} must reconnect from the client portal.`,
    sent: (owner: string, at: string) => `Reconnect request sent to ${owner} · ${at}`,
  },
  connection: {
    title: "Connection",
    company: "Company",
    authorizedBy: "Authorized by",
    authorizedByValue: (name: string, on: string) => `${name} (client portal) · ${on}`,
    expired: "expired",
    mode: "Mode",
    modeWrite: "Client-authorized: read ledger, post approved entries",
    modeRead: "Client-authorized: read ledger",
    lastSync: "Last sync",
    lastSyncValue: (at: string, read: string | null, errors: number | null) =>
      [
        at,
        read === null ? null : `${read} transactions read`,
        errors === null ? null : `${String(errors)} errors`,
      ]
        .filter((p) => p !== null)
        .join(" · "),
    failedRateLimit: (at: string, retry: string | null) =>
      retry === null
        ? `failed ${at} · QuickBooks Online rate limit`
        : `failed ${at} · QuickBooks Online rate limit · retrying ${retry}`,
    failedExpired: (at: string) => `failed ${at} · authorization expired`,
    failed: (at: string) => `failed ${at}`,
    nextSync: "Next sync",
    hourly: (at: string) => `${at} (hourly)`,
    retry: (at: string) => `${at} (retry)`,
    paused: (owner: string) => `Paused until ${owner} reconnects`,
    closingDate: "Closing date",
    closingDateValue: (on: string, by: string | null, at: string | null) =>
      by === null || at === null ? on : `${on} · set by ${by}, ${at}`,
    writeScope: "Write scope",
    writeScopeValue: "Journal entries · closing date",
    readOnly: "Read only",
    agents: "Agents using it",
    syncNow: "Sync now",
    retryNow: "Retry now",
    syncing: "Syncing…",
    requestReconnect: "Request reconnect…",
    integration: "Integration details ›",
    noConnection: "No QuickBooks Online connection for this entity.",
  },
  log: {
    title: "Posting log",
    export: "Export",
    columns: ["Batch", "Period", "Entries", "Amount", "Status", "Posted", "QuickBooks ids", "By"],
    approved: (n: number, of: number) => `${String(n)} of ${String(of)} approved`,
    postingPaused: "posting paused",
    resolved: (n: number) => `${String(n)} failure resolved`,
    qbo: (first: string, last: string) =>
      first === last ? `QBO ${first}` : `QBO ${first}–${last}`,
    empty: "No batches match these filters.",
    failures: "Failures",
    failuresResolved: (n: number) => `${String(n)} resolved`,
    resolvedBy: (name: string | null, at: string) =>
      name === null ? `resolved: retried ${at}` : `resolved: retried by ${name}, ${at}`,
  },
  events: {
    today: (day: string) => `Today · ${day}`,
    sync: "Sync",
    syncRead: (n: string) => `${n} transactions read · 0 errors`,
    syncFailed: "Sync failed",
    reasons: {
      rate_limited: "QuickBooks Online rate limit",
      token_expired: "authorization expired",
      invalid_grant: "authorization expired",
    } as Record<string, string>,
    posted: (code: string, n: number) => `Posted ${code} (${String(n)} entries)`,
    failedPost: (ref: string) => `Failed post ${ref}`,
    closingDate: (on: string) => `Closing date set to ${on}`,
    empty: "No sync events yet.",
  },
  dialog: {
    title: "Request reconnect",
    recipient: "To",
    toValue: (names: readonly string[], company: string) =>
      names.map((n) => `${n} · Owner, ${company}`).join("; "),
    sends: "Sends",
    sendsValue: "Reconnect request email (POR-20)",
    reconnectsIn: "Reconnects in",
    reconnectsInValue: "Client portal › Connections (POR-16)",
    note: (owner: string, firm: string) =>
      `${owner} signs in to QuickBooks Online and approves the same access: read the ledger and post approved entries. ${firm} never sees or enters the client's ledger password.`,
    preview: "Email preview",
    showText: "Show plain text",
    hideText: "Hide plain text",
    missing:
      "This firm has no Reconnect request template, so the request is recorded but no email is sent. Publish one in Settings › Email templates.",
    cancel: "Cancel",
    send: "Send request",
    noOwner: "No owner on this client can receive the request.",
  },
  failedToLoad: "The ledger console could not load.",
  retryLoad: "Retry",
};
