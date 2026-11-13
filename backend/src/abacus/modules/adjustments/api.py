"""Public interface of the adjustments module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140); A-06-T05 (DEC-1965): the C8 contract stub
(`docs/contracts/adjustments.md`). Nothing here posts to a client system (ADR-040).
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.adjustments.client_approvals import (
    ProposedEntryApprovals,
)
from abacus.modules.adjustments.client_approvals import (
    apply_client_decision as apply_client_decision,
)
from abacus.modules.adjustments.contract import router
from abacus.modules.adjustments.decisions import (
    SUBSCRIPTIONS,
    register_client_delivery,
    register_entry_decision_hook,
    register_evidence_engagement,
)
from abacus.modules.adjustments.entries import (
    AUDIT_KINDS,
    audit_owners,
    entries_of,
    recorded_entries,
    register_entry_proposed_hook,
)
from abacus.modules.engagements.api import deliver_proposed_entries, register_client_approval_kind
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.ledger.api import register_adjustment_source

# A-06-T09 (DEC-2061): the ledger's layers read the approved entries; the trail places them.
register_adjustment_source(recorded_entries)
register_engagement_owners(AUDIT_KINDS, audit_owners)
# R-02-T07: A-06's C18 port, wired to C18. After the 10-second Undo window the batch's entries are
# before the client on their work item (`client_approval.requested`, one per entry).
register_client_delivery(deliver_proposed_entries)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)
# The worker serves a module with SUBSCRIPTIONS (A-06-T10's send): no workflows or activities.
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

from abacus.modules.adjustments.decisions import (  # noqa: E402 -- A-06-T28
    record_client_decision as record_entry_decision,
)
from abacus.modules.adjustments.decisions import send as send_entries  # noqa: E402

# T-05-T33 (DEC-4618): the tax layers for the entity TB read model.
from abacus.modules.adjustments.entries import Entry as Entry  # noqa: E402 -- T-05-T37 drawer
from abacus.modules.adjustments.entries import NewEntry, NewLine  # noqa: E402
from abacus.modules.adjustments.entries import TaxLayersView as TaxLayersView  # noqa: E402
from abacus.modules.adjustments.entries import adjusted_tb as adjusted_tb  # noqa: E402
from abacus.modules.adjustments.entries import propose as propose_entry  # noqa: E402

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "Entry",
    "NewEntry",
    "NewLine",
    "entries_of",
    "propose_entry",
    "record_entry_decision",
    "recorded_entries",
    "register_client_delivery",
    "register_entry_decision_hook",
    "register_entry_proposed_hook",
    "register_evidence_engagement",
    "router",
    "send_entries",
]

# R-02-T11 (C18, DEC-3009): POR-08 e's `proposed_entry` kind, decided through the portal.
register_client_approval_kind("proposed_entry", ProposedEntryApprovals())
