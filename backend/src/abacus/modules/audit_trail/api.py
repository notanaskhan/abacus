"""Public interface of the audit_trail module; other modules import only this (ADR-008)."""

from abacus.kernel.uow.chain import Checkpoint, latest_checkpoint, verify_chain
from abacus.modules.audit_trail.routes import router
from abacus.modules.audit_trail.service import events_for_target
from abacus.modules.identity.api import AbacusRouter, register_target_events

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

# G-01-T09 (AC8.6): the wall log reads its wall's events from the trail.
register_target_events(events_for_target)

# Q-02-T21: the audit hash chain lives beside the events it seals (kernel.uow); the audit trail
# answers for it (Q-02 §4.1: `latest_checkpoint`, `verify_chain`).
__all__ = [
    "ROUTERS",
    "Checkpoint",
    "events_for_target",
    "latest_checkpoint",
    "router",
    "verify_chain",
]
