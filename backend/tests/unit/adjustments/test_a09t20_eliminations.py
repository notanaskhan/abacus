"""A-09-T20 (red): eliminations refuse an agent or the system at the service layer, and an
unbalanced entry shows its off-by (approval answers 409 `unbalanced_entry`)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.adjustments.api import eliminations as elim
from abacus.modules.identity.api import AuthContext, Forbidden


def _ctx(kind: str) -> AuthContext:
    who = uuid.uuid4()
    tenant = TenantContext(uuid.uuid4(), kind, str(who), who if kind == "agent" else None)  # type: ignore[arg-type] -- the test's actor kind
    return AuthContext(tenant, who, uuid.uuid4(), None, datetime.now(UTC))


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_ac_an_agent_or_system_principal_is_refused_at_the_service(kind: str) -> None:
    with pytest.raises(Forbidden):
        await elim.approve(_ctx(kind), [uuid.uuid4()])
    with pytest.raises(Forbidden):
        await elim.post(_ctx(kind), uuid.uuid4())


def test_an_unbalanced_entry_shows_its_off_by() -> None:
    entity = uuid.uuid4()
    lines = (
        elim.EliminationLine("Intercompany payable", entity, D("2400000.00"), D(0)),
        elim.EliminationLine("Intercompany receivable", entity, D(0), D("2300000.00")),
    )
    view = elim.EliminationView(uuid.uuid4(), "E4", 2, "Intercompany balances", "proposed", lines,
                                D("2400000.00"), D("2300000.00"))  # fmt: skip
    assert view.off_by == D("100000.00")
    assert elim.UnbalancedEntry(facts={"entry": "x"}).code == "unbalanced_entry"
