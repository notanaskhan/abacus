"""Public interface of the audit_trail module; other modules import only this (ADR-008)."""

from abacus.modules.audit_trail.routes import router

__all__ = ["router"]
