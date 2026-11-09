"""Public interface of the collaboration module; other modules import only this (ADR-008).

P-05 (SPEC-650; ADR-236 proposed): comments v2 and to-dos. P-05-T03 lands the contract stub
(`contract.py`, 501 behind `collaboration.v2`); the anchor slot and the services arrive with
P-05-T05 and T06.
"""

from abacus.modules.collaboration.contract import threads_router, todos_router
from abacus.modules.identity.api import AbacusRouter

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    threads_router,  # P-05-T03 stub: /v1/comment-threads*, /v1/thread-comments*, candidates
    todos_router,  # P-05-T03 stub: /v1/todos*
)

__all__ = ["ROUTERS"]
