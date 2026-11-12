"""The shared return frame's tabs (T-04-T55; T-04 AC-13.2; DEC-4514). RED: the live TAX-02 path.

`GET /v1/tax-returns/{id}` (T-02's `ReturnFrame`) lists the frame's tabs. Overview and Intake are
T-02's and always present; a workspace screen joins the frame by registering its tab here with the
flag that gates it, so the frame never names a screen whose flag is off for the firm (the tab and
its route answer 404 together). T-04 registers Review (TAX-04), Worksheets (TAX-05), Issues
(TAX-06) and Sign-offs (TAX-07); T-05's entity tabs use the same seam. Counts are the screen's own
reads (TAX-04's `/tab-counts`), so the frame carries `count: null` and never computes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.tax.returns_contract import TabCountOut

# T-02's own tabs, always first (T-02-T14).
BASE_TABS: Final = ("overview", "intake")


@dataclass(frozen=True)
class ReturnTab:
    tab: str
    flag: Flag
    order: int
    forms: frozenset[str] | None = None  # None: every form family


_TABS: dict[str, ReturnTab] = {}


def register_return_tab(
    tab: str, flag: Flag, *, order: int, forms: frozenset[str] | None = None
) -> None:
    """A workspace tab on the return frame, after T-02's; the same tab registered again with the
    same flag is a no-op, a different one raises."""
    if tab in BASE_TABS:
        raise ValueError(f"return tab {tab!r} is T-02's own")
    known = _TABS.get(tab)
    entry = ReturnTab(tab, flag, order, forms)
    if known is not None and known != entry:
        raise ValueError(f"return tab {tab!r} is already registered")
    _TABS[tab] = entry


async def frame_tabs(tenant: TenantContext, form: str) -> list[TabCountOut]:
    """The frame's tabs for a return of `form`, in order: T-02's, then each registered tab whose
    flag is on for the firm and whose forms include this one."""
    tabs = [TabCountOut(tab=t, count=None) for t in BASE_TABS]
    for entry in sorted(_TABS.values(), key=lambda e: (e.order, e.tab)):
        if entry.forms is not None and form not in entry.forms:
            continue
        if await flag_enabled(tenant, entry.flag):
            tabs.append(TabCountOut(tab=entry.tab, count=None))
    return tabs


def registered_tabs() -> tuple[ReturnTab, ...]:
    return tuple(sorted(_TABS.values(), key=lambda e: (e.order, e.tab)))
