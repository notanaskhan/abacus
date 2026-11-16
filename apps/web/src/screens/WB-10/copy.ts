// WB-10 · Workbench › Connect copy (W-01-T12; docs/screens/WB-10.md). Tile names, descriptions,
// auth lines and blocked reasons are catalogue content from the API, never typed here; status
// words are C2's (`integration`). Strings marked (undesigned) are composed from the kits.
export const COPY = {
  title: "Connect",
  tabs: { label: "Workbench", sessions: "Sessions", agents: "Agents", connect: "Connect" },
  search: "Search integrations",
  categories: "Categories",
  all: "All",
  status: "Status",
  grid: "Integrations",
  about: {
    title: "Connect",
    body: "Firm connections are managed by IT and firm admins. Personal ones act as you. Accrued reads what each one shares and never writes without a declared capability.", // (undesigned)
  },
  buildOnAccrued: "Build on Accrued",
  notBuilt: "Not built yet",
  enable: "Enable",
  connect: "Connect",
  reconnect: "Reconnect",
  notifyMe: "Notify me",
  notified: "We'll let you know", // (undesigned)
  details: "Details…",
  connectedAsYou: "Connected as you",
  connectedBy: (name: string) => `Connected by ${name}`,
  connectFailed: "That didn't connect. Try again.", // (undesigned)
  noMatch: (q: string) => `No integrations match '${q}'.`,
  empty: "No integrations to show.", // (undesigned)
  flagLabel: "Connect",
} as const;
