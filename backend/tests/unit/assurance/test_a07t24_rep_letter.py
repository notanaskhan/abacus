"""A-07-T24 (TASK-6208; A-07 F3; AU-C 580; DEC-2808): the representation letter service.

Row acceptance: "Dana Kowalski's Oct 9 signature records G7, an Oct 8 signature yields Date
mismatch with Start re-date, and Send is refused before Margaret Okonkwo approves."
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.modules.assurance import rep_letters as rl

REPORT_DATE = date(2026, 10, 9)


def test_ac_dana_signing_on_the_report_date_records_g7() -> None:
    signed = datetime(2026, 10, 9, 15, 12, tzinfo=UTC)  # 10:12 AM CDT
    outcome = rl.g7_outcome(signed, REPORT_DATE, date(2026, 10, 9))
    assert outcome.status == "signed"


def test_ac_an_oct_8_signature_is_a_date_mismatch() -> None:
    signed = datetime(2026, 10, 8, 22, 0, tzinfo=UTC)
    outcome = rl.g7_outcome(signed, REPORT_DATE, date(2026, 10, 8))
    assert (outcome.status, outcome.signed_on) == ("date_mismatch", date(2026, 10, 8))


class _Session:
    def __init__(self, approved: bool) -> None:
        self.approved = approved

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
        return SimpleNamespace(first=lambda: SimpleNamespace(current_version_id=uuid.uuid4()))

    async def scalar(self, *_a: object, **_k: object) -> bool:
        return self.approved


def _sessions(*, approved: bool) -> Callable[[object], _Session]:
    def open_session(_tenant: object) -> _Session:
        return _Session(approved=approved)

    return open_session


@pytest.mark.asyncio
async def test_ac_send_is_refused_before_the_partner_approves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant: Any = SimpleNamespace()  # Any: a test double
    monkeypatch.setattr(rl, "tenant_session", _sessions(approved=False))
    with pytest.raises(rl.LetterNotApproved):
        await rl.ensure_approved(tenant, uuid.uuid4())
    monkeypatch.setattr(rl, "tenant_session", _sessions(approved=True))
    await rl.ensure_approved(tenant, uuid.uuid4())


@pytest.mark.parametrize(
    "wording",
    [
        "Corrected for $2,140.",
        "The late deposit of 2,140.00 was corrected.",
        "Over 18,915 in total.",
    ],
)
def test_no_amount_in_letter_text(wording: str) -> None:
    assert rl._AMOUNT.search(wording)  # pyright: ignore[reportPrivateUsage]  # a test double or a private name the test pins


def test_plain_wording_passes_the_amount_rule() -> None:
    assert not rl._AMOUNT.search("The late deposit was corrected and reported in 2025.")  # pyright: ignore[reportPrivateUsage]  # a test double or a private name the test pins


@pytest.mark.asyncio
async def test_specific_representations_follow_their_triggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def yes(*_a: object) -> bool:
        return True

    async def no(*_a: object) -> bool:
        return False

    monkeypatch.setattr(
        rl,
        "_TRIGGERS",
        {"late_remittance": yes, "certified_investments": yes, "going_concern_doubt": no},
    )
    clauses = [
        ("late_remittance", False),
        ("certified_investments", False),
        ("going_concern_doubt", False),
        ("firm_own_clause", True),  # no trigger: the template's default stands
    ]
    reps = await rl.compose(SimpleNamespace(), uuid.uuid4(), clauses)  # type: ignore[arg-type]  # a test double or a private name the test pins
    assert [(r.n, r.included) for r in reps] == [(12, True), (13, True), (14, False), (15, True)]
