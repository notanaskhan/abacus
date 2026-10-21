"""Public interface of the fieldwork module; other modules import only this (ADR-008).

Procedures and their records (SPEC-037; TASK-083; ADR-131, ADR-132): materiality entered by
people, journal entry testing's population and selection by code (`sampling`).
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.engagements.api import register_judgment_source
from abacus.modules.fieldwork.activities import ACTIVITIES
from abacus.modules.fieldwork.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.fieldwork.misstatements import adjustment_entries, judgments
from abacus.modules.fieldwork.routes import firm_router, router
from abacus.modules.fieldwork.service import WORKFLOWS
from abacus.modules.fieldwork.workflow_types import ProcedureSelectInput
from abacus.modules.fieldwork.workflows import ProcedureSelectWorkflow
from abacus.modules.fieldwork.workpapers import (
    EntryFacts,
    assessable_items,
    entry_facts,
    items_with_results,
    record_result,
    selection_item_ids,
)
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.ledger.api import register_adjustment_source

SUBSCRIPTIONS: dict[str, object] = {}

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    firm_router,
)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)
# SPEC-311 (TASK-322): recorded entries feed the trial balance's AJE, RJE and Final layers.
register_adjustment_source(adjustment_entries)
# SPEC-314 (TASK-332): materiality, significant risks and the SUM feed the EQR digest.
register_judgment_source("fieldwork", judgments)

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "EntryFacts",
    "ProcedureSelectInput",
    "ProcedureSelectWorkflow",
    "assessable_items",
    "entry_facts",
    "firm_router",
    "items_with_results",
    "record_result",
    "router",
    "selection_item_ids",
]
