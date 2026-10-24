// Portal sign-in (P-08 §5.2, L3): branding and the pre-session family over the generated client.
// Start, verify and resend are the generated functions since P-08-T10 serves them (P-08-T11), the
// second step and the invitation since P-08-T17 and T18 (P-08-T19), so
// fixture mode and the live API answer the same calls (fixture-mode swaps the client's fetch).
// Branding and links/renew still name their paths on the generated `client` (P-08-T05 and T21
// move them). Codes, emails and tokens are never logged, stored or put in a URL (P-08 §5.4).

import {
  acceptInvitation,
  portalMfa,
  portalMfaSetup,
  portalMfaSetupVerify,
  portalResend,
  portalStart,
  portalVerify,
  previewInvitation,
} from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import type { PortalBrand } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type {
  AcceptInvitationIn,
  AcceptedInvitationOut,
  InvitationPreviewOut,
  PortalBrandingOut,
  PortalMfaIn,
  PortalMfaSetupOut,
  PortalMfaSetupVerifyOut,
  PortalErrorOut,
  PortalLinkRenewIn,
  PortalLinkRenewOut,
  PortalSignInResendIn,
  PortalSignInStartIn,
  PortalSignInStartOut,
  PortalSignInVerifyIn,
  PortalSignInVerifyOut,
} from "../../app-core/portal-contracts";

const JSON_HEADERS = { "Content-Type": "application/json" } as const;

export async function getBranding(): Promise<PortalBrandingOut> {
  const { data } = await client.get<{ 200: PortalBrandingOut }, { 404: PortalErrorOut }, true>({
    url: "/v1/portal/branding",
    throwOnError: true,
  });
  return data;
}

async function post<Out>(url: string, body: object): Promise<Out> {
  const { data } = await client.post<{ 200: Out; 202: Out }, Record<number, PortalErrorOut>, true>(
    { url, body, headers: JSON_HEADERS, throwOnError: true },
  );
  return data;
}

export const signIn = {
  start: async (body: PortalSignInStartIn): Promise<PortalSignInStartOut> =>
    (await portalStart({ body, throwOnError: true })).data,
  verify: async (body: PortalSignInVerifyIn): Promise<PortalSignInVerifyOut> =>
    (await portalVerify({ body, throwOnError: true })).data,
  resend: async (body: PortalSignInResendIn): Promise<PortalSignInStartOut> =>
    (await portalResend({ body, throwOnError: true })).data,
  renewLink: (body: PortalLinkRenewIn) => post<PortalLinkRenewOut>("/v1/portal/links/renew", body),
  // POR-01 c and c′ (P-08-T19): the second step with a single-use `mfa_token`, or its setup.
  mfa: async (body: PortalMfaIn): Promise<PortalSignInVerifyOut> =>
    (await portalMfa({ body, throwOnError: true })).data,
  mfaSetup: async (mfaToken: string): Promise<PortalMfaSetupOut> =>
    (await portalMfaSetup({ body: { mfa_token: mfaToken }, throwOnError: true })).data,
  mfaSetupVerify: async (mfaToken: string, totp: string): Promise<PortalMfaSetupVerifyOut> =>
    (await portalMfaSetupVerify({ body: { mfa_token: mfaToken, totp }, throwOnError: true })).data,
};

/** POR-01 d (P-08-T18, T19): the invitation's preview before any session (one 404 for every
 * failure), and its acceptance with the invitee's own session (the bearer verify returned). */
export const invitation = {
  preview: async (token: string): Promise<InvitationPreviewOut> =>
    (await previewInvitation({ body: { token }, throwOnError: true })).data,
  accept: async (body: AcceptInvitationIn, accessToken: string): Promise<AcceptedInvitationOut> =>
    (
      await acceptInvitation({
        body,
        headers: { Authorization: `Bearer ${accessToken}` },
        throwOnError: true,
      })
    ).data,
};

/** A pre-session failure as the screen reads it: its code and identifier facts, or `network`. */
export interface SignInFailure {
  code: string;
  triesLeft?: number;
  lockedUntil?: string;
  resendAvailableAt?: string;
}

/** The thrown value of a failed call (the parsed error body, or a fetch error) as a failure. */
export function failureOf(error: unknown): SignInFailure {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const body = error as PortalErrorOut;
    const facts = body.facts ?? {};
    return {
      code: typeof body.detail === "string" ? body.detail : "unknown",
      ...(facts.tries_left === undefined ? {} : { triesLeft: facts.tries_left }),
      ...(facts.locked_until === undefined ? {} : { lockedUntil: facts.locked_until }),
      ...(facts.resend_available_at === undefined
        ? {}
        : { resendAvailableAt: facts.resend_available_at }),
    };
  }
  return { code: "network" };
}

/** `GET /v1/portal/branding`, once per page (it changes only through ADM-10). */
export function useBranding() {
  return useQuery({
    queryKey: ["portal", "branding"],
    queryFn: getBranding,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}

/** The branding as the design system's portal brand. An unknown host's neutral answer has no
 * firm name: the brand's name is then empty and no firm mark, name or address is drawn. */
export function brandOf(b: PortalBrandingOut): PortalBrand {
  return {
    name: b.firm_name ?? "",
    ...(b.portal_name === null ? {} : { portalName: b.portal_name }),
    ...(b.logo_url === null ? {} : { logo: b.logo_url }),
    ...(b.address_line === null ? {} : { addressLine: b.address_line }),
    ...(b.help_url === null ? {} : { helpUrl: b.help_url }),
    ...(b.privacy_url === null ? {} : { privacyUrl: b.privacy_url }),
    ...(b.support_contact_name === null ? {} : { supportContactName: b.support_contact_name }),
    securedFooter: b.secured_footer,
    signInMethods: b.sign_in.methods,
    ...(b.maintenance_banner == null ? {} : { maintenanceBanner: b.maintenance_banner }),
  };
}
