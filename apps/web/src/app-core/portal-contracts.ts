// The portal's pre-session and branding types (P-08-T09; build-screen-from-handoff §0). Start,
// verify and resend re-export the generated types now that P-08-T10 serves them (P-08-T11). The
// rest are still drafts copied field for field from the backend's contract models, which the
// P-08-T02 contract tests hold (backend/src/abacus/modules/identity/portal_contract.py,
// backend/src/abacus/modules/portal/contract.py `PortalBrandingOut`): branding moves to the
// generated type with P-08-T05's follow-up, links/renew and invitation preview when P-08-T21 and
// T18 serve them (docs/screens/POR-01.md, Open gaps). In app-core so the portal domain, the portal
// entry and the fixtures share them.

import type { MePortalOut } from "@abacus/api-client";

export type PortalLanding = MePortalOut["landing"];

/** `GET /v1/portal/branding`: public fields only; the same shape on an unknown host. */
export interface PortalBrandingOut {
  firm_name: string | null;
  portal_name: string | null;
  logo_url: string | null;
  address_line: string | null;
  help_url: string | null;
  privacy_url: string | null;
  support_contact_name: string | null;
  secured_footer: boolean;
  sign_in: { methods: "email_code"[]; mfa_floor: ("owner" | "signer" | "approver")[] };
  maintenance_banner?: string | null;
}

// The pre-session sign-in shapes are generated since P-08-T10 serves them (P-08-T11).
export type {
  PortalSignInResendIn,
  PortalSignInStartIn,
  PortalSignInStartOut,
  PortalSignInVerifyIn,
  PortalSignInVerifyOut,
} from "@abacus/api-client";

export interface PortalLinkRenewIn {
  link_token: string;
}

export interface PortalLinkRenewOut {
  accepted: true;
}

/** What a sign-in page has already done when it opens: an email in the field, a reminder link's
 * token from the fragment, a code typed. A person's own clicks do the same through the same
 * routes; the gallery's artboards open part-way (fixtures/scenarios/POR-01.ts). */
export interface SignInOpening {
  email: string;
  /** Ask for a code (Continue) on open. */
  start?: boolean;
  /** A reminder link's token, moved from the fragment to the page's memory. */
  linkToken?: string;
  /** Digits typed into the code boxes. */
  code?: string;
  /** Submit the typed code on open. */
  verify?: boolean;
}

/** `POST /v1/invitations/preview` (POR-01 d): one 404 for every failure. */
export interface InvitationPreviewOut {
  firm_name: string;
  organisation_name?: string | null;
  invitee_name?: string | null;
  invitee_email: string;
  access: {
    kind: "firm_invite" | "colleague" | "outside_org" | "delegate";
    item_count?: number | null;
    scope_label: string;
  };
  terms_url?: string | null;
  terms_version?: number | null;
  expires_at: string;
}

/** The pre-session family's error body (docs/contracts/portal-identity.md §6). */
export interface PortalErrorOut {
  detail: string;
  facts?: {
    tries_left?: number;
    locked_until?: string;
    resend_available_at?: string;
  };
}
