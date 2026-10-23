// Draft types for the portal's pre-session family and branding (P-08-T09; build-screen-from-
// handoff §0). These routes are not served yet (DEC-139: they need an ADR-152 public-route entry,
// P-08 OQ-2), so the OpenAPI document has no schema for them and the generated client no type or
// function. The shapes are copied field for field from the backend's contract models, which the
// P-08-T02 contract tests hold (backend/src/abacus/modules/identity/portal_contract.py,
// backend/src/abacus/modules/portal/contract.py `PortalBrandingOut`). When P-08-T05 and T10 serve
// the routes and `make generate` runs, these drafts are deleted for the generated types and the
// calls in domain/portal/sign-in.ts move to the generated functions (docs/screens/POR-01.md,
// Open gaps). In app-core so the portal domain, the portal entry and the fixtures share them.

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

/** `POST /v1/portal/auth/start`: at most one of the two tokens. */
export interface PortalSignInStartIn {
  email: string;
  link_token?: string | null;
  invitation_token?: string | null;
}

/** Always 202 with this shape, for any email. */
export interface PortalSignInStartOut {
  challenge_id: string;
  code_expires_at: string;
  resend_available_at: string;
}

export interface PortalSignInVerifyIn {
  challenge_id: string;
  code: string;
}

export interface PortalSignInVerifyOut {
  state: "signed_in" | "mfa_required" | "mfa_setup_required";
  access_token?: string | null;
  expires_in?: number | null;
  landing?: PortalLanding | null;
  mfa_token?: string | null;
}

export interface PortalSignInResendIn {
  challenge_id: string;
}

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
