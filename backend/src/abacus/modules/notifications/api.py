"""Public interface of the notifications module; other modules import only this (ADR-008).
Nothing imports it to send: modules publish domain events, and this module subscribes."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.notifications.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.notifications.catalogue import CATALOGUE, TEMPLATES
from abacus.modules.notifications.contract import feed_router, preferences_router
from abacus.modules.notifications.kinds import (
    NotificationKind,
    Row,
    kind_of,
    register_kind,
    registered,
)
from abacus.modules.notifications.routes import router
from abacus.modules.notifications.service import notify, run_purge_job

# The relay hands each catalogued event to `notify` (SPEC-013 §6).
SUBSCRIPTIONS = dict.fromkeys(CATALOGUE, notify)
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (feed_router, router, preferences_router)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "CATALOGUE",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "TEMPLATES",
    "WORKFLOWS",
    "NotificationKind",
    "Row",
    "kind_of",
    "register_kind",
    "registered",
    "router",
    "run_purge_job",
]
