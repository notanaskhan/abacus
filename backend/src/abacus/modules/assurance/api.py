"""Public interface of the assurance module; other modules import only this (ADR-008).

The audit line's read models and actions: the AUD-06 trial balance first (SPEC-309).
"""

from abacus.modules.assurance.routes import router
from abacus.modules.assurance.trial_balance import tb_reviewables
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.review.api import register_reviewable

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

# SPEC-313 (TASK-325): trial balances appear in the sign-off matrix and count toward G5.
register_reviewable("trial_balance", tb_reviewables)

__all__ = ["ROUTERS", "router"]
