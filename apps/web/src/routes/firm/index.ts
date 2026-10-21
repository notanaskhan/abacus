import { clientRoutes } from "./clients";
import { engagementRoutes } from "./engagements";
import { homeRoutes } from "./home";
import { knowledgeRoutes } from "./knowledge";
import { settingsRoutes } from "./settings";

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
  { key: "binders", label: "Binders", routes: [] },
  { key: "notices", label: "Notices", routes: [] },
  { key: "audits", label: "Audits", routes: [] },
  { key: "closes", label: "Closes", routes: [] },
  { key: "signatures", label: "Signatures", routes: [] },
  { key: "settings", label: "Settings", routes: settingsRoutes },
] as const;

export const firmRoutes = [
  ...homeRoutes,
  ...engagementRoutes,
  ...knowledgeRoutes,
  ...clientRoutes,
  ...settingsRoutes,
] as const;
