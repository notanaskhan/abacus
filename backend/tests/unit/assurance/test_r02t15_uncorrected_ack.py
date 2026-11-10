"""R-02-T15 (TASK-6513; SPEC-646 AC-12; DEC-3113): the uncorrected-misstatements acknowledgement.

Row acceptance: "Dana's acknowledgement stores 22,250 taken from the snapshot with no client-side
arithmetic."
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abacus.modules.assurance import uncorrected_ack as ua
from abacus.modules.engagements.api import ClientDecision, ClientDecisionContext, ItemChanged

pytestmark = pytest.mark.asyncio
SNAPSHOT = uuid.uuid4()


def test_the_net_effect_is_the_snapshots_frozen_total() -> None:
    # Northwind PY2025: 35,300.00 - 13,050.00 = 22,250.00, frozen as the iron-curtain total.
    totals = {"rollover": "34150", "iron_curtain": "22250", "aggregate": "34150"}
    assert ua.net_effect(totals) == Decimal("22250.00")


def test_a_snapshot_without_its_total_cannot_be_acknowledged() -> None:
    with pytest.raises(ItemChanged):
        ua.net_effect({"rollover": "34150"})


def test_the_seen_hash_moves_with_the_snapshot() -> None:
    a = ua.seen_hash(SNAPSHOT, "a" * 64, Decimal("22250.00"))
    assert a == ua.seen_hash(SNAPSHOT, "a" * 64, Decimal("22250.00"))
    assert a != ua.seen_hash(SNAPSHOT, "b" * 64, Decimal("22250.00"))
    assert a != ua.seen_hash(SNAPSHOT, "a" * 64, Decimal("22250.01"))


async def test_only_an_acknowledgement_is_taken() -> None:
    context = ClientDecisionContext(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "owner", datetime.now(UTC), uuid.uuid4()
    )
    with pytest.raises(ItemChanged):
        await ua.PROVIDER.decide(
            None,  # type: ignore[arg-type]  # refused before any read
            SNAPSHOT,
            ClientDecision("approve", "a" * 64),
            context,
        )
