"""N-04-T22 (US-8.3, INV-4): POR-02's info row carries no figure and reads only scoped items."""

from __future__ import annotations

from dataclasses import asdict, fields
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.modules.notices.portal_home import (
    IN_REVIEW,
    WAITING,
    PortalNoticeRow,
    _subject,
)
from abacus.modules.portal.contract import PortalHomeNoticeOut
from abacus.modules.portal.home_sources import HomeScope, NoticeInfo
from abacus.modules.portal.home_sources import notices as source


def test_the_row_has_no_field_for_a_figure_or_the_analysis() -> None:
    assert {f.name for f in fields(NoticeInfo)} == {"notice_id", "code", "subject"}
    assert set(PortalHomeNoticeOut.model_fields) == {"notice_id", "code", "subject"}


def test_the_subject_names_the_agency_and_the_year() -> None:
    assert _subject("IRS", 2024) == "IRS notice, tax year 2024"
    assert _subject(None, None) == "Tax agency notice"


async def test_only_this_scopes_notice_items_are_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notice, other = uuid4(), uuid4()
    asked: list[object] = []

    async def rows(_tenant: object, ids: list[object]) -> list[PortalNoticeRow]:
        asked.extend(ids)
        return [PortalNoticeRow(notice, WAITING, "IRS notice, tax year 2024")]

    monkeypatch.setattr(source, "portal_notice_rows", rows)
    scope = HomeScope(
        "household",
        uuid4(),
        uuid4(),
        (),
        (
            SimpleNamespace(id=notice, kind="notice"),  # type: ignore[arg-type]  # a stand-in item
            SimpleNamespace(id=other, kind="tax_return"),  # type: ignore[arg-type]  # a stand-in item
        ),
        date(2026, 9, 14),
    )
    part = await source.notices_source(SimpleNamespace(tenant=None), scope)  # type: ignore[arg-type]  # a stand-in context
    assert asked == [notice]
    assert [asdict(n) for n in part.notices] == [
        {"notice_id": notice, "code": WAITING, "subject": "IRS notice, tax year 2024"}
    ]
    assert IN_REVIEW != WAITING
