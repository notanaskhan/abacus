"""C5 v1.1, the portal half: client identity (P-08-T01 stub; ADR P-36, ADR P-54, ADR-163).
Contract: `docs/contracts/portal-identity.md`; spec: SPEC-320.

The firm-side contact unlock and MFA reset (their models here) are served by organisations since
P-08-T21 (`organisations/contacts_contract.py`, which owns the contact), behind
`portal.sign_in_v2`; both are human-only, the agent and system principals denied at the matrix
(INV-1). `/v1/me` gains the additive `portal` and `mfa` fields (`MePortalOut`, `MeMfaOut`).

Not served by this stub (DEC-139): the pre-session family (`/v1/portal/auth/*`,
`/v1/portal/links/renew`, `/v1/invitations/preview`) answers before any session exists, so it
cannot sit behind `AbacusRouter` and needs its own entry on ADR-152's public-route list, which is
protected and changes only with a decision. P-08-T10, T18 and T21 serve these routes once that
decision lands (P-08 OQ-2). Their shapes are fixed here so they are reviewed and tested with the
rest of the contract: start, renew and preview answer one shape for every input (no enumeration).
P-08-T21 serves `/v1/portal/links/renew` (communications) under the `PRE_SESSION` marker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import InvitationStatus
from abacus.kernel.classification import classified
from abacus.modules.identity.client_access import ScopeKind

PortalShell = Literal["full", "k1", "limited", "none"]
# The portal nav (DEC-129, DEC-45): Approvals only for entity scopes; no bell (DEC-58(d)).
PortalNavItem = Literal[
    "home", "documents", "questions", "approvals", "sign", "messages", "deliverables"
]
# The role-routed landing after sign-in (P-08 Story 2.3).
PortalLanding = Literal[
    "home", "requests", "k1s", "governance", "intake", "component_room", "none"
]


# --- /v1/me, additive (P-08-T07 fills `portal`, T17 fills `mfa`) -------------------------------


class MePortalScopeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[ScopeKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]  # "Feld Household"
    role_label: Annotated[str, classified("internal")]  # "Taxpayer"


class MePortalOut(BaseModel):
    """The portal shell for a client user in the active firm (role union, DEC-129)."""

    model_config = ConfigDict(frozen=True)

    shell: Annotated[PortalShell, classified("internal")]
    scopes: Annotated[list[MePortalScopeOut], classified("internal")]
    nav: Annotated[list[PortalNavItem], classified("internal")]
    landing: Annotated[PortalLanding, classified("internal")]


class MeMfaOut(BaseModel):
    """The person's second step: whether the DEC-34 floor requires it and whether a factor and a
    trusted device exist. Never the factor, a secret or a backup code."""

    model_config = ConfigDict(frozen=True)

    enrolled: Annotated[bool, classified("internal")]
    required: Annotated[bool, classified("internal")]
    trusted_until: Annotated[datetime | None, classified("internal")] = None


# --- Firm-side recovery (Stories 7.1, 7.2) ------------------------------------------------------


class ContactPortalStatusOut(BaseModel):
    """The contact's portal access after an unlock (CLI-04 badge; `invitation` status words)."""

    model_config = ConfigDict(frozen=True)

    client_id: Annotated[UUID, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]
    portal_status: Annotated[InvitationStatus, classified("internal")]
    locked_until: Annotated[datetime | None, classified("internal")] = None


class ContactMfaResetOut(BaseModel):
    """After a reset the next sign-in goes to two-step setup (POR-01, the setup state)."""

    model_config = ConfigDict(frozen=True)

    client_id: Annotated[UUID, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]
    mfa_enrolled: Annotated[bool, classified("internal")]
    trusted_devices_revoked: Annotated[int, Field(ge=0), classified("internal")]
    reset_at: Annotated[datetime, classified("internal")]


# --- Not served by this stub: the pre-session family (DEC-139; P-08-T10, T18, T21) ---------------


class PortalSignInStartIn(BaseModel):
    """`POST /v1/portal/auth/start`. At most one of the two tokens."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    email: Annotated[str, Field(min_length=3, max_length=320), classified("confidential")]
    link_token: Annotated[str | None, Field(max_length=128), classified("restricted")] = None
    invitation_token: Annotated[str | None, Field(max_length=128), classified("restricted")] = None


class PortalSignInStartOut(BaseModel):
    """Always 202 with this shape, for any email (unknown, staff, no grant, another firm's,
    locked): identical status, body and padded timing. No email is sent unless eligible."""

    model_config = ConfigDict(frozen=True)

    challenge_id: Annotated[UUID, classified("internal")]
    code_expires_at: Annotated[datetime, classified("internal")]
    resend_available_at: Annotated[datetime, classified("internal")]


class PortalSignInVerifyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    challenge_id: Annotated[UUID, classified("internal")]
    code: Annotated[str, Field(pattern=r"^[0-9]{6}$"), classified("restricted")]


class PortalSignInVerifyOut(BaseModel):
    """200. `signed_in` carries the access token and the landing; the MFA states carry a
    5-minute single-use `mfa_token`. Errors: 401 `code_mismatch {tries_left}`, 423
    `sign_in_locked {locked_until}`, 410 `code_expired`, 503 `sign_in_paused`."""

    model_config = ConfigDict(frozen=True)

    state: Annotated[
        Literal["signed_in", "mfa_required", "mfa_setup_required"], classified("internal")
    ]
    access_token: Annotated[str | None, classified("restricted")] = None
    expires_in: Annotated[int | None, classified("internal")] = None
    landing: Annotated[PortalLanding | None, classified("internal")] = None
    mfa_token: Annotated[str | None, classified("restricted")] = None


class PortalSignInResendIn(BaseModel):
    """New code, old code void, tries not reset; 429 `resend_too_soon {resend_available_at}`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    challenge_id: Annotated[UUID, classified("internal")]


class PortalMfaIn(BaseModel):
    """`POST /v1/portal/auth/mfa`: exactly one of `totp` and `backup_code`. Errors: 401
    `mfa_mismatch {tries_left}`, 423 `mfa_locked {locked_until}`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mfa_token: Annotated[str, Field(max_length=512), classified("restricted")]
    totp: Annotated[str | None, Field(pattern=r"^[0-9]{6}$"), classified("restricted")] = None
    backup_code: Annotated[str | None, Field(max_length=32), classified("restricted")] = None
    trust_device: Annotated[bool, classified("internal")] = False


class PortalMfaSetupIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mfa_token: Annotated[str, Field(max_length=512), classified("restricted")]


class PortalMfaSetupOut(BaseModel):
    """The QR code's URI and the manual key (DF-17, POR-01 setup state)."""

    model_config = ConfigDict(frozen=True)

    otpauth_uri: Annotated[str, classified("restricted")]
    manual_key: Annotated[str, classified("restricted")]


class PortalMfaSetupVerifyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mfa_token: Annotated[str, Field(max_length=512), classified("restricted")]
    totp: Annotated[str, Field(pattern=r"^[0-9]{6}$"), classified("restricted")]


class PortalMfaSetupVerifyOut(BaseModel):
    """Eight backup codes, shown once; then the session as `PortalSignInVerifyOut` signed in."""

    model_config = ConfigDict(frozen=True)

    backup_codes: Annotated[list[str], classified("restricted")]
    session: Annotated[PortalSignInVerifyOut, classified("internal")]


class PortalLinkRenewIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    link_token: Annotated[str, Field(max_length=128), classified("restricted")]


class PortalLinkRenewOut(BaseModel):
    """Always 202 with this shape, for any token; a new link goes only to the address the old one
    was sent to. The toast names that address from the SPA's own state, never from here."""

    model_config = ConfigDict(frozen=True)

    accepted: Annotated[Literal[True], classified("internal")] = True


class InvitationPreviewIn(BaseModel):
    """POST keeps the token out of URLs and logs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: Annotated[str, Field(max_length=128), classified("restricted")]


class InvitationAccessOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[
        Literal["firm_invite", "colleague", "outside_org", "delegate"], classified("internal")
    ]
    item_count: Annotated[int | None, Field(ge=0), classified("internal")] = None
    scope_label: Annotated[str, classified("confidential")]


class InvitationPreviewOut(BaseModel):
    """POR-01 d. Every failure (expired, used, revoked, malformed, a staff member's) answers the
    same 404."""

    model_config = ConfigDict(frozen=True)

    firm_name: Annotated[str, classified("public")]
    organisation_name: Annotated[str | None, classified("confidential")] = None
    invitee_name: Annotated[str | None, classified("confidential")] = None
    invitee_email: Annotated[str, classified("confidential")]  # read-only on the card
    access: Annotated[InvitationAccessOut, classified("internal")]
    terms_url: Annotated[str | None, classified("public")] = None
    terms_version: Annotated[int | None, classified("internal")] = None
    expires_at: Annotated[datetime, classified("internal")]


class InvitationAcceptV2In(BaseModel):
    """`POST /v1/invitations/accept` v2 (P-08-T18): the existing body plus the accepted terms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: Annotated[str, Field(max_length=128), classified("restricted")]
    terms_version: Annotated[int | None, Field(ge=1), classified("internal")] = None
