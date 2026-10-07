"""Public interface of the platform module; other modules import only this (ADR-008)."""

from abacus.modules.platform.routes import router
from abacus.modules.platform.service import BudgetInvalid

__all__ = ["BudgetInvalid", "router"]
