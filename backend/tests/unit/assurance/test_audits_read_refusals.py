"""Security review of A-01-T08 to T10 (SPEC-330 AC-21, AC-22; DEC-311, DEC-312): a client
principal, an agent or the system is refused by the live index and cockpit routes and by their
read models themselves (client principals hold `engagement.read_metadata` cells), before
anything is read; a provider's required action is part of its registration."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.db import ActorKind, TenantContext
from abacus.modules.assurance import api as assurance_api
from abacus.modules.assurance import audits_contract, cockpit, index, sections
from abacus.modules.identity.api import AuthContext, Forbidden

assert assurance_api.ROUTERS  # registers A-01's rows

REFUSED: tuple[tuple[ActorKind, bool], ...] = (
    ("human", True),
    ("agent", False),
    ("system", False),
)


def _ctx(kind: ActorKind, *, client: bool) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)), user, uuid.uuid4(), None, None, client=client
    )


async def _never(*_args: object) -> bool:
    raise AssertionError("refused before the flag is read")


@pytest.mark.parametrize(("kind", "client"), REFUSED)
async def test_ac21_the_index_route_refuses_client_agent_and_system(
    kind: ActorKind, client: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audits_contract, "flag_enabled", _never)
    with pytest.raises(Forbidden):
        await audits_contract.audits_index_route(ctx=_ctx(kind, client=client))


@pytest.mark.parametrize(("kind", "client"), REFUSED)
async def test_ac21_the_cockpit_route_refuses_client_agent_and_system(
    kind: ActorKind, client: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audits_contract, "flag_enabled", _never)
    with pytest.raises(Forbidden):
        await audits_contract.audit_cockpit_route(uuid.uuid4(), ctx=_ctx(kind, client=client))


@pytest.mark.parametrize(("kind", "client"), REFUSED)
async def test_ac21_the_read_models_refuse_client_agent_and_system_themselves(
    kind: ActorKind, client: bool
) -> None:
    ctx = _ctx(kind, client=client)
    with pytest.raises(Forbidden):
        await index.audits_index(ctx, index.IndexFilters(), cursor=None, limit=10)
    with pytest.raises(Forbidden):
        await cockpit.audit_cockpit(ctx, uuid.uuid4())


def test_ac22_the_methodology_row_requires_methodology_read_on_the_firm() -> None:
    found = {s.key: s for s in sections.registered_sections()}
    assert (found["methodology"].required_action, found["methodology"].action_scope) == (
        "methodology.read",
        "firm",
    )
    assert all(s.required_action is None for k, s in found.items() if k != "methodology")


def test_ac18_the_search_is_a_literal_substring() -> None:
    assert index.like_escaped("50%_off\\") == "50\\%\\_off\\\\"
