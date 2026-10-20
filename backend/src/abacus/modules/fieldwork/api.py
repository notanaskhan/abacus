"""Public interface of the fieldwork module; other modules import only this (ADR-008).

Procedures and their records (SPEC-037; TASK-083; ADR-131, ADR-132): materiality entered by
people, journal entry testing's population and selection by code (`sampling`).
"""

from abacus.modules.fieldwork.activities import ACTIVITIES
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

SUBSCRIPTIONS: dict[str, object] = {}

__all__ = [
    "ACTIVITIES",
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
