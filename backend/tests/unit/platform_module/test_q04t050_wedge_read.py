"""Q-04-T050: W4 and W5 coloured by chapter 11 §11.6.2, red W4 only after four weeks and at two
firms, and every amber or red carrying an owner and an action."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from abacus.modules.platform.pilot_read import (
    OWNER,
    SINGLE_FIRM_NOTE,
    FirmRead,
    SignalRead,
    colour,
    cross_firm,
    report,
)

D = Decimal


@pytest.mark.parametrize(
    ("signal", "value", "weeks", "expected"),
    [
        ("W4", D("0.80"), 1, "green"),
        ("W4", D("0.7999"), 6, "amber"),
        ("W4", D("0.50"), 6, "amber"),
        ("W4", D("0.4999"), 3, "amber"),  # not yet four weeks
        ("W4", D("0.4999"), 4, "red"),
        ("W5", D("0.70"), 1, "green"),
        ("W5", D("0.40"), 1, "amber"),
        ("W5", D("0.3999"), 1, "red"),
        ("W5", None, 9, "no data"),
    ],
)
def test_the_chapter_11_bands(
    signal: str, value: Decimal | None, weeks: int, expected: str
) -> None:
    assert colour(signal, value, weeks) == expected  # type: ignore[arg-type]  # literal from params


def _firm(w4: str, w5: str = "green") -> FirmRead:
    def sig(name: str, c: str) -> SignalRead:
        flagged = c in ("amber", "red")
        return SignalRead(
            name,  # type: ignore[arg-type]  # W4 or W5
            D("0.4"),
            1,
            (D("0.4"),),
            c,  # type: ignore[arg-type]  # a colour
            OWNER if flagged else None,
            "act" if flagged else None,
        )

    return FirmRead(uuid4(), "Firm", True, date(2026, 10, 26), 5, (sig("W4", w4), sig("W5", w5)))


def test_one_firm_below_50_percent_stays_amber_two_make_it_red() -> None:
    [alone] = cross_firm([_firm("red")])
    w4 = alone.signals[0]
    assert (w4.colour, w4.note, w4.owner) == ("amber", SINGLE_FIRM_NOTE, OWNER)
    both = cross_firm([_firm("red"), _firm("red")])
    assert [r.signals[0].colour for r in both] == ["red", "red"]


def test_every_amber_or_red_row_names_an_owner_and_an_action() -> None:
    text = report(cross_firm([_firm("amber", "red"), _firm("green")]))
    rows = [line for line in text.splitlines()[2:] if "| amber |" in line or "| red |" in line]
    assert len(rows) == 2
    for line in rows:
        cells = [c.strip() for c in line.strip("|").split("|")]
        assert cells[7] == OWNER and cells[8]
    assert "Firm (synthetic)" in text
