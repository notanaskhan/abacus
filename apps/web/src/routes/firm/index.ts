import { areaRoutes } from "./areas";
import { auditRoutes } from "./audits";
import { binderRoutes } from "./binders";
import { clientRoutes } from "./clients";
import { engagementRoutes } from "./engagements";
import { homeRoutes } from "./home";
import { knowledgeRoutes } from "./knowledge";
import { settingsRoutes } from "./settings";
// SHL-08 (P-03-T14): registers the `?ov=viewer` drawer for every firm route.
import "./viewer";
import "./run-trace";

// The firm's areas, once, in the bar's order (chapter 04 §2.2; F-03-T17). An area without
// screens yet has no routes; its file arrives with its first epic.
export const FIRM_AREAS = [
  { key: "home", label: "Home", routes: homeRoutes },
  { key: "engagements", label: "Engagements", routes: engagementRoutes },
  { key: "tax_returns", label: "Tax Returns", routes: [] },
  { key: "files", label: "Files", routes: [] },
  { key: "knowledge", label: "Knowledge", routes: knowledgeRoutes },
  { key: "workbench", label: "Workbench", routes: [] },
  { key: "inbox", label: "Inbox", routes: [] },
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
  ...settingsRoutes,
  // A-01-T11, A-01-T12: AUD-01 and AUD-02 behind `audits.cockpit`.
  ...auditRoutes,
  // P-01-T02: the Engagements index and the flag-off landings of planned areas.
  ...areaRoutes,
] as const;
