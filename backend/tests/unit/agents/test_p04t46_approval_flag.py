"""P-04-T46 (TASK-2339; DEC-1385): SHL-10's live approval of agent output behind
`review.approve_agent_output`, per firm.

Off: approve, reject, route and follow-up answer 404 and the proposal view offers none of them;
reading a proposal needs no flag (`review.grammar_api` retired, P-04-T62) and Undo stays open. On:
the decisions are offered and reach the service.
"""

from __future__ import annotations

import inspect
import uuid
from typing import cast

import pytest

from abacus.kernel._flags import REVIEW_APPROVE_AGENT_OUTPUT
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag
from abacus.modules.agents import contract
from abacus.modules.identity.api import AuthContext

pytestmark = pytest.mark.asyncio
DECIDING_ROUTES = (
    contract.proposal_approve_route,
    contract.proposal_reject_route,
    contract.proposal_route_to_route,
    contract.proposal_follow_up_route,
)


class _Ctx:
    tenant = object()


def _flags(monkeypatch: pytest.MonkeyPatch, *, approve: bool) -> None:
    async def enabled(_tenant: object, flag: Flag) -> bool:
        if flag is REVIEW_APPROVE_AGENT_OUTPUT:
            return approve
        raise AssertionError(flag.name)

    monkeypatch.setattr(contract, "flag_enabled", enabled)


def _ctx() -> AuthContext:
    return cast(AuthContext, _Ctx())


def test_the_flag_is_registered_off_by_default() -> None:
    assert REVIEW_APPROVE_AGENT_OUTPUT.name == "review.approve_agent_output"
    assert (REVIEW_APPROVE_AGENT_OUTPUT.kind, REVIEW_APPROVE_AGENT_OUTPUT.default) == (
        "boolean",
        "false",
    )


async def test_ac_a_decision_answers_404_until_the_firm_turns_approval_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _flags(monkeypatch, approve=False)
    with pytest.raises(NotFound):
        await contract._deciding(_ctx())  # pyright: ignore[reportPrivateUsage] -- the guard under test
    _flags(monkeypatch, approve=True)
    await contract._deciding(_ctx())  # pyright: ignore[reportPrivateUsage] -- the guard under test


def test_ac_every_decision_route_uses_the_guard_and_undo_does_not() -> None:
    for route in DECIDING_ROUTES:
        source = inspect.getsource(route)
        assert "await _deciding(ctx)" in source, route.__name__
        assert "await _live(ctx)" not in source, route.__name__
    assert "await _deciding(ctx)" not in inspect.getsource(contract.proposal_undo_route)


async def test_ac_the_view_offers_no_decision_while_approval_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    offered = ["proposal.read", "proposal.approve", "proposal.reject", "proposal.route"]
    out = contract.AgentProposalOut.model_construct(
        ref=str(uuid.uuid4()), allowed_actions=[*offered, "proposal.follow_up"]
    )
    _flags(monkeypatch, approve=False)
    shown = await contract._shown(_ctx(), out)  # pyright: ignore[reportPrivateUsage] -- under test
    assert shown.allowed_actions == ["proposal.read"]
    _flags(monkeypatch, approve=True)
    shown = await contract._shown(_ctx(), out)  # pyright: ignore[reportPrivateUsage] -- under test
    assert shown.allowed_actions == [*offered, "proposal.follow_up"]
