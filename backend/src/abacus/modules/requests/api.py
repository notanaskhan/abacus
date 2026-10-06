"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.modules.requests.routes import router

__all__ = ["router"]
