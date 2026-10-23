// The portal's fixture routes (P-08-T08): branding, the pre-session sign-in family, the portal
// shell on `/v1/me` and the POR-02 home. The pre-session routes are not served yet (DEC-139), so
// these answer the shapes the backend contract models fix (app-core/portal-contracts.ts):
// - `start` answers 202 with the same body for any email (no enumeration); a reminder link older
//   than 14 days answers 410 `link_expired` (the contract has no such answer yet: an open gap in
//   docs/screens/POR-01.md);
// - `verify` takes the fixture code 481027; a wrong code costs one of three tries (401
//   `code_mismatch {tries_left}`), the third locks sign-in for 15 minutes (423 `sign_in_locked`);
//   an owner (the MFA floor) answers `mfa_required`;
// - `resend` answers 429 `resend_too_soon` before the countdown ends; `links/renew` 202.
// Times are offsets from the scenario's clock; nothing here reads the device clock.

import type { MeOut, PortalHomeOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type FixtureRequest,
  json,
  never,
} from "../../app-core/fixture-mode";
import type {
  InvitationPreviewOut,
  PortalBrandingOut,
  PortalSignInStartIn,
  PortalSignInStartOut,
  PortalSignInVerifyIn,
  PortalSignInVerifyOut,
} from "../../app-core/portal-contracts";
import { getSeed, meFor } from "../seed";
import {
  BRIGHTWATER_BRANDING,
  FIXTURE_CODE,
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

  const start = ({ body, persona }: FixtureRequest) => {
    const given = (body ?? {}) as Partial<PortalSignInStartIn>;
    const linkIssued = options.linkIssuedAt;
    if (
      typeof given.link_token === "string" &&
      linkIssued !== undefined &&
      Date.parse(clock) - Date.parse(linkIssued) > LINK_DAYS * 24 * 60 * MINUTE
    ) {
      return json(errorBody("link_expired"), 410);
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
    const shell = PORTAL_SHELLS[who];
    const out: PortalSignInVerifyOut = MFA_FLOOR_PERSONAS.has(who)
      ? {
          state: options.mfaEnrolled === false ? "mfa_setup_required" : "mfa_required",
          mfa_token: stableId(`portal:mfa:${who}`),
        }
      : {
          state: "signed_in",
          access_token: stableId(`portal:session:${who}`),
          expires_in: 900,
          landing: shell?.landing ?? "none",
        };
    return json(out);
  };

  return {
    "GET /v1/portal/branding": () => json(options.branding ?? BRIGHTWATER_BRANDING),
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
    "GET /v1/portal/home": () => {
      if (options.home === null) return never();
      return options.home === undefined ? json({ detail: "not found" }, 404) : json(options.home);
    },
  };
}
