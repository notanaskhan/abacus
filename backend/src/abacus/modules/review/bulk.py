"""Bulk sign-off (P-04-T22, TASK-1401; R-SO-7; ADR-160 clause 4; SHL-12 f; DEC-500, DEC-501).

Reviewers sign several targets at one level in one request. Each item is decided on its own,
through the one sign-off path (`sign_offs.sign_target`: its own unit of work, target lock and
every R-SO rule), so one item's refusal never undoes another's signature. A refused item is
excluded with the fixed code the single sign-off would answer; a target the caller may not see
(unknown, walled, another firm's) is `level_not_permitted`, so an exclusion never tells a hidden
target from a missing one.

`Idempotency-Key` (P-36): the first answer for (tenant, actor, route, key) is stored with a hash
of the request; a replay with the same key and body returns it, the same key with another body is
422 `idempotency_key_reused`. Rows carry `bulk_request_id` (derived from the tenant, the signer and
the key): a concurrent duplicate that reaches a target the first already signed reports that row
as signed, so both answers agree.

`sign_off.bulk` holds `mfa_recent: required` (DEC-501): a stale second factor answers 403
`mfa_required` before anything is signed. A caller who holds `sign_off.bulk` on none of the
targets' engagements (staff, or targets they can't see) is refused the whole request (403).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import MFA_RECENT, AuthContext, Forbidden, authorise
from abacus.modules.review.decisions import MfaRequired
from abacus.modules.review.service import SignOffInvalid
from abacus.modules.review.sign_offs import LEVEL_CODES, live_human, sign_target
from abacus.modules.review.slots import UnregisteredKind, reviewable_facts

ROUTE: Final = "sign_off.bulk"
_NAMESPACE: Final = uuid.UUID("2f0a4f8e-7c51-4f6e-9a0d-1b5c8e3d6a27")
# The exclusion codes (contract `ExclusionCode`): the single sign-off's fixed codes (§6).
# Anything else is reported as `level_not_permitted`, never as free text.
EXCLUSIONS: Final = frozenset(
    {
        "content_changed",
        "segregation",
        "open_review_notes",
        "independence_pending",
        "incomplete",
        "uncited_change",
        "level_not_permitted",
        "not_prepared",
        "already_signed",
        "sign_off_invalid",
    }
)


@dataclass(frozen=True)
class BulkTarget:
    target_type: str
    target_id: UUID
    seen_hash: str


@dataclass(frozen=True)
class BulkItem:
    target_type: str
    target_id: UUID
    ok: bool
    sign_off_id: UUID | None
    detail: str | None


@dataclass(frozen=True)
class BulkResult:
    results: list[BulkItem]
    signed: int
    excluded: int


def bulk_request_id(ctx: AuthContext, key: str) -> UUID:
    """The id a bulk request's rows carry: per firm, signer and key, never the key itself."""
    return uuid.uuid5(_NAMESPACE, f"{ctx.tenant_id}:{ctx.user_id}:{key}")


def _exclusion(error: Exception) -> str:
    code = getattr(error, "code", None)
    return code if isinstance(code, str) and code in EXCLUSIONS else "level_not_permitted"


async def _sign_one(
    ctx: AuthContext, target: BulkTarget, level: int, statement: str, request: UUID
) -> BulkItem:
    def excluded(code: str) -> BulkItem:
        return BulkItem(target.target_type, target.target_id, False, None, code)

    try:
        facts = await reviewable_facts(ctx.tenant, target.target_type, target.target_id)
        resource = await engagement_resource_of(ctx.tenant, facts.engagement_id)
        await authorise(ctx, ROUTE, resource)
    except (NotFound, UnregisteredKind, Forbidden):
        return excluded("level_not_permitted")
    try:
        signed = await sign_target(
            ctx,
            target.target_type,
            target.target_id,
            level,
            target.seen_hash,
            statement,
            bulk_request_id=request,
        )
    except (DomainConflict, DomainInvalid, DomainForbidden, Forbidden, NotFound) as refused:
        return excluded(_exclusion(refused))
    return BulkItem(target.target_type, target.target_id, True, signed.id, None)


async def _reviewer_somewhere(ctx: AuthContext, targets: list[BulkTarget]) -> bool:
    """R-SO-7, reviewers only: the caller holds `sign_off.bulk` on at least one target's
    engagement (a replay is checked again). A request naming only targets the caller may not
    bulk-sign, may not see or that don't exist is refused whole, alike."""
    seen: set[UUID] = set()
    for target in targets:
        try:
            facts = await reviewable_facts(ctx.tenant, target.target_type, target.target_id)
        except (NotFound, UnregisteredKind):
            continue
        if facts.engagement_id in seen:
            continue
        seen.add(facts.engagement_id)
        try:
            await authorise(
                ctx, ROUTE, await engagement_resource_of(ctx.tenant, facts.engagement_id)
            )
        except (NotFound, Forbidden):
            continue
        return True
    return False


async def bulk_sign(
    ctx: AuthContext,
    *,
    targets: list[BulkTarget],
    level: int,
    statement_version: str,
    idempotency_key: str,
) -> BulkResult:
    """`POST /v1/sign-offs:bulk`: each target signed or excluded on its own; a replay with the
    same key returns the stored result."""
    if not live_human(ctx):
        raise Forbidden(ROUTE, "role")
    if ctx.mfa_at is None or system_now() - ctx.mfa_at > MFA_RECENT:
        raise MfaRequired(facts={"max_age_s": int(MFA_RECENT.total_seconds())})
    if len({(t.target_type, t.target_id) for t in targets}) != len(targets):
        raise SignOffInvalid(facts={"field": "targets"})
    if not await _reviewer_somewhere(ctx, targets):
        raise Forbidden(ROUTE, "role")
    request = bulk_request_id(ctx, idempotency_key)

    async def run() -> tuple[int, dict[str, object]]:
        items = [await _sign_one(ctx, t, level, statement_version, request) for t in targets]
        return 200, {
            "results": [
                {
                    "target_type": i.target_type,
                    "target_id": str(i.target_id),
                    "ok": i.ok,
                    "sign_off_id": str(i.sign_off_id) if i.sign_off_id else None,
                    "detail": i.detail,
                }
                for i in items
            ]
        }

    stored = await idempotent(
        ctx.tenant,
        route=ROUTE,
        key=idempotency_key,
        body={
            "level": LEVEL_CODES[level],
            "statement_version": statement_version,
            "targets": [
                {"type": t.target_type, "id": str(t.target_id), "seen": t.seen_hash}
                for t in targets
            ],
        },
        run=run,
    )
    raw = cast(list[dict[str, object]], stored.body["results"])
    results = [
        BulkItem(
            target_type=str(r["target_type"]),
            target_id=UUID(str(r["target_id"])),
            ok=bool(r["ok"]),
            sign_off_id=UUID(str(r["sign_off_id"])) if r.get("sign_off_id") else None,
            detail=cast(str | None, r.get("detail")),
        )
        for r in raw
    ]
    signed = sum(1 for r in results if r.ok)
    return BulkResult(results, signed, len(results) - signed)
