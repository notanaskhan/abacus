// ADM-02 copy, verbatim from the handoff (screens/ADM-02 spec.md, README and screenshots) and
// G-01 §3.3–3.6; deviations are docs/screens/ADM-02.md's (DEC-352, DEC-353). Row text (names,
// emails, titles, offices, teams, groups) is data, never here.

import type { CapabilityWords } from "@abacus/ui";

type Template =
  | "partner"
  | "manager"
  | "tax_reviewer"
  | "senior"
  | "staff"
  | "tax_preparer"
  | "firm_admin"
  | "it_security";
type Band = "partners" | "managers" | "seniors" | "staff" | "seasonal" | "operations";

const n = (value: number): string => String(value);

export const COPY = {
  title: "Firm settings",
  navTitle: "Settings",
  back: "Back",
  notAllowed: "You don't have access to firm settings.",
  segmentsLabel: "People",
  segments: {
    users: "Users",
    templates: "Role templates",
    invitations: "Invitations",
    independence: "Independence",
  },
  addSeats: "Add seats…",
  invite: "Invite user…",
  tally: {
    label: "People",
    seats: "SEATS",
    seatsValue: (used: number, total: number, pending: number) =>
      pending > 0
        ? `${n(used)} of ${n(total)} · ${n(pending)} pending`
        : `${n(used)} of ${n(total)}`,
    full: "Full",
    roles: "ROLES",
    rolesValue: (p: number, pro: number, ops: number) =>
      `${n(p)} partners · ${n(pro)} professionals · ${n(ops)} operations`,
    signIn: "SIGN-IN",
    signInValue: (sso: number, of: number) => `SSO + MFA ${n(sso)} of ${n(of)}`,
    walls: "WALLS",
    wallsValue: (active: number) => `${n(active)} active`,
    seasonal: "SEASONAL",
    seasonalValue: (count: number, on: string) => `${n(count)} · access ends ${on}`,
    seasonalEnded: (count: number, on: string) => `${n(count)} · access ended ${on}`,
  },
  search: "Search people",
  clear: "Clear search",
  chips: {
    role: "Role",
    office: "Office",
    team: "Team",
    status: "Status",
    all: "All",
    allOffices: "All offices",
  },
  statuses: { active: "Active", invited: "Invited", deactivated: "Deactivated" },
  count: (people: number) => (people === 1 ? "1 person" : `${n(people)} people`),
  table: "People",
  columns: {
    name: "Name",
    role: "Role",
    office: "Office",
    team: "Team · groups",
    signIn: "Sign-in",
    lastActive: "Last active",
    more: "Actions",
  },
  bands: {
    partners: "PARTNERS",
    managers: "MANAGERS & REVIEWERS",
    seniors: "SENIORS",
    staff: "STAFF & PREPARERS",
    seasonal: "SEASONAL",
    operations: "OPERATIONS",
  } satisfies Record<Band, string>,
  // DEC-353: the row carries no identity-provider name.
  sso: "SSO",
  ssoChecked: "SSO, signed in with MFA",
  none: "—",
  today: (time: string) => `Today ${time}`,
  wallTag: (count: number) => `Wall ${n(count)}`,
  openPerson: (name: string) => `Open ${name}`,
  rowMenu: (name: string) => `More for ${name}`,
  empty: "No people match these filters.",
  clearFilters: "Clear filters",
  error: "People couldn't be loaded.",
  invitationsEmpty: "No pending invitations.",
  templates: {
    partner: { label: "Partner", line: "Sign-off L4, release, final approval" },
    manager: { label: "Manager", line: "Review L2/L3, AJE within threshold" },
    tax_reviewer: { label: "Tax Reviewer", line: "Review returns, export after approval" },
    senior: { label: "Senior", line: "Prepare, first-level review" },
    staff: { label: "Staff", line: "Prepare and adopt agent work" },
    tax_preparer: { label: "Tax Preparer", line: "Prepare returns" },
    firm_admin: { label: "Firm Admin", line: "People, clients, firm-ops agents" },
    it_security: { label: "IT / Security", line: "Security roles, SSO, keys, audit log" },
  } satisfies Record<Template, { label: string; line: string }>,
  templateList: "Role templates",
  agent: {
    name: "Accrued Agent",
    line: "non-human · locked",
    text: "Accrued Agent — Draft · Test · Propose · Chase within the invoking user's scope. Never approves, signs off, releases, sends final, posts or exports.",
    locked: "Locked",
  },
  grid: {
    label: "Capabilities by role template",
    header: "Capability",
    footer:
      "Default policy from 01 §2.4. Firms may only make it stricter. Hard limits are locked.",
  },
  cells: {
    allow: "Allowed",
    allowWith: (c: string) => `Allowed: ${c}`,
    conditional: (c: string) => `Allowed with a condition: ${c}`,
    delegated: "Draft or propose only",
    deny: "No access",
    locked: "Locked",
  } satisfies CapabilityWords,
  inviteDrawer: {
    title: "Invite user",
    person: "Person",
    name: "Name",
    namePlaceholder: "First and last name",
    email: "Email",
    emailPlaceholder: "name@example.com",
    access: "Access",
    role: "Role",
    office: "Office",
    team: "Team",
    seasonal: "Seasonal",
    accessEnds: "Access ends",
    accessEndsPlaceholder: "YYYY-MM-DD",
    offshore: "Offshore / restricted",
    // DEC-352 (TASK-1207): consent gates assignment, not visibility.
    offshoreHelp:
      "Members are assigned only to clients with a valid §7216 offshore consent; SSNs masked.",
    seatsFull: (total: number) =>
      `All ${n(total)} seats are assigned. Add seats or deactivate a user first.`,
    cancel: "Cancel",
    send: "Send invite",
    sent: "Invite sent",
  },
  personDrawer: {
    access: "Access",
    role: "Role",
    seasonal: (template: string) => `${template} · seasonal`,
    office: "Office",
    team: "Team",
    email: "Email",
    accessEnds: "Access ends",
    offshore: "Offshore / restricted",
    status: "Status",
    walls: "Ethical walls",
    wallLine: (client: string, added: string) => `${client} (added ${added})`,
    assignments: "Assignments",
    assignmentCount: (count: number) => (count === 1 ? "1 assignment" : `${n(count)} assignments`),
    noAssignments: "No assignments",
    signIns: "Sign-in history",
    signIn: (when: string, method: string, mfa: boolean, ip: string | null | undefined) =>
      [when, method, ...(mfa ? ["MFA"] : []), ...(ip ? [ip] : [])].join(" · "),
    noSignIns: "No sign-ins yet",
    changeRole: "Change role…",
    deactivate: "Deactivate…",
    close: "Close",
  },
  statusWords: { active: "Active", invited: "Invite pending", deactivated: "Deactivated" },
  confirmRole: {
    title: (name: string, template: string) => `Change ${name}'s role to ${template}?`,
    body: "The change applies on their next request and is recorded in the audit log.",
    confirm: "Change role",
    cancel: "Cancel",
    done: "Role changed",
  },
  confirmDeactivate: {
    title: (name: string) => `Deactivate ${name}?`,
    body: "Their sessions end and the seat frees. Their sign-offs stay attributed to them.",
    confirm: "Deactivate",
    cancel: "Cancel",
    done: "Deactivated",
  },
  stepUpTitle: "Confirm it's you to change people",
  stepUpBody:
    "Changing people needs a recent sign-in. Sign in again, then try once more. If it still isn't allowed, your role doesn't permit it.",
  cancel: "Cancel",
  signInAgain: "Sign in again",
  errors: {
    seats_full: "All seats are assigned.",
    already_member: "That person is already a member.",
    access_ends_required: "A seasonal member needs the date their access ends.",
    last_admin: "The firm must keep at least one active firm administrator.",
    offshore_assignment_conflict:
      "Offshore can't be turned on while they're assigned to clients without an offshore consent.",
    stale_version: "Changed by someone else — reload",
    unavailable: "That didn't work. Try again.",
  } as Readonly<Record<string, string>>,
  independence: {
    title: (year: number) => `Independence · ${n(year)}`,
    counts: (confirmed: number, notYet: number, declined: number) =>
      `${n(confirmed)} confirmed · ${n(notYet)} not yet · ${n(declined)} declined`,
    table: "Annual independence confirmations",
    person: "Name",
    office: "Office",
    status: "Status",
    decided: "Decided",
    note: "Note",
  },
} as const;

export type Adm02Template = Template;
export type Adm02Band = Band;
