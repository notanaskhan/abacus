"""A-05-T57 close (S31; TASK-6226; DEC-2821): AUD-27's parties in interest carry the year's
transactions a person records; only a person records one, with its ERISA relationship.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid
from abacus.modules.assurance import aud27
from abacus.modules.identity.context import AuthContext


def _ctx(kind: str = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # actor kind under test
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


def test_transactions_read_back_with_their_amounts() -> None:
    raw = [
        {"description": "Fees", "amount": "7800.00"},
        {"description": "Dec 26, 2025 deferrals deposited Jan 9, 2026", "amount": None},
    ]
    assert aud27._transactions(raw) == (  # pyright: ignore[reportPrivateUsage]  # the parser under test
        ("Fees", D("7800.00")),
        ("Dec 26, 2025 deferrals deposited Jan 9, 2026", None),
    )
    assert aud27._transactions(None) == ()  # pyright: ignore[reportPrivateUsage]  # the parser under test


@pytest.mark.parametrize(("kind", "relationship"), [("agent", "TPA"), ("human", "  ")])
async def test_only_a_person_records_a_party_with_its_relationship(
    kind: str, relationship: str
) -> None:
    with pytest.raises(DomainInvalid):
        await aud27.add_party_in_interest(
            _ctx(kind), uuid.uuid4(), "Summit Plan Administrators", relationship=relationship
        )
