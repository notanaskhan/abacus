"""Public interface of the audit_trail module; other modules import only this (ADR-008)."""

from abacus.modules.audit_trail.routes import router
from abacus.modules.identity.api import AbacusRouter

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

__all__ = ["ROUTERS", "router"]
