"""Public interface of the assurance module; other modules import only this (ADR-008).

The audit line's read models and actions: the AUD-06 trial balance first (SPEC-309).
"""

from abacus.modules.assurance.routes import router
from abacus.modules.identity.api import AbacusRouter

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

__all__ = ["ROUTERS", "router"]
