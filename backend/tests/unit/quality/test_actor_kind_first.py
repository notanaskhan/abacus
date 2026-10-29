"""Human-only gates read the actor kind before `ctx.client` (P-07-T59 security review, TASK-1815).

An `AgentContext` has no `client` (nor `is_support`): a gate that tested `ctx.client` first raised
`AttributeError` (a 500, nothing written) for an agent instead of refusing it with 403. Over HTTP
`current_context` only yields an `AuthContext`, so only an agent context handed straight to a
gate met it; the order is fixed everywhere so an agent is refused as one.

Static: no condition in `src/abacus` tests `.client` before `.tenant.actor_kind`. Behaviour: four
of the gates refuse an agent context with `Forbidden`.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import audits_contract
from abacus.modules.engagements import acceptance_contract, intake_contract
from abacus.modules.identity import context
from abacus.modules.identity.api import AgentContext, AuthContext, Forbidden
from abacus.modules.organisations import conflicts_contract

SRC = Path(__file__).resolve().parents[3] / "src" / "abacus"
# `.client` then, in the same `or` chain, the actor kind: the order that breaks for an agent.
CLIENT_FIRST = re.compile(r"\.client\s+or\s+(?:[\w.()]+\s+or\s+)*[\w.]+\.tenant\.actor_kind")


def _agent() -> AgentContext:
    user = uuid.uuid4()
    tenant = TenantContext(uuid.uuid4(), "human", str(user))
    initiator = AuthContext(tenant, user, uuid.uuid4(), "firm_admin", None)
    run = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(tenant.tenant_id, "agent", f"agent:engagement_agent:{run}"),
        agent_id="engagement_agent",
        agent_run_id=run,
        engagement_id=uuid.uuid4(),
        task_scope=frozenset(),
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


def test_no_gate_tests_client_before_the_actor_kind() -> None:
    found = [
        f"{path.relative_to(SRC)}:{n}"
        for path in sorted(SRC.rglob("*.py"))
        for n, line in enumerate(path.read_text().splitlines(), start=1)
        if CLIENT_FIRST.search(line)
    ]
    assert found == []


E = uuid.uuid4()
GATES: dict[str, Callable[[AuthContext], Awaitable[None]]] = {
    "acceptance": lambda ctx: acceptance_contract._allowed(ctx, "acceptance.decide", E),  # pyright: ignore[reportPrivateUsage] -- the gate
    "conflicts": lambda ctx: conflicts_contract._gate(ctx, "conflict.run"),  # pyright: ignore[reportPrivateUsage] -- the gate
    "intake": lambda ctx: intake_contract._gate(ctx, "client.intake"),  # pyright: ignore[reportPrivateUsage] -- the gate
    "audits": lambda ctx: audits_contract._allowed(ctx, "audit.read", None),  # pyright: ignore[reportPrivateUsage] -- the gate
}


@pytest.mark.parametrize("gate", sorted(GATES))
async def test_an_agent_context_is_refused_not_crashed(gate: str) -> None:
    with pytest.raises(Forbidden):
        await GATES[gate](cast(AuthContext, _agent()))
