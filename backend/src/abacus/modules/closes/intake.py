"""Close intake (C-01-T19; C-01 §4.5, F2; SPEC-655 CLS-03, POR-11; amber).

- **BD1 publish** (`publish_requests`, run by `RequestPublishWorkflow` at `requests_publish_on`
  09:00 firm time): pin the close to the plan version effective for its period (QC-2, once, for
  good), read that version's request templates and generate them into the close's `close_intake`
  binder (`requests.api.generate_close_intake`: idempotent on the close and template, bank-feed
  sources internal per QC-1), due on each template's business day, under the authority of the
  person who published the version. Emits `close_requests.published` once per close; a replay
  generates nothing twice and records nothing new.
- **The request tree** (CLS-03): categories from each template's `category_path`, then requests
  with their status words (`request_close`), received counts and overdue flags. An incorporated
  request names the plan rows that read it (`rerun_plan_row_ids` from the template's
  `source_row_ids`): CLS-03 offers "Re-run affected tasks" for exactly those procedures.
- **The questionnaire** (CLS-03 d): the binder's questions and answers when it has one.

Every read authorises `close.read` on the close (walled closes are absent: 404, INV-3). Names and
titles are client and firm content, rendered as text.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Final, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.clock import now as business_now
from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.closes import repository as repo
from abacus.modules.closes.business_days import add_business_days
from abacus.modules.closes.contract_work import (
    CloseQuestionnaireOut,
    RequestNodeOut,
    RequestTreeOut,
)
from abacus.modules.closes.contract_work import (
    QuestionnaireAnswerOut as CloseQuestionnaireAnswer,
)
from abacus.modules.closes.events import CloseRequestsPublished
from abacus.modules.closes.plans import pin_plan
from abacus.modules.closes.request_publish_types import (
    PUBLISH,
    SECONDS_UNTIL,
    PublishInput,
    PublishResult,
)
from abacus.modules.closes.request_publish_workflow import RequestPublishWorkflow
from abacus.modules.identity.api import AuthContext, firm_time_zone
from abacus.modules.requests.api import (
    CloseRequestSpec,
    close_intake_binder,
    generate_close_intake,
    intake_items,
    latest_version_of,
    questionnaires_of_list,
)

ACTOR: Final = "closes:request_publish"
PUBLISH_AT: Final = time(9, 0)
_MONTHS: Final = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_TEMPLATES = text(
    "SELECT t.id, t.title, t.category_path, t.due_business_day, t.client_visible, "
    "t.source_row_ids FROM close_request_templates t WHERE t.version_id = :v "
    "ORDER BY t.created_at, t.id"
)
_VERSION = text("SELECT version, published_by FROM close_plan_versions WHERE id = :v")


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", ACTOR)


def workflow_id(tenant_id: UUID, close_id: UUID) -> str:
    return f"close_requests:{tenant_id}:{close_id}"


async def publish_instant(tenant: TenantContext, close: repo.CloseRow) -> datetime | None:
    """09:00 firm time on the close's BD1 (`requests_publish_on`), or None without one."""
    if close.requests_publish_on is None:
        return None
    zone = ZoneInfo(await firm_time_zone(tenant))
    return datetime.combine(close.requests_publish_on, PUBLISH_AT, tzinfo=zone)


async def seconds_until_publish(tenant_id: UUID, close_id: UUID) -> int:
    """How long the workflow sleeps (0 when the instant passed; -1 when there is nothing to do:
    no such close, no BD1, or already published)."""
    tenant = _system(tenant_id)
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, close_id)
        binder = None if close is None else await close_intake_binder(session, close_id)
    if close is None or binder is not None:
        return -1
    at = await publish_instant(tenant, close)
    if at is None:
        return -1
    return max(0, int((at - await business_now(tenant)).total_seconds()))


@dataclass(frozen=True)
class Published:
    binder_id: UUID | None
    created: int
    plan_version: int | None


async def publish_requests(tenant_id: UUID, close_id: UUID) -> Published:
    """The BD1 steps (module docstring). Safe to repeat: the pin is once, the generation is
    idempotent, and the event is emitted only by the call that created requests."""
    tenant = _system(tenant_id)
    async with uow(tenant) as tx:
        close = await repo.close_row(tx.session, close_id, lock=True)
        if close is None:
            raise NotFound("close")
        await pin_plan(tx.session, close_id)
        pinned = await repo.close_row(tx.session, close_id)
        version_id = None if pinned is None else pinned.close_plan_version_id
        if version_id is None:
            tx.record(
                "close_requests.not_published", target=Target("close", close_id), after=Ref(n=0)
            )
            return Published(None, 0, None)
        version = (await tx.session.execute(_VERSION, {"v": version_id})).first()
        if version is None or version[1] is None:
            tx.record(
                "close_requests.not_published", target=Target("close", close_id), after=Ref(n=0)
            )
            return Published(None, 0, None)
        number, authority = int(version[0]), cast(UUID, version[1])
        year, month = int(close.period[:4]), int(close.period[5:7])
        first_next = datetime(year + (month == 12), month % 12 + 1, 1).date()
        month_end = first_next - timedelta(days=1)
        specs: list[CloseRequestSpec] = []
        for row in (await tx.session.execute(_TEMPLATES, {"v": version_id})).all():
            specs.append(
                CloseRequestSpec(
                    template_id=row[0],
                    title=row[1],
                    category_path=tuple(row[2] or ()),
                    due_on=await add_business_days(month_end, int(row[3])),
                    client_visible=bool(row[4]),
                )
            )
        at = await business_now(tenant)
        generated = await generate_close_intake(
            tx,
            work_item_id=close_id,
            engagement_id=close.engagement_id,
            name=f"{_MONTHS[month - 1]} {year} close requests",
            specs=specs,
            authority=authority,
            at=at,
        )
        if generated.created:
            tx.emit(
                CloseRequestsPublished(
                    close_id=close_id,
                    engagement_id=close.engagement_id,
                    binder_id=generated.binder_id,
                    plan_version=number,
                    count=len(generated.created),
                )
            )
        tx.record(
            "close_requests.published",
            target=Target("close", close_id),
            after=Ref(
                binder_id=generated.binder_id,
                plan_version_id=version_id,
                created=len(generated.created),
            ),
        )
    return Published(generated.binder_id, len(generated.created), number)


@activity.defn(name=SECONDS_UNTIL)
async def seconds_until_activity(given: PublishInput) -> int:
    return await seconds_until_publish(UUID(given.tenant_id), UUID(given.close_id))


@activity.defn(name=PUBLISH)
async def publish_activity(given: PublishInput) -> PublishResult:
    done = await publish_requests(UUID(given.tenant_id), UUID(given.close_id))
    return PublishResult(done.created, done.plan_version)


ACTIVITIES = (seconds_until_activity, publish_activity)


async def schedule_publish(tenant_id: UUID, close_id: UUID) -> None:
    """Start the close's BD1 workflow (idempotent: a running one is kept)."""
    await dispatch(
        RequestPublishWorkflow,
        PublishInput(str(tenant_id), str(close_id)),
        id=workflow_id(tenant_id, close_id),
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


# --- CLS-03 reads
# ---------------------------------------------------------------------------------

_SOURCE_ROWS = text("SELECT id, source_row_ids FROM close_request_templates WHERE id = ANY(:ids)")
_RECEIVED: Final = frozenset({"received", "uploaded", "accepted"})


def _close_status(status: str, incorporation: str) -> str:
    if incorporation == "incorporated":
        return "incorporated"
    if incorporation == "pending_incorporation":
        return "pending_incorporation"
    if status in _RECEIVED:
        return "received"
    return "requested"


async def request_tree(
    ctx: AuthContext,
    close_id: UUID,
    *,
    q: str | None = None,
    status: str | None = None,
) -> RequestTreeOut:
    """CLS-03's tree: categories, then requests, with counts and the re-run offer."""
    from abacus.modules.closes.service import (
        visible_close,
    )

    close = await visible_close(ctx, close_id)
    async with tenant_session(ctx.tenant) as session:
        binder = await close_intake_binder(session, close_id)
        items = (
            []
            if binder is None
            else await intake_items(session, binder.id, await today(ctx.tenant))
        )
        template_ids = [i.template_id for i in items if i.template_id is not None]
        sources: dict[UUID, list[UUID]] = {}
        if template_ids:
            for tid, rows in (await session.execute(_SOURCE_ROWS, {"ids": template_ids})).all():
                sources[tid] = list(rows or ())
        version = None
        if close.close_plan_version_id is not None:
            found = (await session.execute(_VERSION, {"v": close.close_plan_version_id})).first()
            version = None if found is None else int(found[0])
    wanted = (q or "").casefold()
    groups: dict[tuple[str, ...], list[RequestNodeOut]] = defaultdict(list)
    for item in items:
        word = _close_status(item.status, item.incorporation_state)
        if status and word != status:
            continue
        if wanted and wanted not in item.title.casefold():
            continue
        rerun = (
            sources.get(item.template_id, [])
            if (item.template_id is not None and word == "incorporated")
            else []
        )
        groups[item.category_path].append(
            RequestNodeOut(
                node_id=f"r:{item.request_item_id}",
                kind="request",
                title=item.title,
                request_item_id=item.request_item_id,
                status=word,  # pyright: ignore[reportArgumentType] -- a request_close word
                received=int(word != "requested"),
                total=1,
                client_visible=item.client_visible,
                overdue=item.overdue,
                rerun_plan_row_ids=rerun,
                evidence_version_id=(
                    await latest_version_of(ctx.tenant, item.request_item_id)
                    if word != "requested"
                    else None
                ),
                due_on=item.due_on,
            )
        )
    nodes: list[RequestNodeOut] = []
    for path, requests in groups.items():
        if not path:
            nodes.extend(requests)
            continue
        node: RequestNodeOut | None = None
        for depth in range(len(path), 0, -1):
            children = [node] if node is not None else requests
            node = RequestNodeOut(
                node_id=f"c:{'/'.join(path[:depth])}"[:80],
                kind="category",
                title=path[depth - 1],
                received=sum(c.received for c in requests),
                total=sum(c.total for c in requests),
                children=children,
            )
        if node is not None:
            nodes.append(node)
    return RequestTreeOut(
        close_id=close_id,
        published=binder is not None,
        publishes_on=close.requests_publish_on,
        plan_version=version,
        nodes=nodes,
    )


async def close_questionnaire(ctx: AuthContext, close_id: UUID) -> CloseQuestionnaireOut:
    """CLS-03 d: the binder's questionnaire (none yet: 0 of 0)."""
    from abacus.modules.closes.service import (
        visible_close,
    )

    await visible_close(ctx, close_id)
    async with tenant_session(ctx.tenant) as session:
        binder = await close_intake_binder(session, close_id)
    if binder is None:
        return CloseQuestionnaireOut(answered=0, total=0, items=[])
    views = await questionnaires_of_list(ctx, binder.id)
    items = [
        CloseQuestionnaireAnswer(
            question=q.client_wording,
            answer=None if q.answer is None else str(q.answer)[:2000],
        )
        for v in views
        for q in v.questions
    ]
    return CloseQuestionnaireOut(
        answered=sum(v.answered for v in views), total=sum(v.total for v in views), items=items
    )
