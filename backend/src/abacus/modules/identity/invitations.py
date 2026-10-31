"""Client invitations and client members (SPEC-015; v2: SPEC-320 AC-12, AC-13). PROTECTED.

An invitation stores no token. Communications asks for one when it sends the email
(`issue_invitation_token`), and only its SHA-256 is kept, in `invitation_tokens` (TASK-030 D1).
Acceptance needs only a verified identity with a verified email (D2). Users and client
memberships are created only through reviewed definer functions (D3). Every acceptance failure
gives the same answer.

Invitations v2 (P-08-T18; DEC-35, DEC-275): an invitation lasts 14 days and may carry its `kind`,
the contact it is for, a grant template (one role on one scope kind over the listed scopes of its
engagement) and the terms the invitee accepts. `preview_invitation` answers POR-01 d before any
session, the same 404 for every failure (unknown, malformed, used, revoked, expired, another
firm's host, a staff member's address), padded to one duration and with misses counted per
address. The invitee signs in with the token (`portal_session.start_sign_in`) and accepts with
that portal session (`accept_portal_invitation`): the membership, the template's grants, the
terms and the contact's activation commit in one unit of work, attributed to the inviter.

Contact invitations (P-07-T25; DEC-300): an invitation may instead carry `grant_ids`, pending
`client_access_grants` rows made for its contact when the firm invited them (`contact_access`).
Acceptance activates exactly those grants for the person who accepted, after re-checking that
each still lies within the engagement's client and that the inviter may still give it now
(`client_access.grant` itself on its engagement, or on the client for a client-wide one, with
only the fresh-MFA recency waived because the inviter isn't present: DEC-277, DEC-303).
Everything else (single use, the MFA floor in the transaction, ending the other sessions) is the
same path; the hosted sign-in's accept refuses a contact invitation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, NoReturn, cast, get_args
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, text

from abacus.kernel.config import settings
from abacus.kernel.controls import ensure_writable
from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Forbidden, Resource, engagement_client
from abacus.modules.identity.client_access import (
    GRANT_ROLES,
    SCOPE_KINDS,
    GrantRole,
    ScopeKind,
    active_grants,
    grant_in_unit_of_work,
    scope_facts,
)
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import (
    AccessChanged,
    ClientAccessGranted,
    ClientInvitationIssued,
)
from abacus.modules.identity.mfa_floor import mfa_required
from abacus.modules.identity.portal_mfa import record_revoked
from abacus.modules.identity.portal_session import (
    MFA_TOKEN_SECONDS,
    PortalInvitee,
    factor_enrolled,
    landing_of,
    sha256_hex,
)
from abacus.modules.identity.repository import (
    ContactGrantRow,
    accept_invitation_row,
    activate_grant,
    add_client_membership,
    client_contacts,
    display_names,
    engagement_role,
    extend_invitation,
    find_token,
    firm_name_of,
    get_invitation,
    grant_engagement_role,
    grants_by_id,
    held_grant,
    insert_grant_event,
    insert_grant_event_of,
    insert_invitation,
    invitations_today,
    membership_kind,
    pending_invitation_for,
    provision_client_user,
    remove_client_member,
    set_grant_status,
    set_invitation_status,
    set_token_hash,
)
from abacus.modules.identity.service import member_could
from abacus.modules.identity.slots import (
    activate_contact,
    engagement_resource,
    invitation_parties,
)
from abacus.modules.identity.tokens import VerifiedIdentity

ClientRole = Literal["client_admin", "client_contributor"]
InvitationKind = Literal["firm_invite", "colleague", "outside_org", "delegate"]
# SPEC-320 supersedes SPEC-015 Q3 (DEC-35): 14 days, single use; pending rows keep their expiry.
INVITATION_DAYS: Final = 14
MAX_TEMPLATE_SCOPES: Final = 200
# Preview answers take at least this long, found or not, so a live token can't be timed.
PREVIEW_FLOOR_SECONDS: Final = 0.5
_KINDS: Final = frozenset(get_args(InvitationKind))
DAILY_LIMIT: Final = 50
_PLATFORM = UUID(int=0)
_log = get_logger(__name__)


class InvitationLimit(DomainConflict):
    """50 invitations per engagement per day (SPEC-015 Q4)."""

    code = "invitation_limit"


class InvitationInvalid(DomainInvalid):
    code = "invitation_invalid"


class InvitationNotFound(NotFound):
    """The same answer for every failed acceptance (SPEC-015 AC-5)."""


@dataclass(frozen=True)
class IssuedInvitation:
    token: str
    email: str
    expires_at: datetime
    engagement_id: UUID
    invited_by: UUID
    # P-07-T25: a contact invitation (pending grants) is sent from the firm's database template,
    # naming its contact.
    contact_invitation: bool = False
    invitee_name: str | None = None


@dataclass(frozen=True)
class ContactView:
    kind: str  # member | invitation
    id: UUID
    role: str
    email: str | None
    expires_at: datetime | None
    display_name: str | None = None  # members only (SPEC-020: the assignee picker)


@dataclass(frozen=True)
class GrantTemplate:
    """What acceptance grants (P-08 §4.2): one role on one scope kind, over the listed scopes of
    the invitation's engagement (its request items for a third party, for instance)."""

    role: GrantRole
    scope_kind: ScopeKind
    scope_ids: tuple[UUID, ...]

    def as_json(self) -> str:
        return json.dumps(
            {
                "role": self.role,
                "scope_kind": self.scope_kind,
                "scope_ids": [str(i) for i in self.scope_ids],
            }
        )


@dataclass(frozen=True)
class InvitationTerms:
    version: int
    url: str | None = None


@dataclass(frozen=True)
class PortalStep:
    """Where the invitee goes after accepting: signed in (the session continues), or the second
    step the new grants' MFA floor asks for, with its single-use token (Restricted)."""

    state: Literal["signed_in", "mfa_required", "mfa_setup_required"]
    landing: str | None = None
    mfa_token: str | None = None


@dataclass(frozen=True)
class AcceptedInvitation:
    tenant_id: UUID
    engagement_id: UUID
    step: PortalStep | None = None


@dataclass(frozen=True)
class InvitationAccess:
    kind: str
    item_count: int | None
    scope_label: str


@dataclass(frozen=True)
class InvitationPreview:
    """POR-01 d (SPEC-320 AC-12)."""

    firm_name: str
    organisation_name: str | None
    invitee_name: str | None
    invitee_email: str
    access: InvitationAccess
    terms_url: str | None
    terms_version: int | None
    expires_at: datetime


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _client_admin_limited(ctx: AuthContext, engagement_id: UUID, role: str) -> None:
    """A client admin acts on contributors only (SPEC-015 Q2)."""
    if await engagement_role(ctx.tenant, ctx.user_id, engagement_id) == "client_admin" and (
        role != "client_contributor"
    ):
        raise Forbidden("client_contact.invite", "role")


def _template_valid(template: GrantTemplate) -> bool:
    ids = template.scope_ids
    return (
        template.role in GRANT_ROLES
        and template.scope_kind in SCOPE_KINDS
        and 1 <= len(ids) <= MAX_TEMPLATE_SCOPES
        and len(set(ids)) == len(ids)
    )


async def _scopes_within(
    tenant: TenantContext, engagement_id: UUID, template: GrantTemplate
) -> bool:
    """Every scope of the template lies within the invitation's engagement: the engagement
    itself, its work items or request items, or (client-wide) its client or client entity."""
    client_id = await engagement_client(tenant, engagement_id)
    if client_id is None:
        return False
    for scope_id in template.scope_ids:
        facts = await scope_facts(tenant, template.scope_kind, scope_id)
        if facts is None or facts.client_id != client_id:
            return False
        if template.scope_kind in ("client", "client_entity"):
            continue
        if facts.engagement_id != engagement_id:
            return False
    return True


async def create_invitation(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    email: str,
    role: ClientRole,
    *,
    kind: InvitationKind = "firm_invite",
    contact_id: UUID | None = None,
    template: GrantTemplate | None = None,
    terms: InvitationTerms | None = None,
    grant_ids: Sequence[UUID] | None = None,
) -> UUID:
    """Inside the caller's unit of work, after `authorise(client_contact.invite)` (AC-1 to AC-3).
    A pending invitation for the same email and engagement is replaced. v2 (P-08-T18): the kind,
    the contact, a grant template whose scopes lie within the engagement, and the terms; the
    grants are written only when the invitee accepts, attributed to the inviter. P-07-T25: or
    the pending grants (`grant_ids`) `contact_access.invite_contact` made for the contact, which
    acceptance activates."""
    email = email.strip()
    if grant_ids is not None and (
        template is not None or contact_id is None or not 1 <= len(grant_ids) <= 200
    ):
        raise InvitationInvalid("grant_ids")
    if not 3 <= len(email) <= 320 or "@" not in email:
        raise InvitationInvalid("email")
    if kind not in _KINDS:
        raise InvitationInvalid("kind")
    if terms is not None and (
        terms.version < 1 or (terms.url is not None and not terms.url.startswith("https://"))
    ):
        raise InvitationInvalid("terms")
    if template is not None and not (
        _template_valid(template) and await _scopes_within(ctx.tenant, engagement_id, template)
    ):
        raise InvitationInvalid("grant_template")
    if contact_id is not None:
        # The contact must be one of the engagement's client's (DEC-277).
        parties = await invitation_parties(ctx.tenant, engagement_id, contact_id)
        if parties is None or parties.invitee_name is None:
            raise InvitationInvalid("contact_id")
    await _client_admin_limited(ctx, engagement_id, role)
    if template is not None and await engagement_role(ctx.tenant, ctx.user_id, engagement_id) in (
        "client_admin",
        "client_contributor",
    ):
        raise Forbidden("client_contact.invite", "role")  # a template is a firm person's
    if await invitations_today(tx.session, engagement_id) >= DAILY_LIMIT:
        raise InvitationLimit(str(engagement_id))
    replaced = await pending_invitation_for(tx.session, engagement_id, email)
    if replaced is not None:
        await set_invitation_status(tx.session, replaced, "revoked")
        await set_token_hash(tx.session, replaced, None)
        tx.record("client_invitation.revoked", target=Target("client_invitation", replaced))
        await _close_contact_grants(tx, replaced)
    invitation_id = uuid4()
    await insert_invitation(
        tx.session,
        {
            "id": invitation_id,
            "tenant_id": ctx.tenant_id,
            "engagement_id": engagement_id,
            "email": email,
            "role": role,
            "invited_by": ctx.user_id,
            "days": INVITATION_DAYS,
            "kind": kind,
            "contact_id": contact_id,
            "grant_template": template.as_json() if template is not None else None,
            "terms_version": terms.version if terms is not None else None,
            "terms_url": terms.url if terms is not None else None,
            "grant_ids": [str(g) for g in grant_ids] if grant_ids is not None else None,
        },
    )
    tx.record(
        "client_invitation.created",
        target=Target("client_invitation", invitation_id),
        after=Ref(engagement_id=engagement_id, email=_digest(email.casefold())),
    )
    tx.emit(ClientInvitationIssued(invitation_id=invitation_id))
    return invitation_id


async def create_release_invitation(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    email: str,
    contact_id: UUID,
    grant_ids: Sequence[UUID],
    invited_by: UUID,
) -> UUID:
    """T-02-T21: a K-1 release's contact invitation carrying the pending grants it made, in the
    delivery's unit of work and attributed to the person who released. Their decision was
    authorised when they released (fresh second factor, the approval grant the workflow consumed),
    so nothing is re-asked here; acceptance re-checks the inviter as for every contact invitation
    (DEC-277). A pending invitation for the same address and engagement is replaced."""
    email = email.strip()
    if not 3 <= len(email) <= 320 or "@" not in email:
        raise InvitationInvalid("email")
    if not 1 <= len(grant_ids) <= 200:
        raise InvitationInvalid("grant_ids")
    replaced = await pending_invitation_for(tx.session, engagement_id, email)
    if replaced is not None:
        await set_invitation_status(tx.session, replaced, "revoked")
        await set_token_hash(tx.session, replaced, None)
        tx.record("client_invitation.revoked", target=Target("client_invitation", replaced))
        await _close_contact_grants(tx, replaced)
    invitation_id = uuid4()
    await insert_invitation(
        tx.session,
        {
            "id": invitation_id,
            "tenant_id": tenant_id,
            "engagement_id": engagement_id,
            "email": email,
            "role": "client_contributor",
            "invited_by": invited_by,
            "days": INVITATION_DAYS,
            "kind": "firm_invite",
            "contact_id": contact_id,
            "grant_template": None,
            "terms_version": None,
            "terms_url": None,
            "grant_ids": [str(g) for g in grant_ids],
        },
    )
    tx.record(
        "client_invitation.created",
        target=Target("client_invitation", invitation_id),
        after=Ref(engagement_id=engagement_id, email=_digest(email.casefold())),
    )
    tx.emit(ClientInvitationIssued(invitation_id=invitation_id))
    return invitation_id


async def revoke_invitations_by(
    tx: UnitOfWork, user_id: UUID, engagement_id: UUID | None = None
) -> list[UUID]:
    """In the caller's unit of work (offboarding, a firm role change, leaving an engagement):
    the person's pending client invitations, on `engagement_id` or all, revoked with their
    tokens, each audited (DEC-277). Acceptance re-checks the inviter as well."""
    revoked = [
        cast(UUID, r[0])
        for r in await tx.session.execute(
            text("SELECT client_invitations_revoke_by(:user, :engagement)"),
            {"user": user_id, "engagement": engagement_id},
        )
    ]
    for invitation_id in revoked:
        tx.record("client_invitation.revoked", target=Target("client_invitation", invitation_id))
        await _close_contact_grants(tx, invitation_id)
    return revoked


async def _close_contact_grants(tx: UnitOfWork, invitation_id: UUID) -> None:
    """A revoked contact invitation's pending grants close with it (P-07-T25): nothing waits for
    a link that no longer works. CLI-04 invites the contact again."""
    row = await get_invitation(tx.session, invitation_id)
    raw = None if row is None else cast(list[UUID] | None, row["grant_ids"])
    for grant in await grants_by_id(tx.session, [UUID(str(g)) for g in raw or []], lock=True):
        if grant.status == "pending" and await set_grant_status(tx.session, grant.id, "revoked"):
            await insert_grant_event_of(tx.session, grant.id, "revoked", None)


async def revoke_invitation(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, invitation_id: UUID
) -> None:
    row = await get_invitation(tx.session, invitation_id, lock=True)
    if row is None or row["engagement_id"] != engagement_id or row["status"] != "pending":
        raise NotFound("client_invitation")
    await _client_admin_limited(ctx, engagement_id, str(row["role"]))
    await set_invitation_status(tx.session, invitation_id, "revoked")
    await set_token_hash(tx.session, invitation_id, None)
    tx.record("client_invitation.revoked", target=Target("client_invitation", invitation_id))
    await _close_contact_grants(tx, invitation_id)


async def resend_invitation(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, invitation_id: UUID
) -> None:
    """AC-10: the old link stops working now, a new token comes at delivery, and a fresh 14
    days (Q-03-T007: the old hash used to live until the new email went out)."""
    row = await get_invitation(tx.session, invitation_id, lock=True)
    if row is None or row["engagement_id"] != engagement_id or row["status"] != "pending":
        raise NotFound("client_invitation")
    await _client_admin_limited(ctx, engagement_id, str(row["role"]))
    await extend_invitation(tx.session, invitation_id, INVITATION_DAYS)
    await set_token_hash(tx.session, invitation_id, None)
    tx.record("client_invitation.resent", target=Target("client_invitation", invitation_id))
    tx.emit(ClientInvitationIssued(invitation_id=invitation_id))


async def remove_client(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, user_id: UUID
) -> None:
    """AC-8: their next request on the engagement is refused."""
    target_role = await engagement_role(ctx.tenant, user_id, engagement_id)
    if target_role not in ("client_admin", "client_contributor"):
        raise NotFound("client_contact")
    await _client_admin_limited(ctx, engagement_id, str(target_role))
    if not await remove_client_member(tx.session, engagement_id, user_id):
        raise NotFound("client_contact")
    tx.emit(AccessChanged(user_id=user_id))  # F-03-T26: the grant is revoked
    tx.record(
        "client_member.removed",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=user_id),
    )


async def contacts(ctx: AuthContext, engagement_id: UUID) -> list[ContactView]:
    """After `authorise(client_contact.read)` (AC-9)."""
    async with tenant_session(ctx.tenant) as session:
        rows = await client_contacts(session, engagement_id)
    names = await display_names([r["id"] for r in rows if r["kind"] == "member"])
    return [
        ContactView(
            r["kind"],
            r["id"],
            r["role"],
            r["email"],
            r["expires_at"],
            names.get(r["id"]) if r["kind"] == "member" else None,
        )
        for r in rows
    ]


async def issue_invitation_token(tenant_id: UUID, invitation_id: UUID) -> IssuedInvitation | None:
    """For communications, at delivery: a fresh token whose hash replaces any earlier one. None
    when the invitation is no longer pending (revoked, accepted or expired)."""
    token = secrets.token_urlsafe(32)
    ctx = TenantContext(tenant_id, "system", f"invitation:{invitation_id}")
    try:
        async with uow(ctx) as tx:
            row = await get_invitation(tx.session, invitation_id, lock=True)
            if row is None or not row["live"]:
                return None
            await set_token_hash(tx.session, invitation_id, _digest(token))
            tx.record(
                "client_invitation.token_issued",
                target=Target("client_invitation", invitation_id),
            )
    except MissingAuditEvent:
        return None
    contact_invitation = row["grant_ids"] is not None
    parties = (
        await invitation_parties(ctx, row["engagement_id"], row["contact_id"])
        if contact_invitation
        else None
    )
    return IssuedInvitation(
        token,
        str(row["email"]),
        row["expires_at"],
        row["engagement_id"],
        row["invited_by"],
        contact_invitation,
        parties.invitee_name if parties is not None else None,
    )


def _template_of(row: RowMapping) -> GrantTemplate | None:
    raw = row["grant_template"]
    if raw is None:
        return None
    data = cast(dict[str, object], json.loads(raw) if isinstance(raw, str) else raw)
    ids = cast(list[str], data["scope_ids"])
    return GrantTemplate(
        cast(GrantRole, data["role"]),
        cast(ScopeKind, data["scope_kind"]),
        tuple(UUID(i) for i in ids),
    )


async def _pad(began: float) -> None:
    left = PREVIEW_FLOOR_SECONDS - (time.monotonic() - began)
    if left > 0:
        await asyncio.sleep(left)


VIEWER_ADDRESS_HEADER: Final = "cloudfront-viewer-address"


def trust_viewer_address() -> bool:
    """Whether this deployment's edge sets `CloudFront-Viewer-Address` (and overwrites any a
    viewer sends): only then is it believed (`trust_cloudfront_viewer_address`)."""
    return settings().trust_cloudfront_viewer_address


def preview_bucket(viewer_address: str | None, peer: str | None, token: str) -> str:
    """Whose misses a preview counts against (DEC-277). Behind CloudFront every viewer reaches
    the API from an edge address, so the bucket is the viewer address CloudFront forwards, when
    the deployment trusts it; otherwise the peer and the first four hex of the token's digest, so
    other tokens' misses from a shared edge never hold a valid token. Kept only as a digest."""
    if viewer_address and trust_viewer_address():
        address = viewer_address.strip()
        address = address.rsplit(":", 1)[0] if address.count(":") == 1 else address
        return f"viewer#{address.strip('[]')[:64]}"
    return f"peer#{(peer or 'unknown')[:64]}#{_digest(token)[:4]}"


async def preview_invitation(host: str | None, token: str, address: str) -> InvitationPreview:
    """POR-01 d, before any session (SPEC-320 AC-12). `InvitationNotFound` for every failure,
    after the same minimum time; each miss counts against the digest of `address` (a
    `preview_bucket`), and ten in an hour answer that bucket's tokens not found for 15
    minutes."""
    began = time.monotonic()
    try:
        return await _preview(host, token, address)
    finally:
        await _pad(began)


async def _preview(host: str | None, token: str, address: str) -> InvitationPreview:
    pinned = (host or "").split(":", 1)[0].strip().lower()[:253]
    async with platform_transaction("invitations:preview") as conn:
        row = (
            (
                await conn.execute(
                    text("SELECT * FROM portal_invitation_preview(:host, :token, :identity)"),
                    {
                        "host": pinned,
                        "token": _digest(token),
                        "identity": _digest(f"preview#{address}"),
                    },
                )
            )
            .mappings()
            .first()
        )
    if row is None or not 20 <= len(token) <= 128:
        raise InvitationNotFound("invitation")
    tenant_id = cast(UUID, row["tenant_id"])
    tenant = TenantContext(tenant_id, "system", f"invitation:{row['invitation_id']}")
    parties = await invitation_parties(
        tenant, cast(UUID, row["engagement_id"]), cast(UUID | None, row["contact_id"])
    )
    if parties is None:
        raise InvitationNotFound("invitation")
    firm = await firm_name_of(tenant_id)
    if firm is None:
        raise InvitationNotFound("invitation")
    template = _template_of(row)
    count = (
        len(template.scope_ids)
        if template is not None and template.scope_kind in ("request_item", "work_item")
        else await _contact_item_count(tenant, cast(UUID, row["invitation_id"]))
    )
    return InvitationPreview(
        firm_name=firm,
        organisation_name=parties.organisation_name,
        invitee_name=parties.invitee_name,
        invitee_email=str(row["email"]),
        access=InvitationAccess(str(row["kind"]), count, parties.scope_label),
        terms_url=cast(str | None, row["terms_url"]),
        terms_version=cast(int | None, row["terms_version"]),
        expires_at=cast(datetime, row["expires_at"]),
    )


async def _find(token: str, attempt: str) -> RowMapping | None:
    """The token's firm and invitation, counting a miss against `attempt` (0025)."""
    async with uow(TenantContext(_PLATFORM, "system", "invitations:accept")) as tx:
        found = await find_token(tx.session, _digest(token), attempt)
        tx.record(
            "client_invitation.accept_attempted",
            target=Target("client_invitation", found["invitation_id"] if found else _PLATFORM),
            after=Ref(identity=attempt),
        )
    return found


async def _inviter(tenant_id: UUID, invitation_id: UUID) -> UUID | None:
    async with tenant_session(TenantContext(tenant_id, "system", "invitations:accept")) as s:
        row = await get_invitation(s, invitation_id)
    return None if row is None else cast(UUID, row["invited_by"])


async def _within_template(tenant: TenantContext, row: RowMapping) -> GrantTemplate | None:
    """The row's template, re-checked against its engagement at acceptance (a scope since moved
    or removed fails the whole acceptance, never half of it)."""
    template = _template_of(row)
    if template is None:
        return None
    if not _template_valid(template) or not await _scopes_within(
        tenant, cast(UUID, row["engagement_id"]), template
    ):
        raise InvitationNotFound("invitation")
    return template


class _InviterRefused(Exception):
    """The inviter may no longer invite to the engagement (offboarded, off the engagement,
    walled from the client, or the engagement archived): the acceptance writes nothing."""


async def _inviter_may_invite(tenant_id: UUID, inviter: UUID, engagement_id: UUID) -> bool:
    """INV-5 at acceptance (DEC-277): the inviter, as they are now, still passes `authorise` for
    `client_contact.invite` on the engagement (`service.member_could`): an active membership,
    the role and relationship layers, the ethical wall on the client, and the engagement not
    archived. The action asks no fresh MFA, so the inviter needn't be signed in."""
    tenant = TenantContext(tenant_id, "system", "invitations:accept")
    try:
        resource = await engagement_resource(tenant, engagement_id)
    except NotFound:
        return False
    return await member_could(tenant_id, inviter, "client_contact.invite", resource)


async def _refused(tenant_id: UUID, invitation_id: UUID) -> NoReturn:
    """The refusal on the record (its own unit of work: the acceptance's rolled back), then the
    one answer every failure gets."""
    async with uow(TenantContext(tenant_id, "system", f"invitation:{invitation_id}")) as tx:
        tx.record(
            "client_invitation.accept_refused", target=Target("client_invitation", invitation_id)
        )
    raise InvitationNotFound("invitation")


async def accept_invitation(identity: VerifiedIdentity, token: str) -> AcceptedInvitation:
    """AC-4 to AC-6 (the hosted sign-in, `ClientAccept.tsx`). `InvitationNotFound` for every
    failure: an unknown, used, revoked or expired token, another email, a staff member of the
    firm, or a locked-out identity. An invitation with terms is accepted only through the portal
    (`accept_portal_invitation`), where the invitee accepts them."""
    if identity.email is None or not 20 <= len(token) <= 200:
        raise InvitationNotFound("invitation")
    found = await _find(token, _digest(f"{identity.issuer}#{identity.subject}"))
    if found is None:
        raise InvitationNotFound("invitation")
    tenant_id, invitation_id = found["tenant_id"], found["invitation_id"]
    await ensure_writable(tenant_id)  # Q-01-T37: no one joins a firm in read-only mode
    inviter = await _inviter(tenant_id, invitation_id)
    ctx = TenantContext(
        tenant_id, "system", f"invitation:{invitation_id}", on_behalf_of_user_id=inviter
    )
    try:
        async with uow(ctx) as tx:
            row = await get_invitation(tx.session, invitation_id, lock=True)
            if (
                row is None
                or not row["live"]
                or row["terms_version"] is not None
                or row["grant_ids"] is not None  # contact invitations: the portal only (DEC-303)
                or str(row["email"]).casefold() != identity.email.casefold()
            ):
                raise InvitationNotFound("invitation")
            template = await _within_template(ctx, row)
            name = identity.email.split("@", 1)[0][:200] or "Client"
            user_id = await provision_client_user(
                tx.session, identity.issuer, identity.subject, identity.email, name
            )
            engagement_id = await _accept_in(tx, ctx, row, user_id, template, terms=False)
            tx.emit(AccessChanged(user_id=user_id))
    except _InviterRefused:
        await _refused(tenant_id, invitation_id)
    _log.info("client_invitation.accepted", tenant_id=tenant_id, invitation_id=invitation_id)
    return AcceptedInvitation(tenant_id, engagement_id)


async def _accept_in(
    tx: UnitOfWork,
    ctx: TenantContext,
    row: RowMapping,
    user_id: UUID,
    template: GrantTemplate | None,
    *,
    terms: bool,
) -> UUID:
    """The acceptance's writes, in the caller's unit of work: the client membership, the grants
    (the template's, or the legacy engagement role), the invitation accepted and its token gone,
    the contact active, and the audit events, every one attributed to the inviter (INV-5)."""
    if await membership_kind(tx.session, user_id) == "staff":
        raise InvitationNotFound("invitation")  # Q5: never staff and client of one firm
    invitation_id = cast(UUID, row["id"])
    engagement_id = cast(UUID, row["engagement_id"])
    inviter = cast(UUID, row["invited_by"])
    contact_id = cast(UUID | None, row["contact_id"])
    pending = await _pending_grants(tx, ctx, row)
    # The row is locked: the inviter's authority is judged now, not when they invited (DEC-277).
    if pending is not None:
        if not await _inviter_may_give(ctx, inviter, pending):
            raise _InviterRefused
    elif not await _inviter_may_invite(ctx.tenant_id, inviter, engagement_id):
        raise _InviterRefused
    await add_client_membership(tx.session, user_id)
    target = Target("engagement", engagement_id)
    if pending is not None:
        await _activate(tx, ctx, pending, user_id, inviter)
    elif template is not None:
        for scope_id in template.scope_ids:
            await grant_in_unit_of_work(
                tx,
                tenant_id=ctx.tenant_id,
                target=target,
                user_id=user_id,
                role=template.role,
                scope_kind=template.scope_kind,
                scope_id=scope_id,
                granted_by=inviter,
                contact_id=contact_id,
            )
    elif await engagement_role(ctx, user_id, engagement_id) is None:
        # F-03-T26 (ADR-146): a client role on an engagement is a grant.
        grant_id = await grant_engagement_role(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            user_id=user_id,
            role=row["role"],
            by=inviter,
        )
        if grant_id is not None:
            tx.emit(ClientAccessGranted(grant_id=grant_id, user_id=user_id))
    await accept_invitation_row(tx.session, invitation_id, user_id, terms)
    await set_token_hash(tx.session, invitation_id, None)
    if contact_id is not None:
        await activate_contact(tx, contact_id, user_id)
    tx.record(
        "client_invitation.accepted",
        target=Target("client_invitation", invitation_id),
        after=Ref(user_id=user_id),
    )
    return engagement_id


async def accept_portal_invitation(
    invitee: PortalInvitee, token: str, terms_version: int | None
) -> AcceptedInvitation:
    """Accept v2 (SPEC-320 AC-13; DEC-275) with the portal session the invitee's code started.
    `InvitationNotFound` for every failure: the token unknown, used, revoked, expired or another
    firm's; another email; a staff member of the firm; the terms not the invitation's.

    One unit of work: the membership, the template's grants, the terms, the invitation accepted,
    the contact active, and the person's other portal sessions and trusted devices in the firm
    ended (so no `access.changed` is emitted, which would end this session too). Then the new
    grants' MFA floor: a session without a second step ends and the step's token is returned."""
    if not 20 <= len(token) <= 128:
        raise InvitationNotFound("invitation")
    found = await _find(token, _digest(f"portal#{invitee.user_id}"))
    if found is None or found["tenant_id"] != invitee.tenant_id:
        raise InvitationNotFound("invitation")
    tenant_id, invitation_id = invitee.tenant_id, cast(UUID, found["invitation_id"])
    await ensure_writable(tenant_id)  # Q-01-T37: no one joins a firm in read-only mode
    inviter = await _inviter(tenant_id, invitation_id)
    ctx = TenantContext(
        tenant_id, "system", f"invitation:{invitation_id}", on_behalf_of_user_id=inviter
    )
    try:
        async with uow(ctx) as tx:
            row = await get_invitation(tx.session, invitation_id, lock=True)
            if (
                row is None
                or not row["live"]
                or str(row["email"]).casefold() != invitee.email.casefold()
                or (row["terms_version"] is not None and row["terms_version"] != terms_version)
            ):
                raise InvitationNotFound("invitation")
            template = await _within_template(ctx, row)
            engagement_id = await _accept_in(
                tx, ctx, row, invitee.user_id, template, terms=row["terms_version"] is not None
            )
            revoked = (
                await tx.session.execute(
                    text("SELECT * FROM portal_access_revoke_except(:tenant, :user, :keep)"),
                    {"tenant": tenant_id, "user": invitee.user_id, "keep": invitee.session_id},
                )
            ).all()
            record_revoked(tx, invitee.user_id, revoked)
            # The floor the new grants bring is met in this same transaction (DEC-277): a
            # session with no second step ends here, with the grants, never after them.
            step = None
            if not invitee.floor_met and await _floor_after(
                invitee, template, await _owner_among(ctx, row)
            ):
                step = await _begin_second_step(tx, invitee)
    except _InviterRefused:
        await _refused(tenant_id, invitation_id)
    _log.info("client_invitation.accepted", tenant_id=tenant_id, invitation_id=invitation_id)
    return AcceptedInvitation(tenant_id, engagement_id, await _after_commit(invitee, step))


async def _floor_after(
    invitee: PortalInvitee, template: GrantTemplate | None, owner: bool = False
) -> bool:
    """Whether the floor covers the person once the acceptance commits, as far as can be told
    inside it: an `owner` template, or the floor as it already stands (the firm's policy, their
    other grants and designations; fails closed). A designation the new contact link brings is
    seen only after the commit (`_after_commit`), and the per-request floor holds either way."""
    if owner or (template is not None and template.role == "owner"):
        return True
    return await mfa_required(invitee.tenant_id, invitee.user_id)


async def _begin_second_step(tx: UnitOfWork, invitee: PortalInvitee) -> PortalStep:
    """The accepting session ends and a single-use second-step token begins, in `tx`."""
    user_id = invitee.user_id
    state: Literal["mfa_required", "mfa_setup_required"] = (
        "mfa_required" if await factor_enrolled(user_id) else "mfa_setup_required"
    )
    mfa_token = secrets.token_urlsafe(32)
    await tx.session.execute(
        text("SELECT portal_mfa_begin_session(:id, :user, :token, :kind, :seconds)"),
        {
            "id": invitee.session_id,
            "user": user_id,
            "token": sha256_hex(mfa_token),
            "kind": "verify" if state == "mfa_required" else "setup",
            "seconds": MFA_TOKEN_SECONDS,
        },
    )
    return PortalStep(state, mfa_token=mfa_token)


async def _after_commit(invitee: PortalInvitee, begun: PortalStep | None) -> PortalStep:
    """After the commit: the step the acceptance began, or the session continues unless the
    committed access needs a second step it never had (a designation the new contact link
    brought); then it ends and the step begins. If this never runs, `portal_context` refuses the
    session on its next request anyway."""
    if begun is not None:
        return begun
    tenant_id, user_id = invitee.tenant_id, invitee.user_id
    if not invitee.floor_met and await mfa_required(tenant_id, user_id):
        async with uow(TenantContext(tenant_id, "system", f"user:{user_id}")) as tx:
            step = await _begin_second_step(tx, invitee)
            tx.record("session.ended", target=Target("auth_session", invitee.session_id))
        return step
    grants = await active_grants(TenantContext(tenant_id, "human", str(user_id)), user_id)
    return PortalStep("signed_in", landing=landing_of(g.role for g in grants))


# --- contact invitations (P-07-T25; DEC-300) ---------------------------------------------------


async def _pending_grants(
    tx: UnitOfWork, ctx: TenantContext, row: RowMapping
) -> list[ContactGrantRow] | None:
    """A contact invitation's grants, locked: each still pending, the contact's, and within the
    engagement's client (a scope since moved fails the whole acceptance). None for any other
    invitation."""
    raw = cast(list[UUID] | None, row["grant_ids"])
    if raw is None:
        return None
    ids = [UUID(str(g)) for g in raw]
    grants = await grants_by_id(tx.session, ids, lock=True)
    client_id = await engagement_client(ctx, cast(UUID, row["engagement_id"]))
    if len(grants) != len(set(ids)) or client_id is None:
        raise InvitationNotFound("invitation")
    for grant in grants:
        if grant.status != "pending" or grant.contact_id != row["contact_id"]:
            raise InvitationNotFound("invitation")
        facts = await scope_facts(ctx, grant.scope_kind, grant.scope_id)
        if facts is None or facts.client_id != client_id:
            raise InvitationNotFound("invitation")
    return grants


async def grant_resource(
    tenant: TenantContext, scope_kind: str, scope_id: UUID
) -> tuple[Resource, UUID] | None:
    """The resource a contact grant is given on, and its client: the grant's engagement, or the
    client for a client-wide grant (`client`, `client_entity`). None for a scope that resolves
    to no client, or to no engagement when it should."""
    facts = await scope_facts(tenant, scope_kind, scope_id)
    if facts is None:
        return None
    if scope_kind in ("client", "client_entity"):
        return Resource.client(tenant.tenant_id, facts.client_id), facts.client_id
    if facts.engagement_id is None:
        return None
    try:
        resource = await engagement_resource(tenant, facts.engagement_id)
    except NotFound:
        return None
    return resource, facts.client_id


async def _inviter_may_give(
    tenant: TenantContext, inviter: UUID, grants: Sequence[ContactGrantRow]
) -> bool:
    """INV-5 at acceptance for a contact invitation (DEC-277, DEC-300): for every grant, the
    inviter as they are now passes `client_access.grant` on its resource (the grant's engagement,
    or the client for a client-wide grant) with only fresh-MFA recency waived (DEC-303): the wall,
    membership, role cells, G2 on attest clients and the archived rule are judged again."""
    checked: set[tuple[str, UUID | None, UUID | None]] = set()
    for grant in grants:
        found = await grant_resource(tenant, grant.scope_kind, grant.scope_id)
        if found is None:
            return False
        resource, _ = found
        action = "client_access.grant"
        key = (action, resource.engagement_id, resource.client_id)
        if key in checked:
            continue
        if not await member_could(
            tenant.tenant_id, inviter, action, resource, waive_fresh_mfa=True
        ):
            return False
        checked.add(key)
    return True


async def _activate(
    tx: UnitOfWork,
    ctx: TenantContext,
    grants: Sequence[ContactGrantRow],
    user_id: UUID,
    inviter: UUID,
) -> None:
    """Each pending grant becomes the person's, attributed to the inviter (INV-5). Where the
    person already has a row for that role and scope (one per firm): an active one stands and
    the pending grant closes; a revoked or expired one (an earlier access, revoked) is made
    active again by this inviter, audited, and the pending grant closes (DEC-303)."""
    for grant in grants:
        target = (
            Target("firm", ctx.tenant_id)
            if grant.scope_kind in ("client", "client_entity")
            else Target("engagement", await _engagement_of(ctx, grant))
        )
        held = await held_grant(tx.session, user_id, grant.role, grant.scope_kind, grant.scope_id)
        granted = grant.id
        if held is not None:
            await set_grant_status(tx.session, grant.id, "revoked")
            await insert_grant_event(
                tx.session, tenant_id=ctx.tenant_id, grant_id=grant.id, event="revoked", by=inviter
            )
            if held[1] == "active":
                continue
            granted = held[0]
            await set_grant_status(tx.session, granted, "active")
        elif not await activate_grant(tx.session, grant.id, user_id):
            raise InvitationNotFound("invitation")
        await insert_grant_event(
            tx.session, tenant_id=ctx.tenant_id, grant_id=granted, event="activated", by=inviter
        )
        tx.record("client_access.granted", target=target)
        tx.emit(ClientAccessGranted(grant_id=granted, user_id=user_id))


async def _engagement_of(ctx: TenantContext, grant: ContactGrantRow) -> UUID:
    facts = await scope_facts(ctx, grant.scope_kind, grant.scope_id)
    if facts is None or facts.engagement_id is None:
        raise InvitationNotFound("invitation")
    return facts.engagement_id


async def _owner_among(ctx: TenantContext, row: RowMapping) -> bool:
    raw = cast(list[UUID] | None, row["grant_ids"])
    if raw is None:
        return False
    async with tenant_session(ctx) as session:
        grants = await grants_by_id(session, [UUID(str(g)) for g in raw])
    return any(g.role == "owner" for g in grants)


async def _contact_item_count(tenant: TenantContext, invitation_id: UUID) -> int | None:
    """POR-01 d's item count for a contact invitation limited to requests or work items."""
    async with tenant_session(tenant) as session:
        row = await get_invitation(session, invitation_id)
        raw = None if row is None else cast(list[UUID] | None, row["grant_ids"])
        if raw is None:
            return None
        grants = await grants_by_id(session, [UUID(str(g)) for g in raw])
    if grants and all(g.scope_kind in ("request_item", "work_item") for g in grants):
        return len(grants)
    return None
