import type { AgentCardStatus, AgentTone } from "../agent/agent-card";
import type { CatalogCategory } from "../catalog/catalog-kit";
import type { ConnectionStatus } from "../connect/connection-tile";
import type { VendorTone } from "../icons";
import { FIRM, STAFF } from "./seed-figures";

// The T5 and TPL-05 catalogs, word for word from the canvases the boards mount (Wave 0 Foundations
// `#t5`, `#tpl05`: `kits/Agent Kit` and `kits/Connect Kit`). The counts are the seed's (blueprint
// 01 §9.5): Library 28 = Tax Preparation 4 · Tax Review 5 · Tax Research 2 · Client Service 4 ·
// Firm Operations 5 · Audit 5 · Accounting & Close 3; Connect 53 = Connected 9 · Available 38 ·
// Coming soon 6, by tag Tax Software 8 · Practice Management 5 · ERP 8 · Document Management 13 ·
// Communications 8 · Productivity 12 · CRM 3 · HRIS & Payroll 3 · Spend & Payments 5. The nine
// connected integrations are 01 §9.1's, CCH Axcess Practice second, added by Felix Andersen.

export const FELIX = "Felix Andersen";
export const GRACE = "Grace Holloway";
/** The kits' viewer: Hannah Leclerc, who can enable firm connections. */
export const VIEWER = STAFF.hannah;

// ---- Agents (C-11) ------------------------------------------------------------------------------

export type AgentCategoryKey =
  "prep" | "review" | "research" | "client" | "ops" | "audit" | "close";

export const AGENT_CATEGORIES: readonly {
  key: AgentCategoryKey;
  label: string;
  tone: AgentTone;
}[] = [
  { key: "prep", label: "Tax Preparation", tone: "preparation" },
  { key: "review", label: "Tax Review", tone: "review" },
  { key: "research", label: "Tax Research", tone: "research" },
  { key: "client", label: "Client Service", tone: "client" },
  { key: "ops", label: "Firm Operations", tone: "operations" },
  { key: "audit", label: "Audit", tone: "audit" },
  { key: "close", label: "Accounting & Close", tone: "close" },
];

export interface CatalogAgent {
  id: string;
  name: string;
  cat: AgentCategoryKey;
  status: AgentCardStatus;
  text: string;
}

const agent = (
  id: string,
  name: string,
  cat: AgentCategoryKey,
  status: AgentCardStatus,
  text: string,
): CatalogAgent => ({ id, name, cat, status, text });

export const agentCategory = (key: AgentCategoryKey): { label: string; tone: AgentTone } => {
  const c = AGENT_CATEGORIES.find((x) => x.key === key);
  if (c === undefined) throw new Error(`no category ${key}`);
  return c;
};

export type AgentView = "Library" | "My Agents";
export type AgentFilter = "all" | AgentCardStatus;

export const AGENT_FILTERS = [
  { value: "all", label: "All" },
  { value: "available", label: "Available" },
  { value: "installed", label: "Installed" },
  { value: "coming_soon", label: "Coming soon" },
] as const;

/** The grid's agents: the view, the category, the status and the search (name, description and
 * category label, case-insensitive). */
export function visibleAgents(
  all: readonly CatalogAgent[],
  s: { view: AgentView; cat: string; status: AgentFilter; q: string },
): readonly CatalogAgent[] {
  const q = s.q.trim().toLowerCase();
  return all.filter(
    (a) =>
      (s.view === "Library" || a.status === "installed") &&
      (s.cat === "all" || a.cat === s.cat) &&
      (s.status === "all" || a.status === s.status) &&
      (q === "" || `${a.name} ${a.text} ${agentCategory(a.cat).label}`.toLowerCase().includes(q)),
  );
}

/** The CategoryList: counts follow the view, never the search or the status. */
export function agentCategories(
  all: readonly CatalogAgent[],
  view: AgentView,
): readonly CatalogCategory[] {
  const pool = all.filter((a) => view === "Library" || a.status === "installed");
  return [
    { key: "all", label: "All Categories", count: pool.length },
    ...AGENT_CATEGORIES.map((c) => ({
      key: c.key,
      label: c.label,
      count: pool.filter((a) => a.cat === c.key).length,
    })),
  ];
}

// ---- Integrations (C-14) ------------------------------------------------------------------------

export type ConnectCategoryKey =
  "tax" | "practice" | "erp" | "docs" | "comms" | "prod" | "crm" | "hris" | "spend";

export const CONNECT_CATEGORIES: readonly {
  key: ConnectCategoryKey;
  label: string;
  description: string;
  tone: VendorTone;
}[] = [
  {
    key: "tax",
    label: "Tax Software",
    description: "Tax preparation, compliance and e-file",
    tone: "green",
  },
  {
    key: "practice",
    label: "Practice Management",
    description: "Work, time and billing",
    tone: "espresso",
  },
  { key: "erp", label: "ERP", description: "Client ledgers and financial systems", tone: "green" },
  {
    key: "docs",
    label: "Document Management",
    description: "Files, binders and e-signature",
    tone: "clay",
  },
  {
    key: "comms",
    label: "Communications",
    description: "Email, chat, calls and meetings",
    tone: "amber",
  },
  {
    key: "prod",
    label: "Productivity",
    description: "Calendars, tasks and shared sheets",
    tone: "espresso",
  },
  { key: "crm", label: "CRM", description: "Client records and relationships", tone: "clay" },
  {
    key: "hris",
    label: "HRIS & Payroll",
    description: "Payroll and people systems",
    tone: "espresso",
  },
  {
    key: "spend",
    label: "Spend & Payments",
    description: "Bills, cards and payments",
    tone: "red",
  },
];

export const connectCategory = (
  key: ConnectCategoryKey,
): { label: string; tone: VendorTone; description: string } => {
  const c = CONNECT_CATEGORIES.find((x) => x.key === key);
  if (c === undefined) throw new Error(`no category ${key}`);
  return c;
};

export type StoredConnection = Exclude<ConnectionStatus, "connecting">;

export interface CatalogIntegration {
  id: string;
  /** The vendor's name as text only. */
  name: string;
  cats: readonly [ConnectCategoryKey, ...ConnectCategoryKey[]];
  status: StoredConnection;
  kind: "firm" | "personal";
  /** Who added a firm connection; "" when not connected. */
  by: string;
  text: string;
}

const integration = (
  id: string,
  name: string,
  cats: readonly [ConnectCategoryKey, ...ConnectCategoryKey[]],
  status: StoredConnection,
  kind: "firm" | "personal",
  by: string,
  text: string,
): CatalogIntegration => ({ id, name, cats, status, kind, by, text });

export type ConnectFilter = "all" | "connected" | "available" | "coming_soon";

export const CONNECT_FILTERS = [
  { value: "all", label: "All" },
  { value: "connected", label: "Connected" },
  { value: "available", label: "Available" },
  { value: "coming_soon", label: "Coming soon" },
] as const;

/** The scope line under the tags (C-14 §2). */
export function scopeLine(it: CatalogIntegration, status: ConnectionStatus, by?: string): string {
  if (it.kind === "personal") return "Personal connection · acts as you";
  if (status === "connected")
    return `Firm connection · added by ${by ?? (it.by === "" ? VIEWER : it.by)}`;
  return "Firm connection · shared with the firm";
}

/** The Connect grid: category by tag × status × search. */
export function visibleIntegrations(
  all: readonly CatalogIntegration[],
  statusOf: (it: CatalogIntegration) => ConnectionStatus,
  s: { cat: string; status: ConnectFilter; q: string },
): readonly CatalogIntegration[] {
  const q = s.q.trim().toLowerCase();
  return all.filter((it) => {
    if (s.cat !== "all" && !it.cats.includes(s.cat as ConnectCategoryKey)) return false;
    const st = statusOf(it);
    if (s.status !== "all" && st !== s.status) return false;
    const words = `${it.name} ${it.text} ${it.cats.map((k) => connectCategory(k).label).join(" ")}`;
    return q === "" || words.toLowerCase().includes(q);
  });
}

/** The CategoryList with its description lines; counts are by tag, so one integration can count
 * in two categories. */
export function connectCategories(all: readonly CatalogIntegration[]): readonly CatalogCategory[] {
  return [
    { key: "all", label: "All Categories", description: "Every integration", count: all.length },
    ...CONNECT_CATEGORIES.map((c) => ({
      key: c.key,
      label: c.label,
      description: c.description,
      count: all.filter((it) => it.cats.includes(c.key)).length,
    })),
  ];
}

/** The Disconnect confirm (C-14 §4). */
export const disconnectText = (it: CatalogIntegration): string =>
  (it.kind === "firm"
    ? `Agents stop reading from ${it.name} for everyone at ${FIRM}.`
    : `Agents stop acting as you in ${it.name}.`) +
  " Anything already filed in Accrued stays where it is.";

// ---- The rosters --------------------------------------------------------------------------------

export const AGENTS: readonly CatalogAgent[] = [
  agent(
    "rrp",
    "Return Review Packet",
    "review",
    "installed",
    "Assemble a reviewer’s packet: the two-year comparison, open issues and what to look at first, with every number linked to its source.",
  ),
  agent(
    "pyv",
    "Prior-Year & Return Version Check",
    "review",
    "available",
    "Settle which return version is final and what carries forward from last year: NOLs, suspended losses, carryovers and basis.",
  ),
  agent(
    "k1",
    "K-1 Reconciliation Workpaper",
    "prep",
    "installed",
    "Tie every K-1 to the return, or every K-1 back to Schedule K, in a workpaper a reviewer can follow.",
  ),
  agent(
    "mdc",
    "Missing Document Chaser",
    "client",
    "installed",
    "Confirm what each client still owes and draft one clear follow-up per client for a person on your team to send.",
  ),
  agent(
    "memo",
    "Source-Cited Tax Research Memo",
    "research",
    "available",
    "Turn a tax question into a cited memo with assumptions, the controlling authority and the authority against you.",
  ),
  agent(
    "season",
    "Season Progress Reporter",
    "ops",
    "installed",
    "Report where the season stands by office and stage, what has stalled, and the exceptions managers should act on.",
  ),
  agent(
    "ebp",
    "EBP Audit Workpapers",
    "audit",
    "installed",
    "Run planning and fieldwork workpapers for a 401(k) plan audit against your firm’s methodology, citing each program step.",
  ),
  agent(
    "bank",
    "Bank Reconciliation",
    "close",
    "installed",
    "Reconcile bank and card accounts to statements, propose entries and flag stale or unusual items for review.",
  ),
  agent(
    "wsr",
    "Workflow Status Reconciliation",
    "ops",
    "coming_soon",
    "Compare workflow status in Accrued with your practice-management system and propose the corrections.",
  ),
  agent(
    "tbt",
    "Trial Balance Tie-Out",
    "audit",
    "installed",
    "Tie the client’s trial balance to the general ledger and the lead schedules, and list every difference with its entries.",
  ),
  agent(
    "sample",
    "Sample Selection & Item Requests",
    "audit",
    "installed",
    "Select samples from each population by your methodology and draft the item requests for the client portal.",
  ),
  agent(
    "ice",
    "Internal Control Exceptions Grader",
    "audit",
    "available",
    "Grade each control exception from deficiency to material weakness, with the evidence behind every grade.",
  ),
  agent(
    "fraud",
    "Fraud Brainstorm Minutes",
    "audit",
    "coming_soon",
    "Draft the engagement team’s fraud brainstorming minutes from the planning discussion and the risk assessment.",
  ),
  agent(
    "intake",
    "1040 Document Intake",
    "prep",
    "available",
    "Read W-2s, 1099s and 1098s as they arrive, fill the leadsheet and link every figure to its page.",
  ),
  agent(
    "ext",
    "Extension Tracker",
    "prep",
    "installed",
    "Track every return on extension by office and deadline, and list what each one still waits on.",
  ),
  agent(
    "tbi",
    "Trial Balance Import",
    "prep",
    "available",
    "Map the client’s ledger export to the return, carry last year’s mappings forward and flag anything unmapped.",
  ),
  agent(
    "cmp",
    "Two-Year Return Comparison",
    "review",
    "available",
    "Compare this year’s return to last year’s line by line and explain every change above your threshold.",
  ),
  agent(
    "b1099",
    "Composite 1099 Tie-Out",
    "review",
    "available",
    "Tie each brokerage composite 1099 to Schedules B and D and the Form 8949 detail.",
  ),
  agent(
    "appt",
    "State Apportionment Review",
    "review",
    "coming_soon",
    "Check each state’s apportionment factors against payroll, property and sales by state.",
  ),
  agent(
    "notice",
    "Notice Response Drafter",
    "research",
    "available",
    "Read an IRS or state notice, check it against the return as filed and draft the response for review.",
  ),
  agent(
    "org",
    "Organizer Builder",
    "client",
    "available",
    "Prefill each client’s organizer from last year’s return and ask only about what changed.",
  ),
  agent(
    "qa",
    "Portal Question Drafts",
    "client",
    "available",
    "Draft answers to client portal questions from the engagement file, citing the document behind each answer.",
  ),
  agent(
    "deliv",
    "Deliverables Packager",
    "client",
    "available",
    "Assemble the signed return, payment vouchers and filing instructions into one portal delivery per client.",
  ),
  agent(
    "letters",
    "Engagement Letter Renewals",
    "ops",
    "installed",
    "Find engagements without a signed 2026 letter, draft renewals from last year’s terms and queue them for signature.",
  ),
  agent(
    "wip",
    "Unbilled WIP Report",
    "ops",
    "available",
    "Summarize unbilled time by partner and engagement, oldest first, with what is ready to invoice.",
  ),
  agent(
    "cap",
    "Capacity Planner",
    "ops",
    "available",
    "Balance return assignments across preparers by deadline and budgeted hours.",
  ),
  agent(
    "close",
    "Month-End Close Checklist",
    "close",
    "available",
    "Work the close checklist, mark each reconciliation as it ties and list what still needs a person.",
  ),
  agent(
    "flux",
    "Flux Analysis",
    "close",
    "available",
    "Explain month-over-month and year-over-year changes above your threshold, with the entries behind each one.",
  ),
];
export const INTEGRATIONS: readonly CatalogIntegration[] = [
  integration(
    "cch",
    "CCH Axcess Tax",
    ["tax"],
    "connected",
    "firm",
    "Felix Andersen",
    "Import returns, diagnostics and e-file status, and send approved adjustments back.",
  ),
  integration(
    "cchpm",
    "CCH Axcess Practice",
    ["practice"],
    "connected",
    "firm",
    "Felix Andersen",
    "Mirror engagements, due dates and staff assignments, and post status as work moves.",
  ),
  integration(
    "ultratax",
    "UltraTax CS",
    ["tax"],
    "available",
    "firm",
    "",
    "Read return data and print-ready PDFs for review, organizers and comparisons.",
  ),
  integration(
    "qbo",
    "QuickBooks Online",
    ["erp"],
    "connected",
    "firm",
    "Felix Andersen",
    "Pull each client’s trial balance, ledger detail and bank feeds every night.",
  ),
  integration(
    "netsuite",
    "NetSuite",
    ["erp"],
    "connected",
    "firm",
    "Felix Andersen",
    "Pull the trial balance, ledger detail and vendor list every night.",
  ),
  integration(
    "intacct",
    "Sage Intacct",
    ["erp"],
    "connected",
    "firm",
    "Felix Andersen",
    "Read entities, dimensions and journal detail for multi-entity clients.",
  ),
  integration(
    "xero",
    "Xero",
    ["erp"],
    "connected",
    "firm",
    "Felix Andersen",
    "Trial balance, ledger detail and bank feeds for clients on Xero.",
  ),
  integration(
    "box",
    "Box",
    ["docs"],
    "connected",
    "firm",
    "Felix Andersen",
    "File client documents into the right binder and keep folders in sync.",
  ),
  integration(
    "m365",
    "Microsoft 365",
    ["prod", "comms", "docs"],
    "connected",
    "firm",
    "Felix Andersen",
    "File client email and attachments to the engagement, and read shared workbooks from OneDrive.",
  ),
  integration(
    "docusign",
    "DocuSign",
    ["docs"],
    "connected",
    "firm",
    "Grace Holloway",
    "Send engagement letters and 8879s for signature and file the signed copies.",
  ),
  integration(
    "adp",
    "ADP",
    ["hris"],
    "coming_soon",
    "firm",
    "",
    "Payroll registers, census files and contributions for plan audits.",
  ),
  integration(
    "lacerte",
    "Lacerte",
    ["tax"],
    "available",
    "firm",
    "",
    "Sync client returns, K-1 detail and e-file acknowledgments.",
  ),
  integration(
    "proconnect",
    "ProConnect Tax",
    ["tax"],
    "available",
    "firm",
    "",
    "Read return data and e-file status for clients prepared in ProConnect.",
  ),
  integration(
    "gosystem",
    "GoSystem Tax RS",
    ["tax"],
    "available",
    "firm",
    "",
    "Read corporate and partnership returns, state apportionment and e-file status.",
  ),
  integration(
    "drake",
    "Drake Tax",
    ["tax"],
    "available",
    "firm",
    "",
    "Read return data and e-file acknowledgments for individual and business returns.",
  ),
  integration(
    "fx",
    "CCH ProSystem fx Tax",
    ["tax"],
    "available",
    "firm",
    "",
    "Read returns and diagnostics from ProSystem fx while clients move to Axcess.",
  ),
  integration(
    "proseries",
    "ProSeries",
    ["tax"],
    "coming_soon",
    "firm",
    "",
    "Return data and e-file status for clients prepared in ProSeries.",
  ),
  integration(
    "karbon",
    "Karbon",
    ["practice", "comms"],
    "available",
    "firm",
    "",
    "Mirror work items, due dates and assignees, and file client email threads to the engagement.",
  ),
  integration(
    "taxdome",
    "TaxDome",
    ["practice", "docs"],
    "available",
    "firm",
    "",
    "Sync organizers, client documents and job status from the TaxDome portal.",
  ),
  integration(
    "practicecs",
    "Practice CS",
    ["practice"],
    "available",
    "firm",
    "",
    "Pull time, billing and WIP by engagement for capacity and realization reports.",
  ),
  integration(
    "canopy",
    "Canopy",
    ["practice", "docs"],
    "available",
    "firm",
    "",
    "Sync engagements, tasks and the client document vault.",
  ),
  integration(
    "qbd",
    "QuickBooks Desktop",
    ["erp"],
    "available",
    "firm",
    "",
    "Read the trial balance and ledger detail through the desktop connector.",
  ),
  integration(
    "bc",
    "Microsoft Dynamics 365 Business Central",
    ["erp"],
    "available",
    "firm",
    "",
    "Read the trial balance, dimensions and journal detail for each company.",
  ),
  integration(
    "acumatica",
    "Acumatica",
    ["erp"],
    "available",
    "firm",
    "",
    "Read the trial balance, subaccounts and journal detail for each branch.",
  ),
  integration(
    "sage100",
    "Sage 100",
    ["erp"],
    "coming_soon",
    "firm",
    "",
    "Trial balance and ledger detail for clients on Sage 100.",
  ),
  integration(
    "dropbox",
    "Dropbox",
    ["docs", "prod"],
    "available",
    "personal",
    "",
    "Find source documents in shared folders and attach them to a request.",
  ),
  integration(
    "gdrive",
    "Google Drive",
    ["docs", "prod"],
    "available",
    "personal",
    "",
    "Find source documents in your Drive and attach them to a request.",
  ),
  integration(
    "smartvault",
    "SmartVault",
    ["docs"],
    "available",
    "firm",
    "",
    "File returns and source documents to each client’s vault and portal.",
  ),
  integration(
    "sharefile",
    "ShareFile",
    ["docs"],
    "available",
    "firm",
    "",
    "Collect client uploads and file them to the right binder.",
  ),
  integration(
    "safesend",
    "SafeSend Returns",
    ["docs"],
    "available",
    "firm",
    "",
    "Deliver finished returns for review and e-signature, and track every 8879.",
  ),
  integration(
    "acrobat",
    "Adobe Acrobat Sign",
    ["docs"],
    "available",
    "firm",
    "",
    "Send engagement letters and consents for signature and file the signed copies.",
  ),
  integration(
    "egnyte",
    "Egnyte",
    ["docs"],
    "coming_soon",
    "firm",
    "",
    "File client documents into Egnyte folders and keep binders in sync.",
  ),
  integration(
    "teams",
    "Microsoft Teams",
    ["comms", "prod"],
    "available",
    "firm",
    "",
    "Post run summaries and decisions waiting on you to a channel.",
  ),
  integration(
    "slack",
    "Slack",
    ["comms", "prod"],
    "available",
    "firm",
    "",
    "Get a message when an agent needs a decision, and answer from the thread.",
  ),
  integration(
    "zoom",
    "Zoom",
    ["comms", "prod"],
    "available",
    "personal",
    "",
    "Attach meeting notes and recordings to the client’s engagement.",
  ),
  integration(
    "ringcentral",
    "RingCentral",
    ["comms"],
    "available",
    "firm",
    "",
    "Log client calls and voicemails to the right engagement.",
  ),
  integration(
    "liscio",
    "Liscio",
    ["comms", "docs"],
    "available",
    "firm",
    "",
    "Sync client messages and document requests from the Liscio portal.",
  ),
  integration(
    "gmail",
    "Gmail",
    ["comms"],
    "available",
    "personal",
    "",
    "File client email and attachments to the right engagement.",
  ),
  integration(
    "notion",
    "Notion",
    ["prod"],
    "available",
    "firm",
    "",
    "Read firm procedures and checklists so agents follow your house style.",
  ),
  integration(
    "asana",
    "Asana",
    ["prod"],
    "available",
    "firm",
    "",
    "Create follow-up tasks from agent runs and track them to done.",
  ),
  integration(
    "monday",
    "monday.com",
    ["prod"],
    "available",
    "firm",
    "",
    "Mirror engagement boards and post status as agents finish work.",
  ),
  integration(
    "smartsheet",
    "Smartsheet",
    ["prod"],
    "available",
    "firm",
    "",
    "Read and update shared trackers, such as extension and PBC lists.",
  ),
  integration(
    "calendly",
    "Calendly",
    ["prod"],
    "available",
    "personal",
    "",
    "Offer clients meeting times from your calendar inside follow-ups.",
  ),
  integration(
    "zapier",
    "Zapier",
    ["prod"],
    "coming_soon",
    "firm",
    "",
    "Start an agent run from any app your firm already uses.",
  ),
  integration(
    "salesforce",
    "Salesforce",
    ["crm"],
    "available",
    "firm",
    "",
    "Keep client contacts, entities and relationships in step with Accrued.",
  ),
  integration(
    "hubspot",
    "HubSpot",
    ["crm"],
    "available",
    "firm",
    "",
    "Keep prospects, contacts and engagement letters in step with Accrued.",
  ),
  integration(
    "gusto",
    "Gusto",
    ["hris"],
    "available",
    "firm",
    "",
    "Read payroll registers so accruals and 401(k) census data tie out.",
  ),
  integration(
    "paychex",
    "Paychex Flex",
    ["hris"],
    "available",
    "firm",
    "",
    "Read payroll registers and 401(k) contribution files for plan audits.",
  ),
  integration(
    "stripe",
    "Stripe",
    ["spend", "crm"],
    "available",
    "firm",
    "",
    "Collect invoice payments in the portal and match payouts to receivables.",
  ),
  integration(
    "bill",
    "BILL",
    ["spend"],
    "available",
    "firm",
    "",
    "Read client payables and approvals for the monthly close.",
  ),
  integration(
    "expensify",
    "Expensify",
    ["spend"],
    "available",
    "firm",
    "",
    "Read expense reports and receipts so card activity ties to the ledger.",
  ),
  integration(
    "ramp",
    "Ramp",
    ["spend"],
    "available",
    "firm",
    "",
    "Read card transactions, receipts and bill payments for the close.",
  ),
  integration(
    "brex",
    "Brex",
    ["spend"],
    "coming_soon",
    "firm",
    "",
    "Card transactions and receipts for clients on Brex.",
  ),
];
