"""The respond-by risk band (NOT-01: red within 7 days, amber within 30; N-04 §3 F1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

RED_DAYS: Final = 7
AMBER_DAYS: Final = 30
Band = Literal["red", "amber", "none"]


@dataclass(frozen=True)
class Risk:
    band: Band
    days: int | None  # calendar days from `as_of`; negative once past


def band(respond_by: date | None, as_of: date) -> Risk:
    """No respond-by: no band. Past or within 7 days: red; within 30: amber."""
    if respond_by is None:
        return Risk("none", None)
    days = (respond_by - as_of).days
    if days <= RED_DAYS:
        return Risk("red", days)
    if days <= AMBER_DAYS:
        return Risk("amber", days)
    return Risk("none", days)
