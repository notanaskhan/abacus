"""Public interface of the adjustments module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140); A-06-T05 (DEC-1965): the C8 contract stub
(`docs/contracts/adjustments.md`). Nothing here posts to a client system (ADR-040).
"""

from abacus.modules.adjustments.contract import router
from abacus.modules.identity.api import AbacusRouter

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

__all__ = ["ROUTERS", "router"]
