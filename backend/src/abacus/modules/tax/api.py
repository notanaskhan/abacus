"""Public interface of the tax module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). T-01-T02: the engine-bridge and e-file-record stubs
(`engine_contract`). T-01-T18: final approval and its blocker slot (`approval`).
"""

from abacus.kernel.audit_owners import register_engagement_owners, register_entity_owners
from abacus.kernel.uow import OutboxEvent
from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.identity.api import AbacusRouter, register_scope_resolver
from abacus.modules.organisations.api import register_office_facts
from abacus.modules.platform.api import register_search_projection
from abacus.modules.tax import consent_capture, filed_delivery, filing, k1_release
from abacus.modules.tax.approval import Blocker as ApprovalBlocker
from abacus.modules.tax.approval import eligibility as final_approval_eligibility
from abacus.modules.tax.approval import register as register_approval
from abacus.modules.tax.approval import register_final_approval_blocker
from abacus.modules.tax.audit_targets import (
    AUDIT_KINDS,
    ENTITY_KINDS,
    audit_entities,
    audit_owners,
)
from abacus.modules.tax.board import KIND as SEARCH_TYPE
from abacus.modules.tax.board import return_search_document, returns_by_office
from abacus.modules.tax.due_dates import (
    FORM_FOR_RULES,
    on_reference_set_published,
    recompute_unfiled,
    register_due_dates_source,
    rule_texts,
    set_extended,
)
from abacus.modules.tax.engine_contract import engine_router, portal_filing_router
from abacus.modules.tax.engine_import import import_file as import_engine_file
from abacus.modules.tax.engine_sync import register as register_engine_sync
from abacus.modules.tax.filed_delivery import FiledReturn, filed_returns
from abacus.modules.tax.k1_contract import k1_router, portal_k1_router
from abacus.modules.tax.k1_packages import draft_k1_blockers, package_scope
from abacus.modules.tax.k1_packages import share_internal as share_k1_internal
from abacus.modules.tax.k1_release_workflow import (
    K1DeliveryInput,
    K1ReleaseFailure,
    K1ReleaseInput,
    K1ReleaseWorkflow,
)
from abacus.modules.tax.kind import TaxReturnKind
from abacus.modules.tax.overview import on_binder_published, on_sign_off_recorded
from abacus.modules.tax.returns_routes import returns_router
from abacus.modules.tax.status import TRANSITIONS, StaleReturn, TransitionRefused, next_status
from abacus.modules.tax.tax_profile import register as register_tax_profile
from abacus.modules.tax.transitions import apply_transition, record_sync_state

# T-01-T10: §7216 consent capture behind C19's routes, and the `consent_set` envelope source.
consent_capture.register()
filing.register()  # T-01-T36: the `tax_return` envelope source (C7 v1.1)

# F-03-T22: the `tax_return` work-item kind.
register_work_item_kind("tax_return", TaxReturnKind())

# DEC-121: the audit explorer asks which engagement each `tax_return` target belongs to.
register_engagement_owners(AUDIT_KINDS, audit_owners)
register_entity_owners(ENTITY_KINDS, audit_entities)  # T-01: a tax profile's rows
# T-02-T09: ADM-03a's per-office "TY returns" count (G-01) and the C15 search projection.
register_office_facts("tax_returns", returns_by_office)
register_search_projection(SEARCH_TYPE, return_search_document)
# T-01-T18: the return's reviewable facts and the `tax_final_approval` gate kind (C13).
register_approval()
# T-02-T20 (DV-4): a K-1 shared to a return as a draft blocks its final approval until released.
register_final_approval_blocker("draft_k1", draft_k1_blockers)
# T-02-T21 (DEC-34): a `k1_recipient` grant's `k1_package` scope (own-only in the portal reads).
register_scope_resolver("k1_package", package_scope)
# T-01-T43: CLI-05's authorizations, elections, transcripts and comparisons (DEC-1651).
register_tax_profile()
# T-01-T27: the engine-sync gate kinds (C13) and notification kinds (C16) (DEC-1463).
register_engine_sync()

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    returns_router,  # tax returns v1 (T-02-T09 board); `/summary` before `/{return_id}`
    engine_router,  # the engine bridge and the e-file record (T-01-T02 stub)
    k1_router,  # K-1 packages (T-02-T02 stub)
    portal_k1_router,  # POR-13 (T-02-T02 stub)
    portal_filing_router,  # T-01-T41: the filed client copy's download
)


# T-02-T10: a published reference-set correction recomputes every unfiled return's due dates
# (K-02-T12 fans `reference_set.published` out per tenant).
async def _reference_set_published(event: OutboxEvent) -> None:
    """Due dates follow a published set (T-02-T10); corrected 8879 tolerances recheck every open
    binding (T-01-T36)."""
    await on_reference_set_published(event)
    await filing.on_tolerances_published(event)


SUBSCRIPTIONS = {
    "reference_set.published": _reference_set_published,
    # T-01-T36: a return's approved checkpoint rechecks its 8879 binding (I-8879-DRIFT).
    "checkpoint.approved": filing.on_checkpoint_approved,
    # T-01-T10: a completed `consent_set` envelope signs its consents (C7 → C19).
    "envelope.completed": consent_capture.on_envelope_completed,
    # T-02-T13: the record projection (a published binder opens intake; the L1 marks prepared).
    "binder.published": on_binder_published,
    "sign_off.recorded": on_sign_off_recorded,
    # T-02-T21: a release starts its workflow; a resend gives the corrected contact access.
    **k1_release.SUBSCRIPTIONS,
    # T-01-T37: a published filed return emails the client's owners "Deliverable ready".
    **filed_delivery.SUBSCRIPTIONS,
}
# T-02-T21: `K1ReleaseWorkflow` and its activities (the worker composes every module's parts).
WORKFLOWS: dict[type, str] = {**k1_release.WORKFLOWS}
ACTIVITIES: tuple[object, ...] = k1_release.ACTIVITIES

__all__ = [
    "ACTIVITIES",
    "FORM_FOR_RULES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "TRANSITIONS",
    "WORKFLOWS",
    "ApprovalBlocker",
    "FiledReturn",
    "K1DeliveryInput",
    "K1ReleaseFailure",
    "K1ReleaseInput",
    "K1ReleaseWorkflow",
    "StaleReturn",
    "TransitionRefused",
    "apply_transition",
    "filed_returns",
    "final_approval_eligibility",
    "import_engine_file",
    "next_status",
    "recompute_unfiled",
    "record_sync_state",
    "register_due_dates_source",
    "register_final_approval_blocker",
    "rule_texts",
    "set_extended",
    "share_k1_internal",
]
