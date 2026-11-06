"""EBP-04 c (TASK-3362; DEC-2361): a participant's rate is their year's, from their entry date."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from abacus.modules.assurance import ebp_tests
from abacus.modules.assurance.compute.ebp.eligibility import QACA, missed

pytestmark = pytest.mark.asyncio


class _Ctx:
    tenant_id = uuid4()


async def test_a_person_with_no_dates_reads_the_default_rate() -> None:
    person = {"dob_sealed": None, "hire_on": None, "import_id": uuid4(), "participant_key": "P-1"}
    rule = await ebp_tests._rule_of(  # pyright: ignore[reportPrivateUsage] -- the unit under test
        _Ctx(),  # pyright: ignore[reportArgumentType] -- only its tenant_id is read
        person,  # pyright: ignore[reportArgumentType] -- a row's shape, no database here
        2025,
    )
    assert rule is QACA


async def test_the_year_after_entry_adds_a_step(monkeypatch: pytest.MonkeyPatch) -> None:
    async def opened(*_args: object) -> bytes:
        return b"1980-01-01"

    monkeypatch.setattr(ebp_tests, "open_sealed", opened)
    person = {
        "dob_sealed": b"sealed",
        "hire_on": date(2022, 1, 3),
        "import_id": uuid4(),
        "participant_key": "P-2",
    }
    rule = await ebp_tests._rule_of(  # pyright: ignore[reportPrivateUsage] -- the unit under test
        _Ctx(),  # pyright: ignore[reportArgumentType] -- only its tenant_id is read
        person,  # pyright: ignore[reportArgumentType] -- a row's shape, no database here
        2025,
    )
    assert rule.default_pct > QACA.default_pct
    assert missed(Decimal(100000), rule).deferral > missed(Decimal(100000)).deferral
