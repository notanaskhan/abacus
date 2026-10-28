"""A firm's sender domain, the From of its client mail and the client-mail gate (R-01-T27; R-01
§3.8 story 8.3, §3.9 story 9.2; C16 v1.1 §sending domains; DEC-59, DEC-950 to DEC-955;
migration 0340). PROTECTED.

**Domains.** `create_domain` asks SES (`ses_identities`, Q-01-T47) for an identity with Easy DKIM
and the custom MAIL FROM `bounce.<domain>`, then records it `pending_dns` with its five DNS
records (three DKIM CNAMEs, the MAIL FROM MX and SPF). One live domain (`pending_dns` or
`verified`) per firm, and a live domain belongs to one firm (409 `sending_domain_exists` either
way, DEC-951). `refresh` reads the identity and moves the row: `verified` once DKIM and MAIL FROM
are both verified; `failed` with the reason once `VERIFY_WINDOW` (72 hours) has passed without
that; a verified domain whose identity SES no longer verifies is `failed` too. The
`SendingDomainVerification` workflow runs `refresh` every 15 minutes (`workflows.py`); a person
can run it now (`check_domain`). `revoke_domain` ends a domain and deletes its identity after the
commit. Every move is audited `sending_domain.<status>` and emits `sending_domain.status_changed`.

**From** (`sender_for`, DEC-950). With `communications.firm_sender_domain` on and a verified
domain: From `<from_local_part>@<domain>` under the firm's name. Otherwise the neutral sender
(the platform's address, `ses_from_address`, never naming the product) under the firm's name,
with Reply-To the firm's own address when its domain is verified (the RK-52 fallback).

**Gate** (`client_mail_open`, DEC-953). A real firm's client, third-party and respondent mail is
closed until the platform opens it (`abacus_tools.client_mail`, two people named; migration
0340's `set_client_mail`); a synthetic firm's is open (its mail goes to the sink).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel._flags import COMMUNICATIONS_FIRM_SENDER_DOMAIN
from abacus.kernel.clock import now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, DomainUnavailable, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.communications.events import (
    SendingDomainFailed,
    SendingDomainStatusChanged,
    SendingDomainVerified,
)
from abacus.modules.communications.ses_identities import (
    IdentityStatus,
    SesIdentityInvalid,
    SesIdentityNotFound,
    SesIdentityUnavailable,
    ses_identities,
)
from abacus.modules.communications.workflows import (
    SendingDomainVerificationInput,
    SendingDomainVerificationWorkflow,
)
from abacus.modules.identity.api import AuthContext, Resource, authorise, firm_name

DomainStatus = Literal["pending_dns", "verified", "failed", "revoked"]
RecordStatus = Literal["pending", "verified", "failed"]
FailureReason = Literal["dkim_not_verified", "mail_from_not_verified", "identity_missing"]
VERIFY_WINDOW: Final = timedelta(hours=72)
MAIL_FROM_SUBDOMAIN: Final = "bounce"
LIVE: Final = frozenset({"pending_dns", "verified"})
_READ, _MANAGE = "sending_domain.read", "sending_domain.manage"
_LIST_LIMIT: Final = 10
_log = get_logger(__name__)


class SendingDomainExists(DomainConflict):
    code = "sending_domain_exists"


class SendingDomainUnavailable(DomainUnavailable):
    """SES refused or could not be reached; nothing was recorded."""

    code = "sending_domain_unavailable"


@dataclass(frozen=True)
class DomainRecord:
    type: Literal["CNAME", "MX", "TXT"]
    name: str
    value: str
    status: RecordStatus


@dataclass(frozen=True)
class SendingDomain:
    id: UUID
    domain: str
    from_local_part: str
    mail_from_domain: str
    status: DomainStatus
    records: tuple[DomainRecord, ...]
    failure_reason: FailureReason | None
    requested_at: datetime
    verified_at: datetime | None
    last_checked_at: datetime | None


@dataclass(frozen=True)
class Decision:
    """What one check makes of a domain: its status, the two record states and the reason."""

    status: DomainStatus
    dkim: RecordStatus
    mail_from: RecordStatus
    failure_reason: FailureReason | None


def decide(
    status: DomainStatus, found: IdentityStatus | None, requested_at: datetime, at: datetime
) -> Decision:
    """The one rule for a check (pure; R-01-T30 tests it directly). `found` None: SES has no
    identity for the domain. A revoked or failed domain never moves here."""
    dkim: RecordStatus = "pending" if found is None else found.dkim
    mail_from: RecordStatus = "pending" if found is None else found.mail_from
    if status not in LIVE:
        return Decision(status, dkim, mail_from, None)
    if found is not None and found.dkim == "verified" and found.mail_from == "verified":
        return Decision("verified", dkim, mail_from, None)
    reason: FailureReason = (
        "identity_missing"
        if found is None
        else "dkim_not_verified"
        if found.dkim != "verified"
        else "mail_from_not_verified"
    )
    # A verified domain fails only when SES says failed or has no identity (records removed); a
    # temporary failure keeps it. A pending one fails once the window has passed, or as soon as
    # SES itself says failed.
    ses_failed = found is None or "failed" in (found.dkim, found.mail_from)
    if status == "verified":
        if ses_failed:
            return Decision("failed", dkim, mail_from, reason)
        return Decision("verified", dkim, mail_from, None)
    expired = at - requested_at >= VERIFY_WINDOW
    if expired or (found is not None and ses_failed):
        return Decision("failed", dkim, mail_from, reason)
    return Decision("pending_dns", dkim, mail_from, None)


def workflow_id(tenant_id: UUID, domain_id: UUID) -> str:
    return f"sending_domain:{tenant_id}:{domain_id}"


# --- reads -----------------------------------------------------------------------------------

_COLUMNS = (
    "id, domain, from_local_part, mail_from_domain, status, dkim_records, dkim_status, "
    "mail_from_status, failure_reason, requested_at, verified_at, last_checked_at"
)


def _records(raw: object, dkim: str, mail_from: str) -> tuple[DomainRecord, ...]:
    found: list[DomainRecord] = []
    for entry in cast(list[dict[str, str]], raw if isinstance(raw, list) else []):
        kind = cast(Literal["CNAME", "MX", "TXT"], entry.get("type", "TXT"))
        state = dkim if kind == "CNAME" else mail_from
        found.append(
            DomainRecord(kind, entry.get("name", ""), entry.get("value", ""), _state(state))
        )
    return tuple(found)


def _state(value: str) -> RecordStatus:
    if value == "verified" or value == "failed":
        return value
    return "pending"


def _row(row: object) -> SendingDomain:
    r = cast(dict[str, object], row._mapping)  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType] -- a SQLAlchemy Row
    return SendingDomain(
        id=cast(UUID, r["id"]),
        domain=str(r["domain"]),
        from_local_part=str(r["from_local_part"]),
        mail_from_domain=str(r["mail_from_domain"]),
        status=cast(DomainStatus, r["status"]),
        records=_records(r["dkim_records"], str(r["dkim_status"]), str(r["mail_from_status"])),
        failure_reason=cast(FailureReason | None, r["failure_reason"]),
        requested_at=cast(datetime, r["requested_at"]),
        verified_at=cast(datetime | None, r["verified_at"]),
        last_checked_at=cast(datetime | None, r["last_checked_at"]),
    )


async def _domains(tenant: TenantContext) -> list[SendingDomain]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                f"SELECT {_COLUMNS} FROM sending_domains "  # noqa: S608 -- fixed columns
                "ORDER BY requested_at DESC, id LIMIT :limit"
            ),
            {"limit": _LIST_LIMIT},
        )
        return [_row(r) for r in rows]


async def _domain(tenant: TenantContext, domain_id: UUID) -> SendingDomain:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(f"SELECT {_COLUMNS} FROM sending_domains WHERE id = :id"),  # noqa: S608
                {"id": domain_id},
            )
        ).first()
    if row is None:
        raise NotFound("sending_domain")
    return _row(row)


def _firm(ctx: AuthContext) -> Resource:
    return Resource.firm(ctx.tenant_id)


async def authorise_write(ctx: AuthContext) -> None:
    """Authorise first (fresh MFA: the matrix), then the flag (C16 §2: off is 404)."""
    await authorise(ctx, _MANAGE, _firm(ctx))
    if not await flag_enabled(ctx.tenant, COMMUNICATIONS_FIRM_SENDER_DOMAIN):
        raise NotFound(COMMUNICATIONS_FIRM_SENDER_DOMAIN.name)


async def domain_of(ctx: AuthContext, domain_id: UUID) -> SendingDomain:
    """One of the firm's domains (`sending_domain.read`); 404 for another firm's."""
    await authorise(ctx, _READ, _firm(ctx))
    return await _domain(ctx.tenant, domain_id)


async def list_domains(ctx: AuthContext) -> list[SendingDomain]:
    """ADM-10 d: the firm's domains, newest first. Never behind the flag."""
    await authorise(ctx, _READ, _firm(ctx))
    return await _domains(ctx.tenant)


# --- writes ----------------------------------------------------------------------------------


async def create_domain(ctx: AuthContext, domain: str, from_local_part: str) -> SendingDomain:
    """`POST /v1/firm/sending-domains`. The row first, in the same unit of work as the SES call:
    the two unique indexes refuse a second live domain of this firm, or a name live for any firm,
    before SES is asked anything (security review: no firm touches another's identity). Then the
    identity (idempotent at SES for the same domain) and its records; an SES failure rolls the row
    back. 409 `sending_domain_exists`; 503 `sending_domain_unavailable` (DEC-951)."""
    await authorise_write(ctx)
    if any(d.status in LIVE for d in await _domains(ctx.tenant)):
        raise SendingDomainExists
    mail_from = f"{MAIL_FROM_SUBDOMAIN}.{domain}"
    try:
        async with uow(ctx.tenant) as tx:
            domain_id = (
                await tx.session.execute(
                    text(
                        "INSERT INTO sending_domains (tenant_id, domain, from_local_part, "
                        "mail_from_domain, dkim_records, ses_identity_ref, requested_by) VALUES "
                        "(:tenant, :domain, :local, :mail_from, CAST('[]' AS jsonb), :domain, "
                        ":by) RETURNING id"
                    ),
                    {
                        "tenant": ctx.tenant_id,
                        "domain": domain,
                        "local": from_local_part,
                        "mail_from": mail_from,
                        "by": ctx.user_id,
                    },
                )
            ).scalar_one()
            try:
                setup = await asyncio.to_thread(
                    ses_identities().create_identity,
                    domain=domain,
                    mail_from_subdomain=MAIL_FROM_SUBDOMAIN,
                )
            except SesIdentityInvalid:
                raise NotFound("sending_domain") from None  # unreachable: the model's pattern
            except SesIdentityUnavailable as exc:
                _log.warning("sending_domain.ses_unavailable", code=str(exc))
                raise SendingDomainUnavailable from None
            records = [
                {"type": r.type, "name": r.name, "value": r.value} for r in setup.dns_records
            ]
            await tx.session.execute(
                text(
                    "UPDATE sending_domains SET dkim_records = CAST(:records AS jsonb) "
                    "WHERE id = :id"
                ),
                {"records": _json(records), "id": domain_id},
            )
            tx.record(
                "sending_domain.created",
                target=Target("sending_domain", domain_id),
                after=Ref(status="pending_dns"),
            )
            tx.emit(SendingDomainStatusChanged(domain_id=domain_id, status="pending_dns"))
    except IntegrityError:
        # Another live domain won the race, here or in another firm (the two unique indexes).
        raise SendingDomainExists from None
    return await _domain(ctx.tenant, domain_id)


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


async def check_domain(ctx: AuthContext, domain_id: UUID) -> SendingDomain:
    """`POST …/{id}/check`: run the check now (the workflow runs it every 15 minutes)."""
    await authorise_write(ctx)
    await _domain(ctx.tenant, domain_id)  # 404 first for another firm's or an unknown id
    await refresh(ctx.tenant, domain_id)
    return await _domain(ctx.tenant, domain_id)


async def revoke_domain(ctx: AuthContext, domain_id: UUID) -> SendingDomain:
    """`DELETE …/{id}`: the domain ends (client mail goes from the neutral sender again) and its
    SES identity is deleted after the commit. Revoking a revoked domain changes nothing."""
    await authorise_write(ctx)
    current = await _domain(ctx.tenant, domain_id)
    if current.status == "revoked":
        return current
    at = await now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE sending_domains SET status = 'revoked', revoked_at = :at, "
                    "revoked_by = :by WHERE id = :id AND status <> 'revoked' RETURNING id"
                ),
                {"at": at, "by": ctx.user_id, "id": domain_id},
            )
        ).first()
        if moved is not None:
            tx.record(
                "sending_domain.revoked",
                target=Target("sending_domain", domain_id),
                before=Ref(status=current.status),
                after=Ref(status="revoked"),
            )
            tx.emit(SendingDomainStatusChanged(domain_id=domain_id, status="revoked"))
    # Security review: only a live row owns its identity (one live row per name across firms).
    # A failed row's name may be live again, here or at another firm: its identity is left alone.
    if moved is not None and current.status in LIVE:
        try:
            await asyncio.to_thread(ses_identities().delete_identity, domain=current.domain)
        except (SesIdentityUnavailable, SesIdentityInvalid) as exc:
            # The row is revoked; a stale identity sends nothing (no From selects it).
            _log.warning("sending_domain.delete_failed", error=type(exc).__name__)
    return await _domain(ctx.tenant, domain_id)


async def refresh(tenant: TenantContext, domain_id: UUID) -> DomainStatus:
    """One check of the domain against SES, recorded; its status after. Idempotent: a check
    that changes nothing only stamps `last_checked_at`. The workflow's activity and the check
    route both come here, under the firm's row-level security."""
    system = TenantContext(tenant.tenant_id, "system", "sending_domain_verification")
    current = await _domain(system, domain_id)
    if current.status not in LIVE:
        return current.status
    try:
        found: IdentityStatus | None = await asyncio.to_thread(
            ses_identities().identity_status, domain=current.domain
        )
    except SesIdentityNotFound:
        found = None
    except SesIdentityUnavailable as exc:
        _log.warning("sending_domain.ses_unavailable", code=str(exc))
        raise SendingDomainUnavailable from None
    at = await now(system)
    decision = decide(current.status, found, current.requested_at, at)
    async with uow(system) as tx:
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE sending_domains SET status = :status, dkim_status = :dkim, "
                    "mail_from_status = :mail_from, failure_reason = :reason, "
                    "verified_at = CASE WHEN :status = 'verified' "
                    "THEN coalesce(verified_at, :at) ELSE verified_at END, "
                    "last_checked_at = :at WHERE id = :id AND status = :was RETURNING id"
                ),
                {
                    "status": decision.status,
                    "dkim": decision.dkim,
                    "mail_from": decision.mail_from,
                    "reason": decision.failure_reason,
                    "at": at,
                    "id": domain_id,
                    "was": current.status,
                },
            )
        ).first()
        if moved is not None and decision.status != current.status:
            tx.record(
                f"sending_domain.{decision.status}",
                target=Target("sending_domain", domain_id),
                before=Ref(status=current.status),
                after=Ref(status=decision.status)
                if decision.failure_reason is None
                else Ref(status=decision.status, reason=decision.failure_reason),
            )
            tx.emit(SendingDomainStatusChanged(domain_id=domain_id, status=decision.status))
            if decision.status == "verified":
                tx.emit(SendingDomainVerified(domain_id=domain_id))
            elif decision.status == "failed":
                tx.emit(SendingDomainFailed(domain_id=domain_id))
    return decision.status if moved is not None else (await _domain(system, domain_id)).status


# --- the workflow's start --------------------------------------------------------------------


async def on_status_changed(event: OutboxEvent) -> None:
    """`sending_domain.status_changed` to `pending_dns` starts the domain's verification, once
    (reuse rejected): every 15 minutes until verified, failed or revoked."""
    if event.payload.get("status") != "pending_dns":
        return
    domain_id = UUID(str(event.payload["domain_id"]))
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            SendingDomainVerificationWorkflow,
            SendingDomainVerificationInput(str(event.tenant_id), str(domain_id)),
            id=workflow_id(event.tenant_id, domain_id),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


# --- From selection and the gate --------------------------------------------------------------


@dataclass(frozen=True)
class Sender:
    """The From of one firm's client mail (DEC-950). `address` None: the transport's own neutral
    address. `from_domain` is what the message records."""

    display: str
    address: str | None
    reply_to: str | None
    from_domain: str | None


def neutral_domain() -> str | None:
    configured = settings().ses_from_address
    return configured.rsplit("@", 1)[1] if configured and "@" in configured else None


async def sender_for(tenant_id: UUID) -> Sender:
    """The firm's verified domain while `communications.firm_sender_domain` is on; otherwise the
    neutral sender, with Reply-To the firm's address only when its domain is verified (security
    review: a pending or failed domain is not proven to be the firm's, so no reply goes there)."""
    tenant = TenantContext(tenant_id, "system", "sender_selection")
    display = await firm_name(tenant_id)
    domains = await _domains(tenant)
    on_record = next((d for d in domains if d.status != "revoked"), None)
    if (
        on_record is not None
        and on_record.status == "verified"
        and await flag_enabled(tenant, COMMUNICATIONS_FIRM_SENDER_DOMAIN)
    ):
        return Sender(
            display, f"{on_record.from_local_part}@{on_record.domain}", None, on_record.domain
        )
    reply_to = None if on_record is None else f"{on_record.from_local_part}@{on_record.domain}"
    return Sender(display, None, reply_to, neutral_domain())


# The audiences the gate closes (story 9.2): everyone outside the firm.
GATED: Final = frozenset({"client", "third_party", "respondent"})


async def client_mail_open(tenant_id: UUID) -> bool:
    """Whether the firm's client mail is open: the platform's flip, else the firm's synthetic
    flag (migration 0340's `client_mail_enabled()`). Fails closed on any read error."""
    tenant = TenantContext(tenant_id, "system", "client_mail_gate")
    try:
        async with tenant_session(tenant) as session:
            return bool(await session.scalar(text("SELECT client_mail_enabled()")))
    except Exception as exc:  # fail closed: nothing reaches a client on a failed read
        _log.warning("client_mail_gate.read_failed", error=type(exc).__name__)
        return False


def gated(audiences: Sequence[str]) -> bool:
    return any(a in GATED for a in audiences)


@activity.defn(name="communications.check_sending_domain")
async def check_sending_domain_activity(given: SendingDomainVerificationInput) -> str:
    """The workflow's one check: the domain's status after it."""
    tenant = TenantContext(UUID(given.tenant_id), "system", "sending_domain_verification")
    return await refresh(tenant, UUID(given.domain_id))
