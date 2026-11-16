"""A-09-T21 (red): a component auditor reads only its component's room, and a message naming
another component's figures is refused."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.assurance import component_scope as cs
from abacus.modules.identity.api import AuthContext

DISTRIBUTION_REVENUE = 31_000_000_00  # cents
MANUFACTURING_REVENUE = 42_000_000_00


def test_ac_a_message_naming_another_components_figures_is_refused() -> None:
    own, others = {DISTRIBUTION_REVENUE}, {MANUFACTURING_REVENUE}
    assert cs.foreign_figures("Revenue of $42,000,000.00 at Manufacturing", own, others) == [
        MANUFACTURING_REVENUE
    ]
    assert cs.foreign_figures("Your revenue of 31,000,000 ties", own, others) == []
    assert cs.foreign_figures("Please reply within 14 days", own, others) == []


async def test_a_firm_member_holds_no_component_scope() -> None:
    who = uuid.uuid4()
    ctx = AuthContext(TenantContext(uuid.uuid4(), "human", str(who)), who, uuid.uuid4(), None,
                      datetime.now(UTC))  # fmt: skip
    assert await cs.component_ids(ctx) == frozenset()
    with pytest.raises(NotFound):
        await cs.require_room(ctx, uuid.uuid4())
