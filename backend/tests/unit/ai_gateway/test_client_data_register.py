"""SPEC-036 AC-4, AC-8 (TASK-075) against what is actually committed: the real agent specs and the
real provider terms register, with every other condition of the five-part check held true.

Nothing opens yet: the register starts empty and no agent is cleared. These tests say so, and say
that each of those facts alone refuses a real firm, so clearing an agent or entering Bedrock's
terms is a change someone has to make on purpose (and a test here will say what it unlocks).
Expectations come from the spec, not the implementation.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from abacus.ai_gateway import boundary
from abacus.ai_gateway.boundary import DataBoundaryRefused, enforce_boundary
from abacus.kernel import provider_terms
from abacus.kernel.config import Route
from abacus.kernel.db import TenantContext
from abacus.modules.agents.api import cleared_for_client_data
from abacus.modules.agents.specs._specs import SPECS

PROMPT = "evidence.screen@v0"


class _Settings:
    model_data_boundary = "client_data"


class _Tx:
    def record(self, action: str, **kwargs: object) -> None:
        pass


class _Uow:
    def __init__(self, tenant: object) -> None:
        pass

    async def __aenter__(self) -> _Tx:
        return _Tx()

    async def __aexit__(self, *exc: object) -> None:
        return None


@pytest.fixture(autouse=True)
def real_firm_with_everything_else_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real (not synthetic) firm that has opted in, an engagement AI is not off for, an agent
    stage that is live, and `client_data` settings. Clearance and the register stay real."""

    async def real(tenant: object) -> bool:
        return False

    async def yes(*_: object) -> bool:
        return True

    async def not_excluded(*_: object) -> bool:
        return False

    async def live(*_: object) -> str | None:
        return "live"

    monkeypatch.setattr(boundary, "uow", _Uow)
    monkeypatch.setattr(boundary, "settings", _Settings)
    monkeypatch.setattr(boundary, "_check", real)
    monkeypatch.setattr(boundary, "_opted_in", yes)
    monkeypatch.setattr(boundary, "_excluded", not_excluded)
    monkeypatch.setattr(boundary, "_stage", live)
    boundary.clear_cache()


async def _refusal(agent_id: str, route: Route = "bedrock") -> str:
    tenant = TenantContext(uuid.uuid4(), "system", "test")
    with pytest.raises(DataBoundaryRefused) as raised:
        await enforce_boundary(
            tenant, route, PROMPT, agent_id=agent_id, engagement_id=uuid.uuid4()
        )
    return raised.value.reason


# --- AC-4: no agent is cleared -------------------------------------------------------------------


def test_ac4_the_committed_specs_are_not_empty() -> None:
    assert len(SPECS) >= 5


@pytest.mark.parametrize("agent_id", sorted(SPECS))
def test_ac4_no_agent_spec_is_cleared_for_client_data(agent_id: str) -> None:
    assert cleared_for_client_data(agent_id) is False


async def test_ac4_an_agent_that_is_not_a_declared_spec_is_not_cleared() -> None:
    assert cleared_for_client_data("made.up_agent") is False


@pytest.mark.parametrize("agent_id", sorted(SPECS))
async def test_ac4_an_uncleared_agent_is_refused_for_a_real_firm_by_the_real_clearance(
    monkeypatch: pytest.MonkeyPatch, agent_id: str
) -> None:
    """The terms are current in this case, so the agent is the one condition that fails."""
    today = date.today()
    current = provider_terms.TermsEntry(
        "bedrock", "AWS", "us-east-1", today, date(today.year + 1, 1, 1)
    )

    def covering(route: str, on: date) -> provider_terms.TermsEntry | None:
        return current

    monkeypatch.setattr(provider_terms, "covering", covering)
    assert await _refusal(agent_id) == "agent"


# --- AC-8: the committed register ----------------------------------------------------------------


def test_ac8_the_committed_register_has_no_bedrock_entry_yet() -> None:
    assert provider_terms.covering("bedrock", date.today()) is None
    assert provider_terms.covering("bedrock", date(2030, 1, 1)) is None


async def test_ac8_with_no_current_entry_a_real_firm_is_refused_for_terms() -> None:
    """Before the agent: terms are checked first, whatever the agent."""
    assert await _refusal("evidence.screener") == "terms"
    assert await _refusal("not.an_agent") == "terms"


async def test_ac8_the_direct_route_is_refused_whatever_the_register_says() -> None:
    assert await _refusal("evidence.screener", "direct") == "route"
