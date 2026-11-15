"""Public interface of the closes module; other modules import only this (ADR-008).

C-01 (SPEC-655): the close engine. Contract stubs: the portfolio, record, runs and plans
(`contract.py`, C-01-T04) and the intake, accounts, reconciliation, review, flux and portal
question routes (`contract_work.py`, C-01-T05); `docs/contracts/closes.md`. The record service
(`service.py`, C-01-T14): the portfolio, the summary, the status machine and assignments. Consumer
API: `close_for`, the fail-closed `register_status_guard` slot C-02 fills (C-01 §4.4) and
`start_close`, the system's Not started → In progress on the first run or incorporation.
"""

from abacus.kernel.audit_owners import register_engagement_owners, register_entity_owners
from abacus.modules.closes.audit_targets import (
    AUDIT_KINDS,
    ENTITY_KINDS,
    audit_entities,
    audit_owners,
)
from abacus.modules.closes.contract import (
    CloseFacts,
    StatusGuard,
    TransitionNotAvailable,
    close_for,
    closes_router,
    register_status_guard,
    status_guard,
)
from abacus.modules.closes.contract_work import close_work_router, portal_close_router
from abacus.modules.closes.gate_sources import register_close_gates
from abacus.modules.closes.kind import CloseKind
from abacus.modules.closes.service import start_close
from abacus.modules.engagements.api import register_work_item_kind

# F-03-T22: the `close` work-item kind.
register_work_item_kind("close", CloseKind())
# C-01-T15 (QC-8): a requested publication waits on the engagement's Managers and Partners.
register_close_gates()
# The explorer's owners for a close and its plan (SPEC-304).
register_engagement_owners(AUDIT_KINDS, audit_owners)
register_entity_owners(ENTITY_KINDS, audit_entities)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS = (closes_router, close_work_router, portal_close_router)

__all__ = [
    "ROUTERS",
    "CloseFacts",
    "StatusGuard",
    "TransitionNotAvailable",
    "close_for",
    "register_status_guard",
    "start_close",
    "status_guard",
]
