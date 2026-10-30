"""Duplicate uploads: accepted and flagged for a person, then resolved (T-02-T17; DEC-58 g;
T-02 §3.4 TAX-03 e; DEC-1371). PROTECTED (evidence, red).

- **Policy**: under `evidence.duplicate_review`, a client-channel upload (a client person's own,
  never the firm's on their behalf) whose bytes match a live version on the request is accepted
  and flagged: an `upload_checks` row `duplicate_hash` (outcome `problem`, the firm's audience)
  names the version it repeats by the check, never the bytes. Off, or a firm upload: 409
  `duplicate_upload` as before.
- **Resolution** (`evidence.resolve_duplicate`, a person on the request): `discard_duplicate`
  voids and hides the flagged version through P-31's path (its fulfilment voided, the request
  back to requested if it was the only one), never deleting it; `keep_newer` supersedes the older
  version the same way and keeps the flagged one. An accepted version is never discarded or
  superseded (409 `evidence_accepted`); a version is resolved once (409 `duplicate_resolved`). One
  insert-only `duplicate_resolutions` row records the decision.
"""

from __future__ import annotations

from typing import Final, Literal
from uuid import UUID

from sqlalchemy import insert, select

from abacus.kernel._flags import EVIDENCE_DUPLICATE_REVIEW
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.models import (
    DuplicateResolution,
    EvidenceVersion,
    ReviewDecision,
    UploadCheck,
)
from abacus.modules.evidence.repository import insert_checks, not_withdrawn
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.requests.api import item_ref, item_versions, withdraw_upload

ACTION: Final = "evidence.resolve_duplicate"
CHECK: Final = "duplicate_hash"
CHECKER: Final = "v1"
Decision = Literal["keep_newer", "discard_duplicate"]


class DuplicateResolved(DomainConflict):
    """The version's duplicate was already resolved."""

    code = "duplicate_resolved"


class NotADuplicate(DomainConflict):
    """The version carries no duplicate flag."""

    code = "not_a_duplicate"


class DuplicateAccepted(DomainConflict):
    """An accepted version is never discarded or superseded."""

    code = "evidence_accepted"


async def accepts_duplicates(ctx: AuthContext, on_behalf: bool) -> bool:
    """A client person's own upload, with the review flag on (firm uploads keep the 409)."""
    return (
        ctx.client and not on_behalf and await flag_enabled(ctx.tenant, EVIDENCE_DUPLICATE_REVIEW)
    )


async def repeated(tx: UnitOfWork, item_id: UUID, fingerprint: str) -> UUID | None:
    """The live version on the request with these bytes, or None."""
    ids = await item_versions(tx, item_id)
    if not ids:
        return None
    return (
        await tx.session.execute(
            select(EvidenceVersion.id)
            .where(
                EvidenceVersion.id.in_(ids),
                EvidenceVersion.fingerprint == fingerprint,
                not_withdrawn(),
            )
            .order_by(EvidenceVersion.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()


async def flag(tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> None:
    """The `duplicate_hash` check on the newly accepted version, and its audit row."""
    await insert_checks(
        tx.session,
        [
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "evidence_version_id": version_id,
                "checker_version": CHECKER,
                "document_kind": None,
                "check_code": CHECK,
                "outcome": "problem",
                "audience": "firm",
                "reason": "same_hash",
            }
        ],
    )
    tx.record(
        "evidence_version.flagged",
        target=Target("evidence_version", version_id),
        after=Ref(),  # identifiers only: the check and its checker are on the review flag
    )


async def _accepted(tx: UnitOfWork, version_id: UUID) -> bool:
    return (
        await tx.session.execute(
            select(ReviewDecision.id)
            .where(
                ReviewDecision.evidence_version_id == version_id,
                ReviewDecision.decision == "accept",
            )
            .limit(1)
        )
    ).scalar_one_or_none() is not None


async def resolve(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID, decision: Decision
) -> UUID:
    """A person's decision on a flagged duplicate; returns the version kept."""
    from abacus.modules.evidence.uploads import item_resource  # uploads imports this module

    if ctx.client:
        raise NotFound("evidence_version")
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(ACTION, "role")
    engagement = await get_ref(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        locked_engagement = await lock_ref(tx, engagement_id)
        item = await item_ref(tx, item_id, lock=True)
        if item.engagement_id != engagement.id:
            raise NotFound("request_item")
        await authorise(ctx, ACTION, item_resource(item, locked_engagement.resource()))
        version = (
            await tx.session.execute(
                select(EvidenceVersion).where(EvidenceVersion.id == version_id, not_withdrawn())
            )
        ).scalar_one_or_none()
        if version is None or version_id not in await item_versions(tx, item_id):
            raise NotFound("evidence_version")
        flagged = (
            await tx.session.execute(
                select(UploadCheck.id).where(
                    UploadCheck.evidence_version_id == version_id,
                    UploadCheck.check_code == CHECK,
                )
            )
        ).first()
        if flagged is None:
            raise NotADuplicate(facts={"evidence_version_id": str(version_id)})
        done = (
            await tx.session.execute(
                select(DuplicateResolution.id).where(DuplicateResolution.version_id == version_id)
            )
        ).first()
        if done is not None:
            raise DuplicateResolved(facts={"evidence_version_id": str(version_id)})
        others = [v for v in await item_versions(tx, item_id) if v != version_id]
        original = (
            await tx.session.execute(
                select(EvidenceVersion.id)
                .where(
                    EvidenceVersion.id.in_(others),
                    EvidenceVersion.fingerprint == version.fingerprint,
                    not_withdrawn(),
                )
                .order_by(EvidenceVersion.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if original is None:
            raise NotADuplicate(facts={"evidence_version_id": str(version_id)})
        dropped, kept = (
            (version_id, original) if decision == "discard_duplicate" else (original, version_id)
        )
        if await _accepted(tx, dropped):
            raise DuplicateAccepted(facts={"evidence_version_id": str(dropped)})
        await withdraw_upload(
            tx, evidence_version_id=dropped, withdrawn_by=ctx.user_id, item_ids=[item_id]
        )
        await tx.session.execute(
            insert(DuplicateResolution).values(
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                version_id=version_id,
                kept_version_id=kept,
                decision=decision,
                decided_by=ctx.user_id,
            )
        )
        tx.record(
            "evidence_version.duplicate_discarded"
            if decision == "discard_duplicate"
            else "evidence_version.duplicate_kept",
            target=Target("evidence_version", version_id),
            after=Ref(kept=kept, voided=dropped, request_item_id=item_id),
        )
    return kept


__all__ = [
    "ACTION",
    "CHECK",
    "Decision",
    "DuplicateAccepted",
    "DuplicateResolved",
    "NotADuplicate",
    "accepts_duplicates",
    "flag",
    "repeated",
    "resolve",
]
