// G-02-T07: the Brightwater Hale governance slice for ADM-04 and ADM-06 fixture mode, verbatim
// from the ADM-04 and ADM-06 handoff specs and G-02 §5.4; the shared golden is
// backend/tests/golden/scenario/brightwater_hale/governance_e0.json. Synthetic only.
//
// Typed with the generated client where a contract exists (incidents: compliance-kernel v1.1).
// The security-center (G-02-T11) and AI-policy (G-02-T15) contracts don't exist yet, so those
// records use the local shapes below; each task types them against its models when it lands.
// The live seed cannot hold most of this yet (DEC-419): the policy versions wait for G-02-T23,
// the sign-in policy and MFA counts for T14, closed incidents for T18, WISP for T20, the export
// history for Q-02-T43 (compliance.ts already serves it).
import type { IncidentOut } from "@abacus/api-client";
import { stableId } from "./prng";

/** ADM-06 C rows 2 and 3: closed, not notification events. Times of day are not in the
 * handoff, so each is the discovery date at midnight CT. */
function closed(
  ref: string,
  title: string,
  eventKind: IncidentOut["event_kind"],
  day: string,
  consumers: number,
  unencrypted: boolean | null,
  notifyBy: string,
): IncidentOut {
  const at = `${day}T05:00:00Z`;
  // `platform.clock_day`: calendar days since discovery, at E0 (Mon Sep 14, 2026).
  const clockDay = Math.round((Date.parse("2026-09-14") - Date.parse(day)) / 86_400_000);
  return {
    id: stableId(`incident:${ref}`),
    ref,
    title,
    event_kind: eventKind,
    discovered_at: at,
    consumers_affected: consumers,
    unencrypted,
    notification_event: false,
    ftc_notify_by: notifyBy,
    clock_day: clockDay,
    clock_days: 30,
    source: "firm",
    accrued_ref: null,
    accrued_confirmed_at: null,
    dpa_notice_at: null,
    created_at: at,
  };
}

export const INC_2026_004: IncidentOut = closed(
  "INC-2026-004",
  "Phishing email to docs@brightwaterhale.com (no click)",
  "other",
  "2026-09-08",
  0,
  null,
  "2026-10-08",
);
export const INC_2026_003: IncidentOut = closed(
  "INC-2026-003",
  "Lost laptop, full-disk encrypted (Chicago)",
  "lost_device",
  "2026-07-21",
  0,
  false,
  "2026-08-20",
);

/** ADM-06d: INC-2026-005's timeline, in order, as codes and facts (the drawer's words come
 * from the screen's copy registry, G-02-T16). */
export const INC_2026_005_TIMELINE: readonly {
  at: string;
  code: string;
  facts: Record<string, string | number>;
}[] = [
  {
    at: "2026-09-10T07:14:00Z",
    code: "sign_ins_blocked",
    facts: { failed: 1812, network: "203.0.113.0/24" },
  },
  { at: "2026-09-10T12:05:00Z", code: "rate_limit_tightened", facts: { by: "FA" } },
  { at: "2026-09-11", code: "review_completed", facts: { accounts_accessed: 0 } },
  { at: "2026-09-14", code: "status_set", facts: { status: "investigating" } },
];

export interface PersonRef {
  user_id: string;
  display_name: string;
}
const person = (name: string): PersonRef => ({
  user_id: stableId(`user:${name.toLowerCase().replace(/[^a-z]+/g, "-")}`),
  display_name: name,
});
export const MARGARET = person("Margaret Okonkwo");
export const DANIEL = person("Daniel Reyes");
export const FELIX = person("Felix Andersen");

/** ADM-04j: v1 Jan 5, v2 Jan 9, v3 Jan 14, 2026, each published by Margaret Okonkwo and
 * approved by Daniel Reyes (G-02 §5.4); v3 is effective at E0. */
export interface PolicyVersion {
  version: number;
  name: string;
  state: "published";
  published_on: string;
  requested_by: PersonRef;
  approved_by: PersonRef;
}
export const AI_POLICY_VERSIONS: readonly PolicyVersion[] = [
  ["2026-01-05", 1],
  ["2026-01-09", 2],
  ["2026-01-14", 3],
].map(([on, version]) => ({
  version: Number(version),
  name: `BH AI policy v${String(version)}`,
  state: "published",
  published_on: String(on),
  requested_by: MARGARET,
  approved_by: DANIEL,
}));

/** ADM-06a fieldset A, and e (the Jan 11, 2026 snapshot before enforcement). */
export interface SignInSnapshot {
  as_of: string;
  provider: "Microsoft Entra ID";
  require_sso: boolean;
  sso_enforced_on: string | null;
  sso_enforced_by: PersonRef | null;
  mfa_enrolled: number;
  seats: number;
}
export const SIGN_IN_E0: SignInSnapshot = {
  as_of: "2026-09-14",
  provider: "Microsoft Entra ID",
  require_sso: true,
  sso_enforced_on: "2026-01-12",
  sso_enforced_by: FELIX,
  mfa_enrolled: 46,
  seats: 46,
};
export const SIGN_IN_JAN_11: SignInSnapshot = {
  as_of: "2026-01-11",
  provider: "Microsoft Entra ID",
  require_sso: false,
  sso_enforced_on: null,
  sso_enforced_by: null,
  mfa_enrolled: 41,
  seats: 46,
};

/** ADM-06 support card: the last session, closed. */
export const LAST_SUPPORT_SESSION = {
  on: "2026-08-17",
  from: "10:12 AM",
  to: "11:40 AM",
  engineer: "Jordan Pryce",
  scope: "integration settings only",
  state: "closed",
} as const;

/** ADM-06 fieldset D. The 20 Pub 4557 control definitions are platform content imported through
 * the staff route (G-02 §4.2), never committed: only the counts are seeded here. */
export const WISP = {
  name: "BH WISP v4",
  format: "IRS Pub 5708 format",
  approved_by: MARGARET,
  approved_on: "2026-01-15",
  controls_evidenced: 18,
  controls_total: 20,
} as const;
