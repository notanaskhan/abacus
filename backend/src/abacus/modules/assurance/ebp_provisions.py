"""A-05-T16: the EBP-02 provisions service (A-05 §3 F2; SPEC-641; DEC-2069).

A provisions review reads the plan's documents and verifies, one by one, the twenty provisions
the tests depend on (`compute/ebp/provisions.py`: the registry, the amendment rule and the SPD
comparison).

- **Start** (`POST …/ebp/plan-reviews`): a person names the document versions in order (the
  adoption agreement, the amendment when it governs, the SPD); the review is recorded
  (`ebp_plan_reviews`, review 1, 2, ...) and a section-drafter run of mode `ebp_provisions` starts
  on EBP-02. The mode's mapping gives the run those documents as D1 to D3 (masked page text); it
  suggests each provision's election (B<row>) and reference (C<row>), cited to the clause.
- **Provisions** are EBP-02's own cells: a person adopts a suggestion (C3, `workpaper_cell`), and
  **verifying** is a C3 field tick (L1) on the value cell; a tick on an earlier value is stale.
- **Sign off** waits for every provision verified: a sign-off guard on the `ebp_provisions` kind
  answers 409 `sign_off_blocked` with `facts.reason` `provisions_unverified` and how many remain.
- **Downstream** (EBP-03's entry rule, EBP-04's match formula, EBP-09's expenses clause) reads
  `verified_provisions`: only ticked values, never a draft.
- **Conflicts**: code compares the governing wording with the SPD (`compute.conflicts`) over the
  values a person enters for the SPD; only a person raises one (SHL-15 → AUD-15).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Row

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Scope, Target, uow
from abacus.modules.agents.api import (
    ModeDocument,
    ModeInputs,
    ModePage,
    SourcePaper,
    start_section_draft,
)
from abacus.modules.assurance.compute.ebp.provisions import (
    PROVISIONS,
    Provision,
    provisions_for,
)
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.evidence.api import review_material, version_view
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.review.api import (
    FieldState,
    field_states,
)
from abacus.modules.workpapers.api import CELL_TARGET, paper_of_kind

KIND: Final = "ebp_provisions"
PAPER_TARGET: Final = "workpaper"
MODE: Final = "ebp_provisions"
AUDIT_TARGET: Final = "ebp_plan_review"
UNVERIFIED: Final = "provisions_unverified"
DOCUMENT_TITLES: Final = ("Adoption agreement", "Amendment", "Summary plan description")


class ReviewInvalid(DomainInvalid):
    code = "plan_review_invalid"


@dataclass(frozen=True)
class ProvisionState:
    provision: Provision
    value: str | None
    reference: str | None
    verified: bool
    citation_count: int
    value_hash: str | None = None  # what a tick on the value signs (None before a value)


@dataclass(frozen=True)
class SignedLevel:
    level: int
    user_id: UUID
    at: datetime
    stale: bool


@dataclass(frozen=True)
class PlanReview:
    review_no: int
    provisions: tuple[ProvisionState, ...]
    workpaper_id: UUID | None = None
    sign_offs: tuple[SignedLevel, ...] = ()

    @property
    def verified(self) -> int:
        return sum(1 for p in self.provisions if p.verified)


_LATEST: Final = text(
    "SELECT review_no, document_version_ids, amendment_in_force FROM ebp_plan_reviews "
    "WHERE work_item_id = :w ORDER BY review_no DESC LIMIT 1"
)
_BY_NO: Final = text(
    "SELECT review_no, document_version_ids, amendment_in_force FROM ebp_plan_reviews "
    "WHERE work_item_id = :w AND review_no = :n"
)
_AMENDED: Final = text(
    "SELECT latest_amendment_ref IS NOT NULL FROM ebp_plans WHERE work_item_id = :w"
)
_INSERT: Final = text(
    "INSERT INTO ebp_plan_reviews (tenant_id, engagement_id, work_item_id, workpaper_id, "
    "review_no, document_version_ids, amendment_in_force, started_by) "
    "SELECT :tenant, :engagement, :w, :paper, coalesce(max(review_no), 0) + 1, "
    "CAST(:docs AS uuid[]), :amended, :user FROM ebp_plan_reviews WHERE work_item_id = :w "
    "RETURNING id, review_no"
)


async def start_review(
    ctx: AuthContext,
    work_item_id: UUID,
    document_version_ids: Sequence[UUID],
    idempotency_key: str,
) -> UUID:
    """A person starts a provisions read; the drafter run's id. The route authorised
    `workpaper.draft` and the flags; the drafter checks them again (defence in depth)."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("workpaper.draft", "role")
    if len(set(document_version_ids)) != len(document_version_ids):
        raise ReviewInvalid(facts={"field": "document_version_ids"})
    item = await assurance_item(ctx.tenant, work_item_id)
    engagement = await get_ref(ctx, item.engagement_id)
    await authorise(ctx, "workpaper.draft", engagement.resource())
    for version_id in document_version_ids:
        if (await version_view(ctx.tenant, version_id)).engagement_id != item.engagement_id:
            raise NotFound("evidence_version")
    paper = await paper_of_kind(ctx, item.engagement_id, KIND)
    async with tenant_session(ctx.tenant) as session:
        amended = bool((await session.execute(_AMENDED, {"w": work_item_id})).scalar())
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                _INSERT,
                {
                    "tenant": ctx.tenant_id,
                    "engagement": item.engagement_id,
                    "w": work_item_id,
                    "paper": paper,
                    "docs": [str(v) for v in document_version_ids],
                    "amended": amended,
                    "user": ctx.user_id,
                },
            )
        ).one()
        tx.record(
            "ebp_plan_review.started",
            target=Target(AUDIT_TARGET, row.id),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=work_item_id),
        )
    return await start_section_draft(
        ctx, item.engagement_id, paper, MODE, None, f"{idempotency_key}:{row.review_no}"
    )


async def provisions_inputs(actor: AuthContext, paper: SourcePaper) -> ModeInputs:
    """The `ebp_provisions` mode's documents: the latest review's versions as D1 to D3, masked
    page text only (fail closed: a version not yet scanned is left out)."""
    async with tenant_session(actor.tenant) as session:
        latest = (await session.execute(_LATEST, {"w": paper.work_item_id})).first()
    if latest is None:
        return ModeInputs()
    documents: list[ModeDocument] = []
    titles = DOCUMENT_TITLES if latest.amendment_in_force else DOCUMENT_TITLES[::2]
    for n, version_id in enumerate(latest.document_version_ids):
        material = await review_material(actor.tenant, version_id, sheets=False)
        if material is None or not material.pages:
            continue
        title = titles[n] if n < len(titles) else f"Document {n + 1}"
        documents.append(
            ModeDocument(
                version_id,
                title,
                tuple(ModePage(p, body) for p, body in sorted(material.pages.items())),
            )
        )
    return ModeInputs(documents=tuple(documents))


def _text_of(state: FieldState | None) -> str | None:
    if state is None or state.value is None:
        return None
    value = state.value.get("v")
    return None if value is None else str(value)


def _verified(state: FieldState) -> bool:
    """Verified: a current tick (any level) on a value that exists."""
    return bool(state.ticked_levels) and state.value is not None


async def _states(
    tenant: TenantContext, workpaper_id: UUID, rows: Sequence[Provision]
) -> dict[str, FieldState]:
    keys = [k for p in rows for k in (p.value_cell, p.reference_cell)]
    return await field_states(tenant, CELL_TARGET, workpaper_id, keys)


async def _review_row(
    tenant: TenantContext, work_item_id: UUID, review_no: int | None
) -> Row[Any] | None:  # Any: the row's columns are the query's (review_no, ids, amended)
    async with tenant_session(tenant) as session:
        if review_no is None:
            return (await session.execute(_LATEST, {"w": work_item_id})).first()
        return (await session.execute(_BY_NO, {"w": work_item_id, "n": review_no})).first()


async def review_of(ctx: AuthContext, work_item_id: UUID, review_no: int | None) -> PlanReview:
    """EBP-02's provisions for the latest review (or `review_no`, read-only b2): each row's
    adopted value and reference, and whether its value is verified now."""
    item = await assurance_item(ctx.tenant, work_item_id)
    found = await _review_row(ctx.tenant, work_item_id, review_no)
    if found is None:
        if review_no is not None:
            raise NotFound("ebp_plan_review")
        return PlanReview(0, ())
    paper = await paper_of_kind(ctx, item.engagement_id, KIND)
    rows = provisions_for(amendment_in_force=bool(found.amendment_in_force))
    states = await _states(ctx.tenant, paper, rows)
    return PlanReview(
        int(found.review_no),
        tuple(
            ProvisionState(
                p,
                _text_of(states.get(p.value_cell)),
                _text_of(states.get(p.reference_cell)),
                bool(states[p.value_cell].ticked_levels)
                and states[p.value_cell].value is not None,
                len(states[p.value_cell].citation_ids),
            )
            for p in rows
        ),
    )


async def unverified_count(tenant: TenantContext, workpaper_id: UUID, work_item_id: UUID) -> int:
    async with tenant_session(tenant) as session:
        latest = (await session.execute(_LATEST, {"w": work_item_id})).first()
    rows = provisions_for(amendment_in_force=True if latest is None else latest.amendment_in_force)
    return unverified_of(rows, await _states(tenant, workpaper_id, rows))


async def sign_off_guard(
    tenant: TenantContext, workpaper_id: UUID, work_item_id: UUID | None
) -> tuple[str, int] | None:
    """EBP-02 signs off once every provision is verified (fail closed without a work item)."""
    if work_item_id is None:
        return (UNVERIFIED, len(PROVISIONS))
    left = await unverified_count(tenant, workpaper_id, work_item_id)
    return None if left == 0 else (UNVERIFIED, left)


async def verified_provisions(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID, workpaper_id: UUID
) -> Mapping[str, str]:
    """The verified elections by provision key, for EBP-03, EBP-04 and EBP-09's engines: a value
    without a current tick is left out, so a draft is never consumed downstream."""
    del engagement_id  # the caller authorised on it
    async with tenant_session(tenant) as session:
        latest = (await session.execute(_LATEST, {"w": work_item_id})).first()
    if latest is None:
        return {}
    rows = provisions_for(amendment_in_force=latest.amendment_in_force)
    return verified_of(rows, await _states(tenant, workpaper_id, rows))


def unverified_of(rows: Sequence[Provision], states: Mapping[str, FieldState]) -> int:
    return sum(1 for p in rows if not _verified(states[p.value_cell]))


def verified_of(rows: Sequence[Provision], states: Mapping[str, FieldState]) -> dict[str, str]:
    """Only the ticked values: an untouched, drafted or since-changed value is left out."""
    out: dict[str, str] = {}
    for p in rows:
        state = states[p.value_cell]
        value = _text_of(state)
        if _verified(state) and value is not None:
            out[p.key] = value
    return out
