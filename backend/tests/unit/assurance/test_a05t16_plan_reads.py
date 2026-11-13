"""A-05-T16 (TASK-5307, TASK-5308; DEC-2488, DEC-2489): verified provisions reach downstream.

The row's title publishes `verified_provisions` to the downstream readers. Code reads the verified
Default deferral rate, Auto-escalation, Safe harbor match and Plan expenses elections exactly as
the handoff words them, or leaves them for a person; a drafted value never reaches a figure, and
QACA's constants never stand in for an unverified plan.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.assurance import ebp_provisions
from abacus.modules.assurance.compute.ebp.eligibility import (
    QACA,
    Escalation,
    match_pct_from,
    missed,
    rates_from,
)
from abacus.modules.assurance.compute.ebp.expenses import plan_may_pay
from abacus.modules.assurance.compute.ebp.provisions import BY_KEY

NORTHWIND = {
    "minimum_age": "21",
    "service_requirement": "3 months (elapsed time)",
    "entry_dates": "First of month following",
    "default_deferral_rate": "6%",
    "auto_escalation": "+1% each Jan 1 after one full plan year, to 15%",
    "safe_harbor_match": "100% of first 1% + 50% of next 5%",
    "plan_expenses": "Reasonable expenses may be paid from plan",
}


def test_ac_northwinds_wording_reads_as_qacas_figures() -> None:
    rates = rates_from(NORTHWIND)
    assert rates is not None
    assert (rates.escalation, rates.match_pct) == (QACA, Decimal("3.5"))
    gone = missed(Decimal("41200.00"), rates.escalation, rates.match_pct)
    assert (gone.deferral, gone.match) == (Decimal("2472.00"), Decimal("1442.00"))


def test_ac_another_plans_verified_rates_move_the_figures() -> None:
    rates = rates_from(
        NORTHWIND
        | {
            "default_deferral_rate": "3%",
            "auto_escalation": "1% a year up to 10%",
            "safe_harbor_match": "100% of first 4%",
        }
    )
    assert rates is not None
    assert rates.escalation == Escalation(Decimal(3), Decimal(1), Decimal(10))
    gone = missed(Decimal("41200.00"), rates.escalation, rates.match_pct)
    assert (gone.deferral, gone.match) == (Decimal("1236.00"), Decimal("1648.00"))


@pytest.mark.parametrize(
    "wording",
    [
        "Enhanced: 100% of first 4%, discretionary profit sharing",
        "<100% of first 4%",
        "50% of next 5%",
        "100% of next 1% + 50% of first 5%",
    ],
)
def test_a_match_code_does_not_read_is_left_for_a_person(wording: str) -> None:
    assert match_pct_from(wording) is None


def test_ac_an_unticked_rate_never_reaches_a_figure() -> None:
    drafted = dict(NORTHWIND)
    drafted.pop("safe_harbor_match")
    assert ebp_provisions.rates_of(drafted) == ebp_provisions.RatesRead("unverified")
    unread = NORTHWIND | {"auto_escalation": "Per the employer's annual resolution"}
    assert ebp_provisions.rates_of(unread) == ebp_provisions.RatesRead("unreadable")


@pytest.mark.parametrize(
    ("wording", "may"),
    [
        ("Reasonable expenses may be paid from plan", True),
        ("Expenses paid by employer", False),
        ("Per the trust agreement", None),
    ],
)
def test_ac_ebp09_reads_the_plan_expenses_election(wording: str, may: bool | None) -> None:
    assert plan_may_pay(wording) is may
    read = ebp_provisions.expenses_clause_of({"plan_expenses": wording})
    assert read.plan_may_pay is may
    assert read.state == ("unreadable" if may is None else "verified")
    assert ebp_provisions.expenses_clause_of({}).state == "unverified"


async def test_no_ebp_02_paper_leaves_every_read_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_paper(*_: object) -> None:
        return None

    monkeypatch.setattr(ebp_provisions, "paper_id_of_kind", no_paper)
    reads = await ebp_provisions.plan_reads(object(), uuid.uuid4(), uuid.uuid4())  # pyright: ignore[reportArgumentType] -- never read
    assert (reads.entry.state, reads.rates.state, reads.expenses.state) == ("unverified",) * 3


# --- the SPD comparison and the amendment tag (DEC-2489) ---------------------------------------
_SPD = ebp_provisions.DocumentValue("Quarterly", "SPD p. 6", 6, uuid.uuid4(), "m-1")


def _docs(spd: object = _SPD, effective: object = None) -> ebp_provisions.ProvisionDocuments:
    return ebp_provisions.ProvisionDocuments(spd, None, effective)  # pyright: ignore[reportArgumentType] -- test values


def test_ac_an_spd_that_reads_differently_is_a_conflict_by_code() -> None:
    entry = BY_KEY["entry_dates"]
    found = ebp_provisions.compared(
        entry, "First of month following", _docs(), amendment_in_force=True, plan_year_end=None
    )
    assert found == ("SPD: Quarterly", _SPD, None)
    same = ebp_provisions.DocumentValue("first of the month following", "n", 6, uuid.uuid4(), None)
    assert ebp_provisions.compared(
        entry, "First of month following", _docs(same), amendment_in_force=True, plan_year_end=None
    ) == (None, None, None)
    assert ebp_provisions.compared(
        entry, "First of month following", None, amendment_in_force=True, plan_year_end=None
    ) == (None, None, None)


@pytest.mark.parametrize(
    ("key", "in_force", "effective", "tagged"),
    [
        ("catch_up", True, date(2025, 1, 1), date(2025, 1, 1)),
        ("catch_up", False, date(2025, 1, 1), None),
        ("catch_up", True, date(2026, 1, 1), None),  # after the plan year's end
        ("entry_dates", True, date(2025, 1, 1), None),  # not a provision the amendment governs
    ],
)
def test_ac_the_amendment_tag_is_codes(
    key: str, in_force: bool, effective: date, tagged: date | None
) -> None:
    _, _, amended = ebp_provisions.compared(
        BY_KEY[key],
        "Yes",
        _docs(None, effective),
        amendment_in_force=in_force,
        plan_year_end=date(2025, 12, 31),
    )
    assert amended == tagged
