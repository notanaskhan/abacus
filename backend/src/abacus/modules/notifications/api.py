"""Public interface of the notifications module; other modules import only this (ADR-008).
Nothing imports it to send: modules publish domain events, and this module subscribes."""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.notifications.catalogue import CATALOGUE, TEMPLATES
from abacus.modules.notifications.routes import router
from abacus.modules.notifications.service import notify, run_purge_job

# The relay hands each catalogued event to `notify` (SPEC-013 §6).
SUBSCRIPTIONS = dict.fromkeys(CATALOGUE, notify)
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

__all__ = [
    "ACTIVITIES",
    "CATALOGUE",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "TEMPLATES",
    "WORKFLOWS",
    "router",
    "run_purge_job",
]
