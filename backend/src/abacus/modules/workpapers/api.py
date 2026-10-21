"""Public interface of the workpapers module; other modules import only this (ADR-008).

Working papers (A-04; SPEC-308): the grid, formulas, citations and sign-offs.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.workpapers.routes import router
from abacus.modules.workpapers.service import CodeTaken, NoAssuranceItem, WorkpaperInvalid

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

__all__ = ["ROUTERS", "CodeTaken", "NoAssuranceItem", "WorkpaperInvalid", "router"]
