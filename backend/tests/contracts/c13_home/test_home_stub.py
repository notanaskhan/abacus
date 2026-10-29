"""C13 home half, the stub (I-01-T02; `docs/contracts/home-and-gates.md`): `GET /v1/home`
declares `home.read` and answers 404 for a client principal, 403 for a principal the matrix
refuses, 404 with `home.dashboard` off (501 with it on until I-01-T10 made it live); every field
is classified; `home.read` is every firm role's and never a client's, the agent's or the
system's; the home-count slot fails closed."""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import HOME_DASHBOARD
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.platform.api import (
    HomeCount,
    HomeStatusCount,
    home_count,
    home_count_keys,
    register_home_count,
)
from abacus.modules.practice import home_contract as contract
from abacus.modules.practice.home import HomeView

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
FIRM_ROLES = {
    "firm_admin",
    "practice_leader",
    "quality_partner",
    "security_admin",
    "firm_partner",
    "firm_manager",
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "eqr_reviewer",
    "specialist",
    "client_service",
}
MODELS: list[type[BaseModel]] = [
    v
    for v in vars(contract).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == contract.__name__
]


def _ctx(*, client: bool = False, actor_kind: str = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), actor_kind, str(user)),  # type: ignore[arg-type]  # the actor kind under test is a plain str
        user,
        uuid.uuid4(),
        None,
        None,
        client=client,
    )


def test_i01t02_home_declares_home_read_and_is_live() -> None:
    op = PATHS["/v1/home"]["get"]
    assert op["x-abacus-action"] == "home.read"
    assert {"403", "404"} <= set(cast(Json, op["responses"]))
    assert "501" not in cast(Json, op["responses"])  # I-01-T10: live (TASK-1508)
    assert set(PATHS["/v1/home"]) == {"get"}  # Home writes nothing


def test_i01t02_home_read_is_every_firm_role_and_never_a_client_agent_or_system() -> None:
    decisions = RULES["home.read"].decisions
    assert {r for r, d in decisions.items() if d == "allow"} == FIRM_ROLES
    for role in ("client_admin", "client_contributor", "agent", "system"):
        assert decisions.get(role, "deny") == "deny"


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_adr031_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_dec43_no_shape_counts_what_walls_left_out() -> None:
    for model in MODELS:
        for name in model.model_fields:
            assert not any(w in name for w in ("hidden", "walled", "omitted")), name


def _flags(monkeypatch: pytest.MonkeyPatch, value: bool) -> list[Flag]:
    seen: list[Flag] = []

    async def flag_enabled(_tenant: object, flag: Flag) -> bool:
        seen.append(flag)
        return value

    monkeypatch.setattr(contract, "flag_enabled", flag_enabled)
    return seen


def _authorise(monkeypatch: pytest.MonkeyPatch, *, allow: bool) -> list[str]:
    asked: list[str] = []

    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        asked.append(action)
        if not allow:
            raise Forbidden(action, "role")

    monkeypatch.setattr(contract, "authorise", authorise)
    return asked


async def test_i01t02_flag_off_is_404_and_on_answers_home(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _authorise(monkeypatch, allow=True)
    seen = _flags(monkeypatch, False)
    with pytest.raises(NotFound):
        await contract.home_route(_ctx(), None)
    assert seen == [HOME_DASHBOARD] and asked == ["home.read"]
    _flags(monkeypatch, True)
    narrowed: list[uuid.UUID | None] = []

    async def home_view(_ctx: object, office_id: uuid.UUID | None) -> HomeView:
        narrowed.append(office_id)
        return HomeView("Daniel", date(2026, 9, 14), [], None, [], [], None, None)

    async def client_activity(_ctx: object, office_id: uuid.UUID | None) -> list[object]:
        narrowed.append(office_id)
        return []

    monkeypatch.setattr(contract, "home_view", home_view)
    monkeypatch.setattr(contract, "client_activity", client_activity)  # I-01-T12
    office = uuid.uuid4()
    out = await contract.home_route(_ctx(), office)
    assert narrowed == [office, office]  # DEC-30: the office reaches every read
    assert (out.greeting.first_name, out.your_work, out.running_count) == ("Daniel", None, None)


async def test_inv4_a_client_is_404_and_inv1_a_refused_principal_403_before_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _flags(monkeypatch, True)
    _authorise(monkeypatch, allow=True)
    with pytest.raises(NotFound):
        await contract.home_route(_ctx(client=True), None)
    _authorise(monkeypatch, allow=False)
    for kind in ("agent", "system"):
        with pytest.raises(Forbidden):
            await contract.home_route(_ctx(actor_kind=kind), None)
    assert seen == []  # the flag is never read for a principal the matrix refuses


async def _counts(_viewer: object, office_id: uuid.UUID | None) -> HomeCount:
    return HomeCount(
        total=27 if office_id is None else 9,
        by_status=(HomeStatusCount("planning", 17, "phase=planning"),),
    )


async def _broken(_viewer: object, _office_id: uuid.UUID | None) -> HomeCount:
    raise RuntimeError("owner down")


async def test_the_home_count_slot_fails_closed() -> None:
    register_home_count("probe_audits", _counts)
    register_home_count("probe_audits", _counts)  # the same function again is a no-op
    register_home_count("probe_broken", _broken)
    assert {"probe_audits", "probe_broken"} <= set(home_count_keys())
    found = await home_count(object(), "probe_audits", None)
    assert found is not None and found.total == 27
    assert (await home_count(object(), "probe_audits", uuid.uuid4())) == HomeCount(
        9, (HomeStatusCount("planning", 17, "phase=planning"),)
    )
    assert await home_count(object(), "probe_unregistered", None) is None
    assert await home_count(object(), "probe_broken", None) is None
    with pytest.raises(ValueError, match="already registered"):
        register_home_count("probe_audits", _broken)
    with pytest.raises(ValueError, match="snake_case"):
        register_home_count("Probe-Audits", _counts)
