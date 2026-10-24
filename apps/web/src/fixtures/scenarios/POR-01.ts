// POR-01 Portal sign-in: one fixture scenario per artboard (P-08-T08; docs/screens/POR-01.md), plus
// c2 (c′, the DF-17 two-step setup state) and M (the 390 layout). Each is a data condition on the
// portal's fixture routes (fixtures/handlers/portal.ts); `START` names what the artboard has done
// when it opens (typed an email, asked for a code, typed or submitted a code), which the screen
// replays through the same routes a person's clicks call:
//
//   a   Claire Feld: no session; the email field holds her address          Mon Sep 14, 9:22 AM CT
//   b   Claire: start answered 202, resend 42 s ahead; 481027 typed
//   c   Tess Moreno: an owner grant meets the MFA floor → mfa_required (P-08-T19)
//   c2  Tess with no factor yet → mfa_setup_required (DF-17; P-08-T19)
//   d   Sam Ortiz: a pending invitation, 9 Northwind 401(k) requests        Wed Sep 2, 2026
//   e   Claire opens a reminder link issued Aug 20 (25 days old) → expired
//   f   Claire mistypes 481072 → 401 code_mismatch, 2 tries left
//   g   Claire's third wrong code → 423 sign_in_locked for 15 minutes
//   M   a at 390 × 844 (DF-03)
//
// Dev and test only: nothing here may reach the portal's production build.

import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import type { InvitationPreviewOut, SignInOpening } from "../../app-core/portal-contracts";
import { portalHandlers } from "../handlers/portal";
import { getSeed } from "../seed";
import { FIXTURE_CODE, MISTYPED_CODE } from "../seed/portal-home";

const seed = getSeed();

/** Mon Sep 14, 2026, 9:22 AM CT: two minutes before E0 (POR-01 a–c, e–g). */
export const SIGN_IN_CLOCK = "2026-09-14T09:22:00-05:00";
/** Wed Sep 2, 2026 (d); the handoff names the day only, so the morning hour is the seed's. */
export const INVITE_CLOCK = "2026-09-02T09:22:00-05:00";
/** e: the reminder link went out Thu Aug 20, 2026. */
export const LINK_ISSUED_AT = "2026-08-20T14:00:00Z";
/** A reminder link's token in the fragment (fixture only; real tokens are 256-bit). */
export const FIXTURE_LINK_TOKEN = "fixture-reminder-link-feld-2026-08-20";
/** d: Sam Ortiz's invitation token in the `/accept` fragment (fixture only). */
export const FIXTURE_INVITATION_TOKEN = "fixture-invitation-sam-ortiz-2026-09-02";

export function emailOf(slug: string): string {
  return seed.people.find((p) => p.slug === slug)?.email ?? "";
}

/** Northwind's 24 PBC requests as CLI-04 delegates them (P-07 §5: 10 + 9 + 2 + 2 + 1 = 24);
 * Keystone Retirement Services holds 9 (d, POR-14). The interim seed's per-request `owner` column
 * names Keystone on 7 of them: an open gap in docs/screens/POR-01.md, not a second figure. */
export const NORTHWIND_DELEGATIONS = [10, 9, 2, 2, 1] as const;
export const KEYSTONE_DELEGATED = NORTHWIND_DELEGATIONS[1];

/** Requests the seed's owner column gives Keystone (for the recorded gap). */
export function keystoneOwned(): number {
  return Object.values(seed.requestOwners).filter((o) => o === "Keystone Retirement Services")
    .length;
}

export const SAM_INVITATION: InvitationPreviewOut = {
  firm_name: "Brightwater Hale LLP",
  organisation_name: "Keystone Retirement Services",
  invitee_name: "Sam Ortiz",
  invitee_email: emailOf("sam-ortiz"),
  access: {
    kind: "delegate",
    item_count: KEYSTONE_DELEGATED,
    scope_label: "Northwind Robotics 401(k) Plan",
  },
  terms_url: "https://www.brightwaterhale.example/portal-terms",
  terms_version: 1,
  expires_at: "2026-09-16T14:22:00Z",
};

const at = (
  state: string,
  persona: string,
  options: Omit<Parameters<typeof portalHandlers>[0], "clock"> = {},
  clock = SIGN_IN_CLOCK,
): Scenario => ({ state, persona, clock, handlers: portalHandlers({ clock, ...options }) });

export const scenarios = defineScenarios({
  a: at("a", "claire-feld"),
  b: at("b", "claire-feld"),
  c: at("c", "tess-moreno"),
  c2: at("c2", "tess-moreno", { mfaEnrolled: false }),
  d: at("d", "sam-ortiz", { invitation: SAM_INVITATION }, INVITE_CLOCK),
  e: at("e", "claire-feld", { linkIssuedAt: LINK_ISSUED_AT }),
  f: at("f", "claire-feld"),
  g: at("g", "claire-feld", { triesLeft: 1 }),
  M: at("M", "claire-feld"),
});

export type Por01Scenario = keyof typeof scenarios;

/** What each artboard has done when it opens: the screen replays it through the routes. */
export const START: Readonly<Record<Por01Scenario, SignInOpening>> = {
  a: { email: emailOf("claire-feld") },
  b: { email: emailOf("claire-feld"), start: true, code: FIXTURE_CODE },
  c: { email: emailOf("tess-moreno"), start: true, code: FIXTURE_CODE, verify: true },
  c2: { email: emailOf("tess-moreno"), start: true, code: FIXTURE_CODE, verify: true },
  d: { email: emailOf("sam-ortiz"), invitationToken: FIXTURE_INVITATION_TOKEN },
  e: { email: emailOf("claire-feld"), start: true, linkToken: FIXTURE_LINK_TOKEN },
  f: { email: emailOf("claire-feld"), start: true, code: MISTYPED_CODE, verify: true },
  g: { email: emailOf("claire-feld"), start: true, code: MISTYPED_CODE, verify: true },
  M: { email: emailOf("claire-feld") },
};
