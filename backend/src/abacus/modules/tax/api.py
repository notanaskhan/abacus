"""Public interface of the tax module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140): empty until its first epic lands.
"""

from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.tax.kind import TaxReturnKind

# F-03-T22: the `tax_return` work-item kind.
register_work_item_kind("tax_return", TaxReturnKind())

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[()] = ()
