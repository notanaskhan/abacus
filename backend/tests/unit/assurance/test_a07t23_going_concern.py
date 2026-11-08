"""A-07-T23 (TASK-6207; DEC-2807): going concern's inputs are code's; the decision is the EP's.
Granite Peak: DSCR 1.32x against the 1.25x covenant (AUD-19 e)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.kernel.errors import DomainInvalid
from abacus.modules.assurance.subsequent_events import GoingConcernInputs, going_concern_facts


def test_granite_peak_reads_1_32x_against_1_25x() -> None:
    facts = going_concern_facts(
        GoingConcernInputs(
            Decimal("1584000"), Decimal("1200000"), Decimal("1.25"), date(2028, 3, 31)
        )
    )
    assert (facts.dscr, facts.covenant_dscr, facts.meets_covenant) == (
        Decimal("1.32"),
        Decimal("1.25"),
        True,
    )
    assert facts.headroom == Decimal("0.07")


def test_no_debt_service_is_refused() -> None:
    with pytest.raises(DomainInvalid):
        going_concern_facts(GoingConcernInputs(Decimal(1), Decimal(0), Decimal("1.25")))
