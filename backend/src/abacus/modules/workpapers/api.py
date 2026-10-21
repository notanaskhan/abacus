"""Public interface of the workpapers module; other modules import only this (ADR-008).

Working papers (A-04; SPEC-308): the grid, formulas, citations and sign-offs.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.review.api import register_reviewable
from abacus.modules.workpapers.routes import checks_router, router
from abacus.modules.workpapers.service import (
    CodeTaken,
    NoAssuranceItem,
    WorkpaperInvalid,
    workpaper_reviewables,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router, checks_router)

# SPEC-313 (TASK-331): papers appear in the sign-off matrix and count toward G5.
register_reviewable("workpaper", workpaper_reviewables)

__all__ = [
    "ROUTERS",
    "CodeTaken",
    "NoAssuranceItem",
    "WorkpaperInvalid",
    "checks_router",
    "router",
]
