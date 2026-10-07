"""Public interface of the communications module; other modules import only this (ADR-008)."""

from abacus.modules.communications.scope import Violation, check_scope
from abacus.modules.communications.service import Draft, MessageView, OutOfScope, send

__all__ = ["Draft", "MessageView", "OutOfScope", "Violation", "check_scope", "send"]
