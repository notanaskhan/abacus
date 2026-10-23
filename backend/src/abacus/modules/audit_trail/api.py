"""Public interface of the audit_trail module; other modules import only this (ADR-008)."""

from abacus.kernel.uow.chain import Checkpoint, latest_checkpoint, verify_chain
from abacus.modules.audit_trail.routes import router
from abacus.modules.identity.api import AbacusRouter

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

# Q-02-T21: the audit hash chain lives beside the events it seals (kernel.uow); the audit trail
# answers for it (Q-02 §4.1: `latest_checkpoint`, `verify_chain`).
__all__ = ["ROUTERS", "Checkpoint", "latest_checkpoint", "router", "verify_chain"]
