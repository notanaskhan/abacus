// SHL-05's words, verbatim from the handoff (screens/SHL-05 spec.md) and the blueprint's status
// words (01 §3.3.1: "Operational" as a plain label, "Needs attention" for Degraded).
export const COPY = {
  title: "Support",
  online: (minutes: number | null): string =>
    minutes === null ? "Online" : `Online · replies in ~${String(minutes)} min`,
  offline: (at: string): string => `Offline · we reply by ${at}`,
  tabs: { chat: "Chat", help: "Help articles", status: "System status" },
  notice:
    "Accrued Support can't see your clients' documents or returns. If they need to, you'll be asked to grant a time-boxed support session (ADM-06).",
  staffSender: (name: string): string => `${name} at Accrued Support`,
  relatedArticle: "Related article",
  readMinutes: (n: number): string => `${String(n)} min read`,
  composer: { online: "Message Accrued Support", offline: "Leave a message" },
  offlineNotice: (email: string): string => `We'll email ${email} when we reply.`,
  card: {
    requestedBy: "Requested by",
    requester: "Accrued Support",
    scope: "Scope",
    duration: "Duration",
    hours: (minutes: number): string =>
      minutes % 60 === 0
        ? `${String(minutes / 60)} ${minutes === 60 ? "hour" : "hours"}`
        : `${String(minutes)} min`,
    status: "Status",
    awaiting: "Awaiting firm approval",
    granted: (name: string, until: string): string => `Granted by ${name} · until ${until}`,
    decline: "Decline",
    review: "Review in Settings",
    revoke: "Revoke",
    declined: "Declined",
    ended: "Ended",
  },
  empty: { suggestions: ["Ask about a sync", "Report a problem with an agent run"] },
  help: { search: "Search help", back: "Back to help articles" },
  status: {
    card: "All core services",
    states: {
      operational: "Operational",
      needs_attention: "Needs attention",
      outage: "Outage",
      maintenance: "Maintenance",
    } as Record<string, string>,
    history: "Incident history",
    region: (label: string): string => `Your firm's data region: ${label}`,
  },
} as const;
