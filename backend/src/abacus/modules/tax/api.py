"""Public interface of the tax module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). T-01-T02: the engine-bridge and e-file-record stubs
(`engine_contract`). T-01-T18: final approval and its blocker slot (`approval`).
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.organisations.api import register_office_facts
from abacus.modules.platform.api import register_search_projection
from abacus.modules.tax.approval import Blocker as ApprovalBlocker
from abacus.modules.tax.approval import eligibility as final_approval_eligibility
from abacus.modules.tax.approval import register as register_approval
from abacus.modules.tax.approval import register_final_approval_blocker
from abacus.modules.tax.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.tax.board import KIND as SEARCH_TYPE
from abacus.modules.tax.board import return_search_document, returns_by_office
from abacus.modules.tax.due_dates import (
    FORM_FOR_RULES,
    on_reference_set_published,
    recompute_unfiled,
    rule_texts,
    set_extended,
)
from abacus.modules.tax.engine_contract import engine_router
from abacus.modules.tax.k1_contract import k1_router, portal_k1_router
from abacus.modules.tax.kind import TaxReturnKind
from abacus.modules.tax.returns_routes import returns_router
from abacus.modules.tax.status import TRANSITIONS, StaleReturn, TransitionRefused, next_status
from abacus.modules.tax.transitions import apply_transition, record_sync_state

# F-03-T22: the `tax_return` work-item kind.
register_work_item_kind("tax_return", TaxReturnKind())

# DEC-121: the audit explorer asks which engagement each `tax_return` target belongs to.
register_engagement_owners(AUDIT_KINDS, audit_owners)
# T-02-T09: ADM-03a's per-office "TY returns" count (G-01) and the C15 search projection.
register_office_facts("tax_returns", returns_by_office)
register_search_projection(SEARCH_TYPE, return_search_document)
# T-01-T18: the return's reviewable facts and the `tax_final_approval` gate kind (C13).
register_approval()

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    returns_router,  # tax returns v1 (T-02-T09 board); `/summary` before `/{return_id}`
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
    "final_approval_eligibility",
    "next_status",
    "recompute_unfiled",
    "record_sync_state",
    "register_final_approval_blocker",
    "rule_texts",
    "set_extended",
]
