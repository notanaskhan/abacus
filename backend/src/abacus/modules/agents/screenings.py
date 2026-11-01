"""Starting screening from relayed events (TASK-011 design §7). PROTECTED.

The relay (at least once) hands each `evidence_version.created` to `start_screening`, which
starts `screening:<tenant_id>:<evidence_version_id>` (tenant-qualified: Temporal's namespace is
shared by every firm). There is no execution timeout: each activity has its own, and the run is
always ended by `screening.fail_run`, so a run never stays `running` because the workflow was
killed. A redelivery attaches to the running workflow or finds
it finished: either way the event counts as delivered. `requested_by` comes only from the event,
which the evidence module writes in the same transaction as the version.
"""

from __future__ import annotations

from contextlib import suppress
from uuid import NAMESPACE_URL, UUID, uuid5

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.agents.assess_start import WORKFLOWS as ASSESS_WORKFLOWS
from abacus.modules.agents.draft_start import WORKFLOWS as DRAFT_WORKFLOWS
from abacus.modules.agents.engagement_agent import agent_on, firm_resumed, to_agent
from abacus.modules.agents.engagement_agent_workflow import EngagementAgent
from abacus.modules.agents.events import KnowledgeDocumentAdded, UploadReviewRecorded
from abacus.modules.agents.intake_start import WORKFLOWS as INTAKE_WORKFLOWS
from abacus.modules.agents.intake_start import start_intake_match
from abacus.modules.agents.knowledge_workflow import KnowledgeEmbeddingWorkflow
from abacus.modules.agents.match_start import WORKFLOWS as MATCH_WORKFLOWS
from abacus.modules.agents.match_start import start_match
from abacus.modules.agents.methodology_import_workflow import MethodologyImportWorkflow
from abacus.modules.agents.review_start import WORKFLOWS as REVIEW_WORKFLOWS
from abacus.modules.agents.review_start import start_upload_review
from abacus.modules.agents.screening_aggregate import on_version_event, on_version_withdrawn
from abacus.modules.agents.section_draft import WORKFLOWS as SECTION_DRAFT_WORKFLOWS
from abacus.modules.agents.service import SCREENER
from abacus.modules.agents.spec import spec
from abacus.modules.agents.workflow_types import KnowledgeInput, ScreeningInput
from abacus.modules.agents.workflows import ScreeningWorkflow
from abacus.modules.communications.api import InboxAttachmentMatchable
from abacus.modules.engagements.api import EngagementCreated, get_ref
from abacus.modules.evidence.api import (
    EvidenceVersionCreated,
    EvidenceVersionWithdrawn,
    InboxFileAdded,
    InboxFileExtracted,
    UploadChecksRecorded,
    version_view,
)
from abacus.modules.identity.api import (
    AuthContext,
    FirmAgentsResumed,
    authorise,
    autonomy_level,
)
from abacus.modules.requests.api import DueDatesChanged, RequestItemClassified

EVIDENCE_VERSION_CREATED = EvidenceVersionCreated.event_type
# Each workflow's work class (ADR-071): screening runs in the screener's class (its spec).
# Registered here, beside the only code that starts it, so it can't be started unregistered.
# Knowledge embedding is batch work (SPEC-009 §6; ADR-071).
WORKFLOWS: dict[type, WorkClass] = {
    ScreeningWorkflow: spec(SCREENER).work_class,
    KnowledgeEmbeddingWorkflow: "batch",
    EngagementAgent: "background",  # SPEC-027 (TASK-050): one per engagement, long-lived
    MethodologyImportWorkflow: "background",  # K-01-T21 (K-01 §4.4)
}
WORKFLOWS.update(REVIEW_WORKFLOWS)  # SPEC-030 (TASK-059): the worker hosts it with these
WORKFLOWS.update(MATCH_WORKFLOWS)  # SPEC-033 (TASK-066)
WORKFLOWS.update(INTAKE_WORKFLOWS)  # N-01-T22
WORKFLOWS.update(DRAFT_WORKFLOWS)  # SPEC-035 (TASK-073)
WORKFLOWS.update(ASSESS_WORKFLOWS)  # SPEC-037 Q4 (TASK-085)
WORKFLOWS.update(SECTION_DRAFT_WORKFLOWS)  # A-04-T11
register_work_classes(WORKFLOWS)


def workflow_id(tenant_id: UUID, evidence_version_id: UUID) -> str:
    return f"screening:{tenant_id}:{evidence_version_id}"


def screening_input(event: OutboxEvent) -> ScreeningInput:
    """The workflow input, from the event's identifiers only (a malformed event raises: the relay
    backs it off and eventually parks it)."""
    version = UUID(str(event.payload["evidence_version_id"]))
    requested = event.payload.get("requested_by")
    return ScreeningInput(
        str(event.tenant_id),
        str(version),
        str(event.event_id),
        str(UUID(str(requested))) if requested is not None else None,
    )


async def start_screening(event: OutboxEvent) -> None:
    # SPEC-027 (TASK-050): with the engagement agent on, its P-1 decides (paused, Advise).
    if await agent_on(event.tenant_id):
        await to_agent(event)
        return
    # SPEC-024 Q4: at Advise (autonomy level 0) nothing is screened on its own; a person starts
    # it ("Screen now", `request_screening`).
    if await autonomy_level(event.tenant_id) < 1:
        _log.info("screening.skipped", tenant_id=event.tenant_id, reason="advise")
        return
    await dispatch_screening(screening_input(event))


async def dispatch_screening(input: ScreeningInput) -> None:
    # Already screened (or screening): the event counts as delivered.
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            ScreeningWorkflow,
            input,
            id=workflow_id(UUID(input.tenant_id), UUID(input.evidence_version_id)),
            # A failed workflow may be started again by a redelivery; a finished one may not.
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


async def start_knowledge_embedding(event: OutboxEvent) -> None:
    """`knowledge-embed:<tenant_id>:<document_id>`; a redelivery attaches or finds it finished."""
    document_id = UUID(str(event.payload["document_id"]))
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            KnowledgeEmbeddingWorkflow,
            KnowledgeInput(str(event.tenant_id), str(document_id)),
            id=f"knowledge-embed:{event.tenant_id}:{document_id}",
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


async def on_upload_checks_recorded(event: OutboxEvent) -> None:
    """The reviewer may start (SPEC-030), then the aggregate recomposes from the code checks
    (P-06-T20): the period check is code's, so it needs no review."""
    await start_upload_review(event)
    await on_version_event(event)


SUBSCRIPTIONS = {
    EVIDENCE_VERSION_CREATED: start_screening,
    KnowledgeDocumentAdded.event_type: start_knowledge_embedding,
    # SPEC-027 (TASK-050): the engagement agent hears its engagement's events (when on).
    EngagementCreated.event_type: to_agent,
    "connection.created": to_agent,  # by name: nothing imports connections (BOUND-002)
    RequestItemClassified.event_type: to_agent,
    InboxFileAdded.event_type: to_agent,
    DueDatesChanged.event_type: to_agent,  # SPEC-027 (TASK-051): reminders start again
    FirmAgentsResumed.event_type: firm_resumed,
    # SPEC-030 (TASK-059): checks recorded for an upload; the reviewer may follow (P-6), and
    # P-06-T20's aggregate recomposes from the code checks.
    UploadChecksRecorded.event_type: on_upload_checks_recorded,
    # P-06-T20: a review recorded, or a client's withdrawal: the request batches recompose.
    UploadReviewRecorded.event_type: on_version_event,
    EvidenceVersionWithdrawn.event_type: on_version_withdrawn,
    # SPEC-033 (TASK-066): an inbox file was read; the matcher may follow (P-7).
    InboxFileExtracted.event_type: start_match,
    # N-01-T22: an intake attachment of a known client was classified; its intake mode follows.
    InboxAttachmentMatchable.event_type: start_intake_match,
}


_log = get_logger(__name__)


async def request_screening(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> None:
    """SPEC-024 (TASK-042 D1): a person starts screening of one version ("Screen now", at
    Advise or any level). Once per version: the workflow ID is the automatic one, so a running
    or finished screening is attached to, not repeated. The person is who the agent acts for."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "screening.request", engagement.resource())
    version = await version_view(ctx.tenant, version_id)
    if version.engagement_id != engagement_id:
        raise NotFound("evidence_version")
    async with uow(ctx.tenant) as tx:
        tx.record(
            "screening.requested",
            target=Target("evidence_version", version_id),
            after=Ref(user_id=ctx.user_id),
        )
    source = uuid5(NAMESPACE_URL, f"abacus:screen-now:{ctx.tenant_id}:{version_id}")
    await dispatch_screening(
        ScreeningInput(str(ctx.tenant_id), str(version_id), str(source), str(ctx.user_id))
    )
