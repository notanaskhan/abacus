"""Public interface of the assurance module; other modules import only this (ADR-008).

The audit line's read models and actions: the AUD-06 trial balance first (SPEC-309).
"""

from abacus.modules.assurance.completion import g6, g7, g8, g9
from abacus.modules.assurance.completion_routes import router as completion_router
from abacus.modules.assurance.mapping import mapping_reviewables
from abacus.modules.assurance.mapping_routes import firm_router as grouping_router
from abacus.modules.assurance.mapping_routes import router as mapping_router
from abacus.modules.assurance.routes import router
from abacus.modules.assurance.trial_balance import tb_reviewables
from abacus.modules.engagements.api import register_gate_provider
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.review.api import register_reviewable

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router, completion_router, mapping_router, grouping_router)

# SPEC-313 (TASK-331): trial balances appear in the sign-off matrix and count toward G5.
register_reviewable("trial_balance", tb_reviewables)
# SPEC-316 (TASK-345): the account mapping is signed like a working paper.
register_reviewable("mapping_set", mapping_reviewables)

# SPEC-314 (TASK-332): EQR concurrence, the representation letter, release and the archive.
register_gate_provider("G6", g6)
register_gate_provider("G7", g7)
register_gate_provider("G8", g8)
register_gate_provider("G9", g9)

__all__ = ["ROUTERS", "completion_router", "router"]
