import { areaRoutes } from "./areas";
import { auditRoutes } from "./audits";
import { binderRoutes } from "./binders";
import { clientRoutes } from "./clients";
import { engagementRoutes } from "./engagements";
import { filesRoutes } from "./files";
import { homeRoutes } from "./home";
import { inboxRoutes } from "./inbox";
import { knowledgeRoutes } from "./knowledge";
import { settingsRoutes } from "./settings";
import { taxReturnRoutes } from "./tax-returns";
// SHL-08 (P-03-T14): registers the `?ov=viewer` drawer for every firm route.
import "./viewer";
import "./run-trace";
// SHL-10 and SIG-02 (P-04-T41, N-02-T21): the `?ov=approve` and `?ov=envelope` sheets,
// registered lazily (the 250 KB initial budget).
import "./sheets";

// The firm's areas, once, in the bar's order (chapter 04 §2.2; F-03-T17). An area without
// screens yet has no routes; its file arrives with its first epic.
export const FIRM_AREAS = [
  { key: "home", label: "Home", routes: homeRoutes },
  { key: "engagements", label: "Engagements", routes: engagementRoutes },
  { key: "tax_returns", label: "Tax Returns", routes: taxReturnRoutes },
  { key: "files", label: "Files", routes: filesRoutes },
  { key: "knowledge", label: "Knowledge", routes: knowledgeRoutes },
  { key: "workbench", label: "Workbench", routes: [] },
  { key: "inbox", label: "Inbox", routes: inboxRoutes },
  { key: "clients", label: "Clients", routes: clientRoutes },
  { key: "binders", label: "Binders", routes: binderRoutes },
  { key: "notices", label: "Notices", routes: [] },
  { key: "audits", label: "Audits", routes: auditRoutes },
  { key: "closes", label: "Closes", routes: [] },
  { key: "signatures", label: "Signatures", routes: [] },
  { key: "settings", label: "Settings", routes: settingsRoutes },
] as const;

export const firmRoutes = [
  ...homeRoutes,
  ...engagementRoutes,
  ...knowledgeRoutes,
  ...clientRoutes,
  ...binderRoutes,
  // N-01-T16: FIL-01 behind `files.browser`.
  ...filesRoutes,
  ...inboxRoutes,
  ...settingsRoutes,
  // A-01-T11, A-01-T12: AUD-01 and AUD-02 behind `audits.cockpit`.
  ...auditRoutes,
  // T-02-T12: TAX-01 behind `tax.returns_v1`.
  ...taxReturnRoutes,
  // P-01-T02: the Engagements index and the flag-off landings of planned areas.
  ...areaRoutes,
] as const;
