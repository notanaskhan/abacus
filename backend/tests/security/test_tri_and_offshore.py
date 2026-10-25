# ac-test-author: notanaskhan (G-01-T09; T-01 adds the I-7216 cases with its consent provider)
"""I-OFFSHORE (G-01 AC9.2 to AC9.4; DEC-52, ADR P-12, §7216) against Postgres: an offshore
member, and an agent or system run acting for one, is refused every matrix action on a client
without a valid offshore-disclosure consent, at the wall (404 everywhere); no reveal of a TIN or
other identifier is ever among their allowed actions, consent or not; and every response field
tagged `pii_kind=tin` reaches them masked or null. TIN fields are few until T-01 adds them: the
served routes that carry one are pinned here, and the hook is proved on a tagged test model.

The control is an onshore manager on the same engagements: their answers differ, so a refusal
can't pass by accident."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast, get_args

import pytest
from fastapi.routing import iter_route_contexts
from pydantic import BaseModel
from sqlalchemy import ColumnElement, literal

from abacus.api import create_app
from abacus.kernel.classification import classified, pii_paths
from abacus.kernel.db import TenantContext
from abacus.modules.identity import slots
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    agent_context_for_run,
    allowed_actions,
    authorise,
    mask_tins_for,
)
from abacus.modules.identity.authz.matrix import RULES

from .support import Env, Person

REVEALS = ("tin.reveal", "pii.reveal")
# The served responses that carry a `pii_kind=tin` field today (route, model), and how each
# reaches an offshore principal: the record through `mask_tins_for`, the reveal never (its action
# is `not_offshore`). A new one fails here until it is wired.
TIN_ROUTES = {
    ("GET", "/v1/clients/{client_id}"): "masked",
    ("PATCH", "/v1/clients/{client_id}"): "masked",
    ("POST", "/v1/client-entities/{entity_id}/tin/reveal"): "refused",
}


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _offshore(env: Env) -> Person:
    who = await env.net.seed.person(env.tenant_id)
    for site in (env.a, env.b):
        await env.net.seed.member(site, who, "manager")
    await env.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        env.tenant_id,
        who.user_id,
    )
    return who


@pytest.fixture
def b_consented(env: Env) -> Iterator[None]:
    """T-01's provider stand-in: a valid consent covers client B only."""
    b = env.b.client_id

    async def check(_tenant: TenantContext, client: uuid.UUID, _p: str, _at: datetime) -> bool:
        return client == b

    def column(client_id: object, _purpose: str) -> ColumnElement[bool]:
        return literal(b) == client_id

    slots.register_consent_check(slots.OFFSHORE_DISCLOSURE, check, column)
    yield
    slots._CONSENTS.pop(slots.OFFSHORE_DISCLOSURE, None)  # pyright: ignore[reportPrivateUsage] -- drops the stand-in
    slots._CONSENT_COLUMNS.pop(slots.OFFSHORE_DISCLOSURE, None)  # pyright: ignore[reportPrivateUsage] -- drops the stand-in


# --- refused at the wall, for every action -------------------------------------------------------


async def test_i_offshore_every_action_on_a_non_consented_client_is_refused_at_the_wall(
    env: Env,
) -> None:
    remy = _ctx(await _offshore(env))
    resources = (
        Resource.client(env.tenant_id, env.a.client_id),
        Resource.engagement(env.tenant_id, env.a.engagement_id, archived=False),
    )
    found: list[str] = []
    for action in sorted(RULES):
        for resource in resources:
            try:
                await authorise(remy, action, resource, reason="probe")
            except Forbidden as denied:
                if denied.layer != "wall":
                    found.append(f"{action}: {denied.layer}")
            else:
                found.append(f"{action}: allowed")
    assert found == []
    assert await allowed_actions(remy, resources[1]) == frozenset()


async def test_i_offshore_the_control_onshore_manager_is_allowed(env: Env) -> None:
    manager = await env.net.seed.person(env.tenant_id)
    await env.net.seed.member(env.a, manager, "manager")
    resource = Resource.engagement(env.tenant_id, env.a.engagement_id, archived=False)
    assert "engagement.read" in await allowed_actions(_ctx(manager), resource)


async def test_i_offshore_an_agent_and_a_system_run_for_remy_are_refused_too(env: Env) -> None:
    remy = await _offshore(env)
    run = await env.net.seed.value(
        "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, status) VALUES ($1, 'evidence.screener', 1, $2, $3, "
        "'{}', 'running') RETURNING id",
        env.tenant_id,
        env.a.engagement_id,
        remy.user_id,
    )
    agent = await agent_context_for_run(
        tenant_id=env.tenant_id,
        run_id=uuid.UUID(str(run)),
        agent_id="evidence.screener",
        engagement_id=env.a.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=remy.user_id,
    )
    resource = Resource.engagement(env.tenant_id, env.a.engagement_id, archived=False)
    with pytest.raises(Forbidden) as denied:
        await authorise(agent, "evidence.read", resource)
    assert denied.value.layer == "wall"


# --- no reveal, ever -----------------------------------------------------------------------------


def test_i_offshore_every_reveal_action_is_not_offshore_in_the_matrix() -> None:
    reveals = sorted(a for a in RULES if a.endswith(".reveal"))
    assert set(REVEALS) <= set(reveals)
    assert [a for a in reveals if not RULES[a].not_offshore] == []


async def test_i_offshore_a_consented_client_still_allows_no_reveal(
    env: Env, b_consented: None
) -> None:
    remy = _ctx(await _offshore(env))
    resource = Resource.engagement(env.tenant_id, env.b.engagement_id, archived=False)
    allowed = await allowed_actions(remy, resource)
    assert "engagement.read" in allowed  # consented: his manager role applies again
    assert not set(REVEALS) & allowed
    walled = Resource.engagement(env.tenant_id, env.a.engagement_id, archived=False)
    assert await allowed_actions(remy, walled) == frozenset()


# --- TIN fields reach an offshore principal masked -----------------------------------------------


class _TinOut(BaseModel):
    tin: Annotated[str, classified("restricted", pii_kind="tin")]
    last4: Annotated[str | None, classified("restricted", pii_kind="tin")] = None
    name: Annotated[str, classified("confidential")]


class _NestedOut(BaseModel):
    one: _TinOut
    many: Annotated[list[_TinOut], classified("internal")]


def _sample() -> _NestedOut:
    tin = _TinOut(tin="900-12-3456", last4="3456", name="Remy")
    return _NestedOut(one=tin, many=[tin, tin])


async def test_i_offshore_tagged_tin_fields_are_masked_or_null_for_an_offshore_principal(
    env: Env,
) -> None:
    remy = _ctx(await _offshore(env))
    masked = await mask_tins_for(remy, _sample())
    for item in (masked.one, *masked.many):
        assert item.tin == "•••-••-3456"
        assert item.last4 is None
        assert item.name == "Remy"
    manager = await env.net.seed.person(env.tenant_id)
    assert await mask_tins_for(_ctx(manager), _sample()) == _sample()


def test_i_offshore_every_served_tin_field_is_masked_or_refused() -> None:
    def models(annotation: object) -> Iterator[type[BaseModel]]:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield annotation
        for arg in get_args(annotation):
            yield from models(arg)

    found: dict[tuple[str, str], str] = {}
    for context in iter_route_contexts(create_app().routes):
        route = context.original_route
        path = str(context.path)
        methods = cast(set[str], getattr(route, "methods", None) or set())
        for model in models(getattr(route, "response_model", None)):
            if pii_paths(model, "tin"):
                for method in methods:
                    found[(method, path)] = TIN_ROUTES.get((method, path), "?")
    assert found == TIN_ROUTES
    reveal = RULES["tin.reveal"]
    assert reveal.not_offshore
