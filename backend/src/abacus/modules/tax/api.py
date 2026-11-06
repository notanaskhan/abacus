"""Public interface of the tax module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). T-01-T02: the engine-bridge and e-file-record stubs
(`engine_contract`). T-01-T18: final approval and its blocker slot (`approval`).
"""

from datetime import date
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.audit_owners import register_engagement_owners, register_entity_owners
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import OutboxEvent
from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.identity.api import AbacusRouter, register_scope_resolver
from abacus.modules.organisations.api import register_office_facts
from abacus.modules.platform.api import register_search_projection
from abacus.modules.tax import consent_capture, filed_delivery, filing, k1_release
from abacus.modules.tax import extensions as _extensions
from abacus.modules.tax import schedule_workflows as _schedule_workflows
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
from abacus.modules.tax.schedules_contract import schedules_router
from abacus.modules.tax.status import TRANSITIONS, StaleReturn, TransitionRefused, next_status
from abacus.modules.tax.tax_profile import (
    authorization_on_file as authorization_on_file,
)
from abacus.modules.tax.tax_profile import register as register_tax_profile
from abacus.modules.tax.tax_profile import return_for_entity as return_for_entity
from abacus.modules.tax.tax_profile import return_label as return_label
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
    schedules_router,  # extensions, estimates and payments (T-03-T02 stub)
)


# T-02-T10: a published reference-set correction recomputes every unfiled return's due dates
# (K-02-T12 fans `reference_set.published` out per tenant).
async def _reference_set_published(event: OutboxEvent) -> None:
    """Due dates follow a published set (T-02-T10); corrected 8879 tolerances recheck every open
    binding (T-01-T36)."""
    await on_reference_set_published(event)
    await filing.on_tolerances_published(event)
    await _extensions.on_reference_set_published(event)


async def _filing_acknowledged(event: OutboxEvent) -> None:
    await _extensions.on_filing_acknowledged(event)


_extensions.register_approval_kind()  # T-03-T07 (DEC-2350): submit-for-approval's card

SUBSCRIPTIONS = {
    "reference_set.published": _reference_set_published,
    "filing.acknowledged": _filing_acknowledged,
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
WORKFLOWS: dict[type, str] = {**k1_release.WORKFLOWS, **_schedule_workflows.WORKFLOWS}
ACTIVITIES: tuple[object, ...] = (*k1_release.ACTIVITIES, *_schedule_workflows.ACTIVITIES)
SCHEDULES = _schedule_workflows.SCHEDULES


async def extension_for(tenant: TenantContext, tax_return_id: UUID) -> list[dict[str, object]]:
    """C21-side read for T-08 and R-03: the return's lines (contract §2)."""
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text("SELECT * FROM filing_extensions WHERE tax_return_id = :r ORDER BY jurisdiction"),
            {"r": tax_return_id},
        )
        return [dict(row) for row in found.mappings()]


async def estimates_for(
    tenant: TenantContext, client_entity_id: UUID, tax_year: int
) -> list[dict[str, object]]:
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text(
                "SELECT * FROM estimate_schedules WHERE client_entity_id = :c AND tax_year = :y "
                "ORDER BY jurisdiction"
            ),
            {"c": client_entity_id, "y": tax_year},
        )
        return [dict(row) for row in found.mappings()]


async def installments_due(
    tenant: TenantContext, start: date, end: date
) -> list[dict[str, object]]:
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text(
                "SELECT i.*, s.client_entity_id, s.form, s.jurisdiction "
                "FROM estimate_installments i JOIN estimate_schedules s ON s.id = i.schedule_id "
                "WHERE i.due_on BETWEEN :a AND :b ORDER BY i.due_on, i.id"
            ),
            {"a": start, "b": end},
        )
        return [dict(row) for row in found.mappings()]


__all__ = [
    "ACTIVITIES",
    "FORM_FOR_RULES",
    "ROUTERS",
    "SCHEDULES",
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
    "estimates_for",
    "extension_for",
    "filed_returns",
    "final_approval_eligibility",
    "import_engine_file",
    "installments_due",
    "next_status",
    "recompute_unfiled",
    "record_sync_state",
    "register_due_dates_source",
    "register_final_approval_blocker",
    "rule_texts",
    "set_extended",
    "share_k1_internal",
]

# T-03 (S27): imported so its refusal codes are catalogued (the routes import it lazily).
from abacus.modules.tax import (  # noqa: E402
    estimates as _estimates,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- codes
)
from abacus.modules.tax import (  # noqa: E402
    extensions as _extensions_codes,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- imported to register and catalogue it
)
