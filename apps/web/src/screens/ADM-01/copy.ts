// ADM-01 copy, verbatim from the handoff (screens/ADM-01 spec.md and README) and G-01 §3.1–3.2.
// At a glance words are built from each row's facts (`GlanceRowOut.facts` are counts by key).

import type { SettingsGroup } from "@abacus/ui";

export const COPY = {
  title: "Firm settings",
  navTitle: "Settings",
  back: "Back",
  readOnly: "Only firm admins can edit these settings.",
  saved: "Firm settings saved",
  unsaved: "Unsaved changes",
  discardTitle: "Discard changes?",
  discardBody: "Your changes to this section haven't been saved.",
  discardConfirm: "Discard",
  keepEditing: "Keep editing",
  stale: (who: string) => `Changed by ${who} — reload`,
  staleAnonymous: "Changed by someone else — reload",
  required: "Required",
  stepUpTitle: "Confirm it's you to save firm settings",
  stepUpBody:
    "Saving firm settings needs a recent sign-in. Sign in again, then save once more. If it still isn't allowed, your role doesn't permit it.",
  cancel: "Cancel",
  signInAgain: "Sign in again",
  displayNameHelp: "Enter the name clients see in the portal.",
  notAllowed: "You don't have access to firm settings.",
  notBuilt: (section: string) => `${section} opens its own screen, which isn't built yet.`,
  unavailable: "Status unavailable",
  glanceTitle: "At a glance",
  updated: (time: string) => `Updated ${time}`,
  fieldsets: {
    profile: "Firm profile",
    offices: "Offices",
    plan: "Plan & seats",
    defaults: "Defaults",
  },
  addOffice: "Office",
  rows: {
    legal_name: "Legal name",
    display_name: "Display name",
    region: "Primary region",
    time_zone: "Default time zone",
    intake_mailbox: "Intake mailbox",
    website: "Website",
    logo: "Logo",
    seats: "Seats",
    people: "People",
    modules: "Modules",
    renewal_on: "Renewal",
    billing_contact_user_id: "Billing contact",
    return_approval_policy: "Return approval policy",
    aje_threshold_policy: "AJE threshold policy",
    auto_mode_new_audits: "Auto mode for new audits",
    portal_secured_footer: 'Show "Secured by Accrued" in the client portal footer',
    week_starts_on: "Week starts on",
  },
  regionValue: "United States",
  regionHelp: "Fixed at provisioning. Client data, logs and AI inference stay in the US.",
  replaceLogo: "Replace…",
  seatsUsed: (used: number, total: number) => `${String(used)} of ${String(total)} used`,
  seatsFull: "All seats are assigned. Add seats before inviting another user.",
  peopleLine: (partners: number, professionals: number, operations: number, seatless: number) =>
    `${String(partners)} partners · ${String(professionals)} professional staff · ${String(operations)} operations; ${String(seatless)} back-office staff hold no seat`,
  help: {
    return_approval_policy: "The signing partner gives final approval on returns he or she signs.",
    aje_threshold_policy: "Published in Knowledge › Firm standards (KNW-04).",
    auto_mode_new_audits: "Set per engagement type in AI policy.",
  },
  office: (seats: number, returns: number | undefined, hq: boolean) =>
    `${String(seats)} seats${returns === undefined ? "" : ` · ${String(returns)} ${hq ? "TY2025 returns" : "returns"}`}`,
  officeName: (name: string, hq: boolean) => (hq ? `${name} · HQ` : name),
  allOffices: "All offices",
  allOfficesValue: (seats: number, returns: number | undefined) =>
    `${String(seats)} seats${returns === undefined ? "" : ` · ${String(returns)} returns`}`,
  timeZones: [
    { value: "America/New_York", label: "Eastern Time (ET)" },
    { value: "America/Chicago", label: "Central Time (CT)" },
    { value: "America/Denver", label: "Mountain Time (MT)" },
    { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
  ],
  weekStarts: [
    { value: "monday", label: "Monday" },
    { value: "sunday", label: "Sunday" },
  ],
  modules: {
    tax: "Tax",
    audit: "Audit & assurance",
    cas: "Client accounting",
    advisory: "Advisory",
  } as Readonly<Record<string, string>>,
} as const;

/** The section list (G-01 §2.1): fourteen sections in four groups. Only General is built here;
 * the rest open their own screens (planned until their rows land). */
export const GROUPS: readonly SettingsGroup[] = [
  {
    label: "FIRM",
    sections: [
      { id: "general", label: "General", icon: "building-2" },
      { id: "people", label: "People", icon: "users-round" },
      { id: "offices", label: "Offices & teams", icon: "map-pin" },
      { id: "plan-usage", label: "Plan & usage", icon: "credit-card" },
    ],
  },
  {
    label: "SECURITY & AI",
    sections: [
      { id: "security", label: "Security", icon: "lock" },
      { id: "ai-policy", label: "AI policy", icon: "sparkles" },
      { id: "consents", label: "Consents", icon: "signature" },
      { id: "developer", label: "Developer", icon: "code" },
    ],
  },
  {
    label: "CLIENTS",
    sections: [
      { id: "integrations", label: "Integrations", icon: "plug" },
      { id: "portal", label: "Portal", icon: "panels-top-left" },
      { id: "data-model", label: "Data model", icon: "database" },
    ],
  },
  {
    label: "QUALITY",
    sections: [
      { id: "quality", label: "Quality", icon: "shield-check" },
      { id: "monitoring", label: "Monitoring", icon: "gauge" },
      { id: "audit-log", label: "Audit log", icon: "scroll-text" },
    ],
  },
];

type Facts = Readonly<Record<string, number>>;
const n = (facts: Facts, key: string): string => String(facts[key] ?? 0);

/** Each At a glance row: its area's name and its one-line status from the facts. */
export const GLANCE: Readonly<
  Record<string, { name: string; line: (f: Facts) => string; section: string }>
> = {
  people: {
    name: "People",
    line: (f) => `${n(f, "used")} of ${n(f, "total")} seats · ${n(f, "pending")} pending invites`,
    section: "people",
  },
  offices_teams: {
    name: "Offices & teams",
    line: (f) =>
      f.walls === undefined
        ? `${n(f, "offices")} offices · ${n(f, "teams")} teams`
        : `${n(f, "offices")} offices · ${n(f, "teams")} teams · ${n(f, "walls")} ethical walls`,
    section: "offices",
  },
  security: {
    name: "Security",
    line: (f) =>
      `SSO + MFA enforced · ${n(f, "open_incidents")} open incident (day ${n(f, "day")} of ${n(f, "of")})`,
    section: "security",
  },
  ai_policy: {
    name: "AI policy",
    line: (f) => `BH AI policy v${n(f, "version")} · policy acceptance off`,
    section: "ai-policy",
  },
  consents: {
    name: "Consents",
    line: (f) =>
      `${n(f, "expiring")} expiring in ${n(f, "within_days")} days · ${n(f, "expired")} expired`,
    section: "consents",
  },
  developer: {
    name: "Developer",
    line: (f) =>
      `${n(f, "api_keys")} API keys · ${n(f, "webhooks")} webhooks · ${n(f, "mcp_connections")} MCP connection`,
    section: "developer",
  },
  integrations: {
    name: "Integrations",
    line: (f) => `${n(f, "connected")} connected · ${n(f, "errors")} errors`,
    section: "integrations",
  },
  portal: {
    name: "Portal",
    line: (f) =>
      `portal.brightwaterhale.com · ${n(f, "published")} of ${n(f, "templates")} email templates published · ${n(f, "draft_changes")} draft change`,
    section: "portal",
  },
  quality: {
    name: "Quality",
    line: (f) =>
      `${n(f, "objectives_at_risk")} objectives at risk · ${n(f, "open_findings")} open findings`,
    section: "quality",
  },
  monitoring: {
    name: "Monitoring",
    line: (f) =>
      `${n(f, "inspections")} inspections · ${n(f, "concluded")} concluded · ${n(f, "in_progress")} in progress · ${n(f, "planned")} planned`,
    section: "monitoring",
  },
  audit_log: {
    name: "Audit log",
    line: (f) => `Immutable · retained ${n(f, "retained_years")} years`,
    section: "audit-log",
  },
};
