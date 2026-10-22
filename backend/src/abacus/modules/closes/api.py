"""Public interface of the closes module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140): empty until its first epic lands.
"""

from abacus.modules.closes.kind import CloseKind
from abacus.modules.engagements.api import register_work_item_kind

# F-03-T22: the `close` work-item kind.
register_work_item_kind("close", CloseKind())

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[()] = ()
