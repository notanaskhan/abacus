"""The sign-off service behind `/v1/sign-offs` (P-04-T18, T19; ADR-160 clauses 2 to 4; SHL-12).

A person signs what they saw at a level the matrix allows them. The owner's facts
(`ReviewableFacts`) say what the target is now: its hash, version, preparers, required levels
and the R-SO-6 and R-SO-8 facts. Every rule answers a fixed code:

- R-SO-1 only a live human (the matrix denies agent and system; this refuses a client
  principal, a non-human actor and break-glass support first; the table's CHECK binds the
  row to the transaction's actor);
- R-SO-2 the level's matrix row: 403 `level_not_permitted`;
- R-SO-3 segregation: a preparer never signs L2 or L3 (the row's `not_preparer_of_target`),
  409 `segregation`; the EQR holds only the L5 row and the engagement partner never the L5 row;
- R-SO-4 open review notes block L2 and above: 409 `open_review_notes` with the count;
- R-SO-5 the signer's own independence (`engagements.api.independence_cleared`, ADR-164 item 4)
  and, on an attest client, the G2 gate: 409 `independence_pending`;
- R-SO-6 empty required fields 409 `incomplete`, uncited agent values 422 `uncited_change`;
- R-SO-8 an L1 on agent work records the run it adopted.

`seen_hash` differing from the target's current hash answers 409 `content_changed` and writes
nothing. A stale level is signed again as a new row (DEC-84); no row is ever updated.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from abacus.kernel.clock import now as business_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import (
    attest_of,
    engagement_resource_of,
    gate_fact,
    independence_cleared,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    TargetFacts,
    allowed_actions,
    authorise,
    engagement_role_of,
    names_of,
)
from abacus.modules.review.events import SignOffRecorded
from abacus.modules.review.issues import open_blocking
from abacus.modules.review.mfa import require_fresh
from abacus.modules.review.models import SignOff
from abacus.modules.review.notes import OPEN
from abacus.modules.review.repository import (
    insert_sign_off,
    lock_target,
    notes_of_target,
    sign_offs_of,
)
from abacus.modules.review.service import AlreadySigned, NotPrepared, SignOffInvalid
from abacus.modules.review.slots import ReviewableFacts, reviewable_facts

LevelCode = Literal["L1_preparer", "L2_reviewer", "L3_manager", "L4_partner", "L5_eqr"]
LEVEL_CODES: Final[dict[int, LevelCode]] = {
    1: "L1_preparer",
    2: "L2_reviewer",
    3: "L3_manager",
    4: "L4_partner",
    5: "L5_eqr",
}
LEVEL_OF: Final[dict[str, int]] = {code: n for n, code in LEVEL_CODES.items()}
# The level rows of the permission matrix (the plan's sign_off.l1 to l5; DEC-135).
LEVEL_ACTIONS: Final[dict[int, str]] = {
    1: "sign_off.prepare",
    2: "sign_off.review",
    3: "sign_off.manager",
    4: "sign_off.partner",
    5: "sign_off.eqr",
}
SEGREGATED: Final = frozenset({2, 3})  # never the target's preparer (R-SO-3)


@dataclass(frozen=True)
class Statement:
    version: str
    text: str


# What a signer affirms, versioned: the copy is SHL-12's (handoff spec e and state 7). A changed
# text is a new version; a sign-off records the version it was made under.
_REVIEWER = Statement(
    "reviewer-v1",
    "I reviewed this work. It is sufficient and appropriate, and its conclusions are supported.",
)
_EQR = Statement(
    "eqr-v1",
    "I objectively evaluated the significant judgments and the conclusions reached.",
)
# The preparer, manager and partner levels affirm the reviewer statement until SHL-12 gives
# them their own (DEC-400).
STATEMENTS: Final[dict[int, Statement]] = {
    1: _REVIEWER,
    2: _REVIEWER,
    3: _REVIEWER,
    4: _REVIEWER,
    5: _EQR,
}


class ContentChanged(DomainConflict):
    """The target changed since the signer saw it: nothing is written."""

    code = "content_changed"


class Segregation(DomainConflict):
    """R-SO-3: the target's preparer never signs L2 or L3 on it."""

    code = "segregation"


class OpenReviewNotes(DomainConflict):
    """R-SO-4: open review notes on the target block L2 and above."""

    code = "open_review_notes"


class IndependencePending(DomainConflict):
    """R-SO-5: the signer's independence confirmation (G2) is not on file."""

    code = "independence_pending"


class Incomplete(DomainConflict):
    """R-SO-6: required fields are still empty."""

    code = "incomplete"


class UncitedChange(DomainInvalid):
    """R-SO-6: an agent value carries no citation (INV-2)."""

    code = "uncited_change"


class LevelNotPermitted(DomainForbidden):
    """R-SO-2: the matrix does not allow the caller this level on this target."""

    code = "level_not_permitted"


def hash_out(digest: str) -> str:
    return f"sha256:{digest}"


def _hash_in(seen: str) -> str:
    return seen.removeprefix("sha256:")


_LETTERS = re.compile(r"[A-Za-z]")


def initials_of(name: str) -> str | None:
    """ "Hannah Leclerc" -> "HL": the first letter of each word, A to Z, at most four."""
    letters = [m.group(0).upper() for w in name.split() if (m := _LETTERS.search(w))]
    return "".join(letters[:4]) or None


# --- Reading -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class SignOffView:
    id: UUID
    target_type: str
    target_id: UUID
    kind: str
    level: int
    signer_user_id: UUID
    signer_name: str
    initials: str
    signed_at: datetime
    content_hash: str
    version_no: int
    statement_version: str
    adopted_run_id: UUID | None
    adopted_run_number: int | None
    stale: bool


@dataclass(frozen=True)
class LadderLevel:
    level: int
    required: bool
    latest: SignOffView | None


@dataclass(frozen=True)
class Check:
    code: str
    result: Literal["pass", "fail", "warn"]
    facts: dict[str, str | int | bool | None]
    refs: list[tuple[str, UUID]]


@dataclass(frozen=True)
class Ladder:
    facts: ReviewableFacts
    levels: list[LadderLevel]
    allowed_actions: list[str]


@dataclass(frozen=True)
class Eligibility:
    facts: ReviewableFacts
    level: int
    levels_allowed: list[int]
    ladder: list[LadderLevel]
    checks: list[Check]
    eligible: bool
    statement: Statement


async def _target(
    ctx: AuthContext, target_type: str, target_id: UUID
) -> tuple[ReviewableFacts, Resource]:
    facts = await reviewable_facts(ctx.tenant, target_type, target_id)
    resource = await engagement_resource_of(ctx.tenant, facts.engagement_id)
    return facts, resource


def _preparers(facts: ReviewableFacts, rows: list[SignOff]) -> frozenset[UUID]:
    """The owner's preparers and everyone who has signed L1 on the target, on any content."""
    return facts.preparer_user_ids | {r.signed_by for r in rows if r.level == 1}


def _with_preparers(resource: Resource, preparers: frozenset[UUID]) -> Resource:
    return replace(resource, target=TargetFacts(preparer_user_ids=preparers))


async def _rows(tenant: TenantContext, target_type: str, target_id: UUID) -> list[SignOff]:
    async with tenant_session(tenant) as session:
        return list(await sign_offs_of(session, target_type, [target_id]))


async def _ladder(
    tenant: TenantContext, facts: ReviewableFacts, rows: list[SignOff]
) -> list[LadderLevel]:
    names = await names_of(sorted({r.signed_by for r in rows}))
    out: list[LadderLevel] = []
    for level in LEVEL_CODES:
        newest = next((r for r in rows if r.level == level), None)  # rows are newest first
        view = None
        if newest is not None:
            name = names.get(newest.signed_by, "")
            view = SignOffView(
                id=newest.id,
                target_type=newest.target_type,
                target_id=newest.target_id,
                kind=newest.kind,
                level=level,
                signer_user_id=newest.signed_by,
                signer_name=name,
                initials=newest.initials or initials_of(name) or "",
                signed_at=newest.created_at,
                content_hash=hash_out(newest.content_hash),
                version_no=newest.version_no or facts.version_no,
                statement_version=newest.statement_version or "",
                adopted_run_id=newest.adopted_run_id,
                adopted_run_number=(
                    facts.adopted_run_number
                    if newest.adopted_run_id is not None
                    and newest.adopted_run_id == facts.adopted_run_id
                    else None
                ),
                stale=newest.content_hash != facts.content_hash,
            )
        out.append(LadderLevel(level, level in facts.required_levels, view))
    return out


async def _levels_allowed(
    ctx: AuthContext, resource: Resource, preparers: frozenset[UUID]
) -> list[int]:
    """The levels the caller could sign now, by every layer but fresh MFA, which is asked for at
    the moment of signing (`allowed_actions`, DEC-505)."""
    if not _live_human(ctx) or "sign_off.create" not in await allowed_actions(
        ctx, resource, ["sign_off.create"]
    ):
        return []
    target = _with_preparers(resource, preparers)
    held = await allowed_actions(ctx, target, list(LEVEL_ACTIONS.values()))
    return [n for n, action in LEVEL_ACTIONS.items() if action in held]


async def ladder(ctx: AuthContext, target_type: str, target_id: UUID) -> Ladder:
    """SHL-12: the ladder per level, with computed staleness. `sign_off.read` on the target's
    engagement (walls answer 404)."""
    facts, resource = await _target(ctx, target_type, target_id)
    await authorise(ctx, "sign_off.read", resource)
    rows = await _rows(ctx.tenant, target_type, target_id)
    levels = await _ladder(ctx.tenant, facts, rows)
    allowed = await _levels_allowed(ctx, resource, _preparers(facts, rows))
    actions = [f"sign_off.{LEVEL_CODES[n]}" for n in allowed]
    stale = {lv.level for lv in levels if lv.latest is not None and lv.latest.stale}
    actions += [f"sign_off.resign.{LEVEL_CODES[n]}" for n in allowed if n in stale]
    return Ladder(facts, levels, actions)


async def _open_notes(tenant: TenantContext, target_id: UUID) -> list[UUID]:
    async with tenant_session(tenant) as session:
        notes = await notes_of_target(session, target_id)
    return [n.id for n in notes if n.status in OPEN]


async def _independent(ctx: AuthContext, engagement_id: UUID) -> bool:
    """R-SO-5 (P-04-T19): the signer's own confirmation for this engagement, on every client;
    on an attest client (unknown counts as attest) the G2 gate must be met too."""
    if not await independence_cleared(ctx.tenant, engagement_id, ctx.user_id):
        return False
    if await attest_of(ctx.tenant, engagement_id) is False:
        return True
    return (await gate_fact(ctx.tenant, engagement_id, "G2")).met


async def eligibility(
    ctx: AuthContext, target_type: str, target_id: UUID, level: int
) -> Eligibility:
    """SHL-12 a to h: target, levels allowed, checks and the statement for one level."""
    facts, resource = await _target(ctx, target_type, target_id)
    await authorise(ctx, "sign_off.read", resource)
    rows = await _rows(ctx.tenant, target_type, target_id)
    preparers = _preparers(facts, rows)
    levels = await _ladder(ctx.tenant, facts, rows)
    allowed = await _levels_allowed(ctx, resource, preparers)
    notes = await _open_notes(ctx.tenant, target_id) if level > 1 else []
    independent = await _independent(ctx, facts.engagement_id)
    segregated = level in SEGREGATED and ctx.user_id in preparers
    blocking = await open_blocking(
        ctx.tenant,
        target_id,
        # The final level, or any above it a firm may ask for, is final approval.
        "final_approval" if level >= max(facts.required_levels) else "sign_off",
    )
    checks = [
        # P-04-T30: open issues that block this level read as one check, however many there are.
        Check(
            "open_issues",
            "fail" if blocking else "pass",
            {"count": len(blocking)},
            [("issue", i) for i in blocking],
        ),
        Check(
            "open_review_notes",
            "fail" if notes else "pass",
            {"count": len(notes)},
            [("review_note", n) for n in notes],
        ),
        Check("independence", "pass" if independent else "fail", {}, []),
        Check("segregation", "fail" if segregated else "pass", {}, []),
        Check(
            "all_cited",
            "fail" if facts.uncited_count or facts.incomplete_count else "pass",
            {
                "cited": facts.cited_count,
                "cells": facts.cell_count,
                "uncited": facts.uncited_count,
                "empty": facts.incomplete_count,
            },
            [],
        ),
    ]
    preparer = levels[0].latest
    prepared = preparer is not None and not preparer.stale
    eligible = (
        level in allowed
        and all(c.result != "fail" for c in checks)
        and (level == 1 or prepared)
        and not facts.locked
    )
    return Eligibility(facts, level, allowed, levels, checks, eligible, STATEMENTS[level])


# --- Signing -----------------------------------------------------------------------------------


async def _view_of(row: SignOff, facts: ReviewableFacts) -> SignOffView:
    name = (await names_of([row.signed_by])).get(row.signed_by, "")
    return SignOffView(
        id=row.id,
        target_type=row.target_type,
        target_id=row.target_id,
        kind=row.kind,
        level=row.level,
        signer_user_id=row.signed_by,
        signer_name=name,
        initials=row.initials or initials_of(name) or "",
        signed_at=row.created_at,
        content_hash=hash_out(row.content_hash),
        version_no=row.version_no or facts.version_no,
        statement_version=row.statement_version or "",
        adopted_run_id=row.adopted_run_id,
        adopted_run_number=None,
        stale=row.content_hash != facts.content_hash,
    )


def _live_human(ctx: AuthContext) -> bool:
    """INV-1 (`require_live_human`): a person's own act, never an agent, the platform, a client
    principal or a break-glass support session."""
    return (
        isinstance(cast(object, ctx), AuthContext)  # an agent principal reaches a route too
        and not ctx.client
        and ctx.tenant.actor_kind == "human"
        and not ctx.is_support
    )


live_human = _live_human  # P-04-T22: bulk sign-off asks the same first


async def _authorise_level(
    ctx: AuthContext, level: int, resource: Resource, preparers: frozenset[UUID]
) -> None:
    try:
        await authorise(ctx, LEVEL_ACTIONS[level], _with_preparers(resource, preparers))
    except Forbidden as denied:
        if denied.layer == "independence":
            raise IndependencePending(facts={"level": LEVEL_CODES[level]}) from None
        if denied.layer == "condition" and level in SEGREGATED and ctx.user_id in preparers:
            raise Segregation(facts={"level": LEVEL_CODES[level]}) from None
        if denied.layer in ("role", "condition"):
            raise LevelNotPermitted(facts={"level": LEVEL_CODES[level]}) from None
        raise


async def sign_target(
    ctx: AuthContext,
    target_type: str,
    target_id: UUID,
    level: int,
    seen_hash: str,
    statement_version: str,
    kind: Literal["ladder", "field_tick", "final_approval"] = "ladder",
    *,
    bulk_request_id: UUID | None = None,
) -> SignOffView:
    """`POST /v1/sign-offs`: one insert-only row, audited `sign_off.recorded` and announced on
    the outbox. R-SO-1 first: nobody but a live person reaches the rules. A bulk item
    (P-04-T22) passes its request's id: the row records it, and a row that request already wrote
    for this target and level is answered again rather than refused."""
    if not _live_human(ctx):
        raise Forbidden("sign_off.create", "role")
    require_fresh(ctx)  # DEC-505: `sign_off.create` holds `mfa_recent`; answer the fixed code
    if kind != "ladder":
        # Field ticks are P-04-T35's and final approval P-04-T31's; until then only the ladder.
        raise SignOffInvalid(facts={"field": "kind"})
    facts, resource = await _target(ctx, target_type, target_id)
    await authorise(ctx, "sign_off.create", resource)
    async with uow(ctx.tenant) as tx:
        # One signer per target at a time (security review M1, L4): the rows, the owner's facts
        # and the insert are read and written under the same lock, so two levels signed at once
        # each see the other.
        await lock_target(tx.session, target_type, target_id)
        facts = await reviewable_facts(ctx.tenant, target_type, target_id)
        rows = list(await sign_offs_of(tx.session, target_type, [target_id]))
        if bulk_request_id is not None:
            done = next(
                (
                    r
                    for r in rows
                    if r.bulk_request_id == bulk_request_id
                    and r.level == level
                    and r.signed_by == ctx.user_id
                ),
                None,
            )
            if done is not None:
                return await _view_of(done, facts)
        preparers = _preparers(facts, rows)
        await _authorise_level(ctx, level, resource, preparers)
        if not await _independent(ctx, facts.engagement_id):
            raise IndependencePending(facts={"level": LEVEL_CODES[level]})
        if facts.locked:
            raise SignOffInvalid(facts={"field": "locked"})
        if _hash_in(seen_hash) != facts.content_hash:
            raise ContentChanged(facts={"version_no": facts.version_no})
        if statement_version != STATEMENTS[level].version:
            raise SignOffInvalid(facts={"field": "statement_version"})
        if facts.incomplete_count:
            raise Incomplete(facts={"count": facts.incomplete_count})
        if facts.uncited_count:
            raise UncitedChange(facts={"count": facts.uncited_count})
        await _rules(tx, ctx, facts, rows, level, preparers)
        return await _insert(
            tx, ctx, facts, resource, level, kind, statement_version, bulk_request_id
        )


async def _rules(
    tx: UnitOfWork,
    ctx: AuthContext,
    facts: ReviewableFacts,
    rows: list[SignOff],
    level: int,
    preparers: frozenset[UUID],
) -> None:
    newest = {lv: next((r for r in rows if r.level == lv), None) for lv in LEVEL_CODES}
    mine = newest[level]
    if (
        mine is not None
        and mine.content_hash == facts.content_hash
        and mine.signed_by == ctx.user_id
    ):
        raise AlreadySigned(facts={"level": LEVEL_CODES[level]})
    if level > 1:
        notes = await notes_of_target(tx.session, facts.target_id)
        count = sum(1 for n in notes if n.status in OPEN)
        if count:
            raise OpenReviewNotes(facts={"count": count})
        preparer = newest[1]
        if preparer is None or preparer.content_hash != facts.content_hash:
            raise NotPrepared(facts={"level": LEVEL_CODES[level]})
    if level in SEGREGATED and ctx.user_id in preparers:  # also the matrix (R-SO-3)
        raise Segregation(facts={"level": LEVEL_CODES[level]})
    # R-SO-3 the other way round (security review M1, L2): whoever reviewed a target (L2, L3)
    # never prepares it, and its EQR (L5) and its L1 to L4 signers are never the same person,
    # whatever their role is now. Any content counts: a role held once on a target stays held.
    mine_levels = {r.level for r in rows if r.signed_by == ctx.user_id}
    if level == 1 and mine_levels & SEGREGATED:
        raise Segregation(facts={"level": LEVEL_CODES[level]})
    if (level == 5 and mine_levels & {1, 2, 3, 4}) or (level < 5 and 5 in mine_levels):
        raise Segregation(facts={"level": LEVEL_CODES[level]})


async def _insert(
    tx: UnitOfWork,
    ctx: AuthContext,
    facts: ReviewableFacts,
    resource: Resource,
    level: int,
    kind: str,
    statement_version: str,
    bulk_request_id: UUID | None = None,
) -> SignOffView:
    name = (await names_of([ctx.user_id])).get(ctx.user_id, "")
    initials = initials_of(name)
    role = await engagement_role_of(ctx.tenant, facts.engagement_id, ctx.user_id)
    adopted = facts.adopted_run_id if level == 1 else None
    now = await business_now(ctx.tenant)
    sign_off_id = await insert_sign_off(
        tx.session,
        tenant_id=ctx.tenant_id,
        engagement_id=facts.engagement_id,
        target_type=facts.target_type,
        target_id=facts.target_id,
        level=level,
        content_hash=facts.content_hash,
        signed_by=ctx.user_id,
        kind=kind,
        work_item_id=facts.work_item_id,
        initials=initials,
        engagement_role_at_sign=role,
        version_no=max(facts.version_no, 1),
        statement_version=statement_version,
        adopted_run_id=adopted,
        independence_checked_at=now,
        bulk_request_id=bulk_request_id,
    )
    tx.record(
        "sign_off.recorded",
        target=Target(facts.target_type, facts.target_id),
        after=Ref(level=level, content_hash=facts.content_hash, sign_off=sign_off_id),
        scope=Scope(engagement_id=facts.engagement_id, work_item_id=facts.work_item_id),
    )
    tx.emit(
        SignOffRecorded(
            sign_off_id=sign_off_id,
            engagement_id=facts.engagement_id,
            target_type=facts.target_type,
            target_id=facts.target_id,
            level=level,
            signed_by=ctx.user_id,
        )
    )
    return SignOffView(
        id=sign_off_id,
        target_type=facts.target_type,
        target_id=facts.target_id,
        kind=kind,
        level=level,
        signer_user_id=ctx.user_id,
        signer_name=name,
        initials=initials or "",
        signed_at=now,
        content_hash=hash_out(facts.content_hash),
        version_no=max(facts.version_no, 1),
        statement_version=statement_version,
        adopted_run_id=adopted,
        adopted_run_number=facts.adopted_run_number if adopted is not None else None,
        stale=False,
    )


# --- Field ticks (P-04-T35; ADR-160 clause 5; SHL-09) ------------------------------------------


@dataclass(frozen=True)
class FieldNow:
    """A field as its tick sees it: its `field` target id, current hash and whether the current
    value is unsupported (an agent value without a verified citation)."""

    field_id: UUID
    content_hash: str
    unsupported: bool


async def tick_field(
    ctx: AuthContext,
    target_type: str,
    target_id: UUID,
    field_key: str,
    level: int,
    seen_hash: str,
    current: Callable[[UnitOfWork], Awaitable[FieldNow | None]],
) -> UUID:
    """`POST /v1/fields/…/ticks`, "Sign off field": a `field_tick` sign-off at L1 or L2 on the
    field's `field` target, bound to the value's hash. A person only (INV-1); the owner target's
    engagement authorises `field.sign_off`. An unsupported value is 422 `uncited_change` ("Add a
    reference before signing off", INV-2); a moved hash is 409 `content_changed`. The same person
    never ticks a value at both levels (R-SO-3)."""
    if not _live_human(ctx):
        raise Forbidden("field.sign_off", "role")
    if level not in (1, 2):
        raise SignOffInvalid(facts={"field": "level"})
    facts, resource = await _target(ctx, target_type, target_id)
    resource = replace(resource, work_item_id=facts.work_item_id)
    await authorise(ctx, "field.sign_off", resource)
    if not await _independent(ctx, facts.engagement_id):
        raise IndependencePending(facts={"level": LEVEL_CODES[level]})
    async with uow(ctx.tenant) as tx:
        now_field = await current(tx)
        if now_field is None:
            raise UncitedChange(facts={"count": 1})
        await lock_target(tx.session, "field", now_field.field_id)
        if now_field.unsupported:
            raise UncitedChange(facts={"count": 1})
        if _hash_in(seen_hash) != now_field.content_hash:
            raise ContentChanged(facts={"version_no": 1})
        rows = [
            r
            for r in await sign_offs_of(tx.session, "field", [now_field.field_id])
            if r.kind == "field_tick" and r.content_hash == now_field.content_hash
        ]
        if any(r.signed_by == ctx.user_id and r.level == level for r in rows):
            raise AlreadySigned(facts={"level": LEVEL_CODES[level]})
        if any(r.signed_by == ctx.user_id and r.level != level for r in rows):
            raise Segregation(facts={"level": LEVEL_CODES[level]})
        field_facts = replace(
            facts,
            target_type="field",
            target_id=now_field.field_id,
            content_hash=now_field.content_hash,
            adopted_run_id=None,
        )
        view = await _insert(tx, ctx, field_facts, resource, level, "field_tick", FIELD_STATEMENT)
    return view.id


# A field tick carries no ladder statement (the tray shows none); a fixed marker keeps the
# column's meaning: what the person signed is the field's hash.
FIELD_STATEMENT: Final = "field_tick.v1"
