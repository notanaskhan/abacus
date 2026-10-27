// POR-16 Connections copy (A-02-T18): the screen's chrome, verbatim from the handoff
// (screens/POR-16, spec.md and README) with DF-19's read-only masks (A-02 §3.9 AC-9.4, §5.4): no
// "post entries" copy anywhere until P-16. The consent sheet's lists, toggle sentence and button
// are catalogue content (the cards' `consent`), never written here. The firm's name comes from
// the branding; the product's name never appears (DEC-01).

export const COPY = {
  pane: "Connections",
  back: "Home", // POR-12 (Account) is N-03's: the back chip reads "‹ Home" until then (A-02 §11.2 Q4)
  // DF-19: the design's "reads your books and posts only the entries you approve", masked.
  relationship: (firm: string): string =>
    `${firm} reads the books you connect. Nothing in your accounting system changes.`,
  footer: (firm: string): string =>
    `You can disconnect anytime. Disconnecting stops new data; what ${firm} already received stays in your client file.`,
  empty: (firm: string): string => `${firm} hasn’t asked to connect any systems`,
  loading: "Loading connections",
  loadError: "Connections couldn’t load",
  retryLoad: "Try again",
  notAllowed: "You don’t have access to this entity’s connections",
  details: "Details",
  disconnect: "Disconnect",
  reconnect: "Reconnect",
  connect: "Connect",
  connectMore: "Connect…",
  exportInstead: "Export instead",
  tryAgain: "Try again",
  connecting: "Connecting…",
  connectedBy: (who: string, day: string): string => `Connected by ${who} · ${day}`,
  reconnectedBy: (who: string, when: string): string => `reconnected by ${who} · ${when}`,
  lastSync: (when: string): string => `last sync ${when}`,
  asked: (firm: string, day: string): string => `${firm} asked on ${day}.`,
  syncFailed: (day: string): string => `Last sync failed ${day}`,
  will: (firm: string): string => `${firm} will`,
  wont: (firm: string): string => `${firm} won’t`,
  disconnectTitle: (name: string): string => `Disconnect ${name}?`,
  // DF-19: the design's "or post accepted entries" is masked; the plan's disconnect sentence.
  disconnectBody: (firm: string): string =>
    `${firm} won’t be able to read your books. What it already received stays in your client file.`,
  cancel: "Cancel",
  exportNone: (firm: string): string =>
    `${firm} will ask when they need a trial balance export from you.`,
  failed: "Something went wrong. Try again.",
  retried: "Trying the sync again",
  disconnected: (name: string): string => `${name} disconnected`,
  scopes: "Access",
  recent: "Recent syncs",
  activity: "Activity",
  noSyncs: "No syncs yet",
} as const;
