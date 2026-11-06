"""Public interface of the workbench module; other modules import only this (ADR-008).

P-10-T09: C6 v2's sessions half, a stub; P-10-T04 owns the tables.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.workbench.sessions_contract import agent_badge_router, sessions_router

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (sessions_router, agent_badge_router)

__all__ = ["ROUTERS"]
