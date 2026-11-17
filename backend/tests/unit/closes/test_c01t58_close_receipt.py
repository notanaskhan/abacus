"""C-01-T58: the close_receipt intake destination (N-01 DV-7; DEC-5414)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

import abacus.api.app  # noqa: F401  # pyright: ignore[reportUnusedImport] -- modules register at import
from abacus.kernel.db import TenantContext
from abacus.modules.closes import intake_destination as d


def test_the_destination_is_registered_on_communications() -> None:
    from abacus.modules.communications.triage_apply import (
        _DESTINATIONS,  # pyright: ignore[reportPrivateUsage] -- the registry under test
    )

    assert _DESTINATIONS[d.KIND].place is d.place_close_receipt


def test_a_card_charge_is_information_with_a_stable_id() -> None:
    close = uuid.UUID(int=5)
    assert d.charge_id(close, "snap:12") == d.charge_id(close, "snap:12")
    assert d.charge_id(close, "snap:12") != d.charge_id(close, "snap:13")
    assert d.charge_label("Front Range Office Supply", None, "2026-08-21", Decimal("-212.40")) == (
        "Front Range Office Supply · 2026-08-21 · 212.40"
    )
    assert (
        d.charge_label(None, None, "2026-08-21", Decimal("5")) == "Card charge · 2026-08-21 · 5.00"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["agent", "system"])
async def test_an_agent_or_the_system_never_places_a_close_receipt(actor: str) -> None:
    from abacus.modules.identity.api import Forbidden

    tenant = TenantContext(uuid.uuid4(), actor, f"{actor}:probe")  # type: ignore[arg-type] -- the actor kind under test
    with pytest.raises(Forbidden):
        await d.place_close_receipt(tenant, None, uuid.uuid4())  # type: ignore[arg-type] -- refused before the transaction is used
