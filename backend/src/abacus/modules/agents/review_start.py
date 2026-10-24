"""Starting the upload reviewer (SPEC-030; TASK-059). PROTECTED.

`upload_checks.recorded` (SPEC-029's checks of a version on a request item) goes to the
engagement agent when it's on (its P-6 decides), or is decided here by the same rules: the firm's
`upload_review.enabled` flag, and the Routine autonomy level or above. The reviewer acts for the
engagement partner (TASK-059 D2), never the uploader, who may be a client. "Review now"
(`upload_review.request`) starts it at any level. One run per version and source:
`upload_review:<tenant>:<version>`, so a redelivery attaches to it.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.agents.engagement_agent import agent_on, to_agent
from abacus.modules.agents.repository import latest_review_run, shown_flag_counts, shown_flags
from abacus.modules.agents.spec import spec
from abacus.modules.agents.upload_review import REVIEWER, model_available
from abacus.modules.agents.workflow_types import ScreeningInput
from abacus.modules.agents.workflows import UploadReviewWorkflow
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import version_view, withdrawn_among
from abacus.modules.identity.api import AuthContext, authorise, autonomy_level, earliest_partner

_log = get_logger(__name__)
WORKFLOWS: dict[type, WorkClass] = {UploadReviewWorkflow: spec(REVIEWER).work_class}
register_work_classes(WORKFLOWS)


def workflow_id(tenant_id: UUID, version_id: UUID) -> str:
    return f"upload_review:{tenant_id}:{version_id}"


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "agents.upload_review")


async def review_enabled(tenant_id: UUID) -> bool:
    return await flag_enabled(_system(tenant_id), _flags.UPLOAD_REVIEW_ENABLED)


async def dispatch_review(given: ScreeningInput, *, again: bool = False) -> None:
    """Start the reviewer's workflow; a running or finished one is attached to (a "Review now"
    after a kind change starts a new one: `again`)."""
    version = UUID(given.evidence_version_id)
    suffix = f":{given.event_id}" if again else ""
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            UploadReviewWorkflow,
            given,
            id=workflow_id(UUID(given.tenant_id), version) + suffix,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


class ReviewUnavailable(DomainConflict):
    """No real model route is enabled for the reviewer here (TASK-059 D3)."""

    code = "ai_review_unavailable"


async def review_for(
    tenant: TenantContext, engagement_id: UUID, version: UUID, source: UUID
) -> bool:
    """Start the reviewer on behalf of the engagement partner; False when there's none."""
    partner = await earliest_partner(tenant, engagement_id)
    if partner is None:
        return False
    await dispatch_review(
        ScreeningInput(str(tenant.tenant_id), str(version), str(source), str(partner))
    )
    return True


async def start_upload_review(event: OutboxEvent) -> None:
    """With the engagement agent on, its P-6 decides; otherwise the same rules apply here."""
    if await agent_on(event.tenant_id):
        await to_agent(event)
        return
    if not await review_enabled(event.tenant_id) or not model_available():
        return
    if await autonomy_level(event.tenant_id) < 1:
        _log.info("upload_review.skipped", tenant_id=event.tenant_id, reason="advise")
        return
    await review_for(
        _system(event.tenant_id),
        UUID(str(event.payload["engagement_id"])),
        UUID(str(event.payload["evidence_version_id"])),
        event.event_id,
    )


async def request_review(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> None:
    """SPEC-030 §6.4: a person starts the reviewer on one version ("Review now"), at any level,
    acting for themselves. Each request is its own run (the kind may have changed)."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "upload_review.request", engagement.resource())
    if not model_available():
        raise ReviewUnavailable(str(version_id))
    version = await version_view(ctx.tenant, version_id)
    if version.engagement_id != engagement_id:
        raise NotFound("evidence_version")
    source = uuid5(NAMESPACE_URL, f"abacus:review-now:{ctx.tenant_id}:{version_id}:{ctx.user_id}")
    async with uow(ctx.tenant) as tx:
        tx.record(
            "upload_review.requested",
            target=Target("evidence_version", version_id),
            after=Ref(user_id=ctx.user_id),
        )
    await dispatch_review(
        ScreeningInput(str(ctx.tenant_id), str(version_id), str(source), str(ctx.user_id)),
        again=True,
    )


# --- Reading reviews (SPEC-030 AC-6; TASK-059 D1) ------------------------------------------------


@dataclass(frozen=True)
class QuoteView:
    page: int | None
    sheet: str | None
    cell: str | None
    quote: str


@dataclass(frozen=True)
class FlagView:
    category: str
    confidence: Decimal
    rationale: str
    quotes: tuple[QuoteView, ...]  # verified quotes only


@dataclass(frozen=True)
class ReviewView:
    status: str  # none | running | completed | failed | escalated
    reason: str | None  # why a run failed (data_boundary: not for real client data yet)
    flags: tuple[FlagView, ...]


def _quotes(raw: object) -> tuple[QuoteView, ...]:
    citations = cast(list[dict[str, object]], raw if isinstance(raw, list) else [])
    return tuple(
        QuoteView(
            cast(int | None, c.get("page")),
            cast(str | None, c.get("sheet")),
            cast(str | None, c.get("cell")),
            str(c.get("quote") or ""),
        )
        for c in citations
        if c.get("verified") is True  # SPEC-030 Q3: the firm sees verified quotes only
    )


async def review_of(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> ReviewView:
    """The latest review of a version, firm roles only (`upload_review.read`)."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "upload_review.read", engagement.resource())
    version = await version_view(ctx.tenant, version_id)
    if version.engagement_id != engagement_id:
        raise NotFound("evidence_version")
    async with tenant_session(ctx.tenant) as session:
        run = await latest_review_run(session, ctx, REVIEWER, version_id)
        flags = await shown_flags(session, ctx, run.id) if run is not None else []
    if run is None:
        return ReviewView("none", None, ())
    return ReviewView(
        run.status,
        run.failure_code,
        tuple(
            FlagView(f.category, f.confidence, f.rationale, _quotes(f.citations)) for f in flags
        ),
    )


async def review_flag_counts(ctx: AuthContext, engagement_id: UUID) -> dict[UUID, int]:
    """For the Board: per evidence version, the shown flags of its latest review."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "upload_review.read", engagement.resource())
    async with tenant_session(ctx.tenant) as session:
        counts = await shown_flag_counts(session, ctx, engagement_id)
    hidden = await withdrawn_among(ctx.tenant, list(counts))  # P-06-T19 (ADR-162 §4)
    return {version: n for version, n in counts.items() if version not in hidden}
