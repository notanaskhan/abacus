"""The Today context slot (I-02-T14; ADR-008, ADR-106; DEC-4932). Green.

A Today question's turn (workbench) reads the day's brief (practice), and neither module may
import the other (nothing imports practice or workbench). Practice registers how the brief's
context is read; workbench reads it here, through the module both already depend on.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Protocol
from uuid import UUID

from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext


class TodayContext(Protocol):
    """The brief as the viewer sees it now: its id, day, chip and code-written summary lines."""

    @property
    def brief_id(self) -> UUID | None: ...
    @property
    def brief_date(self) -> date: ...
    @property
    def chip_label(self) -> str: ...
    @property
    def lines(self) -> tuple[str, ...]: ...
    @property
    def briefing_ids(self) -> tuple[UUID, ...]: ...


TodayContextSource = Callable[[AuthContext], Awaitable[TodayContext]]
_SOURCE: list[TodayContextSource] = []


def register_today_context(source: TodayContextSource) -> None:
    """Practice registers the brief's reader once (ADR-106 slot)."""
    if _SOURCE and _SOURCE[0] is not source:
        raise ValueError("the Today context source is already registered")
    _SOURCE[:] = [source]


async def today_context(ctx: AuthContext) -> TodayContext:
    if not _SOURCE:
        raise NotFound("daily_briefing")  # practice is not mounted: no brief to ask about
    return await _SOURCE[0](ctx)


__all__ = ["TodayContext", "TodayContextSource", "register_today_context", "today_context"]
