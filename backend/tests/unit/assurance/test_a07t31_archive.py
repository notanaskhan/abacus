"""A-07-T31 (TASK-6508; A-07 F7; SPEC-644; DEC-3108): the archive, its nine items and the binder.

Row acceptance: "On Thu Oct 22, 2026 Northwind reads Archive in 47 days, 8 of 9 with one named
open item, and a binder index of 26 workpapers and 24 source documents."
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import archive_gate as ag
from abacus.modules.assurance import archive_records as ev
from abacus.modules.assurance.archive_records import ArchiveRow, BinderSection

pytestmark = pytest.mark.asyncio
TENANT = TenantContext(uuid.uuid4(), "system", "test")
WORK_ITEM, ENGAGEMENT = uuid.uuid4(), uuid.uuid4()


def _archive() -> ArchiveRow:
    return ArchiveRow(
        uuid.uuid4(),
        WORK_ITEM,
        ENGAGEMENT,
        "assembling",
        uuid.uuid4(),
        datetime(2026, 10, 9, 15, 7, tzinfo=UTC),
        date(2026, 10, 9),
        date(2026, 12, 8),
        date(2033, 10, 9),
        None,
        None,
        None,
    )


def test_the_five_year_floor_and_a_leap_day() -> None:
    assert ev.five_year_floor(date(2026, 10, 9)) == date(2031, 10, 9)
    assert ev.five_year_floor(date(2028, 2, 29)) == date(2033, 2, 28)


def test_the_binder_index_hash_is_its_content() -> None:
    a = [BinderSection("A", "Planning", 6, 0, 0)]
    assert ev.index_sha256(a) == ev.index_sha256(list(a))
    assert ev.index_sha256(a) != ev.index_sha256([BinderSection("A", "Planning", 7, 0, 0)])


@dataclass(frozen=True)
class _Section:
    key: str
    band: str
    state_provider: Callable[..., object]


async def test_the_binder_maps_rail_rows_to_a_to_h(monkeypatch: pytest.MonkeyPatch) -> None:
    async def present(_t: TenantContext, _w: uuid.UUID) -> object:
        return object()

    async def absent(_t: TenantContext, _w: uuid.UUID) -> None:
        return None

    rows = [
        _Section("ebp_01", "planning", present),
        _Section("sample_selection", "fieldwork", present),
        _Section("ebp_04", "fieldwork", present),  # a test paper: C
        _Section("ebp_09", "fieldwork", absent),  # not in this file
        _Section("eqr", "completion", present),
        _Section("auditors_report", "reporting", present),
        _Section("client", "overview", present),  # not a workpaper
    ]

    async def runs(_t: TenantContext, _e: uuid.UUID) -> tuple[int, int]:
        return 23, 23

    async def documents(_t: TenantContext, _e: uuid.UUID) -> int:
        return 24

    async def team(_tenant: uuid.UUID, _e: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
        return [(uuid.uuid4(), "manager") for _ in range(5)]

    async def cleared(*_a: object) -> bool:
        return True

    monkeypatch.setattr("abacus.modules.assurance.sections.registered_sections", lambda: rows)
    monkeypatch.setattr("abacus.modules.agents.api.run_log_count", runs)
    monkeypatch.setattr("abacus.modules.evidence.api.source_document_count", documents)
    monkeypatch.setattr("abacus.modules.identity.api.team_of", team)
    monkeypatch.setattr("abacus.modules.engagements.api.independence_cleared", cleared)
    binder = {b.section: b for b in await ag.binder_sections(TENANT, ENGAGEMENT, WORK_ITEM)}
    assert list(binder) == list("ABCDEFGH")
    assert (binder["A"].workpapers, binder["B"].workpapers, binder["C"].workpapers) == (1, 1, 1)
    assert (binder["D"].workpapers, binder["E"].workpapers) == (1, 1)
    assert binder["F"].source_documents == 24 and binder["G"].run_logs == 23
    assert binder["H"].independence == 5


def _state(open_keys: set[str]) -> ag.ArchiveState:
    items = tuple(
        ag.ArchiveItem(key, title, key not in open_keys) for key, title in ag.ARCHIVE_ITEMS
    )
    return ag.ArchiveState(_archive(), items, (), 47)


def test_nine_items_eight_done_names_the_open_one() -> None:
    state = _state({"governance_filed"})
    assert (state.done, len(state.items)) == (8, 9)
    assert [i.title for i in state.items if not i.done] == ["Governance communications filed"]


async def test_the_lock_request_is_refused_at_8_of_9(monkeypatch: pytest.MonkeyPatch) -> None:
    async def eight(_t: TenantContext, _w: uuid.UUID) -> ag.ArchiveState:
        return _state({"governance_filed"})

    monkeypatch.setattr(ag, "archive_state", eight)
    ctx = SimpleNamespace(tenant=TENANT, user_id=uuid.uuid4())
    with pytest.raises(ag.ChecklistIncomplete):
        await ag.request_lock(ctx, WORK_ITEM)  # type: ignore[arg-type]  # a test double


async def test_archive_in_47_days_on_oct_22(monkeypatch: pytest.MonkeyPatch) -> None:
    async def item(_t: TenantContext, _w: uuid.UUID) -> object:
        return SimpleNamespace(engagement_id=ENGAGEMENT)

    async def archive(_t: TenantContext, _w: uuid.UUID) -> ArchiveRow:
        return _archive()

    async def binder(*_a: object) -> tuple[BinderSection, ...]:
        return ()

    async def items(*_a: object) -> tuple[ag.ArchiveItem, ...]:
        return _state({"governance_filed"}).items

    async def today(_t: TenantContext) -> date:
        return date(2026, 10, 22)

    monkeypatch.setattr(ag, "assurance_item", item)
    monkeypatch.setattr("abacus.modules.assurance.archive_records.archive_of", archive)
    monkeypatch.setattr(ag, "binder_sections", binder)
    monkeypatch.setattr(ag, "_items", items)
    monkeypatch.setattr(ag.clock, "today", today)
    state = await ag.archive_state(TENANT, WORK_ITEM)
    assert state.days_left == 47  # "Archive in 47 days"
    assert state.archive is not None
    assert state.archive.documentation_completion_date == date(2026, 12, 8)
