// ADM-06 copy, verbatim from the handoff (screens/ADM-06 spec.md and revision.md R2) and
// docs/screens/ADM-06.md with the T03 deviations: fieldset B's MFA row is DF-17's locked floor,
// the lockout DEC-35's "3 codes · 15 minutes" (locked), retention read-only with its FIL-02
// planned link; the sessions drawer, unlock, the IdP-MFA attestation and the support-session
// states are T03's new v1 rows. Rows carry codes and facts; the words are composed here.

import { count } from "@abacus/ui";

type Facts = Readonly<Record<string, string | number | boolean | null>>;
const fact = (v: string | number | boolean | null | undefined): string =>
  v === null || v === undefined ? "" : String(v);

export const COPY = {
  title: "Firm settings",
  navTitle: "Settings",
  back: "Back",
  section: "Security",
  readOnly: "Only IT/Security can change security settings.",
  unsaved: "Unsaved changes",
  saved: "Security settings saved",
  error: "The security settings couldn't load.",
  saveFailed: "Couldn't save. Try again.",
  stale: "Changed by someone else — reload",
  ssoNotVerified: "Sign in once with SSO as an admin before enforcing it.",
  loosening: "Session limits can only be shortened.",
  tooShort: "That limit is shorter than the platform allows.",
  stepUpTitle: "Confirm it's you to change security settings",
  stepUpBody:
    "Changing security settings needs a recent sign-in. Sign in again, then try once more. If it still isn't allowed, your role doesn't permit it.",
  cancel: "Cancel",
  signInAgain: "Sign in again",
  exportWisp: "Export WISP pack",
  wispReady: (n: number) => `WISP evidence pack prepared · ${String(n)} documents`,

  // A. Firm sign-in
  signIn: "Firm sign-in",
  identityProvider: "Identity provider",
  sso: (provider: string) => `${provider} (SSO)`,
  noProvider: "Not connected",
  requireSso: "Require SSO for all firm users",
  requireSsoR2: "Require SSO",
  ssoSince: (on: string, by: string) => `Enforced since ${on} by ${by}.`,
  mfa: "Multi-factor authentication",
  mfaEnrolled: (enrolled: number, seats: number) =>
    `Enforced · ${String(enrolled)} of ${String(seats)} enrolled`,
  mfaGap: (enrolled: number, seats: number) => `${String(enrolled)} of ${String(seats)} enrolled`,
  mfaGapBanner: (missing: number) =>
    `${String(missing)} users without MFA. Enforcing SSO will require MFA at next sign-in.`,
  idpMfa: "IdP enforces MFA",
  idpMfaHelp: "Count SSO users as enrolled from the identity provider's MFA claim.",
  sessionLength: "Session length",
  idleTimeout: "Idle timeout",
  hours: (h: number) => `${String(h)} ${h === 1 ? "hour" : "hours"}`,
  minutes: (m: number) => `${String(m)} minutes`,
  breakGlass: "Break-glass account",
  breakGlassValue: (tested: string | null) =>
    tested === null
      ? "1 · hardware key · not tested yet"
      : `1 · hardware key · last tested ${tested}`,
  breakGlassNone: "None",
  sessions: "Active sessions",
  sessionsOpen: (n: number) => `${String(n)} active ›`,

  // R2 (fixture only until G-03-T29)
  allUsers: "All users",
  perUser: "Per user",
  exceptions: (n: number) => `Exceptions — ${String(n)} (break-glass account)`,
  idpInitiated: "IdP-initiated SSO",
  idpInitiatedHelp: (provider: string) =>
    `People can open Accrued from the ${provider} app launcher.`,
  scim: "SCIM provisioning",
  scimStatus: "Status",
  scimConnected: (provider: string) => `Connected · ${provider}`,
  scimUsers: "Users provisioned",
  scimSeats: (n: number, of: number) => `${String(n)} of ${String(of)} seats`,
  scimGroups: "Groups mapped",
  scimDeprovision: "Deprovisioning",
  scimDeprovisionValue: (provider: string, seasonalEnds: string) =>
    `Access ends when a user is disabled in ${provider}; Seasonal ends ${seasonalEnds}`,
  scimLastSync: "Last sync",
  scimSynced: (at: string, errors: number) => `Today ${at} · ${String(errors)} errors`,
  scimError: (n: number, used: number, seats: number) =>
    `${String(n)} user not provisioned · seat limit ${String(used)} of ${String(seats)}`,
  openSeats: "Open seats (ADM-02) →",
  perUserTable: "Require SSO per user",
  person: "Person",
  ssoColumn: "SSO",
  exempt: "Exempt",
  scimPosture: "SCIM provisioning on",

  // B. Client portal sign-in
  portal: "Client portal sign-in",
  passwordless: "Passwordless email code",
  portalMfa:
    "Require MFA for owners, signers, approvers and anyone who can see tax return information",
  portalSession: "Portal session length",
  lockout: "Lock after failed codes",
  lockoutValue: (codes: number, minutes: number) =>
    `${String(codes)} codes · ${String(minutes)} minutes`,
  lockedFloor: "Required by the platform",

  // C. Incident register
  incidents: "Incident register",
  addIncident: "Incident",
  incidentColumns: ["ID", "Event", "Discovered", "Consumers affected", "FTC clock", "Status"],
  confirmed: (n: number) => `${String(n)} confirmed`,
  encrypted: (n: number) => `${String(n)} (encrypted)`,
  clock: (day: number, of: number, by: string) =>
    `Day ${String(day)} of ${String(of)} · notify by ${by} if ≥ 500`,
  notNotification: "Not a notification event",
  investigating: "Investigating",
  closed: "Closed",
  ftcHelp:
    "FTC Safeguards Rule, 16 CFR 314.4(j): notify the FTC as soon as possible and no later than 30 days after discovering a notification event involving unencrypted customer information of 500 or more consumers. State breach laws may also apply.",

  // D. WISP & safeguards
  wisp: "WISP & safeguards",
  qi: "Qualified Individual",
  wispPlan: "Written information security plan",
  wispValue: (name: string, by: string, on: string) =>
    `${name} (IRS Pub 5708 format) · approved by ${by} ${on}`,
  open: "Open ›",
  annualReport: "Annual written report to the partners (16 CFR 314.4(i))",
  annualReportValue: (last: string, next: string) => `Last delivered ${last} · next due ${next}`,
  pub4557: "IRS Pub 4557 controls",
  pub4557Value: (done: number, total: number) => `${String(done)} of ${String(total)} evidenced`,
  scheduled: (title: string, on: string) => `${title} — scheduled ${on}`,
  due: (title: string, on: string) => `${title} — due ${on}`,
  training: "Security training",
  trainingValue: (done: number, total: number) =>
    `${String(done)} of ${String(total)} complete (seasonal staff on hire)`,
  ptin: "PTIN renewal data-security plan attestation (Form W-12 / online renewal)",
  ptinValue: (done: number, total: number) =>
    `${String(done)} of ${String(total)} PTIN holders on the Tax team`,
  accessReview: "Quarterly access review",
  accessReviewValue: (quarter: string, due: string, status: string) =>
    `${quarter} · due ${due} · ${status}`,
  inProgress: "in progress",

  // E. Data residency
  residency: "Data residency",
  region: "Region",
  regionValue: "United States",
  regionHelp: "Pinned at provisioning (PLT-01). Changing region requires a new tenant.",
  storage: "Storage",
  storageValue: "US · primary Ohio, backup Oregon",
  aiInference: "AI inference",
  aiInferenceValue: "US only",
  logs: "Logs & traces",
  logsValue: "US",
  encryption: "Encryption",
  encryptionValue: "AES-256 at rest · TLS 1.3 in transit",

  // F. Retention defaults (read-only; FIL-02)
  retention: "Retention defaults",
  retentionHelp: "Clocks and holds are managed in Files › Retention (FIL-02).",
  retentionRows: [
    ["Form 8879 family", "7 years"],
    ["Returns, workpapers and source documents", "7 years"],
    ["Audit documentation", "7 years · WORM after assembly"],
    ["Engagement letters & consents", "Life of relationship + 7 years"],
    ["Permanent file (elections, basis, instruments)", "While active + 7 years"],
    ["Email & portal messages", "7 years"],
  ] as const,
  legalHolds: "Legal holds",
  legalHoldsValue: "0 active ›",

  // Cards
  dataExport: "Data export",
  scheduledPill: "Scheduled",
  schedule: "Schedule",
  scheduleValue: "Monthly · 1st at 2:00 AM CT",
  contents: "Contents",
  contentsValue: "Clients, entities, files, workpapers, returns, closes, audit log",
  format: "Format",
  formatValue: "Encrypted archive (AES-256) + SHA-256 manifest",
  lastExport: "Last export",
  lastExportValue: (on: string, gb: number) => `${on} · ${String(gb)} GB`,
  next: "Next",
  approval: "Approval",
  approvalValue: (a: string, b: string) => `Two people: ${a} + ${b}`,
  history: "History",
  exportNow: "Export now…",
  approveExport: "Approve export",
  waitingFor: (name: string) => `Waiting for approval · ${name}`,
  exportApproved: "Export approved",
  exportDialogTitle: "Export all firm data?",
  exportDialogBody: (approver: string) =>
    `Creates an encrypted archive of all client, file, workpaper and audit-log data. ${approver} must approve before the download link is issued. The link expires after 7 days.`,
  requestExport: "Request export",
  exportRequested: "Data export requested",
  actions: "Actions",
  changeSchedule: "Change schedule",
  historyRow: (on: string, gb: number) => `${on} · ${String(gb)} GB`,

  supportAccess: "Support access",
  supportBody: "Accrued support sees no client content without a session you approve.",
  lastSession: "Last session",
  supportSessionValue: (on: string, from: string, to: string, who: string) =>
    `${on} · ${from}–${to} · ${who} (Accrued Support) · integration settings only`,
  awaitingApproval: "Awaiting firm approval",
  grantedUntil: (at: string) => `Granted until ${at}`,
  revoked: "Revoked",
  approve: "Approve",
  revoke: "Revoke",
  allowRequests: "Allow support session requests",

  posture: "Posture",
  postureSso: "SSO enforced",
  postureSsoOff: "SSO not enforced",
  postureMfa: (n: number, of: number) => `MFA ${String(n)}/${String(of)}`,
  postureUs: "US residency",
  postureIncidents: (n: number) => `${String(n)} open ${n === 1 ? "incident" : "incidents"}`,
  posturePub4557: (n: number) => `${String(n)} Pub 4557 ${n === 1 ? "item" : "items"} open`,

  // Sessions drawer and unlock
  sessionsTitle: "Active sessions",
  sessionColumns: ["Person", "Device", "IP", "Started", "Last seen", "MFA"],
  signOutOf: (firm: string) => `Sign out of ${firm}`,
  signedOut: (who: string) => `${who} signed out of this firm`,
  thisSession: "This session",
  unlock: "Unlock",
  unlocked: "Sign-in unlocked",
  unlocksAt: (at: string) => `Unlocks automatically at ${at}`,
  notLocked: "Not locked",
  noSessions: "No active sessions.",

  // Incident drawer (d)
  timeline: "Timeline",
  clockLabel: (day: number, of: number) => `Day ${String(day)} of ${String(of)}`,
  closeNotReportable: "Close as not reportable…",
  closeHint: "Partner + QI",
  startNotification: "Start notification…",
  waitingDecision: (name: string) => `Waiting for ${name}`,
  timelineWords: {
    sign_ins_blocked: (f: Facts) =>
      `${count(fact(f.failed))} failed sign-ins from ${fact(f.network)} blocked`,
    rate_limit_tightened: (f: Facts) => `Rate limit tightened by ${fact(f.by)}`,
    review_completed: (f: Facts) =>
      `Forensic review: ${fact(f.accounts_accessed)} accounts accessed`,
    status_set: () => "Status Investigating",
  } as Record<string, (facts: Facts) => string>,
} as const;

export const SESSION_OPTIONS = [12, 10, 8, 4, 1].map((h) => ({
  value: String(h * 60),
  label: COPY.hours(h),
}));
export const IDLE_OPTIONS = [30, 20, 15, 10, 5].map((m) => ({
  value: String(m),
  label: COPY.minutes(m),
}));
export const PORTAL_OPTIONS = [8, 4, 2, 1].map((h) => ({
  value: String(h * 60),
  label: COPY.hours(h),
}));
