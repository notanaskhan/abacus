"""The SHL-20 card's service: read the aggregate, rerun, feedback (P-06-T20; DEC-221, DEC-324).

The aggregate is code's (`screening_aggregate`). A person reads it, asks for a rerun, or gives
feedback, and none of these writes a request's status or a review decision (ADR-005). The read
leaves out any version withdrawn since the head was composed (DEC-299). The head is then stale,
so it never shows `passed` until code recomposes it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from abacus.kernel._flags import SCREENING_CARD
from abacus.kernel.clock import system_now
from abacus.kernel.crypto import seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.repository import (
    ReviewRunFacts,
    aggregate_for,
    aggregate_head_for,
    insert_feedback,
    insert_rerun,
    latest_feedback,
    lock_item_rerun,
    rerun_since,
    review_runs_of_versions,
)
from abacus.modules.agents.review_start import dispatch_review, review_enabled
from abacus.modules.agents.screening_aggregate import (
    RIGHT_DOCUMENT,
    RIGHT_PERIOD,
    WRONG_DOCUMENT,
    compose_for_item,
    latest_reviews,
)
from abacus.modules.agents.spec import spec
from abacus.modules.agents.tri_gate import model_blocked
from abacus.modules.agents.upload_review import REVIEWER, model_available
from abacus.modules.agents.workflow_types import ScreeningInput
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import screening_facts, withdrawn_among
from abacus.modules.identity.api import AuthContext, Resource, allowed_actions, authorise
from abacus.modules.requests.api import ScreeningSubject, read_item_versions, screening_subject

_CARD_ACTIONS = ("screening.request", "screening.feedback")
# One rerun per request item per minute of system time (security review, DEC-324).
RERUN_WINDOW_SECONDS: Final = 60


class ScreeningRunning(DomainConflict):
    """A screening of this request's files is still running: wait for it, then rerun."""

    code = "screening_running"


@dataclass(frozen=True)
class CheckView:
    key: str
    verdict: str
    source: str
    answer_ref: str | None
    citation_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class FileFlagView:
    evidence_version_id: UUID
    file_name: str
    reason_code: str
    region_ref: str | None


@dataclass(frozen=True)
class FeedbackView:
    screening_result_id: UUID
    thumb: str
    reason_code: str | None
    created_at: datetime


@dataclass(frozen=True)
class CardView:
    request_item_id: UUID
    screening_result_id: UUID | None
    batch_no: int | None
    verdict: str
    running: bool
    files_total: int
    files_answering: int
    checks: tuple[CheckView, ...]
    file_flags: tuple[FileFlagView, ...]
    prompt_ref: str | None
    duration_ms: int | None
    screened_at: datetime | None
    my_feedback: FeedbackView | None
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class RerunView:
    request_item_id: UUID
    running: bool
    as_of: datetime


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, SCREENING_CARD):
        raise NotFound("screening.card")


async def _subject(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> ScreeningSubject:
    subject = await screening_subject(ctx.tenant, item_id)
    if subject is None or subject.engagement_id != engagement_id:
        raise NotFound("request_item")
    return subject


async def _current(ctx: AuthContext, item_id: UUID) -> list[UUID]:
    """The item's live fulfilments the client has not withdrawn."""
    live = await read_item_versions(ctx.tenant, item_id)
    hidden = await withdrawn_among(ctx.tenant, live)
    return [v for v in live if v not in hidden]


def _running(runs: Sequence[ReviewRunFacts]) -> bool:
    return any(r.status == "running" for r in runs)


def _str_list(value: object) -> list[str]:
    return [str(v) for v in cast(list[object], value)] if isinstance(value, list) else []


async def screening_card(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> CardView:
    """SHL-20 a to e. Firm reviewer roles only (`upload_review.read`; `client_service` and
    clients are refused by role, DEC-20)."""
    await _gate(ctx)
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "upload_review.read", engagement.resource())
    await _subject(ctx, engagement_id, item_id)
    current = await _current(ctx, item_id)
    async with tenant_session(ctx.tenant) as session:
        head = await aggregate_head_for(session, ctx, item_id)
        runs = await review_runs_of_versions(session, REVIEWER, current)
        mine = await latest_feedback(session, head.id, ctx.user_id) if head is not None else None
    running = _running(runs)
    allowed = set(await allowed_actions(ctx, engagement.resource(), _CARD_ACTIONS))
    if running:
        allowed.discard("screening.request")
    if head is None:
        allowed.discard("screening.feedback")
        return CardView(
            item_id,
            None,
            None,
            "not_screened",
            running,
            len(current),
            0,
            (
                CheckView(RIGHT_DOCUMENT, "not_run", "model", str(item_id), ()),
                CheckView(RIGHT_PERIOD, "not_run", "code", str(item_id), ()),
            ),
            (),
            None,
            None,
            None,
            None,
            tuple(sorted(allowed)),
        )
    composed = [UUID(str(v)) for v in head.evidence_version_ids or []]
    facts = await screening_facts(ctx.tenant, composed)
    shown = [v for v in composed if v in facts]  # withdrawn since composing: left out
    stale = len(shown) != len(composed)
    flags = tuple(
        FileFlagView(
            UUID(str(f["evidence_version_id"])),
            facts[UUID(str(f["evidence_version_id"]))].file_name,
            str(f["reason_code"]),
            str(f["region_ref"]) if f.get("region_ref") else None,
        )
        for f in head.file_flags or []
        if UUID(str(f["evidence_version_id"])) in facts
    )
    regions = {f.region_ref for f in flags if f.region_ref}
    checks = tuple(
        CheckView(
            str(c["key"]),
            str(c["verdict"]),
            str(c["source"]),
            str(c["answer_ref"]) if c.get("answer_ref") else None,
            tuple(UUID(i) for i in _str_list(c.get("citation_ids")) if not stale or i in regions),
        )
        for c in head.checks or []
    )
    verdict = str(head.verdict)
    if stale:  # never a verdict about a file the client withdrew; code recomposes shortly
        verdict = "flagged" if flags else "not_screened"
    wrong = {f.evidence_version_id for f in flags if f.reason_code == WRONG_DOCUMENT}
    composed_reviews = {UUID(str(r)) for r in head.source_review_ids or []}
    newest = max(
        (r for r in latest_reviews(runs).values() if r.review_id in composed_reviews),
        key=lambda r: (r.finished_at or r.started_at, r.run_id),
        default=None,
    )
    duration = (
        round((newest.finished_at - newest.started_at).total_seconds() * 1000)
        if newest is not None and newest.finished_at is not None
        else None
    )
    return CardView(
        item_id,
        head.id,
        head.batch_no,
        verdict,
        running,
        len(shown),
        len([v for v in shown if v not in wrong]),
        checks,
        flags,
        newest.prompt_ref if newest is not None else None,
        duration,
        head.created_at,
        FeedbackView(mine.screening_result_id, mine.thumb, mine.reason_code, mine.created_at)
        if mine is not None
        else None,
        tuple(sorted(allowed)),
    )


def rerun_source(tenant_id: UUID, item_id: UUID, version: UUID, user: UUID, prompt: str) -> UUID:
    """One source event per item, version, person and prompt version (as "Review now"'s): a
    repeated rerun attaches to the same workflow and run instead of starting another."""
    return uuid5(
        NAMESPACE_URL, f"abacus:screening-rerun:{tenant_id}:{item_id}:{version}:{user}:{prompt}"
    )


async def _may_review(ctx: AuthContext, resource: Resource, item_id: UUID) -> bool:
    """Reviews start only as "Review now" would allow them (DEC-324): a real reviewer route, the
    caller's `upload_review.request` (not staff's), the firm's `upload_review.enabled`, and no
    tax-return information without consent."""
    if not model_available():
        return False
    if "upload_review.request" not in await allowed_actions(
        ctx, resource, ("upload_review.request",)
    ):
        return False
    if not await review_enabled(ctx.tenant_id):
        return False
    return not await model_blocked(ctx.tenant, [item_id])


async def rerun_screening(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> RerunView:
    """SHL-20 c: code recomposes the aggregate; reviews start, for a caller who may start them,
    on the current versions with no completed review under the reviewer's current prompt.

    One rerun per item at a time: under the item's advisory lock, 409 `screening_running` while
    a review of these files runs or within `RERUN_WINDOW_SECONDS` of the last rerun, and the
    dispatch happens under the same lock. The person is who the reviewer acts for."""
    await _gate(ctx)
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "screening.request", engagement.resource())
    await _subject(ctx, engagement_id, item_id)
    current = await _current(ctx, item_id)
    may_review = await _may_review(ctx, engagement.resource(), item_id)
    if may_review:
        await authorise(ctx, "upload_review.request", engagement.resource())
    prompt = spec(REVIEWER).prompt
    async with uow(ctx.tenant) as tx:
        await lock_item_rerun(tx.session, item_id)
        runs = await review_runs_of_versions(tx.session, REVIEWER, current)
        if _running(runs) or await rerun_since(tx.session, item_id, RERUN_WINDOW_SECONDS):
            raise ScreeningRunning(str(item_id))
        reviewed = {
            r.evidence_version_id for r in latest_reviews(runs).values() if r.prompt_ref == prompt
        }
        starting = [v for v in current if v not in reviewed] if may_review else []
        await insert_rerun(
            tx.session,
            values={
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "request_item_id": item_id,
                "requested_by": ctx.user_id,
                "files": len(starting),
            },
        )
        tx.record(
            "screening.rerun_requested",
            target=Target("request_item", item_id),
            after=Ref(user_id=ctx.user_id, files=len(starting)),
        )
        for version in starting:
            source = rerun_source(ctx.tenant_id, item_id, version, ctx.user_id, prompt)
            await dispatch_review(
                ScreeningInput(str(ctx.tenant_id), str(version), str(source), str(ctx.user_id)),
                again=True,
            )
    await compose_for_item(ctx.tenant_id, item_id)
    return RerunView(item_id, bool(starting), system_now())


def _note_context(feedback_id: UUID) -> str:
    """What a sealed note is bound to (its feedback row), so it never opens as another's."""
    return hashlib.sha256(f"screening_feedback.note:{feedback_id}".encode()).hexdigest()


async def give_feedback(
    ctx: AuthContext,
    screening_result_id: UUID,
    thumb: str,
    reason_code: str | None,
    note: str | None,
) -> FeedbackView:
    """SHL-20 f: a person's thumbs up or down on an aggregate, insert-only. The agent is denied
    (`screening.feedback`), and the database binds the row to the session's own person."""
    await _gate(ctx)
    async with tenant_session(ctx.tenant) as session:
        row = await aggregate_for(session, ctx, screening_result_id)
    if row is None:
        raise NotFound("screening_result")
    engagement = await get_ref(ctx, row.engagement_id)
    await authorise(ctx, "screening.feedback", engagement.resource())
    feedback_id = uuid4()
    sealed = (
        await seal(ctx.tenant_id, note.encode(), _note_context(feedback_id))
        if note is not None
        else None
    )
    async with uow(ctx.tenant) as tx:
        await insert_feedback(
            tx.session,
            values={
                "id": feedback_id,
                "tenant_id": ctx.tenant_id,
                "engagement_id": row.engagement_id,
                "screening_result_id": row.id,
                "user_id": ctx.user_id,
                "thumb": thumb,
                "reason_code": reason_code,
                "note_sealed": sealed,
            },
        )
        tx.record(
            "screening.feedback_sent",
            target=Target("screening_result", row.id),
            after=Ref(feedback_id=feedback_id, thumb_up=int(thumb == "up")),
        )
    async with tenant_session(ctx.tenant) as session:
        mine = await latest_feedback(session, row.id, ctx.user_id)
    if mine is None:  # pragma: no cover - the row was just committed
        raise NotFound("screening_feedback")
    return FeedbackView(mine.screening_result_id, mine.thumb, mine.reason_code, mine.created_at)
