"""Starting the matcher, and reading what it proposed (SPEC-033; TASK-066). PROTECTED.

`inbox_file.extracted` goes to the engagement agent when it's on (its P-7 decides), or is decided
here by the same rules: the firm's `matching.enabled` flag, a real model route, the Routine
autonomy level or above, and code's content rules not already decisive (SPEC-033 Q3). The matcher
acts for the engagement partner (D2), never the uploader, who may be a client. "Suggest with AI"
(`inbox_match.request`) starts it at any level. One run per file and source:
`inbox_match:<tenant>:<file>`, so a redelivery attaches to it.

Reads: the firm sees each file's latest run and its shown proposals with verified quotes
(`inbox_match.read`, firm roles). Everyone who may see a file gets the matcher's picks as request
IDs through evidence's inbox listing (D1): never its words (ADR-111).
"""

from __future__ import annotations

from collections.abc import Sequence
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
from abacus.modules.agents.inbox_match import MATCHER, model_available
from abacus.modules.agents.repository import latest_match_runs, list_match_results, shown_picks
from abacus.modules.agents.review_start import QuoteView
from abacus.modules.agents.review_start import (
    _quotes as verified_quotes,  # pyright: ignore[reportPrivateUsage] -- the same verified-only rule
)
from abacus.modules.agents.spec import spec
from abacus.modules.agents.workflow_types import MatchInput
from abacus.modules.agents.workflows import InboxMatchWorkflow
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import match_material, register_match_picks, worth_matching
from abacus.modules.identity.api import AuthContext, authorise, autonomy_level, earliest_partner

_log = get_logger(__name__)
WORKFLOWS: dict[type, WorkClass] = {InboxMatchWorkflow: spec(MATCHER).work_class}
register_work_classes(WORKFLOWS)


def workflow_id(tenant_id: UUID, inbox_file_id: UUID) -> str:
    return f"inbox_match:{tenant_id}:{inbox_file_id}"


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "agents.inbox_match")


async def matching_enabled(tenant_id: UUID) -> bool:
    return await flag_enabled(_system(tenant_id), _flags.MATCHING_ENABLED)


async def dispatch_match(given: MatchInput, *, again: bool = False) -> None:
    """Start the matcher's workflow; a running or finished one is attached to ("Suggest with AI"
    starts a new one: `again`)."""
    suffix = f":{given.event_id}" if again else ""
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            InboxMatchWorkflow,
            given,
            id=workflow_id(UUID(given.tenant_id), UUID(given.inbox_file_id)) + suffix,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


class MatchUnavailable(DomainConflict):
    """No real model route is enabled for the matcher here."""

    code = "ai_match_unavailable"


async def worth_it(tenant: TenantContext, inbox_file_id: UUID) -> bool:
    """SPEC-033 Q3: there's something for the matcher to add (D3: a decisive file isn't
    recorded)."""
    return await worth_matching(tenant, inbox_file_id)


async def match_for(
    tenant: TenantContext, engagement_id: UUID, inbox_file_id: UUID, source: UUID
) -> bool:
    """Start the matcher on behalf of the engagement partner; False when there's none."""
    partner = await earliest_partner(tenant, engagement_id)
    if partner is None:
        return False
    await dispatch_match(
        MatchInput(str(tenant.tenant_id), str(inbox_file_id), str(source), str(partner))
    )
    return True


async def start_match(event: OutboxEvent) -> None:
    """With the engagement agent on, its P-7 decides; otherwise the same rules apply here."""
    if await agent_on(event.tenant_id):
        await to_agent(event)
        return
    if not await matching_enabled(event.tenant_id) or not model_available():
        return
    if await autonomy_level(event.tenant_id) < 1:
        _log.info("inbox_match.skipped", tenant_id=event.tenant_id, reason="advise")
        return
    tenant = _system(event.tenant_id)
    inbox_file_id = UUID(str(event.payload["inbox_file_id"]))
    if not await worth_it(tenant, inbox_file_id):
        return
    await match_for(
        tenant, UUID(str(event.payload["engagement_id"])), inbox_file_id, event.event_id
    )


async def request_match(ctx: AuthContext, engagement_id: UUID, inbox_file_id: UUID) -> None:
    """SPEC-033 §4.5: a person starts the matcher on one file ("Suggest with AI"), at any level,
    acting for themselves; each request is its own run."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "inbox_match.request", engagement.resource())
    if not model_available():
        raise MatchUnavailable(str(inbox_file_id))
    material = await match_material(ctx.tenant, inbox_file_id)
    if material is None or material.engagement_id != engagement_id:
        raise NotFound("inbox_file")
    source = uuid5(
        NAMESPACE_URL, f"abacus:match-now:{ctx.tenant_id}:{inbox_file_id}:{ctx.user_id}"
    )
    async with uow(ctx.tenant) as tx:
        tx.record(
            "inbox_match.requested",
            target=Target("inbox_file", inbox_file_id),
            after=Ref(user_id=ctx.user_id),
        )
    await dispatch_match(
        MatchInput(str(ctx.tenant_id), str(inbox_file_id), str(source), str(ctx.user_id)),
        again=True,
    )


# --- Reading (SPEC-033 AC-3, AC-5) -------------------------------------------------------------


@dataclass(frozen=True)
class ProposalView:
    request_item_id: UUID
    confidence: Decimal
    rationale: str
    quotes: tuple[QuoteView, ...]  # verified quotes only


@dataclass(frozen=True)
class FileMatchView:
    inbox_file_id: UUID
    status: str  # running | completed | failed | escalated
    reason: str | None  # why a run failed (data_boundary: not for real client data yet)
    none_fit: bool
    none_fit_rationale: str | None
    proposals: tuple[ProposalView, ...]


async def matches_of(ctx: AuthContext, engagement_id: UUID) -> list[FileMatchView]:
    """The latest matcher run of each inbox file, firm roles only (`inbox_match.read`)."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "inbox_match.read", engagement.resource())
    async with tenant_session(ctx.tenant) as session:
        runs = await latest_match_runs(session, ctx, MATCHER, engagement_id)
        results = await list_match_results(session, ctx, [r.id for r in runs])
    by_run: dict[UUID, list[ProposalView]] = {}
    none_fit: dict[UUID, bool] = {}
    for match_run, proposal in results:
        none_fit[match_run.agent_run_id] = match_run.none_fit
        if proposal is not None:
            by_run.setdefault(match_run.agent_run_id, []).append(
                ProposalView(
                    proposal.request_item_id,
                    proposal.confidence,
                    proposal.rationale,
                    verified_quotes(proposal.citations),
                )
            )
    views: list[FileMatchView] = []
    for run in runs:
        output = run.output or {}
        rationale = output.get("rationale")
        views.append(
            FileMatchView(
                cast(UUID, run.inbox_file_id),
                run.status,
                run.failure_code,
                none_fit.get(run.id, False),
                str(rationale) if none_fit.get(run.id) and rationale else None,
                tuple(by_run.get(run.id, [])),
            )
        )
    return views


async def picks_for(
    tenant: TenantContext, inbox_file_ids: Sequence[UUID]
) -> dict[UUID, list[tuple[UUID, int]]]:
    """D1: the matcher's shown picks per file, as request IDs with a 0-100 confidence, for
    evidence's inbox listing (which authorised the caller on these files)."""
    async with tenant_session(tenant) as session:
        found = await shown_picks(session, inbox_file_ids)
    return {f: [(i, round(c * 100)) for i, c in picks] for f, picks in found.items()}


register_match_picks(picks_for)
