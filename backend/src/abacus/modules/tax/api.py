"""Public interface of the tax module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). T-01-T02: the engine-bridge and e-file-record stubs
(`engine_contract`) and final approval's blocker API, raising until T-01-T27.
"""

from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.tax.engine_contract import (
    ApprovalBlocker,
    engine_router,
    final_approval_blockers,
    register_final_approval_blocker,
)
from abacus.modules.tax.kind import TaxReturnKind
from abacus.modules.tax.returns_contract import returns_router

# F-03-T22: the `tax_return` work-item kind.
register_work_item_kind("tax_return", TaxReturnKind())

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    returns_router,  # tax returns v1 (T-02-T01 stub); `/summary` before `/{return_id}`
    engine_router,  # the engine bridge and the e-file record (T-01-T02 stub)
)

__all__ = [
    "ROUTERS",
    "ApprovalBlocker",
    "final_approval_blockers",
    "register_final_approval_blocker",
]
