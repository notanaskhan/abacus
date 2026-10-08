"""Public interface of the notifications module; other modules import only this (ADR-008).
Nothing imports it to send: modules publish domain events, and this module subscribes."""

from abacus.modules.notifications.catalogue import CATALOGUE, TEMPLATES
from abacus.modules.notifications.routes import router
from abacus.modules.notifications.service import notify, run_purge_job

# The relay hands each catalogued event to `notify` (SPEC-013 §6).
SUBSCRIPTIONS = dict.fromkeys(CATALOGUE, notify)
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

__all__ = [
    "ACTIVITIES",
    "CATALOGUE",
    "SUBSCRIPTIONS",
    "TEMPLATES",
    "WORKFLOWS",
    "router",
    "run_purge_job",
]
