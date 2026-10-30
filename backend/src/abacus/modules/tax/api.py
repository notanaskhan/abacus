"""Public interface of the tax module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). T-01-T02: the engine-bridge and e-file-record stubs
(`engine_contract`) and final approval's blocker API, raising until T-01-T27.
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.tax.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.tax.due_dates import (
    FORM_FOR_RULES,
    on_reference_set_published,
    recompute_unfiled,
    rule_texts,
    set_extended,
)
from abacus.modules.tax.engine_contract import (
    ApprovalBlocker,
    engine_router,
    final_approval_blockers,
    register_final_approval_blocker,
)
from abacus.modules.tax.k1_contract import k1_router, portal_k1_router
from abacus.modules.tax.kind import TaxReturnKind
from abacus.modules.tax.returns_contract import returns_router
from abacus.modules.tax.status import TRANSITIONS, StaleReturn, TransitionRefused, next_status
from abacus.modules.tax.transitions import apply_transition, record_sync_state

# F-03-T22: the `tax_return` work-item kind.
register_work_item_kind("tax_return", TaxReturnKind())

# DEC-121: the audit explorer asks which engagement each `tax_return` target belongs to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    returns_router,  # tax returns v1 (T-02-T01 stub); `/summary` before `/{return_id}`
    engine_router,  # the engine bridge and the e-file record (T-01-T02 stub)
    k1_router,  # K-1 packages (T-02-T02 stub)
    portal_k1_router,  # POR-13 (T-02-T02 stub)
)

# T-02-T10: a published reference-set correction recomputes every unfiled return's due dates
# (K-02-T12 fans `reference_set.published` out per tenant).
SUBSCRIPTIONS = {"reference_set.published": on_reference_set_published}

__all__ = [
    "FORM_FOR_RULES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "TRANSITIONS",
    "ApprovalBlocker",
    "StaleReturn",
    "TransitionRefused",
    "apply_transition",
    "final_approval_blockers",
    "next_status",
    "recompute_unfiled",
    "record_sync_state",
    "register_final_approval_blocker",
    "rule_texts",
    "set_extended",
]
