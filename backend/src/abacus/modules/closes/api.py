"""Public interface of the closes module; other modules import only this (ADR-008).

C-01 (SPEC-655): the close engine. C-01-T04 adds the contract stub for the portfolio, record,
runs and plans (`contract.py`; `docs/contracts/closes.md`) and the consumer API: `close_for`
and the fail-closed `register_status_guard` slot C-02 fills (C-01 §4.4).
"""

from abacus.modules.closes.contract import (
    CloseFacts,
    StatusGuard,
    TransitionNotAvailable,
    close_for,
    closes_router,
    register_status_guard,
    status_guard,
)
from abacus.modules.closes.kind import CloseKind
from abacus.modules.engagements.api import register_work_item_kind

# F-03-T22: the `close` work-item kind.
register_work_item_kind("close", CloseKind())

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS = (closes_router,)

__all__ = [
    "ROUTERS",
    "CloseFacts",
    "StatusGuard",
    "TransitionNotAvailable",
    "close_for",
    "register_status_guard",
    "status_guard",
]
