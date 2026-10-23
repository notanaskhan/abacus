"""The notification email channel (P-01-T12; C16; SPEC-013 AC-1; P-01 AC 4.1.2).

At fan-out, a new notification gets an email delivery row when its recipient's email choice
for the kind is on (their stored preference, else the kind's `email_default`):
- `notifications.email` on (the per-firm kill switch): the row is `queued` and
  `NotificationEmail` starts, once per notification (`notification_email:<tenant>:<id>`);
- off: the row is `suppressed` and nothing is sent.

Rows hold identifiers and codes only. The email itself is rendered and sent by communications
(`send_notification_email`, through `send_email`: the synthetic sink rule and suppression
apply). One notification gives at most one delivery row (UNIQUE) and one workflow, so a
redelivered event sends nothing twice.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel._flags import NOTIFICATIONS_EMAIL
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import MissingAuditEvent, Target, uow
from abacus.modules.communications.api import NotificationMail, send_notification_email
from abacus.modules.identity.api import engagement_resource, member_facts, walled_from
from abacus.modules.notifications.catalogue import CATALOGUE, TEMPLATES
from abacus.modules.notifications.kinds import kind_of
from abacus.modules.notifications.repository import (
    delivery_facts,
    email_choices,
    insert_delivery,
    made_for_event,
    queued_for_event,
    settle_delivery,
)
from abacus.modules.notifications.workflows import (
    DeliveryOutcome,
    NotificationEmailInput,
    NotificationEmailWorkflow,
    notification_email_id,
)

WORKFLOWS: dict[type, WorkClass] = {NotificationEmailWorkflow: "time_sensitive"}
register_work_classes(WORKFLOWS)
_STATUS_OF: Final = {"sent": "sent", "suppressed": "suppressed"}
_log = get_logger(__name__)
_emails = meter(__name__).create_counter(
    "abacus.notifications.emails", description="Notification email outcomes, by kind and status"
)
# The kind's sentence (SPEC-013 AC-7's fixed text, keyed by its event).
SENTENCES: Final = {entry.kind: TEMPLATES[event] for event, entry in CATALOGUE.items()}

Starter = Callable[[NotificationEmailInput], Awaitable[None]]


async def _start(given: NotificationEmailInput) -> None:
    try:
        await dispatch(
            NotificationEmailWorkflow,
            given,
            id=notification_email_id(given.tenant_id, given.notification_id),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    except WorkflowAlreadyStartedError:
        return  # this notification's email has run already: never twice


_starter: Starter = _start


def configure_email_starter(starter: Starter | None) -> None:
    """Tests: start emails some other way (None restores `kernel.dispatch`)."""
    global _starter
    _starter = starter or _start


async def queue_emails(ctx: TenantContext, event_id: UUID, code: str) -> None:
    """After the event's notifications are made: delivery rows for the recipients who want
    email, in one unit of work with their audit events."""
    kind = kind_of(code)
    if kind is None:
        return
    async with tenant_session(ctx) as session:
        made = await made_for_event(session, event_id, code)
        chosen = await email_choices(session, code, [user for user, _ in made.values()])
    # INV-4 (P-01-T14): notification email goes to firm staff only, never to a client user
    # (a client may be mentioned in a comment and so hold an in-app row).
    staff = {
        user
        for user, _ in made.values()
        if (facts := await member_facts(ctx, user)) is not None and not facts.client
    }
    wanted = [
        n
        for n, (user, _) in made.items()
        if user in staff and chosen.get(user, kind.email_default)
    ]
    if not wanted:
        return
    status = "queued" if await flag_enabled(ctx, NOTIFICATIONS_EMAIL) else "suppressed"
    try:
        async with uow(ctx) as tx:
            for notification_id in wanted:
                if await insert_delivery(tx.session, ctx.tenant_id, notification_id, status):
                    tx.record(
                        f"notification_delivery.{status}",
                        target=Target("notification", notification_id),
                    )
    except MissingAuditEvent:
        return  # a redelivery: every row was already there


async def start_queued(ctx: TenantContext, event_id: UUID) -> int:
    """Start the email of every queued delivery of the event (again after a redelivery: the
    workflow id lets each start once)."""
    async with tenant_session(ctx) as session:
        queued = await queued_for_event(session, event_id)
    for notification_id in queued:
        await _starter(NotificationEmailInput(str(ctx.tenant_id), str(notification_id)))
    return len(queued)


async def _walled(tenant: TenantContext, user: UUID, engagement_id: UUID | None) -> bool:
    """INV-3 at send time: a wall added since the fan-out stops the email."""
    if engagement_id is None:
        return False
    try:
        client = (await engagement_resource(tenant, engagement_id)).client_id
    except NotFound:
        return True
    return client is not None and client in await walled_from(tenant, user)


@activity.defn(name="notifications.send_email")
async def send_email_activity(given: NotificationEmailInput) -> str:
    """Proves the delivery from its rows, then renders and sends through communications."""
    tenant_id, notification_id = UUID(given.tenant_id), UUID(given.notification_id)
    tenant = TenantContext(tenant_id, "system", "notifications:email")
    async with tenant_session(tenant) as session:
        facts = await delivery_facts(session, notification_id)
    if facts is None:
        return "missing"
    if facts.status != "queued":
        return facts.status  # settled already: nothing is sent again
    if not await flag_enabled(tenant, NOTIFICATIONS_EMAIL):
        return "suppressed"  # the kill switch, turned off since the fan-out
    if await _walled(tenant, facts.recipient_user_id, facts.engagement_id):
        return "suppressed"
    return await send_notification_email(
        NotificationMail(
            tenant_id=tenant_id,
            notification_id=notification_id,
            kind=facts.kind,
            recipient_user_id=facts.recipient_user_id,
            engagement_id=facts.engagement_id,
            sentence=SENTENCES.get(facts.kind, "You have a new notification."),
        )
    )


@activity.defn(name="notifications.record_delivery")
async def record_delivery_activity(given: DeliveryOutcome) -> str:
    """The outcome on the delivery row, once, with its audit event (`notification_delivery.*`)."""
    tenant = TenantContext(UUID(given.tenant_id), "system", "notifications:email")
    notification_id = UUID(given.notification_id)
    status = _STATUS_OF.get(given.outcome, "failed")
    if given.outcome == "missing":
        return given.outcome  # no delivery row: nothing to settle
    try:
        async with uow(tenant) as tx:
            if await settle_delivery(
                tx.session,
                notification_id,
                status,
                str(notification_id) if status == "sent" else None,
            ):
                tx.record(
                    f"notification_delivery.{status}",
                    target=Target("notification", notification_id),
                )
    except MissingAuditEvent:
        return status  # it was settled already
    async with tenant_session(tenant) as session:
        facts = await delivery_facts(session, notification_id)
    _emails.add(1, {"kind": facts.kind if facts else "unknown", "status": status})
    _log.info("notification_email.settled", notification_id=notification_id, status=status)
    return status


ACTIVITIES: tuple[object, ...] = (send_email_activity, record_delivery_activity)
