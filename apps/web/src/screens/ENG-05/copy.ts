// ENG-05 copy, verbatim from the handoff (spec.md and the canvas `Wave 3 - Engagements &
// Projects.dc.html#eng05`; docs/screens/ENG-05.md, Copy). Names, roles' people, hours, dates and
// the engagement's name are data, never copy. Strings the handoff does not write (the Change
// role, Edit hours and Remove dialogs, the failure toast) are recorded in the contract's
// Deviations (TASK-1274, DEC-386).

import type { EqrCheckOut } from "@abacus/api-client";

const n = (v: number): string => String(v);

export const COPY = {
  pane: { title: "Team" },
  noun: "people",
  search: { placeholder: "Search people" },
  header: {
    request: "Request confirmations…",
    requestHint: "Send a confirmation request to everyone still pending",
    requestNone: "Everyone on the team has confirmed",
    add: "Add person",
    addTitle: "Add to the team",
    addPartner: "Engagement partner",
    addNone: "Everyone available is already on the team.",
  },
  columns: {
    person: "Person",
    role: "Role",
    budget: "Budget h",
    actual: "Actual h",
    independence: "Independence",
    portal: "Shown on portal",
    actions: "Actions",
  },
  roles: {
    engagement_partner: "Engagement partner (EP)",
    eqr_reviewer: "EQR reviewer",
    manager: "Manager",
    senior: "Senior (in-charge)",
    staff: "Staff",
    reviewer: "Reviewer",
    specialist: "Specialist",
    client_service: "Client service",
  } as Readonly<Record<string, string>>,
  proposed: (role: string) => `${role} (proposed)`,
  added: (day: string) => `added ${day}`,
  banner: {
    /** "G2 Independent: 5 of 5 assigned members confirmed. Kira Ross is pending — she can't …" */
    text: (confirmed: number, pending: readonly string[]) => {
      const head =
        confirmed > 0
          ? `G2 Independent: ${n(confirmed)} of ${n(confirmed)} assigned members confirmed. `
          : "G2 Independent: no assigned members confirmed yet. ";
      const names =
        pending.length > 1
          ? `${pending.slice(0, -1).join(", ")} and ${pending[pending.length - 1] ?? ""} are`
          : `${pending[0] ?? ""} is`;
      // The roster carries no pronoun (DEC-386): "they" where the canvas reads the seed's.
      return `${head}${names} pending — they can’t be assigned or sign off until they confirm.`;
    },
  },
  row: {
    confirmed: "Confirmed",
    confirmedOn: (day: string) => `Confirmed ${day}`,
    pending: "Pending",
    pendingSince: (day: string) => `Pending · requested ${day}`,
    declined: "Declined",
    remind: "Remind",
    reminded: "Reminded",
    portalOn: (name: string) => `Show ${name} on the client’s team card`,
    portalPending: "Available once they confirm independence",
    menuLabel: (name: string) => `${name} actions`,
    menu: {
      changeRole: "Change role…",
      editHours: "Edit hours…",
      remove: "Remove from team…",
    },
    none: "—",
  },
  totals: {
    people: (count: number) => (count === 1 ? "1 person" : `${n(count)} people`),
    confirmed: (c: number, t: number) => `${n(c)} of ${n(t)} confirmed`,
    shown: (s: number) => `${n(s)} shown`,
  },
  agents: {
    band: "Agents on this engagement",
    name: "Accrued Agent",
    role: "Agent",
    /** P-07 §2.1: without agent-minutes until P-10. */
    sub: "Acts with the invoking user’s permissions · never signs off",
    independence: "Not applicable",
  },
  footer: {
    approved: (by: string, day: string, changes: readonly string[]) =>
      `Team approved by ${by} (EP) · ${day}${
        changes.length > 0 ? ` · changes since: ${changes.join(", ")}` : ""
      }`,
    change: (name: string, day: string) => `+ ${name} (${day}, awaiting approval)`,
    notApproved: (names: readonly string[]) =>
      `Team not approved yet · proposed: ${names.join(", ")}`,
  },
  empty: { title: "No team yet.", action: "Add the engagement partner" },
  filtered: (q: string) => `No people match “${q}”.`,
  inspector: {
    eqr: "EQR eligibility",
    member: "Team member",
    agent: "Agent",
    none: "No EQR reviewer yet.",
    eligible: "Eligible",
    checks: "Checks (SQMS 2)",
    approval: "Approval",
    approvalHelp: "The EP cannot approve the EQR on her own engagement.",
    replace: "Replace EQR…",
    onEngagement: "On this engagement",
    role: "Role",
    budget: "Budget",
    actual: "Actual",
    shown: "Shown on portal",
    yes: "Yes",
    no: "No",
    hours: (h: string) => `${h} h`,
    agentSub: "Agent · independence not applicable",
    permissions: "Permissions",
    permissionsValue: "The invoking user’s",
    signOff: "Sign-off",
    signOffValue: "Never signs off",
  },
  check: (c: EqrCheckOut, client: string): string => {
    switch (c.code) {
      case "not_on_team":
        return "Not a member of the engagement team";
      case "cooling_off":
        return c.result === "fail"
          ? `Cooling-off conflict — EP on this plan for PY${c.year == null ? "" : n(c.year)}`
          : `No cooling-off conflict — not EP on ${client} in the prior two years`;
      case "competence":
        return c.count != null && c.count > 0
          ? `EBP audit competence — ${n(c.count)} EBP EQRs in ${c.year == null ? "" : n(c.year)}`
          : "EBP audit competence";
      case "independence":
        return c.result === "pass" ? "Independence confirmed" : "Independence pending";
      case "capacity":
        return "Capacity";
    }
  },
  blocked: {
    title: "Assignment pending independence",
    body: (person: string, engagement: string) =>
      `${person} hasn’t confirmed independence for ${engagement}. They can view the engagement but can’t be assigned work or sign off.`,
    person: "Person",
    role: "Role",
    send: "Send confirmation request",
    cancel: "Cancel",
  },
  eqr: {
    title: "Replace EQR reviewer",
    current: "Current EQR",
    eligible: "Eligible",
    notEligible: (year: string) =>
      `Not eligible — EP on this plan for ${year} (cooling-off, 2 years)`,
    notEligibleOther: "Not eligible",
    hintCooling:
      "SQMS 2 requires a two-year cooling-off before a former engagement partner can serve as EQR.",
    hintCurrent: (name: string) => `${name} is already the EQR on this engagement.`,
    hintOk: "A QM delegate other than the EP approves the new EQR’s eligibility.",
    cancel: "Cancel",
    assign: "Assign",
  },
  sheet: {
    title: "Request confirmations",
    pending: "Pending independence",
    sub: (role: string, day: string) => `${role} · requested ${day}`,
    note: (engagement: string) =>
      `Each person confirms independence for ${engagement} in their Inbox. Until then they can view the engagement but can’t be assigned work or sign off.`,
    cancel: "Cancel",
    send: "Send",
  },
  dialogs: {
    roleTitle: (name: string) => `Change role — ${name}`,
    hoursTitle: (name: string) => `Edit hours — ${name}`,
    removeTitle: (name: string) => `Remove ${name} from the team?`,
    removeConfirm: "Remove",
    save: "Save",
  },
  toast: {
    sent: (names: readonly string[]) => `Confirmation request sent to ${names.join(", ")}`,
    reminded: (name: string) => `Reminder sent to ${name} · Inbox`,
    shown: (name: string) => `${name} shown on the client’s team card (POR-02)`,
    hidden: (name: string) => `${name} hidden from the client’s team card`,
    eqr: (name: string) => `${name} proposed as EQR · eligibility approval requested`,
    failed: "Couldn’t save the change.",
  },
} as const;
