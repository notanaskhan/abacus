"""A close's intake binder, generated at BD1 (C-01-T19; C-01 §4.5 `RequestPublishWorkflow`; DEC-31,
DEC-09; QC-1). Owner: requests. Caller: closes, through `requests.api`.

`generate_close_intake` runs in the closes caller's unit of work, by the system at 09:00 firm time
on the close's first business day, under the authority of the named person who published the
close plan version the close pins (the plan's request templates are what that person approved;
ADR-005: the system only carries out a human's decision at the time it set). It:

- finds or creates the close's `close_intake` binder (one per close work item, part 1), published
  at once in the authority's name;
- creates one request per template not yet generated (idempotent on the close and the template:
  `linked_ref.close_template_id`), so a replay or a second activity attempt publishes nothing
  twice;
- keeps a template's `client_visible` flag: requests sourced from a bank feed are internal (QC-1)
  and never reach the portal;
- stamps every new request sent, with its due date from the template's business day.

Each request is audited `request_item.created` and announced (`request_item.created`). The
client's email for new close requests is the firm's POR-20 template (R-01, DB rows; C-01-T42
wires it); nothing here composes client text.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import transaction_context
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.models import RequestItem, RequestList
from abacus.modules.requests.repository import insert_binder, insert_request_item, stamp_sent

KIND: Final = "close_intake"
AUDIT_AREA: Final = "close"
WAVE: Final = "close"


@dataclass(frozen=True)
class CloseRequestSpec:
    """One request template of the pinned plan version (`close_request_templates`)."""

    template_id: UUID
    title: str
    category_path: tuple[str, ...]
    due_on: date
    client_visible: bool


@dataclass(frozen=True)
class GeneratedIntake:
    binder_id: UUID
    created: tuple[UUID, ...]
    existing: int


_GENERATED = text(
    "SELECT linked_ref ->> 'close_template_id' FROM request_items "
    "WHERE request_list_id = :b AND deleted_at IS NULL AND linked_ref ? 'close_template_id'"
)


async def close_intake_binder(session: AsyncSession, work_item_id: UUID) -> RequestList | None:
    return (
        await session.execute(
            select(RequestList).where(
                RequestList.work_item_id == work_item_id,
                RequestList.kind == KIND,
                RequestList.part == 1,
            )
        )
    ).scalar_one_or_none()


async def generate_close_intake(
    tx: UnitOfWork,
    *,
    work_item_id: UUID,
    engagement_id: UUID,
    name: str,
    specs: Sequence[CloseRequestSpec],
    authority: UUID,
    at: datetime,
) -> GeneratedIntake:
    """The module docstring's steps, in the caller's unit of work."""
    tenant = await transaction_context(tx.session)
    binder = await close_intake_binder(tx.session, work_item_id)
    if binder is None:
        binder = await insert_binder(
            tx.session,
            id=uuid4(),
            tenant_id=tenant.tenant_id,
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            name=name[:200],
            kind=KIND,
            part=1,
            status="published",
            published_at=at,
            published_by=authority,
            created_from="template",
            template_ref="close_plan",
        )
        tx.record(
            "request_list.created",
            target=Target("request_list", binder.id),
            after=Ref(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    done = {
        str(v) for v in (await tx.session.execute(_GENERATED, {"b": binder.id})).scalars() if v
    }
    created: list[UUID] = []
    for spec in specs:
        if str(spec.template_id) in done:
            continue
        item_id = uuid4()
        await insert_request_item(
            tx.session,
            item_id=item_id,
            tenant_id=tenant.tenant_id,
            engagement_id=engagement_id,
            request_list_id=binder.id,
            description=spec.title,
            audit_area=AUDIT_AREA,
            created_by=authority,
            binder_fields={
                "title": spec.title[:200],
                "client_visible": spec.client_visible,
                "due_on": spec.due_on,
                "wave": WAVE,
                "linked_ref": {
                    "type": "close_request_template",
                    "close_template_id": str(spec.template_id),
                    "category_path": list(spec.category_path),
                },
            },
        )
        tx.record(
            "request_item.created",
            target=Target("request_item", item_id),
            after=Ref(engagement_id=engagement_id, template=spec.template_id),
        )
        tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
        created.append(item_id)
    await stamp_sent(tx.session, created, at=at, by=authority)
    return GeneratedIntake(binder.id, tuple(created), len(done))


@dataclass(frozen=True)
class IntakeItem:
    request_item_id: UUID
    title: str
    category_path: tuple[str, ...]
    status: str
    client_visible: bool
    due_on: date | None
    incorporation_state: str
    template_id: UUID | None
    overdue: bool


async def intake_items(session: AsyncSession, binder_id: UUID, today: date) -> list[IntakeItem]:
    """The binder's live requests in creation order (the caller authorised the close)."""
    rows = (
        (
            await session.execute(
                select(RequestItem)
                .where(RequestItem.request_list_id == binder_id, RequestItem.deleted_at.is_(None))
                .order_by(RequestItem.created_at, RequestItem.id)
            )
        )
        .scalars()
        .all()
    )
    out: list[IntakeItem] = []
    for r in rows:
        ref = r.linked_ref or {}
        path = ref.get("category_path")
        template = ref.get("close_template_id")
        out.append(
            IntakeItem(
                request_item_id=r.id,
                title=r.title or r.description,
                category_path=tuple(str(p) for p in path) if isinstance(path, list) else (),
                status=r.status,
                client_visible=r.client_visible,
                due_on=r.due_on,
                incorporation_state=r.incorporation_state,
                template_id=UUID(str(template)) if template else None,
                overdue=r.due_on is not None
                and r.due_on < today
                and r.status in ("requested", "draft"),
            )
        )
    return out
