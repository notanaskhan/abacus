// CLI-04 copy, verbatim from the handoff spec.md (docs/screens/CLI-04.md, Copy). Contact names,
// emails, roles' scope names, request titles and the email itself are data, never copy: the
// invitation email is the firm's Invitation template (C16, DEC-301). Strings the handoff does not
// write (the drawer, the unlock dialog, the change-scope action, role words) are recorded in the
// screen contract's Deviations (TASK-1216).

import type { ContactRoleOut } from "@abacus/api-client";

export const COPY = {
  pane: { title: "Contacts & access" },
  noun: "contacts",
  search: { placeholder: "Search contacts" },
  header: {
    counts: (active: number, invited: number, notInvited: number) =>
      `${String(active)} active · ${String(invited)} invited · ${String(notInvited)} not invited`,
    locked: (n: number) => ` · ${String(n)} locked`,
    preview: "Portal preview",
    previewHint: "Opens POR-02 rendered as a contact",
    invite: "Invite…",
  },
  columns: {
    contact: "Contact",
    roles: "Roles",
    scope: "Scope",
    portal: "Portal",
    mfa: "MFA",
    lastSeen: "Last seen",
    actions: "Actions",
  },
  row: {
    resend: "Resend",
    invite: "Invite…",
    unlock: "Unlock…",
    menu: { changeScope: "Change scope…", unlock: "Unlock…", revoke: "Revoke…" },
    menuLabel: (name: string) => `${name} actions`,
    mfaOn: "On",
    thirdParty: "Third party",
    /** A third party's scope: its delegated requests only. */
    delegatedOnly: (n: number) => `${String(n)} delegated requests only`,
    /** Anyone else: the entities their roles name, then their delegated requests. */
    requests: (n: number) => `${String(n)} requests`,
    invited: (sent: string, expires: string) => `Sent ${sent} · expires ${expires}`,
    sent: (sent: string) => `Sent ${sent}`,
  },
  /** d: DF-24 amends "5 incorrect codes" to 3 (lockout after three codes, 15 minutes). */
  locked: {
    sub: (time: string | null) =>
      time === null ? "3 incorrect codes" : `3 incorrect codes · ${time}`,
  },
  footer: {
    delegated: (parts: readonly number[], total: number, received: number) =>
      `Requests delegated: ${parts.map(String).join(" + ")} = ${String(total)} · PBC received ${String(received)} of ${String(total)}`,
  },
  /** g: a non-attest client's note. */
  nonAttest: "Non-attest client: no SKE designation required",
  tooltip: {
    ske: "SKE designee: the person with skills, knowledge and experience who oversees nonattest services — attest clients only",
  },
  roles: {
    owner: "Owner",
    cfo: "CFO",
    controller: "Controller",
    trustee: "Trustee",
    executor: "Executor",
    taxpayer: "Taxpayer",
    spouse: "Spouse",
    plan_sponsor_officer: "Plan administrator",
    recordkeeper: "Recordkeeper",
    tpa: "TPA",
    custodian: "Custodian",
    payroll_provider: "Payroll",
    other: "Other",
  } satisfies Record<ContactRoleOut["role"], string>,
  sheet: {
    title: "Invite to portal",
    titleChange: (name: string) => `Change access — ${name}`,
    send: "Send invite",
    save: "Save access",
    who: "Who",
    whatTheySee: "What they can see",
    security: "Security",
    emailPreview: "Email preview",
    keys: {
      organization: "Organization",
      contact: "Contact",
      email: "Email",
      role: "Role",
      access: "Access",
      due: "Due",
      signIn: "Sign-in",
      mfa: "MFA required",
      expires: "Link expires",
    },
    onlyDelegated: "Only delegated requests",
    fullClient: (client: string) => client,
    signIn: "Email code",
    expires: "14 days",
    mfaLocked: "Locked on by firm policy",
    /** No read renders the firm's Invitation template yet (C16): the card names its source. */
    previewSource: "Sent from your firm's Invitation email template.",
    note: (org: string, count: number) =>
      `${org} will see only these ${String(count)} requests. They will not see the plan's other documents, materiality, review notes or other clients.`,
    noRequests: "No delegated requests to give.",
  },
  toast: {
    sent: (org: string) => `Invite sent to ${org}`,
    saved: "Access changed",
    unlocked: "Unlocked",
    revoked: "Access revoked",
    failed: "Couldn’t save the change.",
  },
  revoke: {
    title: (org: string) => `Revoke portal access for ${org}?`,
    /** One full stop when the client's name already ends with one ("Inc."). */
    body: (client: string) =>
      `Their invite stops working immediately. Requests stay assigned to ${client}${client.endsWith(".") ? "" : "."}`,
    confirm: "Revoke",
    cancel: "Cancel",
  },
  unlock: {
    title: (name: string) => `Unlock portal sign-in for ${name}?`,
    body: "They can sign in again with a new email code.",
    confirm: "Unlock",
    cancel: "Cancel",
  },
  drawer: {
    roles: "Roles",
    access: "Access",
    signIns: "Sign-in history",
    noSignIns: "No sign-ins yet.",
    delegated: "Delegated requests",
    noDelegated: "No delegated requests.",
    grant: {
      pending: "Pending",
      active: "Active",
      revoked: "Revoked",
    },
    signIn: {
      signed_in: "Signed in",
      code_failed: "Incorrect code",
      locked: "Locked",
      unlocked: "Unlocked",
    },
  },
  empty: { title: "No contacts yet." },
  none: "—",
} as const;
