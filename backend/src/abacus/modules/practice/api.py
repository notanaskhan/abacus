"""Public interface of the practice module; other modules import only this (ADR-008).

First routes: the C13 home half (I-01-T02), `GET /v1/home` behind `home.dashboard`. Worker
parts (I-01-T12): the client-activity projector and its daily prune.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.practice.activity import rebuild_home_activity
from abacus.modules.practice.home_contract import router as home_router
from abacus.modules.practice.jobs import ACTIVITIES, SCHEDULES, SUBSCRIPTIONS, WORKFLOWS
from abacus.modules.practice.workflows import HOME_ACTIVITY_PRUNE_ID, HomeActivityPruneWorkflow

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (home_router,)

__all__ = [
    "ACTIVITIES",
    "HOME_ACTIVITY_PRUNE_ID",
    "ROUTERS",
    "SCHEDULES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "HomeActivityPruneWorkflow",
    "rebuild_home_activity",
]
