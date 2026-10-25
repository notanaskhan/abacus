// The portal's fixture routes (P-08-T08): branding, the pre-session sign-in family, the portal
// shell on `/v1/me` and the POR-02 home. They answer the shapes the backend contract fixes (the
// generated types; app-core/portal-contracts.ts for the routes not served yet):
// - `start` answers 202 with the same body for any email (no enumeration); a reminder link that
//   can't be used (older than 14 days here) answers 404 `link_expired`, the one answer the backend
//   gives for every bad link (P-08-T21);
// - `verify` takes the fixture code 481027; a wrong code costs one of three tries (401
//   `code_mismatch {tries_left}`), the third locks sign-in for 15 minutes (423 `sign_in_locked`);
//   an owner (the MFA floor) answers `mfa_required` (or `mfa_setup_required` without a factor);
// - `mfa` (c) takes the fixture authenticator code or the first backup code, once; three wrong
//   ones lock (423 `mfa_locked`); `mfa/setup` answers the key once per token and
//   `mfa/setup/verify` the 8 backup codes once (c′, DF-17);
// - `invitations/preview` answers POR-01 d's invitation, `invitations/accept` accepts it once
//   with the shown terms version and lands a third party on `requests` (404 for anything else);
// - `resend` answers 429 `resend_too_soon` before the countdown ends; `links/renew` 202;
// - `refresh` (P-08-T11) stands for the persona's host cookie: a persona with a portal shell gets
//   a fresh token (a reload of a signed-in area), anyone else 401 `session_expired`; `sign-out`
//   ends it.
// Times are offsets from the scenario's clock; nothing here reads the device clock.

import type {
  MeOut,
  PortalHomeOut,
  PortalPreferencesIn,
  PortalPreferencesOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type FixtureRequest,
  json,
  never,
} from "../../app-core/fixture-mode";
import type {
  AcceptInvitationIn,
  AcceptedInvitationOut,
  InvitationPreviewOut,
  PortalBrandingOut,
  PortalMfaIn,
  PortalSignInStartIn,
  PortalSignInStartOut,
  PortalSignInVerifyIn,
  PortalSignInVerifyOut,
} from "../../app-core/portal-contracts";
import { getSeed, meFor } from "../seed";
import {
  BRIGHTWATER_BRANDING,
  FIXTURE_BACKUP_CODES,
  FIXTURE_CODE,
  FIXTURE_TOTP,
  MFA_FLOOR_PERSONAS,
  PORTAL_SHELLS,
} from "../seed/portal-home";
import { stableId } from "../seed/prng";

const SECOND = 1000;
const MINUTE = 60 * SECOND;
/** A link expires after 14 days (DEC-35). */
const LINK_DAYS = 14;

export interface PortalHandlerOptions {
  /** The scenario's instant: every timestamp is an offset from it. */
  clock: string;
  branding?: PortalBrandingOut;
  /** Tries left before the next wrong code (3 for a fresh challenge; g starts at 1). */
  triesLeft?: number;
  /** When the reminder link in the fragment was issued (e: Aug 20). */
  linkIssuedAt?: string;
  /** POR-02's home for the persona; `null` never answers (f, loading). */
  home?: PortalHomeOut | null;
  /** The person's other full-client scopes' homes, by scope id (a role union switching scope). */
  homes?: Readonly<Record<string, PortalHomeOut>>;
  /** An MFA-floor persona with no factor yet goes to two-step setup (c′, DF-17). */
  mfaEnrolled?: boolean;
  /** POR-01 d's pending invitation, answered by `POST /v1/invitations/preview`. */
  invitation?: InvitationPreviewOut;
}

function at(clock: string, offsetMs: number): string {
  return new Date(Date.parse(clock) + offsetMs).toISOString().replace(/\.000Z$/, "Z");
}

function errorBody(detail: string, facts?: Record<string, string | number>) {
  return facts === undefined ? { detail } : { detail, facts };
}

export function portalHandlers(options: PortalHandlerOptions): Record<string, FixtureHandler> {
  const seed = getSeed();
  const { clock } = options;
  // Tries are kept per challenge: each start is a fresh challenge with the scenario's tries.
  const tries = new Map<string, number>();
  let issued = 0;
  const challenge = (persona: string | undefined): PortalSignInStartOut => {
    issued += 1;
    const out = {
      challenge_id: stableId(`portal:challenge:${persona ?? "anyone"}:${clock}:${String(issued)}`),
      code_expires_at: at(clock, 10 * MINUTE),
      resend_available_at: at(clock, 42 * SECOND),
    };
    tries.set(out.challenge_id, options.triesLeft ?? 3);
    return out;
  };

  const signedIn = (who: string): PortalSignInVerifyOut => ({
    state: "signed_in",
    access_token: stableId(`portal:session:${who}`),
    expires_in: 900,
    landing: PORTAL_SHELLS[who]?.landing ?? "none",
  });

  const start = ({ body, persona }: FixtureRequest) => {
    const given = (body ?? {}) as Partial<PortalSignInStartIn>;
    const linkIssued = options.linkIssuedAt;
    if (
      typeof given.link_token === "string" &&
      linkIssued !== undefined &&
      Date.parse(clock) - Date.parse(linkIssued) > LINK_DAYS * 24 * 60 * MINUTE
    ) {
      return json(errorBody("link_expired"), 404);
    }
    return json(challenge(persona), 202);
  };

  const verify = ({ body, persona }: FixtureRequest) => {
    const given = (body ?? {}) as Partial<PortalSignInVerifyIn>;
    const id = given.challenge_id ?? "";
    let triesLeft = tries.get(id) ?? 0;
    if (triesLeft <= 0) {
      return json(errorBody("sign_in_locked", { locked_until: at(clock, 15 * MINUTE) }), 423);
    }
    if (given.code !== FIXTURE_CODE) {
      triesLeft -= 1;
      tries.set(id, triesLeft);
      return triesLeft <= 0
        ? json(errorBody("sign_in_locked", { locked_until: at(clock, 15 * MINUTE) }), 423)
        : json(errorBody("code_mismatch", { tries_left: triesLeft }), 401);
    }
    const who = persona ?? "claire-feld";
    const out: PortalSignInVerifyOut = MFA_FLOOR_PERSONAS.has(who)
      ? {
          state: options.mfaEnrolled === false ? "mfa_setup_required" : "mfa_required",
          // One token per challenge: the scenario's handlers outlive a single sign-in.
          mfa_token: stableId(`portal:mfa:${who}:${id}`),
        }
      : signedIn(who);
    return json(out);
  };

  // c, c′: second-step tokens are single use, and each has three guesses. (The scenario's
  // handlers serve many sign-ins, so the counts are per token; the BFF counts per person.)
  const spent = new Set<string>();
  const mfaTries = new Map<string, number>();
  const mfa = ({ body, persona }: FixtureRequest) => {
    const given = (body ?? {}) as Partial<PortalMfaIn>;
    const token = given.mfa_token ?? "";
    if (token === "" || spent.has(token)) return json(errorBody("mfa_expired"), 410);
    const right =
      given.totp === FIXTURE_TOTP ||
      given.backup_code?.trim().toUpperCase() === FIXTURE_BACKUP_CODES[0];
    if (!right) {
      const left = (mfaTries.get(token) ?? 3) - 1;
      mfaTries.set(token, left);
      if (left <= 0) {
        spent.add(token);
        return json(errorBody("mfa_locked", { locked_until: at(clock, 15 * MINUTE) }), 423);
      }
      return json(errorBody("mfa_mismatch", { tries_left: left }), 401);
    }
    spent.add(token);
    return json(signedIn(persona ?? "tess-moreno"));
  };
  const setupShown = new Set<string>();
  const accepted = new Set<string>();

  return {
    "GET /v1/portal/branding": () => json(options.branding ?? BRIGHTWATER_BRANDING),
    "POST /v1/portal/auth/mfa": mfa,
    "POST /v1/portal/auth/mfa/setup": ({ body }) => {
      const token = (body as { mfa_token?: string } | undefined)?.mfa_token ?? "";
      if (token === "" || spent.has(token) || setupShown.has(token)) {
        return json(errorBody("mfa_expired"), 410);
      }
      setupShown.add(token);
      // RFC 4648's example base32 text, a fixture value only (never a real factor).
      const shown = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";
      return json({
        otpauth_uri: `otpauth://totp/Brightwater%20Hale:client?secret=${shown}&issuer=Brightwater%20Hale`,
        manual_key: shown,
      });
    },
    "POST /v1/portal/auth/mfa/setup/verify": ({ body, persona }) => {
      const given = (body ?? {}) as { mfa_token?: string; totp?: string };
      const token = given.mfa_token ?? "";
      if (token === "" || spent.has(token) || !setupShown.has(token)) {
        return json(errorBody("mfa_expired"), 410);
      }
      if (given.totp !== FIXTURE_TOTP)
        return json(errorBody("mfa_mismatch", { tries_left: 2 }), 401);
      spent.add(token); // the codes come back once
      return json({
        backup_codes: [...FIXTURE_BACKUP_CODES],
        session: signedIn(persona ?? "tess-moreno"),
      });
    },
    "POST /v1/invitations/accept": ({ body, persona }) => {
      const given = (body ?? {}) as Partial<AcceptInvitationIn>;
      const found = options.invitation;
      const token = given.token ?? "";
      if (
        found === undefined ||
        token === "" ||
        accepted.has(token) ||
        (found.terms_version != null && given.terms_version !== found.terms_version)
      ) {
        return json({ detail: "not found" }, 404);
      }
      accepted.add(token);
      const who = persona ?? "sam-ortiz";
      const out: AcceptedInvitationOut = {
        tenant_id: stableId("firm:brightwater-hale"),
        engagement_id: stableId(`portal:invitation:${who}:engagement`),
        session: {
          state: "signed_in",
          landing:
            found.access.kind === "delegate"
              ? "requests"
              : (PORTAL_SHELLS[who]?.landing ?? "home"),
        },
      };
      return json(out);
    },
    "POST /v1/portal/auth/start": start,
    "POST /v1/portal/auth/verify": verify,
    "POST /v1/portal/auth/resend": ({ body }) => {
      const given = (body ?? {}) as { challenge_id?: string };
      if (given.challenge_id === undefined) return json(errorBody("invalid"), 422);
      // The scenario's clock stands still: the 42-second countdown never ends in a fixture.
      return json(
        errorBody("resend_too_soon", { resend_available_at: at(clock, 42 * SECOND) }),
        429,
      );
    },
    "POST /v1/portal/auth/refresh": ({ persona }) =>
      persona !== undefined && PORTAL_SHELLS[persona] !== undefined
        ? json(signedIn(persona))
        : json(errorBody("session_expired"), 401),
    "POST /v1/portal/auth/sign-out": () => json({ ended: true }),
    "POST /v1/portal/links/renew": () => json({ accepted: true }, 202),
    "POST /v1/invitations/preview": () =>
      options.invitation === undefined
        ? json({ detail: "not found" }, 404)
        : json(options.invitation),
    "GET /v1/me": ({ persona }) => {
      const who = persona ?? "claire-feld";
      const me = meFor(seed, who);
      if (me === undefined) return json({ detail: "unknown_persona" }, 404);
      const body: MeOut = { ...me, portal: PORTAL_SHELLS[who] ?? null };
      return json(body);
    },
    // `?scope_id=` picks the scope (P-08-T23, the role union's switcher): the scenario's home
    // answers its own scope, any other scope the person holds a full-client grant on answers from
    // `homes`, and anything else 404 (INV-4: a scope without a grant is never found).
    "GET /v1/portal/home": ({ query }) => {
      if (options.home === null) return never();
      const scope = query.get("scope_id");
      const home =
        scope === null || scope === options.home?.scope.id ? options.home : options.homes?.[scope];
      return home === undefined ? json({ detail: "not found" }, 404) : json(home);
    },
    // P-08-T15: the welcome card's dismissal, per user and scope (P-08 Story 6.2). A scope the
    // person holds no full-client grant on answers 404 (INV-4); a stale version 409.
    "PUT /v1/portal/preferences": ({ body }) => {
      const given = body as PortalPreferencesIn;
      if (options.home == null || given.scope_id !== options.home.scope.id) {
        return json({ detail: "not found" }, 404);
      }
      if (given.version !== 0) return json({ detail: "stale_version" }, 409);
      const out: PortalPreferencesOut = {
        scope_id: given.scope_id,
        version: 1,
        welcome_dismissed: given.welcome_dismissed,
        welcome_dismissed_at: given.welcome_dismissed ? at(clock, 0) : null,
      };
      return json(out);
    },
  };
}
