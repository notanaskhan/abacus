"""Public interface of the notices module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). N-04-T02 (DEC-2051): the notices v1 contract stub
(`docs/contracts/notices.md`).
"""

from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.notices.contract import router
from abacus.modules.notices.kind import NoticeKind

# F-03-T22: the `notice` work-item kind.
register_work_item_kind("notice", NoticeKind())

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)
