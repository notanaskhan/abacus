"""E-file authorization policy and the handwritten fallback (N-02-T27; N-02 §3.7; DF-11;
Pub 1345; DEC-1469).

**Policies.** Each family's policy is data (`envelope_policies`, 0292): a firm's row, else the
code-owned floor below (the published rule, not firm content). `GET /v1/envelope-policies` reads
the four families; `PUT /v1/envelope-policies/{family}` is stricter-only against the floor: the
identity methods may only narrow (the e-file family keeps `kba`; SMS has no value at all), the
KBA attempt limit may only fall, and a firm that required a countersignature cannot drop it
below the floor. Reminder and expiry settings are the firm's within the table's bounds.

**KBA failures.** The provider poll (`activities.envelope_poll`) hands each signer's failure count
to `kba_failures_seen`: one `signer.kba_failed` event per new failure, and at the family's limit
the signer becomes `verification_failed` (whatever the provider says): remote signing closes for
that signer (open signing sessions abandoned; the portal refuses a new one; the poll never moves
the signer back), C7's `envelope.signer_verification_failed` goes out (C16 tells the sender and
T-01 hears it), and SIG-01 shows "Needs a handwritten signature". There is no unlock timer and no
new link. Whether the provider itself also closes the signer's view is [verify] (F-09-T63).

**The handwritten fallback.** `POST …/signers/{sid}/wet-signature`
(`envelope.record_wet_signature`, a person in a live session): a signer whose identity check
failed, or one the envelope names for in-person ID, signs on paper. The scanned form is a file
the person staged first (the import's `stage_file`: scanned before storage), stored with a
manifest (attestation, received date, optional in-person ID type and checker) write-once in the
records bucket and filed as the signed copy; the signer becomes
signed with method `handwritten` and the recorder named (0564: the database refuses anyone but
that person). Taxpayers sign before the ERO, so a later routing group cannot be signed by hand
ahead of an earlier one. When every signer has signed, the envelope completes; the completion
activity then records the remote signers' evidence from the provider and announces
`envelope.completed`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import service_line_of
from abacus.modules.evidence.api import (
    file_signed_copy,
    put_record,
    read_staged,
    retain_until_for,
)
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.signatures.events import (
    EnvelopeSignerSigned,
    EnvelopeSignerVerificationFailed,
)
from abacus.modules.signatures.hub import firm_and_flag, resource_of, visible_head
from abacus.modules.signatures.imports import ImportFileUnavailable, RetentionFloorMissing

Family = Literal["efile_authorization", "engagement_letter", "consent", "general"]
FAMILIES: Final[tuple[Family, ...]] = (
    "efile_authorization",
    "engagement_letter",
    "consent",
    "general",
)
EFILE: Final = "efile_authorization"
READ: Final = "envelope_policy.read"
MANAGE: Final = "envelope_policy.manage"
WET: Final = "envelope.record_wet_signature"
RECORD_TYPE: Final = "signature_evidence"
KBA_LIMIT: Final = 3  # Pub 1345 and DF-11: three failures, then the paper form
OPEN: Final = ("sent", "viewed", "partially_signed")
IdType = Literal["drivers_license", "passport", "state_id", "military_id", "other"]


@dataclass(frozen=True)
class Policy:
    policy_family: Family
    allowed_identity_methods: tuple[str, ...]
    default_identity_method: str
    kba_max_attempts: int
    failure_path: Literal["wet_signature"]
    reminder_cadences: tuple[str, ...]
    max_reminders: int
    default_expiry_days: int
    countersign_required: bool
    version: int  # 0: the floor (no firm row yet)


# The code-owned floor (N-02 §5 `envelope_policies`; DF-11): the published rule each family starts
# from and a firm may only tighten. Identity per family follows SIG-02's picker.
FLOOR: Final[dict[Family, Policy]] = {
    "efile_authorization": Policy(
        EFILE, ("kba", "in_person_id", "firm_sso"), "kba", 3, "wet_signature", (), 3, 30, False, 0
    ),
    "engagement_letter": Policy(
        "engagement_letter",
        ("email_code", "in_person_id", "firm_sso"),
        "email_code",
        3,
        "wet_signature",
        (),
        3,
        30,
        True,
        0,
    ),
    "consent": Policy(
        "consent",
        ("email_code", "in_person_id", "firm_sso"),
        "email_code",
        3,
        "wet_signature",
        (),
        3,
        30,
        False,
        0,
    ),
    "general": Policy(
        "general",
        ("email_code", "in_person_id", "firm_sso"),
        "email_code",
        3,
        "wet_signature",
        (),
        3,
        30,
        False,
        0,
    ),
}


class PolicyNotStricter(DomainConflict):
    """A policy change may only tighten the published floor (AC-9)."""

    code = "policy_not_stricter"


class PolicyStale(DomainConflict):
    """The policy changed since it was read: read it again."""

    code = "stale_version"


class WetSignatureNotAllowed(DomainConflict):
    """This signer cannot sign on paper now: only a signer whose identity check failed, or one
    named for in-person ID, on an open envelope whose earlier signers have signed."""

    code = "wet_signature_not_allowed"


# --- policies -------------------------------------------------------------------------------


_ROWS = text(
    "SELECT policy_family, allowed_identity_methods, default_identity_method, kba_max_attempts, "
    "failure_path, reminder_cadences, max_reminders, default_expiry_days, countersign_required, "
    "version FROM envelope_policies WHERE purpose IS NULL"
)


def _of(row: Mapping[str, object]) -> Policy:
    return Policy(
        policy_family=cast(Family, str(row["policy_family"])),  # the table's CHECK holds four
        allowed_identity_methods=tuple(cast(list[str], row["allowed_identity_methods"])),
        default_identity_method=str(row["default_identity_method"]),
        kba_max_attempts=int(str(row["kba_max_attempts"])),
        failure_path="wet_signature",
        reminder_cadences=tuple(cast(list[str], row["reminder_cadences"])),
        max_reminders=int(str(row["max_reminders"])),
        default_expiry_days=int(str(row["default_expiry_days"])),
        countersign_required=bool(row["countersign_required"]),
        version=int(str(row["version"])),
    )


async def effective_policies(tenant: TenantContext) -> dict[Family, Policy]:
    """Each family's firm row, else its floor."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_ROWS)).mappings().all()
    found = {str(r["policy_family"]): _of(cast(Mapping[str, object], r)) for r in rows}
    return {f: found.get(f, FLOOR[f]) for f in FAMILIES}


async def list_policies(ctx: AuthContext) -> list[Policy]:
    """`GET /v1/envelope-policies`."""
    await firm_and_flag(ctx)
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    return list((await effective_policies(ctx.tenant)).values())


@dataclass(frozen=True)
class PolicyChange:
    allowed_identity_methods: tuple[str, ...]
    default_identity_method: str
    kba_max_attempts: int
    max_reminders: int
    default_expiry_days: int
    countersign_required: bool
    version: int


def check_stricter(family: Family, change: PolicyChange) -> None:
    """Stricter-only against the floor; refuses with the first rule broken."""
    floor = FLOOR[family]
    if not set(change.allowed_identity_methods) <= set(floor.allowed_identity_methods):
        raise PolicyNotStricter(facts={"field": "allowed_identity_methods"})
    if change.default_identity_method not in change.allowed_identity_methods:
        raise PolicyNotStricter(facts={"field": "default_identity_method"})
    if family == EFILE and "kba" not in change.allowed_identity_methods:
        raise PolicyNotStricter(facts={"field": "allowed_identity_methods"})
    if family == EFILE and change.default_identity_method != "kba":
        raise PolicyNotStricter(facts={"field": "default_identity_method"})
    if change.kba_max_attempts > floor.kba_max_attempts:
        raise PolicyNotStricter(facts={"field": "kba_max_attempts"})
    if floor.countersign_required and not change.countersign_required:
        raise PolicyNotStricter(facts={"field": "countersign_required"})


async def update_policy(ctx: AuthContext, family: Family, change: PolicyChange) -> Policy:
    """`PUT /v1/envelope-policies/{family}`: security admin, fresh second factor (matrix)."""
    await firm_and_flag(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(MANAGE, "role")
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    check_stricter(family, change)
    async with uow(ctx.tenant) as tx:
        current = (
            await tx.session.execute(
                text(
                    "SELECT version FROM envelope_policies WHERE policy_family = :f "
                    "AND purpose IS NULL FOR UPDATE"
                ),
                {"f": family},
            )
        ).scalar_one_or_none()
        at = 0 if current is None else int(current)
        if change.version != at:
            raise PolicyStale(facts={"version": at})
        values = {
            "f": family,
            "methods": list(change.allowed_identity_methods),
            "default": change.default_identity_method,
            "kba": change.kba_max_attempts,
            "reminders": change.max_reminders,
            "expiry": change.default_expiry_days,
            "countersign": change.countersign_required,
            "by": ctx.user_id,
            "now": system_now(),
        }
        if current is None:
            await tx.session.execute(
                text(
                    "INSERT INTO envelope_policies (tenant_id, policy_family, "
                    "allowed_identity_methods, default_identity_method, kba_max_attempts, "
                    "max_reminders, default_expiry_days, countersign_required, updated_by, "
                    "updated_at) VALUES (:t, :f, :methods, :default, :kba, :reminders, :expiry, "
                    ":countersign, :by, :now)"
                ),
                {**values, "t": ctx.tenant_id},
            )
        else:
            await tx.session.execute(
                text(
                    "UPDATE envelope_policies SET allowed_identity_methods = :methods, "
                    "default_identity_method = :default, kba_max_attempts = :kba, "
                    "max_reminders = :reminders, default_expiry_days = :expiry, "
                    "countersign_required = :countersign, version = version + 1, "
                    "updated_by = :by, updated_at = :now "
                    "WHERE policy_family = :f AND purpose IS NULL"
                ),
                values,
            )
        tx.record(
            "envelope_policy.updated",
            target=Target("envelope_policy", ctx.tenant_id),
            after=Ref(version=at + 1, kba_max_attempts=change.kba_max_attempts),
        )
    return (await effective_policies(ctx.tenant))[family]


async def kba_limit(tenant: TenantContext, family: str) -> int:
    """The family's KBA attempt limit (the firm's, else the floor's three)."""
    if family not in FLOOR:
        return KBA_LIMIT
    return (await effective_policies(tenant))[family].kba_max_attempts


# --- KBA failures (the poll) ----------------------------------------------------------------


@dataclass(frozen=True)
class SignerSeen:
    signer_id: UUID
    status: str  # our row's status before the poll
    kba_failures: int  # our row's count before the poll
    reported: int  # the provider's count now
    identity_method: str


@dataclass(frozen=True)
class EnvelopeFacts:
    tenant_id: UUID
    envelope_id: UUID
    client_id: UUID
    engagement_id: UUID | None
    source_kind: str | None
    source_id: UUID | None
    policy_family: str
    sent_by: UUID | None = None


async def kba_failures_seen(
    tx: UnitOfWork, env: EnvelopeFacts, seen: Sequence[SignerSeen], limit: int, now: datetime
) -> set[UUID]:
    """Record each new failure and close the signers at the limit; answers the signers closed
    (the poll keeps their status, whatever the provider reports)."""
    closed: set[UUID] = set()
    for s in seen:
        if s.identity_method != "kba" or s.status in ("signed", "declined"):
            continue
        count = min(max(s.reported, s.kba_failures), KBA_LIMIT)
        if count > s.kba_failures:
            for n in range(s.kba_failures + 1, count + 1):
                await tx.session.execute(
                    text(
                        "INSERT INTO envelope_events (tenant_id, envelope_id, signer_id, kind, "
                        "source, occurred_at, payload_sha256) VALUES (:t, :e, :s, "
                        "'signer.kba_failed', 'provider_poll', :at, :n)"
                    ),
                    {
                        "t": env.tenant_id,
                        "e": env.envelope_id,
                        "s": s.signer_id,
                        "at": now,
                        "n": hashlib.sha256(f"{s.signer_id}:kba:{n}".encode()).hexdigest(),
                    },
                )
            await tx.session.execute(
                text("UPDATE envelope_signers SET kba_failures = :n WHERE id = :s"),
                {"n": count, "s": s.signer_id},
            )
            tx.record(
                "signer.kba_failed",
                target=Target("envelope", env.envelope_id),
                after=Ref(signer_id=s.signer_id, failures=count),
            )
        if s.status == "verification_failed":
            closed.add(s.signer_id)
            continue
        if count >= limit and env.policy_family == EFILE:
            await _close_remote(tx, env, s.signer_id, now)
            closed.add(s.signer_id)
    return closed


async def _close_remote(
    tx: UnitOfWork, env: EnvelopeFacts, signer_id: UUID, now: datetime
) -> None:
    await tx.session.execute(
        text("UPDATE envelope_signers SET status = 'verification_failed' WHERE id = :s"),
        {"s": signer_id},
    )
    await tx.session.execute(
        text(
            "UPDATE signing_sessions SET state = 'abandoned' "
            "WHERE signer_id = :s AND state = 'issued'"
        ),
        {"s": signer_id},
    )
    await tx.session.execute(
        text(
            "INSERT INTO envelope_events (tenant_id, envelope_id, signer_id, kind, source, "
            "occurred_at) VALUES (:t, :e, :s, 'signer.verification_failed', 'provider_poll', :at)"
        ),
        {"t": env.tenant_id, "e": env.envelope_id, "s": signer_id, "at": now},
    )
    tx.record(
        "signer.verification_failed",
        target=Target("envelope", env.envelope_id),
        after=Ref(signer_id=signer_id),
    )
    tx.emit(
        EnvelopeSignerVerificationFailed(
            envelope_id=env.envelope_id,
            signer_id=signer_id,
            client_id=env.client_id,
            engagement_id=env.engagement_id,
            source_kind=env.source_kind or "envelope",
            source_id=env.source_id or env.envelope_id,
            sent_by=env.sent_by,
        )
    )


# --- the hand-signed form -------------------------------------------------------------------


@dataclass(frozen=True)
class InPersonId:
    id_type: IdType
    checked_by: UUID


@dataclass(frozen=True)
class WetSignature:
    upload_id: UUID
    signed_on: date
    received_on: date | None = None
    in_person_id: InPersonId | None = None


_SIGNERS = text(
    'SELECT id, "order", routing_group, identity_method, status FROM envelope_signers '
    'WHERE envelope_id = :e ORDER BY "order" FOR UPDATE'
)
_FILE = text(
    "SELECT id, media_type, size_bytes, sha256, storage_key, storage_version_id "
    "FROM envelope_import_files WHERE id = :id AND uploaded_by = :user "
    "AND consumed_envelope_id IS NULL"
)


def _may_sign_on_paper(row: Mapping[str, object]) -> bool:
    if row["status"] == "verification_failed":
        return True
    return row["identity_method"] == "in_person_id" and row["status"] in ("pending", "viewed")


async def record_wet_signature(
    ctx: AuthContext, envelope_id: UUID, signer_id: UUID, given: WetSignature
) -> bool:
    """Record one hand-signed form; answers whether the envelope is now complete."""
    await firm_and_flag(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(WET, "role")  # INV-1: a person in a live session
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
        upload = (
            (await session.execute(_FILE, {"id": given.upload_id, "user": ctx.user_id}))
            .mappings()
            .one_or_none()
        )
    await authorise(ctx, WET, await resource_of(ctx, head))
    if head.status not in OPEN:
        raise WetSignatureNotAllowed(facts={"status": head.status})
    if upload is None:
        raise ImportFileUnavailable
    if given.in_person_id is not None and given.in_person_id.checked_by != ctx.user_id:
        # The checker attests in their own session; recording for someone else is refused.
        raise WetSignatureNotAllowed(facts={"reason": "checker_not_recorder"})
    line = (
        await service_line_of(ctx.tenant, head.engagement_id)
        if head.engagement_id is not None
        else None
    ) or "any"
    now = system_now()
    keep = await retain_until_for(ctx.tenant, RECORD_TYPE, line, now)
    if keep is None:
        raise RetentionFloorMissing
    content = await read_staged(
        ctx.tenant_id,
        str(upload["storage_key"]),
        str(upload["storage_version_id"]),
        str(upload["sha256"]),
        int(str(upload["size_bytes"])),
    )
    scan = await put_record(ctx.tenant_id, RECORD_TYPE, content, keep)
    signed_at = datetime.combine(given.signed_on, time(12, 0), tzinfo=now.tzinfo)
    manifest = json.dumps(
        {
            "envelope_id": str(envelope_id),
            "signer_id": str(signer_id),
            "method": "handwritten",
            "scan_sha256": str(upload["sha256"]),
            "signed_on": given.signed_on.isoformat(),
            "received_on": (given.received_on or now.date()).isoformat(),
            "in_person_id": None
            if given.in_person_id is None
            else {
                "id_type": given.in_person_id.id_type,
                "checked_by": str(given.in_person_id.checked_by),
            },
            "recorded_by": str(ctx.user_id),
            "attested": True,
            "recorded_at": now.isoformat(),
        },
        sort_keys=True,
    ).encode()
    package = await put_record(ctx.tenant_id, RECORD_TYPE, manifest, keep)
    package_sha = hashlib.sha256(manifest).hexdigest()
    async with uow(ctx.tenant) as tx:
        env = (
            (
                await tx.session.execute(
                    text(
                        "SELECT id, status, client_id, engagement_id, work_item_id, title, "
                        "source_kind, source_id, policy_family FROM envelopes "
                        "WHERE id = :e FOR UPDATE"
                    ),
                    {"e": envelope_id},
                )
            )
            .mappings()
            .one()
        )
        if env["status"] not in OPEN:
            raise WetSignatureNotAllowed(facts={"status": str(env["status"])})
        signers = (await tx.session.execute(_SIGNERS, {"e": envelope_id})).mappings().all()
        mine = next((s for s in signers if s["id"] == signer_id), None)
        if mine is None:
            raise NotFound("signer")
        if not _may_sign_on_paper(cast(Mapping[str, object], mine)):
            raise WetSignatureNotAllowed(facts={"status": str(mine["status"])})
        group = int(str(mine["routing_group"]))
        if any(int(str(s["routing_group"])) < group and s["status"] != "signed" for s in signers):
            # Pub 1345: the taxpayer signs before the ERO; an earlier group signs first.
            raise WetSignatureNotAllowed(facts={"reason": "not_your_turn"})
        claimed = await tx.session.execute(
            text(
                "UPDATE envelope_import_files SET consumed_envelope_id = :e "
                "WHERE id = :id AND consumed_envelope_id IS NULL RETURNING id"
            ),
            {"e": envelope_id, "id": given.upload_id},
        )
        if claimed.scalar_one_or_none() is None:
            raise ImportFileUnavailable
        await tx.session.execute(
            text(
                "UPDATE envelope_signers SET status = 'signed', signed_at = :at, "
                "signature_method = 'handwritten', wet_recorded_by = :by WHERE id = :s"
            ),
            {"at": signed_at, "by": ctx.user_id, "s": signer_id},
        )
        result = (
            "Handwritten · paper form"
            if given.in_person_id is None
            else "Handwritten · in-person ID checked"
        )
        await tx.session.execute(
            text(
                "INSERT INTO signature_evidence (tenant_id, envelope_id, signer_id, signed_at, "
                "identity_result, signature_method, document_sha256s, package_key, "
                "package_sha256, retain_until) VALUES (:t, :e, :s, :at, :result, 'handwritten', "
                ":hashes, :key, :sha, :keep)"
            ),
            {
                "t": ctx.tenant_id,
                "e": envelope_id,
                "s": signer_id,
                "at": signed_at,
                "result": result,
                "hashes": [scan.sha256],
                "key": package.key,
                "sha": package_sha,
                "keep": keep.date(),
            },
        )
        await tx.session.execute(
            text(
                "INSERT INTO envelope_events (tenant_id, envelope_id, signer_id, kind, source, "
                "occurred_at, payload_sha256) VALUES (:t, :e, :s, "
                "'signer.wet_signature_recorded', 'firm', :at, :sha)"
            ),
            {"t": ctx.tenant_id, "e": envelope_id, "s": signer_id, "at": now, "sha": package_sha},
        )
        # The scan is the hand-signed copy, filed beside the client's other signed forms.
        await file_signed_copy(
            tx,
            tenant_id=ctx.tenant_id,
            client_id=env["client_id"],
            engagement_id=env["engagement_id"],
            work_item_id=env["work_item_id"],
            title=f"{env['title']} · hand-signed",
            stored_key=str(upload["storage_key"]),
            stored_version_id=str(upload["storage_version_id"]),
            sha256=str(upload["sha256"]),
            size_bytes=int(str(upload["size_bytes"])),
            media_type=str(upload["media_type"]),
            actor_kind=ctx.tenant.actor_kind,
            actor_id=ctx.tenant.actor_id,
        )
        tx.record(
            "signer.wet_signature_recorded",
            target=Target("envelope", envelope_id),
            after=Ref(signer_id=signer_id, package_sha256=package_sha),
        )
        tx.emit(
            EnvelopeSignerSigned(
                envelope_id=envelope_id,
                signer_id=signer_id,
                client_id=env["client_id"],
                engagement_id=env["engagement_id"],
                source_kind=str(env["source_kind"] or "envelope"),
                source_id=env["source_id"] or envelope_id,
            )
        )
        done = all(s["status"] == "signed" or s["id"] == signer_id for s in signers)
        status = "completed" if done else "partially_signed"
        await tx.session.execute(
            text(
                "UPDATE envelopes SET status = :status, completed_at = CASE WHEN :status = "
                "'completed' THEN :now ELSE completed_at END, version = version + 1, "
                "updated_at = :now WHERE id = :e"
            ),
            {"status": status, "now": now, "e": envelope_id},
        )
        if done:
            await tx.session.execute(
                text(
                    "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, "
                    "occurred_at) VALUES (:t, :e, 'envelope.completed', 'firm', :at)"
                ),
                {"t": ctx.tenant_id, "e": envelope_id, "at": now},
            )
    return done


__all__ = [
    "FAMILIES",
    "FLOOR",
    "EnvelopeFacts",
    "ImportFileUnavailable",
    "InPersonId",
    "Policy",
    "PolicyChange",
    "PolicyNotStricter",
    "PolicyStale",
    "SignerSeen",
    "WetSignature",
    "WetSignatureNotAllowed",
    "check_stricter",
    "effective_policies",
    "kba_failures_seen",
    "kba_limit",
    "list_policies",
    "record_wet_signature",
    "update_policy",
]
