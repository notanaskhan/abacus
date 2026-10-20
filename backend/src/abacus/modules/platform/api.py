"""Public interface of the platform module; other modules import only this (ADR-008)."""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.platform.routes import router
from abacus.modules.platform.service import BudgetInvalid
from abacus.modules.platform.slots import (
    SearchDocument,
    register_search_projection,
    search_document,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

__all__ = [
    "ROUTERS",
    "BudgetInvalid",
    "SearchDocument",
    "register_search_projection",
    "router",
    "search_document",
]
