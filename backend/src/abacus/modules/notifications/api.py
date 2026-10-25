"""Public interface of the notifications module; other modules import only this (ADR-008).
Nothing imports it to send: modules publish domain events, and this module subscribes. Its email
channel renders and sends through communications (P-01-T12; COMM-001)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.notifications.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.notifications.catalogue import CATALOGUE, TEMPLATES
from abacus.modules.notifications.contract import feed_router, preferences_router
from abacus.modules.notifications.email import ACTIVITIES as EMAIL_ACTIVITIES
from abacus.modules.notifications.email import WORKFLOWS as EMAIL_WORKFLOWS
from abacus.modules.notifications.email import configure_email_starter
from abacus.modules.notifications.kinds import (
    NotificationKind,
    Row,
    kind_of,
    register_kind,
    registered,
)
from abacus.modules.notifications.purge import ACTIVITIES as PURGE_ACTIVITIES
from abacus.modules.notifications.purge import SCHEDULES
from abacus.modules.notifications.purge import WORKFLOWS as PURGE_WORKFLOWS
from abacus.modules.notifications.routes import router
from abacus.modules.notifications.service import notify, run_purge_job
from abacus.modules.notifications.workflows import (
    NOTIFICATION_PURGE_ID,
    DeliveryOutcome,
    NotificationEmailInput,
    NotificationEmailWorkflow,
    NotificationPurgeWorkflow,
    notification_email_id,
)

# The relay hands each catalogued event to `notify` (SPEC-013 §6).
SUBSCRIPTIONS = dict.fromkeys(CATALOGUE, notify)
# P-01-T12: the email channel's workflow and activities (the worker composes them).
# Q-01-T26: the daily purge runs as a workflow on a Schedule (`SCHEDULES`).
WORKFLOWS: dict[type, str] = {**EMAIL_WORKFLOWS, **PURGE_WORKFLOWS}
ACTIVITIES: tuple[object, ...] = (*EMAIL_ACTIVITIES, *PURGE_ACTIVITIES)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (feed_router, router, preferences_router)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "CATALOGUE",
    "NOTIFICATION_PURGE_ID",
    "ROUTERS",
    "SCHEDULES",
    "SUBSCRIPTIONS",
    "TEMPLATES",
    "WORKFLOWS",
    "DeliveryOutcome",
    "NotificationEmailInput",
    "NotificationEmailWorkflow",
    "NotificationKind",
    "NotificationPurgeWorkflow",
    "Row",
    "configure_email_starter",
    "kind_of",
    "notification_email_id",
    "register_kind",
    "registered",
    "router",
    "run_purge_job",
]
