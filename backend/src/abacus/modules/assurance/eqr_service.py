"""The EQR service (A-07-T18; A-07 §3.1; SQMS 2; SPEC-644 AUD-18; DF-05).

- **Open on assignment.** When ENG-05's quality owner records an EQR as eligible, a review opens
  for each of the engagement's assurance work items, after the eligibility is checked again here
  (P-07): not on the team, not the engagement partner, outside the cooling-off window. The checks
  are kept on the review (`eligibility_snapshot`). The checklist comes from the firm's template
  through `register_eqr_checklist_template`; with none registered the review cannot open (409
  `eqr_template_missing`, fail closed): A-07-T22 brings the template's import.
- **Digest.** Built by code from the engagement partner's decided cards (A-06-T23's read): one card
  per decision with its question, option and date, and a SHA-256 of the snapshot. A rebuild
  supersedes the cards it replaces; a card the EQR already reviewed is replaced only if it moved.
- **The EQR's own acts** (mark a card reviewed, update a checklist item, concur) are the assigned
  EQR's only: anyone else gets 403 `eqr_only`. EQR notes are review notes on the review
  (`target_type = eqr_review`): the EQR raises and clears them, the EP or manager answers.
- **Concur (G6)** is refused while a checklist item is not done (409 `checklist_incomplete`) or an
  EQR note is open (409 `eqr_notes_open`), without the not-involved attestation, without a second
  factor in the last 15 minutes (401 `mfa_required`), and for any actor but a live person (five
  layers: matrix `function_in(eqr)`, this check, the row's actor CHECK, the human-only audit
  action `eqr.concurred`, the transaction actor). It writes the v2 concurrence row, marks the
  review concurred, and tells the engagement partners (`eqr.concurred_v2`).
- **Request EQR…** (DF-05) from AUD-23 tells the assigned EQR the report waits on them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated, ClassVar, Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import eqr_eligibility, get_ref
from abacus.modules.identity.api import AuthContext, authorise, team_of
from abacus.modules.review.api import decided_cards, open_notes

MFA_WINDOW: Final = timedelta(minutes=15)
REVIEW_TARGET: Final = "eqr_review"
_PARTNER_ROLES: Final = frozenset({"engagement_partner"})


class EqrOnly(DomainForbidden):
    """Only the assigned EQR may do this (SQMS 2)."""

    code = "eqr_only"


class ChecklistIncomplete(DomainConflict):
    code = "checklist_incomplete"


class EqrNotesOpen(DomainConflict):
    code = "eqr_notes_open"


class EqrNotEligible(DomainConflict):
    code = "eqr_not_eligible"


class EqrTemplateMissing(DomainConflict):
    code = "eqr_template_missing"


class AlreadyConcurred(DomainConflict):
    code = "eqr_already_concurred"


class StaleItem(DomainConflict):
    code = "stale_version"


class MfaRequired(DomainForbidden):
    """A second factor in the last 15 minutes is needed to concur (the matrix's `mfa_recent`
    refuses first; this holds the row's `mfa_verified_at` to a real time)."""

    code = "mfa_required"


class EqrConcurredV2(DomainEvent):
    """G6 is met on a work item: the assigned EQR concurred (identifiers only)."""

    event_type: ClassVar[str] = "eqr.concurred_v2"

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    eqr_review_id: Annotated[UUID, classified("internal")]
    partner_user_ids: Annotated[list[UUID], classified("internal")]


class EqrRequested(DomainEvent):
    """Request EQR… (DF-05): the report waits on the assigned EQR."""

    event_type: ClassVar[str] = "eqr.requested"

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    eqr_user_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class TemplateItem:
    key: str
    text: str


ChecklistTemplate = Callable[[TenantContext], Awaitable[Sequence[TemplateItem]]]
_TEMPLATE: list[ChecklistTemplate] = []


def register_eqr_checklist_template(provider: ChecklistTemplate) -> None:
    """The firm's EQR checklist (A-07-T22's import); one provider."""
    _TEMPLATE[:] = [provider]


@dataclass(frozen=True)
class ReviewRow:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    eqr_user_id: UUID
    status: str
    version: int


_REVIEW = text(
    "SELECT id, engagement_id, work_item_id, eqr_user_id, status, version FROM eqr_reviews "
    "WHERE work_item_id = :w"
)


async def _review(tenant: TenantContext, work_item_id: UUID) -> ReviewRow:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_REVIEW, {"w": work_item_id})).first()
    if row is None:
        raise NotFound(REVIEW_TARGET)
    return ReviewRow(*row)


async def _as_eqr(ctx: AuthContext, work_item_id: UUID, action: str) -> ReviewRow:
    review = await _review(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, review.engagement_id)
    await authorise(ctx, action, ref.resource())
    if ctx.tenant.actor_kind != "human" or ctx.user_id != review.eqr_user_id:
        raise EqrOnly
    return review


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


# --- open ----------------------------------------------------------------------------------------

_WORK_ITEMS = text(
    "SELECT id FROM work_items WHERE engagement_id = :e AND kind = 'assurance' "
    "AND id NOT IN (SELECT work_item_id FROM eqr_reviews WHERE engagement_id = :e)"
)
_OPEN = text(
    """
    INSERT INTO eqr_reviews (tenant_id, engagement_id, work_item_id, eqr_user_id,
                             eligibility_snapshot, status)
    VALUES (:t, :e, :w, :u, CAST(:snapshot AS jsonb), 'in_progress')
    RETURNING id
    """
)
_ITEM = text(
    """
    INSERT INTO eqr_checklist_items (tenant_id, engagement_id, work_item_id, eqr_review_id,
                                     item_key, position, status, sub_line)
    VALUES (:t, :e, :w, :r, :key, :position, 'todo', :sub_line)
    """
)


async def open_reviews(tenant: TenantContext, engagement_id: UUID, eqr_user_id: UUID) -> int:
    """On assignment (`eqr.eligibility_approved`): one review per assurance work item without one.
    Refused when the eligibility re-check fails or no checklist template is registered."""
    checks = await eqr_eligibility(tenant, engagement_id, eqr_user_id)
    if checks.get("not_on_team") == "fail" or checks.get("cooling_off") == "fail":
        raise EqrNotEligible(facts={k: v for k, v in checks.items() if v == "fail"})
    if not _TEMPLATE:
        raise EqrTemplateMissing
    template = list(await _TEMPLATE[0](tenant))
    if not template:
        raise EqrTemplateMissing
    opened = 0
    async with uow(tenant) as tx:
        work_items = [r.id for r in (await tx.session.execute(_WORK_ITEMS, {"e": engagement_id}))]
        for work_item_id in work_items:
            review_id = (
                await tx.session.execute(
                    _OPEN,
                    {
                        "t": tenant.tenant_id,
                        "e": engagement_id,
                        "w": work_item_id,
                        "u": eqr_user_id,
                        "snapshot": json.dumps(checks, sort_keys=True),
                    },
                )
            ).scalar_one()
            for position, item in enumerate(template, start=1):
                await tx.session.execute(
                    _ITEM,
                    {
                        "t": tenant.tenant_id,
                        "e": engagement_id,
                        "w": work_item_id,
                        "r": review_id,
                        "key": item.key,
                        "position": position,
                        "sub_line": item.text[:280],
                    },
                )
            tx.record(
                "eqr_review.opened",
                target=Target(REVIEW_TARGET, review_id),
                after=Ref(eqr=eqr_user_id, items=len(template)),
                scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
            )
            opened += 1
    return opened


async def on_eligibility_approved(event: OutboxEvent) -> None:
    """`eqr.eligibility_approved`: open the reviews if the EQR is now the engagement's EQR and
    eligible; an ineligible or unassigned candidate opens nothing."""
    tenant = TenantContext(event.tenant_id, "system", "assurance.eqr")
    engagement_id = UUID(str(event.payload["engagement_id"]))
    user_id = UUID(str(event.payload["user_id"]))
    team = await team_of(tenant.tenant_id, engagement_id)
    if not any(member == user_id and role == "eqr_reviewer" for member, role in team):
        return
    try:
        await open_reviews(tenant, engagement_id, user_id)
    except (EqrNotEligible, EqrTemplateMissing):
        return  # nothing opens; ENG-05 shows the candidate's checks


# --- digest --------------------------------------------------------------------------------------

_CURRENT_CARDS = text(
    "SELECT id, source_ref, snapshot_sha256 FROM eqr_digest_cards "
    "WHERE eqr_review_id = :r AND superseded_by IS NULL"
)
_CARD = text(
    """
    INSERT INTO eqr_digest_cards (tenant_id, engagement_id, work_item_id, eqr_review_id,
                                  source_kind, source_ref, title, snapshot, snapshot_sha256)
    VALUES (:t, :e, :w, :r, 'decision', :ref, :title, CAST(:snapshot AS jsonb), :sha)
    RETURNING id
    """
)
_SUPERSEDE = text("UPDATE eqr_digest_cards SET superseded_by = :new WHERE id = :old")


async def build_digest(ctx: AuthContext, work_item_id: UUID) -> int:
    """Code only (ADR-050): one card per decided EP card; unchanged cards are kept."""
    review = await _review(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, review.engagement_id)
    await authorise(ctx, "eqr.build_digest", ref.resource())
    decided = await decided_cards(ctx.tenant, review.engagement_id)
    built = 0
    async with uow(ctx.tenant) as tx:
        current = {
            str(r.source_ref): (r.id, r.snapshot_sha256)
            for r in await tx.session.execute(_CURRENT_CARDS, {"r": review.id})
        }
        for card in decided:
            rows = [
                {"label": "Question", "value": card.question_key},
                {"label": "Decision", "value": card.option_key},
                {"label": "Decided", "value": card.decided_at.date().isoformat()},
            ]
            sha = _sha(rows)
            known = current.get(str(card.card_id))
            if known is not None and known[1] == sha:
                continue
            new_id = (
                await tx.session.execute(
                    _CARD,
                    {
                        "t": ctx.tenant_id,
                        "e": review.engagement_id,
                        "w": work_item_id,
                        "r": review.id,
                        "ref": str(card.card_id),
                        "title": card.kind.replace("_", " ").capitalize()[:200],
                        "snapshot": json.dumps(rows),
                        "sha": sha,
                    },
                )
            ).scalar_one()
            if known is not None:
                await tx.session.execute(_SUPERSEDE, {"new": new_id, "old": known[0]})
            built += 1
        tx.record(
            "eqr_digest.built",
            target=Target(REVIEW_TARGET, review.id),
            after=Ref(cards=built),
            scope=Scope(engagement_id=review.engagement_id, work_item_id=work_item_id),
        )
    return built


# --- the EQR's acts ------------------------------------------------------------------------------

_MARK = text(
    """
    UPDATE eqr_digest_cards
       SET reviewed_at = CASE WHEN :reviewed THEN clock_timestamp() END,
           reviewed_by = CASE WHEN :reviewed THEN CAST(:by AS uuid) END,
           reviewed_actor_kind = CASE WHEN :reviewed THEN 'human' END
     WHERE id = :card AND eqr_review_id = :r AND superseded_by IS NULL
    RETURNING id
    """
)


async def mark_reviewed(
    ctx: AuthContext, work_item_id: UUID, card_id: UUID, reviewed: bool
) -> None:
    review = await _as_eqr(ctx, work_item_id, "eqr.mark_reviewed")
    async with uow(ctx.tenant) as tx:
        found = (
            await tx.session.execute(
                _MARK,
                {"reviewed": reviewed, "by": str(ctx.user_id), "card": card_id, "r": review.id},
            )
        ).first()
        if found is None:
            raise NotFound("eqr_digest_card")
        tx.record(
            "eqr_digest.card_reviewed" if reviewed else "eqr_digest.card_unreviewed",
            target=Target("eqr_digest_card", card_id),
            scope=Scope(engagement_id=review.engagement_id, work_item_id=work_item_id),
        )


_CHECK = text(
    """
    UPDATE eqr_checklist_items
       SET status = :status, sub_line = COALESCE(:sub_line, sub_line), updated_by = :by,
           version = version + 1, updated_at = clock_timestamp()
     WHERE eqr_review_id = :r AND item_key = :key AND version = :seen
    RETURNING version
    """
)


async def update_checklist(
    ctx: AuthContext,
    work_item_id: UUID,
    item_key: str,
    status: str,
    sub_line: str | None,
    seen_version: int,
) -> int:
    review = await _as_eqr(ctx, work_item_id, "eqr.checklist_update")
    if review.status == "concurred":
        raise AlreadyConcurred
    async with uow(ctx.tenant) as tx:
        version = (
            await tx.session.execute(
                _CHECK,
                {
                    "status": status,
                    "sub_line": sub_line,
                    "by": ctx.user_id,
                    "r": review.id,
                    "key": item_key,
                    "seen": seen_version,
                },
            )
        ).scalar_one_or_none()
        if version is None:
            raise StaleItem
        tx.record(
            "eqr_checklist.updated",
            target=Target(REVIEW_TARGET, review.id),
            after=Ref(item=item_key, status=status),
            scope=Scope(engagement_id=review.engagement_id, work_item_id=work_item_id),
        )
    return int(version)


# --- concur (G6) ---------------------------------------------------------------------------------

_ITEMS = text("SELECT item_key, status FROM eqr_checklist_items WHERE eqr_review_id = :r")
_CARD_HASHES = text(
    "SELECT snapshot_sha256 FROM eqr_digest_cards WHERE eqr_review_id = :r "
    "AND superseded_by IS NULL ORDER BY source_ref"
)
_CONCUR = text(
    """
    INSERT INTO eqr_concurrences (tenant_id, engagement_id, digest_hash, not_involved,
        concurred_by, actor_kind, work_item_id, eqr_review_id, concurrence_date,
        checklist_snapshot_sha256, notes_cleared_count, mfa_verified_at)
    VALUES (:t, :e, :digest, true, :by, 'human', :w, :r, :on, :checklist, :cleared, :mfa)
    """
)
_CONCURRED = text(
    "UPDATE eqr_reviews SET status = 'concurred', version = version + 1, "
    "updated_at = clock_timestamp() WHERE id = :r AND status = 'in_progress' RETURNING id"
)


async def concur(
    ctx: AuthContext, work_item_id: UUID, *, not_involved: bool, concurrence_date: date
) -> UUID:
    review = await _as_eqr(ctx, work_item_id, "eqr.concur")
    if review.status == "concurred":
        raise AlreadyConcurred
    if not not_involved:
        raise ChecklistIncomplete(facts={"not_involved": "required"})
    if ctx.mfa_at is None or clock.system_now() - ctx.mfa_at > MFA_WINDOW:
        raise MfaRequired
    review_notes = [
        note
        for note, target in await open_notes(ctx.tenant, review.engagement_id)
        if target == review.id
    ]
    if review_notes:
        raise EqrNotesOpen(facts={"open": str(len(review_notes))})
    team = await team_of(ctx.tenant_id, review.engagement_id)
    partners = sorted({member for member, role in team if role in _PARTNER_ROLES})
    async with uow(ctx.tenant) as tx:
        items = [
            (r.item_key, r.status) for r in await tx.session.execute(_ITEMS, {"r": review.id})
        ]
        open_items = [key for key, status in items if status != "done"]
        if not items or open_items:
            raise ChecklistIncomplete(facts={"open": str(len(open_items))})
        hashes = [r[0] for r in await tx.session.execute(_CARD_HASHES, {"r": review.id})]
        if (await tx.session.execute(_CONCURRED, {"r": review.id})).first() is None:
            raise AlreadyConcurred
        await tx.session.execute(
            _CONCUR,
            {
                "t": ctx.tenant_id,
                "e": review.engagement_id,
                "digest": _sha(hashes),
                "by": ctx.user_id,
                "w": work_item_id,
                "r": review.id,
                "on": concurrence_date,
                "checklist": _sha(sorted(items)),
                "cleared": 0,
                "mfa": ctx.mfa_at,
            },
        )
        tx.record(
            "eqr.concurred",
            target=Target(REVIEW_TARGET, review.id),
            after=Ref(digest=_sha(hashes)),
            scope=Scope(engagement_id=review.engagement_id, work_item_id=work_item_id),
        )
        tx.emit(
            EqrConcurredV2(
                engagement_id=review.engagement_id,
                work_item_id=work_item_id,
                eqr_review_id=review.id,
                partner_user_ids=partners,
            )
        )
    return review.id


async def request_eqr(ctx: AuthContext, work_item_id: UUID) -> None:
    """Request EQR… (DF-05, DV-4): only while the review is not concurred."""
    review = await _review(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, review.engagement_id)
    await authorise(ctx, "eqr.request", ref.resource())
    if review.status == "concurred":
        raise AlreadyConcurred
    async with uow(ctx.tenant) as tx:
        tx.record(
            "eqr.requested",
            target=Target(REVIEW_TARGET, review.id),
            scope=Scope(engagement_id=review.engagement_id, work_item_id=work_item_id),
        )
        tx.emit(
            EqrRequested(
                engagement_id=review.engagement_id,
                work_item_id=work_item_id,
                eqr_user_id=review.eqr_user_id,
            )
        )


SUBSCRIPTIONS: Final = {"eqr.eligibility_approved": on_eligibility_approved}
