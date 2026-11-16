"""T-07-T23: the allocation foots by code, the 65-day window, and an agent never records the
election."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import fiduciary_beneficiaries as fb


def test_ac_the_allocation_foots_160_000_plus_80_000_is_240_000() -> None:
    nora, theo = fb.allocate({"dni": D("240000")}, [("Nora", D("2") / 3), ("Theo", D("1") / 3)])
    assert (nora.total, theo.total) == (D("160000.00"), D("80000.00"))
    assert nora.total + theo.total == D("240000.00")


def test_the_last_beneficiary_takes_the_rounding() -> None:
    parts = fb.allocate(
        {"interest": D("100.00")}, [("A", D("1") / 3), ("B", D("1") / 3), ("C", D("1") / 3)]
    )
    assert sum(p.by_class["interest"] for p in parts) == D("100.00")


def test_the_window_is_the_65th_day_after_year_end() -> None:
    assert fb.window_end(2026) == date(2027, 3, 6)


async def test_ac_an_agent_cannot_record_the_election() -> None:
    who = uuid.uuid4()
    ctx = AuthContext(TenantContext(uuid.uuid4(), "agent", str(who), who), who, uuid.uuid4(),
                      None, datetime.now(UTC))  # fmt: skip
    with pytest.raises(Forbidden):
        await fb.record_election(ctx, uuid.uuid4(), 2026, status="not_made", amount=None,
                                 paid_on=None, decision_owner_contact_id=uuid.uuid4())  # fmt: skip
