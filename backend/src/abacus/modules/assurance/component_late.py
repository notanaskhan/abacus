"""Component deliverables: the late sweep, the Today item and follow-ups (A-09-T28; A-09 §3.6
Story 6.3; SPEC-658 F6; AUD-35 d; POR-23 c; DEC-5406; amber).

- **Sweep** (`ComponentLateSweep`, hourly on the batch class): for each firm, once its local time
  is past 06:00, every Expected deliverable past its due date and not yet stamped goes late:
  `went_late_at` is stamped and `component_deliverable.late` is emitted once (the notification
  `component_deliverable_late` to the engagement's partner and managers, resolved from current
  memberships when it is delivered, so a person who left is never told). One firm's failure
  never stops the rest.
- **Today**: a late deliverable is a HOME-02 gate (`component_deliverable_late`) on the
  engagement partner, which the Today brief lists once ("Interim memo · 1 day late").
- **Follow-up** (P-25 off): the firm's `component_deliverable_follow_up` email template merged
  with code's values (the deliverable, its due date, the auditor's organisation) and sent by a
  person to the auditor's contact. No model writes it; a real firm never receives model text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from sqlalchemy import text

    from abacus.kernel.classification import classified
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.dispatch import PlatformSchedule
    from abacus.kernel.errors import NotFound
    from abacus.kernel.logging import get_logger
    from abacus.kernel.uow import DomainEvent, Ref, Target, uow
    from abacus.modules.identity.api import AuthContext, Forbidden, authorise

_log = get_logger(__name__)
SWEEP_ID: Final = "component_late:platform"
LOCAL_HOUR: Final = 6
GATE: Final = "component_deliverable_late"
FOLLOW_UP_TEMPLATE: Final = "component_deliverable_follow_up"
_I = classified("internal")


class ComponentDeliverableLate(DomainEvent):
    """Once per deliverable: C16 `component_deliverable_late` and the HOME-02 gate."""

    event_type: ClassVar[str] = "component_deliverable.late"

    deliverable_id: Annotated[UUID, _I]
    component_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


_DUE: Final = text(
    "SELECT d.id, d.engagement_id, a.component_id FROM component_deliverables d "
    "JOIN component_auditors a ON a.id = d.component_auditor_id "
    "WHERE d.status = 'expected' AND d.due_on < :today AND d.went_late_at IS NULL"
)
_STAMP: Final = text(
    "UPDATE component_deliverables SET went_late_at = clock_timestamp() WHERE id = :d "
    "AND went_late_at IS NULL AND status = 'expected' RETURNING id"
)
_LATE: Final = text(
    "SELECT d.id, d.engagement_id, d.work_item_id, d.due_on FROM component_deliverables d "
    "WHERE d.status = 'expected' AND d.went_late_at IS NOT NULL"
)


def sweep_due(local_now: datetime) -> bool:
    """A firm is swept once its own clock reads 06:00 or later."""
    return local_now.hour >= LOCAL_HOUR


async def sweep_tenant(tenant_id: UUID) -> int:
    from abacus.kernel.clock import now, today

    tenant = TenantContext(tenant_id, "system", "component_late:sweep")
    if not sweep_due(await now(tenant)):
        return 0
    day = await today(tenant)
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_DUE, {"today": day})).mappings().all()
    went = 0
    for r in rows:
        async with uow(tenant) as tx:
            if await tx.session.scalar(_STAMP, {"d": r["id"]}) is None:
                continue
            tx.record(
                "component_deliverable.went_late",
                target=Target("component_deliverable", cast(UUID, r["id"])),
            )
            tx.emit(
                ComponentDeliverableLate(
                    deliverable_id=cast(UUID, r["id"]),
                    component_id=cast(UUID, r["component_id"]),
                    engagement_id=cast(UUID, r["engagement_id"]),
                )
            )
            went += 1
    return went


@activity.defn(name="assurance.component_late.sweep")
async def sweep_activity() -> int:
    from abacus.modules.identity.api import firm_tenant_ids

    went = 0
    for tenant_id in await firm_tenant_ids():
        try:
            went += await sweep_tenant(tenant_id)
        except Exception as exc:  # one firm's failure is logged; the sweep goes on
            _log.error(
                "component_late.sweep_failed", tenant_id=str(tenant_id), error=type(exc).__name__
            )
    return went


@workflow.defn(name="ComponentLateSweep")
class ComponentLateSweep:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "assurance.component_late.sweep",
            result_type=int,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=30)),
        )


# --- HOME-02 / Today -----------------------------------------------------------------------------


async def late_gates(tenant: TenantContext, engagement_id: UUID | None) -> list[object]:
    from abacus.modules.review.api import OpenGate

    async with tenant_session(tenant) as session:
        rows = (await session.execute(_LATE)).mappings().all()
    return [
        OpenGate(
            r["id"],
            r["engagement_id"],
            role="engagement_partner",
            due_on=cast(date, r["due_on"]),
            work_item_id=r["work_item_id"],
        )
        for r in rows
        if engagement_id is None or r["engagement_id"] == engagement_id
    ]


def register() -> None:
    from abacus.modules.communications.api import register_email_template
    from abacus.modules.review.api import GateSource, register_gate_source

    register_gate_source(
        GateSource(
            "component_deliverable",
            "send",  # the follow-up a person sends (Approvals & sends)
            "component_deliverable.read",
            frozenset(
                {
                    "component_deliverable.late",
                    "component_deliverable.uploaded",
                    "component_deliverable.changed",
                }
            ),
            late_gates,  # type: ignore[arg-type] -- returns OpenGate rows
        )
    )
    register_email_template(
        FOLLOW_UP_TEMPLATE,
        ("third_party",),
        ("organisation_name", "deliverable_title", "due_date", "firm_name", "portal_link"),
        ("room",),
        ("AUD-35", "POR-23"),
        firm_editable=True,
        name="Component deliverable follow-up",
        used_by_label="AUD-35 late deliverables",
    )


# --- follow-ups ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class FollowUpDraft:
    template_key: str
    recipient_contact_id: UUID
    variables: dict[str, str]


_FOR_FOLLOW_UP: Final = text(
    "SELECT d.id, d.title, d.due_on, d.status, d.engagement_id, a.organisation_name, "
    "a.ep_contact_id FROM component_deliverables d JOIN component_auditors a "
    "ON a.id = d.component_auditor_id WHERE d.id = :d"
)


async def _row(ctx: AuthContext, deliverable_id: UUID) -> dict[str, object]:
    from abacus.modules.engagements.api import get_ref

    async with tenant_session(ctx.tenant) as session:
        r = (await session.execute(_FOR_FOLLOW_UP, {"d": deliverable_id})).mappings().first()
    if r is None or r["ep_contact_id"] is None:
        raise NotFound("component_deliverable")
    resource = (await get_ref(ctx, cast(UUID, r["engagement_id"]))).resource()
    await authorise(ctx, "component_deliverable.manage", resource)
    return dict(r)


async def draft_follow_up(ctx: AuthContext, deliverable_id: UUID) -> FollowUpDraft:
    """The drafted follow-up card (AUD-35 d): the template's key and code's values."""
    r = await _row(ctx, deliverable_id)
    return FollowUpDraft(
        FOLLOW_UP_TEMPLATE,
        cast(UUID, r["ep_contact_id"]),
        {
            "organisation_name": str(r["organisation_name"]),
            "deliverable_title": str(r["title"]),
            "due_date": f"{cast(date, r['due_on']):%a %b %-d, %Y}",
        },
    )


async def send_follow_up(ctx: AuthContext, deliverable_id: UUID, idempotency_key: str) -> UUID:
    """A person sends the drafted follow-up ("Follow-up sent to Renee Pruett · 8:52 AM")."""
    from abacus.modules.communications.api import RecipientRef, SendScope, send_templated

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("component_deliverable.manage", "role")
    draft = await draft_follow_up(ctx, deliverable_id)
    r = await _row(ctx, deliverable_id)
    outcome = await send_templated(
        ctx,
        FOLLOW_UP_TEMPLATE,
        RecipientRef("contact", draft.recipient_contact_id),
        draft.variables,
        scope=SendScope(engagement_id=cast(UUID, r["engagement_id"])),
        idempotency_key=f"component_follow_up:{deliverable_id}:{idempotency_key}",
    )
    async with uow(ctx.tenant) as tx:
        tx.record(
            "follow_up.sent",
            target=Target("component_deliverable", deliverable_id),
            after=Ref(message=outcome.message_id),
        )
    return outcome.message_id


WORKFLOWS: Final[dict[type, str]] = {ComponentLateSweep: "batch"}
ACTIVITIES: Final[tuple[object, ...]] = (sweep_activity,)
SCHEDULES: Final[tuple[PlatformSchedule, ...]] = (
    PlatformSchedule(
        id=SWEEP_ID,
        workflow=ComponentLateSweep,
        every=timedelta(hours=1),
        note="A-09-T28: component deliverables go late once at 06:00 firm time",
    ),
)
