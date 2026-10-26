"""K-01-T01 stubs (`docs/contracts/knowledge-catalog.md`, `methodology-programs.md`): every
route declares its one matrix action and answers 404 for a client principal, 404 with its flag
off and 501 with it on; every field is classified; approving and locking are a person's acts
with a fresh second factor, and the agent may only parse; the SPEC-008 rows moved to the
methodology module's matrix file."""

from __future__ import annotations

import inspect
import json
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

import pytest
import yaml
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import KNOWLEDGE_CATALOG, METHODOLOGY_LIFECYCLE, METHODOLOGY_PROGRAMS
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.methodology import contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
MATRIX = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "permission-matrix"

ROUTES: dict[tuple[str, str], tuple[str, Flag]] = {
    ("get", "/v1/knowledge/items"): ("knowledge.read", KNOWLEDGE_CATALOG),
    ("get", "/v1/knowledge/review-queue"): ("knowledge.read", KNOWLEDGE_CATALOG),
    ("get", "/v1/knowledge/change-log"): ("knowledge.read", KNOWLEDGE_CATALOG),
    ("post", "/v1/methodology/versions/{version_id}/submit"): (
        "methodology.manage",
        METHODOLOGY_LIFECYCLE,
    ),
    ("post", "/v1/methodology/versions/{version_id}/approve"): (
        "methodology.approve",
        METHODOLOGY_LIFECYCLE,
    ),
    ("post", "/v1/methodology/versions/{version_id}/drafts"): (
        "methodology.manage",
        METHODOLOGY_PROGRAMS,
    ),
    ("post", "/v1/methodology/versions/{version_id}/discard"): (
        "methodology.manage",
        METHODOLOGY_PROGRAMS,
    ),
    ("get", "/v1/methodology/programs/{program_id}"): ("methodology.read", METHODOLOGY_PROGRAMS),
    ("get", "/v1/methodology/programs/{program_id}/steps"): (
        "methodology.read",
        METHODOLOGY_PROGRAMS,
    ),
    ("get", "/v1/methodology/steps/resolve"): ("methodology.read", METHODOLOGY_PROGRAMS),
    ("patch", "/v1/methodology/versions/{version_id}/steps/{step_id}"): (
        "methodology.manage",
        METHODOLOGY_PROGRAMS,
    ),
    ("post", "/v1/methodology/versions/{version_id}/programs/{program_id}/steps"): (
        "methodology.manage",
        METHODOLOGY_PROGRAMS,
    ),
    ("delete", "/v1/methodology/versions/{version_id}/steps/{step_id}"): (
        "methodology.manage",
        METHODOLOGY_PROGRAMS,
    ),
    ("post", "/v1/methodology/versions/{version_id}/steps/{step_id}/mandatory"): (
        "methodology.approve",
        METHODOLOGY_PROGRAMS,
    ),
    ("get", "/v1/methodology/versions/{version_id}/export.xlsx"): (
        "methodology.read",
        METHODOLOGY_PROGRAMS,
    ),
}
ENDPOINTS: list[tuple[str, Callable[..., Awaitable[object]], Flag]] = []
for _router in (
    contract.knowledge_router,
    contract.methodology_lifecycle_router,
    contract.programs_router,
):
    for _route in _router.routes:
        assert isinstance(_route, APIRoute)
        _method = next(iter(_route.methods or {"GET"})).lower()
        ENDPOINTS.append(
            (
                _route.path,
                cast(Callable[..., Awaitable[object]], _route.endpoint),
                ROUTES[(_method, _route.path)][1],
            )
        )
MODELS: list[type[BaseModel]] = [
    v
    for v in vars(contract).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == contract.__name__
]


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_k01t01_each_route_declares_its_one_action_and_is_a_stub(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)][0]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


def test_k01t01_the_endpoints_are_the_routes_above() -> None:
    assert len(ENDPOINTS) == len(ROUTES)


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_adr031_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def _ctx(*, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        None,
        client=client,
    )


@pytest.mark.parametrize(
    ("path", "endpoint", "flag"), ENDPOINTS, ids=[e.__name__ for _p, e, _f in ENDPOINTS]
)
async def test_k01t01_client_404_flag_off_404_flag_on_501(
    path: str,
    endpoint: Callable[..., Awaitable[object]],
    flag: Flag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Flag] = []

    def flags(value: bool) -> Callable[[object, Flag], Awaitable[bool]]:
        async def flag_enabled(_tenant: object, asked: Flag) -> bool:
            seen.append(asked)
            return value

        return flag_enabled

    params = inspect.signature(endpoint).parameters
    monkeypatch.setattr(contract, "flag_enabled", flags(True))
    with pytest.raises(NotFound):
        await endpoint(**{n: (_ctx(client=True) if n == "ctx" else None) for n in params})
    assert seen == []
    monkeypatch.setattr(contract, "flag_enabled", flags(False))
    with pytest.raises(NotFound):
        await endpoint(**{n: (_ctx() if n == "ctx" else None) for n in params})
    assert seen == [flag]
    monkeypatch.setattr(contract, "flag_enabled", flags(True))
    with pytest.raises(NotImplementedYet):
        await endpoint(**{n: (_ctx() if n == "ctx" else None) for n in params})


def test_inv1_approving_and_locking_are_a_persons_acts_with_a_fresh_factor() -> None:
    rule = RULES["methodology.approve"]
    assert {r for r, d in rule.decisions.items() if d == "allow"} == {"quality_partner"}
    assert rule.decisions.get("agent") == "deny" and rule.decisions.get("system") == "deny"
    assert rule.mfa_recent


def test_the_agent_only_parses_its_own_import() -> None:
    assert RULES["methodology.parse"].decisions == {"agent": "task_scope"}
    assert RULES["methodology.manage"].decisions.get("agent") == "deny"


def test_the_spec008_rows_live_in_the_methodology_matrix_file() -> None:
    mine = cast(Json, yaml.safe_load((MATRIX / "methodology.yaml").read_text())["actions"])
    assert {"methodology.read", "methodology.manage", "methodology.approve"} <= set(mine)
    theirs = cast(Json, yaml.safe_load((MATRIX / "engagements.yaml").read_text())["actions"])
    assert not {a for a in theirs if a.startswith("methodology.")}
