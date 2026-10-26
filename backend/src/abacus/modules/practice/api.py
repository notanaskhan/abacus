"""Public interface of the practice module; other modules import only this (ADR-008).

First routes: the C13 home half (I-01-T02), `GET /v1/home` behind `home.dashboard`.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.practice.home_contract import router as home_router

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (home_router,)
