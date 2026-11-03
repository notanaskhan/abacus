"""Public interface of the adjustments module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140); A-06-T05 (DEC-1965): the C8 contract stub
(`docs/contracts/adjustments.md`). Nothing here posts to a client system (ADR-040).
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.adjustments.contract import router
from abacus.modules.adjustments.decisions import (
    SUBSCRIPTIONS,
    register_client_delivery,
    register_entry_decision_hook,
)
from abacus.modules.adjustments.entries import (
    AUDIT_KINDS,
    audit_owners,
    entries_of,
    recorded_entries,
)
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.ledger.api import register_adjustment_source

# A-06-T09 (DEC-2061): the ledger's layers read the approved entries; the trail places them.
register_adjustment_source(recorded_entries)
register_engagement_owners(AUDIT_KINDS, audit_owners)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)
# The worker serves a module with SUBSCRIPTIONS (A-06-T10's send): no workflows or activities.
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "entries_of",
    "recorded_entries",
    "register_client_delivery",
    "register_entry_decision_hook",
    "router",
]
