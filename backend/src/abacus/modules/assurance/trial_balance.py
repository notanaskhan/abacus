"""The AUD-06 trial balance read model and actions (SPEC-309; TASK-320; A-02 §4.1).

Authorises on the engagement, then asks `ledger.api` for the figures: the ledger computes every
total, balance check, leadsheet and Δ% (ADR-050). Adoption is human only (the matrix denies the
agent; the database CHECK agrees). Names come from the engagement team, never from the ledger.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import uow
from abacus.modules.engagements.api import assurance_item_id, get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, authorise, engagement_team
from abacus.modules.ledger.api import (
    AnnotationEdit,
    Candidate,
    Leadsheet,
    TrialBalanceSummary,
    TrialBalanceView,
    adopt_trial_balance,
    adopt_version,
    annotate,
    candidates,
    engagement_trial_balances,
    leadsheets,
    review_digests,
    trial_balance_authors,
    trial_balance_view,
)
from abacus.modules.review.api import (
    LevelState,
    Reviewable,
    ReviewableFacts,
    record_sign_off,
    sign_off_states,
)
from abacus.modules.workpapers.api import tie_digests

_WP_REF: Final = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,19}$")


class NoAssuranceItem(DomainConflict):
    code = "no_assurance_item"


class AnnotationInvalid(DomainInvalid):
    code = "annotation_invalid"


@dataclass(frozen=True)
class Overview:
    trial_balances: list[TrialBalanceSummary]
    snapshots: list[Candidate]


@dataclass(frozen=True)
class Named:
    view: TrialBalanceView
    names: dict[UUID, str]


async def overview(ctx: AuthContext, engagement_id: UUID) -> Overview:
    """AC-1: the engagement's trial balances and the entity's snapshots to adopt from."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.read", ref.resource())
    return Overview(
        await engagement_trial_balances(ctx.tenant, engagement_id),
        await candidates(ctx.tenant, engagement_id, ref.client_entity_id, None),
    )


async def adopt(
    ctx: AuthContext,
    engagement_id: UUID,
    snapshot_id: UUID,
    prior_snapshot_id: UUID | None,
    label: str,
    display_unit: str,
) -> UUID:
    """AC-1: adopt a snapshot of the engagement's entity as version 1."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "trial_balance.adopt", ref.resource())
        item = await assurance_item_id(ctx.tenant, engagement_id)
        if item is None:
            raise NoAssuranceItem(str(engagement_id))
        return await adopt_trial_balance(
            tx,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            work_item_id=item,
            client_entity_id=ref.client_entity_id,
            snapshot_id=snapshot_id,
            prior_snapshot_id=prior_snapshot_id,
            label=label,
            display_unit=display_unit,
            user_id=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )


async def new_version(
    ctx: AuthContext,
    engagement_id: UUID,
    tb_id: UUID,
    snapshot_id: UUID,
    prior_snapshot_id: UUID | None,
    reason: str,
    seen_version: int,
) -> int:
    """AC-7: adopt a newer snapshot as the next version, with a reason."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "trial_balance.adopt", ref.resource())
        return await adopt_version(
            tx,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            tb_id=tb_id,
            snapshot_id=snapshot_id,
            prior_snapshot_id=prior_snapshot_id,
            reason=reason,
            seen_version=seen_version,
            user_id=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )


async def view(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID, version_no: int | None, layer: str
) -> Named:
    """AC-2, AC-4: the lines, totals and balance of a version, with who adopted each version."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.read", ref.resource())
    found = await trial_balance_view(ctx.tenant, engagement_id, tb_id, version_no, layer)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    return Named(found, names)


async def sheets(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID, version_no: int | None, layer: str
) -> list[Leadsheet]:
    """AC-5: leadsheets by audit area; accounts without an area are under Unassigned. Final
    needs an adjustment source (`layer_unavailable` otherwise)."""
    found = await view(ctx, engagement_id, tb_id, version_no, layer)
    return leadsheets(found.view.lines, layer)


async def newer(ctx: AuthContext, engagement_id: UUID, tb_id: UUID) -> list[Candidate]:
    """AC-7: snapshots for the same entity with their code-computed difference."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.read", ref.resource())
    return await candidates(ctx.tenant, engagement_id, ref.client_entity_id, tb_id)


async def set_annotations(
    ctx: AuthContext,
    engagement_id: UUID,
    tb_id: UUID,
    edits: Sequence[AnnotationEdit],
    reason: str | None,
) -> int:
    """An account's audit area and working-paper reference."""
    clean: list[AnnotationEdit] = []
    seen: set[str] = set()
    for e in edits:
        area = (e.area or "").strip() or None
        wp = (e.wp_ref or "").strip().upper() or None
        code = e.account_code.strip()
        if not 1 <= len(code) <= 64 or code in seen:
            raise AnnotationInvalid("account_code")
        if (area is not None and len(area) > 120) or (wp is not None and not _WP_REF.match(wp)):
            raise AnnotationInvalid("value")
        seen.add(code)
        clean.append(AnnotationEdit(code, area, wp))
    note = (reason or "").strip() or None
    if note is not None and len(note) > 500:
        raise AnnotationInvalid("reason")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "trial_balance.annotate", ref.resource())
        return await annotate(
            tx,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            tb_id=tb_id,
            edits=clean,
            reason=note,
            user_id=ctx.user_id,
        )


# --- Review (SPEC-313; TASK-331) --------------------------------------------------------------

TARGET = "trial_balance"


@dataclass(frozen=True)
class _Signed:
    summary: TrialBalanceSummary
    digest: str


async def signed_digests(tenant: TenantContext, engagement_id: UUID) -> list[_Signed]:
    """What a trial balance's sign-off approves (A-02-T17; SPEC-333 AC-13): the ledger's digest
    of its current version and annotations, and, when it has tie-out checks, their definitions
    and issue links (`workpapers.api.tie_digests`). A trial balance without checks keeps the
    ledger's digest, so its existing sign-offs stay current."""
    found = await review_digests(tenant, engagement_id)
    ties = await tie_digests(tenant, [d.summary.id for d in found])
    out: list[_Signed] = []
    for d in found:
        tie = ties.get(d.summary.id)
        digest = (
            d.digest
            if tie is None
            else hashlib.sha256(f"{d.digest}|ties|{tie}".encode()).hexdigest()
        )
        out.append(_Signed(d.summary, digest))
    return out


async def tb_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    """Each trial balance with what a sign-off approves, for the matrix and G5."""
    return [
        Reviewable(
            TARGET,
            d.summary.id,
            f"TB {d.summary.period_end.isoformat()}",
            f"Trial balance ({d.summary.label}, v{d.summary.current_version_no})",
            d.digest,
            True,
        )
        for d in await signed_digests(tenant, engagement_id)
    ]


async def tb_facts(tenant: TenantContext, tb_id: UUID) -> ReviewableFacts | None:
    """P-04-T15: a trial balance's facts for the sign-off rules. Its preparers are everyone who
    adopted a version of it or annotated it (the ledger's own records)."""
    authors = await trial_balance_authors(tenant, tb_id)
    if authors is None:
        return None
    digest = next(
        (
            d.digest
            for d in await signed_digests(tenant, authors.engagement_id)
            if d.summary.id == tb_id
        ),
        None,
    )
    if digest is None:
        return None
    return ReviewableFacts(
        TARGET,
        tb_id,
        authors.engagement_id,
        digest,
        authors.version_no,
        authors.authors,
        label="Trial Balance",  # P-04-T18: SHL-12's card (the handoff's label)
    )


async def tb_levels(ctx: AuthContext, engagement_id: UUID, tb_id: UUID) -> list[LevelState]:
    digests = {d.summary.id: d.digest for d in await signed_digests(ctx.tenant, engagement_id)}
    if tb_id not in digests:
        raise NotFound("trial_balance")
    return (await sign_off_states(ctx.tenant, TARGET, [tb_id], {tb_id: digests[tb_id]}))[tb_id]


async def sign_off_tb(ctx: AuthContext, engagement_id: UUID, tb_id: UUID, level: int) -> None:
    """Sign the trial balance's current version and annotations at a level."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        digests = {d.summary.id: d.digest for d in await signed_digests(ctx.tenant, engagement_id)}
        if tb_id not in digests:
            raise NotFound("trial_balance")
        await record_sign_off(
            tx, ctx, ref.resource(), engagement_id, TARGET, tb_id, level, digests[tb_id]
        )
