"""I-01-T10: HOME-01's code-computed rules (AC4.1, AC4.2; `due_risk`)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from abacus.modules.engagements.api import AssignedWork
from abacus.modules.practice.home import ADMIN_TILES, PRACTICE_TILES, risk_of, work_label

TODAY = date(2026, 9, 14)


@pytest.mark.parametrize(
    ("due", "risk"),
    [
        (date(2026, 9, 13), "overdue"),
        (date(2026, 9, 14), "due_soon"),
        (date(2026, 9, 21), "due_soon"),
        (date(2026, 9, 22), "approaching"),
        (date(2026, 9, 28), "approaching"),
        (date(2026, 9, 29), "later"),
    ],
)
def test_due_risk_is_a_code_on_the_firm_clock(due: date, risk: str) -> None:
    assert risk_of(due, TODAY) == risk


def _work(kind: str) -> AssignedWork:
    return AssignedWork(uuid.uuid4(), "x", uuid.uuid4(), kind, "active", None, None, None)


def test_the_band_label_follows_the_kinds_of_work() -> None:
    assert work_label([_work("tax_return"), _work("tax_return")]) == "home.your_work.returns"
    assert work_label([_work("assurance")]) == "home.your_work.engagements"
    assert work_label([_work("assurance"), _work("tax_return")]) == "home.your_work.mine"
    assert work_label([]) == "home.your_work.mine"


def test_admins_get_the_metadata_tile_set() -> None:
    assert [t.key for t in ADMIN_TILES] == [
        "signatures_out",
        "inbox_waiting",
        "portal_invites_pending",
        "binders",
    ]
    assert [t.key for t in PRACTICE_TILES] == ["tax_returns", "audits", "closes", "notices"]
