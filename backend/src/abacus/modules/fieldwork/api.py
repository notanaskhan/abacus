"""Public interface of the fieldwork module; other modules import only this (ADR-008).

Procedures and their records (SPEC-037; TASK-083; ADR-131, ADR-132): materiality entered by
people, journal entry testing's population and selection by code (`sampling`).
"""

from abacus.modules.fieldwork.activities import ACTIVITIES
from abacus.modules.fieldwork.routes import firm_router, router
from abacus.modules.fieldwork.service import WORKFLOWS
from abacus.modules.fieldwork.workflow_types import ProcedureSelectInput
from abacus.modules.fieldwork.workflows import ProcedureSelectWorkflow

SUBSCRIPTIONS: dict[str, object] = {}

__all__ = [
    "ACTIVITIES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "ProcedureSelectInput",
    "ProcedureSelectWorkflow",
    "firm_router",
    "router",
]
