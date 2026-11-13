"""T-05-T51 (TASK-7902; T-05 F8; TXP-10, TXP-00; DEC-4903, DEC-4904): TXP-10's queue over C3.

Row acceptance: "5 + 6 = 11 on the seed equals the tab badge and TXP-00's open items, and the
client wording never shows the internal note."
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Literal

import pytest

from abacus.modules.tax import entity_issues as ei
from abacus.modules.tax.entity_issues import (
    QueueIssue,
    counts,
    matches,
    section_of,
    step_of,
)


def _issue(
    status: str,
    section: Literal["waiting_on_client", "review_points", "resolved"],
    step: str | None,
    title: str = "Item L ties the M-2: off 6,200",
) -> QueueIssue:
    return QueueIssue(
        id=uuid.uuid4(), title=title, section=section, step=step, status=status,
        kind="review_point", priority="high", source_kind="self_check", category_path=None,
        blocks=(), assignee=None, links=(), request_item_id=None, version=1,
        created_at=datetime(2026, 9, 14, tzinfo=UTC), allowed_actions=(),
    )  # fmt: skip


def test_ac_five_waiting_and_six_review_points_make_eleven() -> None:
    items = [_issue("open", "waiting_on_client", "capital_m2") for _ in range(5)]
    items += [_issue("in_progress", "review_points", "federal_k1s") for _ in range(6)]
    items += [_issue("resolved", "resolved", "capital_m2") for _ in range(3)]
    by_section, by_step = counts(items)
    assert by_section == {"waiting_on_client": 5, "review_points": 6}
    assert sum(by_section.values()) == 11  # the badge and TXP-00's open items
    assert by_step == {"capital_m2": 5, "federal_k1s": 6}


def test_ac_section_rules() -> None:
    assert section_of("open", True) == "waiting_on_client"
    assert section_of("reopened", False) == "review_points"
    assert section_of("verified", True) == "resolved"


def test_ac_step_from_the_first_linked_cell_sheet() -> None:
    assert step_of([{"sheet": "07", "range": "B9"}]) == "capital_m2"
    assert step_of([{"range": "01!B4:B40"}]) == "import_trial_balance"
    assert step_of([{"sheet": "zz", "range": "A1"}, {"sheet": "09", "range": "C2"}]) == (
        "federal_k1s"
    )
    assert step_of([]) is None


def test_ac_filters_and_search() -> None:
    item = _issue("open", "review_points", "capital_m2")
    assert matches(item, section="review_points", status=None, step=None, q="m-2")
    assert not matches(item, section="waiting_on_client", status=None, step=None, q=None)
    assert not matches(item, section=None, status="resolved", step=None, q=None)
    assert not matches(item, section=None, status=None, step="federal_k1s", q=None)
    assert not matches(item, section=None, status=None, step=None, q="schedule l")


class _Texts:
    def __init__(self, client_wording: str | None) -> None:
        self.title = "§754 election"
        self.internal_note = "Owen said the transfer closed late; check the LPA"
        self.client_wording = client_wording


def test_ac_client_wording_only_never_the_internal_note(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.review import api as review_api

    sent: list[str] = []

    async def on_return(*_a: object) -> None:
        return None

    async def read(_ctx: object, _i: object) -> tuple[None, _Texts, list[str]]:
        return None, _Texts("Please confirm the transfer date of the interest."), []

    async def send(_ctx: object, _i: object, **kw: object) -> uuid.UUID:
        sent.append(str(kw["client_wording"]))
        return uuid.uuid4()

    monkeypatch.setattr(ei, "_on_return", on_return)
    monkeypatch.setattr(review_api, "read_issue", read)
    monkeypatch.setattr(review_api, "send_issue_to_client", send)
    asyncio.run(
        ei.send_to_client(
            object(),  # type: ignore[arg-type] -- the context is only passed through
            uuid.uuid4(), uuid.uuid4(), seen_version=1, contact_id=uuid.uuid4(), due_on=None,
        )
    )  # fmt: skip
    assert sent == ["Please confirm the transfer date of the interest."]
    assert "Owen" not in sent[0]


def test_ac_no_client_wording_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.review import api as review_api

    async def on_return(*_a: object) -> None:
        return None

    async def read(_ctx: object, _i: object) -> tuple[None, _Texts, list[str]]:
        return None, _Texts(None), []

    monkeypatch.setattr(ei, "_on_return", on_return)
    monkeypatch.setattr(review_api, "read_issue", read)
    with pytest.raises(ei.ClientWordingMissing):
        asyncio.run(
            ei.send_to_client(
                object(),  # type: ignore[arg-type] -- the context is only passed through
                uuid.uuid4(), uuid.uuid4(), seen_version=1, contact_id=uuid.uuid4(), due_on=None,
            )
        )  # fmt: skip


def test_ac_resolve_without_an_approved_fix_needs_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    async def on_return(*_a: object) -> None:
        return None

    async def not_fixed(*_a: object) -> bool:
        return False

    monkeypatch.setattr(ei, "_on_return", on_return)
    monkeypatch.setattr(ei, "fix_approved", not_fixed)
    with pytest.raises(ei.ResolutionNoteRequired):
        asyncio.run(
            ei.resolve(
                object(),  # type: ignore[arg-type] -- the context is only passed through
                uuid.uuid4(), uuid.uuid4(), seen_version=1, note="  ",
            )
        )  # fmt: skip
