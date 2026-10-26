"""Public interface of the audit_trail module; other modules import only this (ADR-008)."""

from abacus.kernel.uow.chain import Checkpoint, latest_checkpoint, verify_chain
from abacus.modules.audit_trail.audit_log_contract import router as audit_log_router
from abacus.modules.audit_trail.jobs import ACTIVITIES, SCHEDULES, WORKFLOWS
from abacus.modules.audit_trail.routes import router
from abacus.modules.audit_trail.service import events_for_target
from abacus.modules.identity.api import AbacusRouter, register_target_events

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    audit_log_router,  # G-02-T04: the ADM-07 audit-log contract (stub until G-02-T08, T17)
)

# G-01-T09 (AC8.6): the wall log reads its wall's events from the trail.
register_target_events(events_for_target)

# Q-02-T21: the audit hash chain lives beside the events it seals (kernel.uow); the audit trail
# answers for it (Q-02 §4.1: `latest_checkpoint`, `verify_chain`).
# Q-02-T20, T21: partitions, checkpoints, the nightly verify and the daily anchor on Schedules.
__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SCHEDULES",
    "WORKFLOWS",
    "Checkpoint",
    "events_for_target",
    "latest_checkpoint",
    "router",
    "verify_chain",
]
