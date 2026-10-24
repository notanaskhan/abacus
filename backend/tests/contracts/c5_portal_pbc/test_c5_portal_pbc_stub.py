"""C5 section `portal-pbc` stub (R-01-T01; docs/contracts/portal-pbc.md): every route exists with
its one matrix action and answers 404 with its flag off and 501 with it on; the read action is a
client action that grants no firm role and denies the agent and system; the void is human only;
every client-facing write takes an `Idempotency-Key`; every model field is classified; the three
flags are boolean and off by default. The consumers' own tests are R-01-T02's, in this
directory."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import (
    PORTAL_DOCUMENTS_V2,
    PORTAL_DROP_SORT,
    PORTAL_THIRD_PARTY_ROOM,
)
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.evidence import drops_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.portal import pbc_contract as portal_pbc
from abacus.modules.requests import pbc_contract as requests_pbc

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])

# (method, path) -> (the one matrix action, the flag that gates it) (R-01 §4.3; DEC-139 spelling).
ROUTES: dict[tuple[str, str], tuple[str, Flag]] = {
    ("get", "/v1/portal/binders"): ("portal_documents.read", PORTAL_DOCUMENTS_V2),
    ("get", "/v1/portal/binders/{binder_id}"): ("portal_documents.read", PORTAL_DOCUMENTS_V2),
    ("get", "/v1/portal/request-items/{item_id}"): (
        "portal_documents.read",
        PORTAL_DOCUMENTS_V2,
    ),
    ("get", "/v1/portal/room"): ("portal_documents.read", PORTAL_THIRD_PARTY_ROOM),
    ("post", "/v1/portal/room/suggest"): ("portal_documents.read", PORTAL_THIRD_PARTY_ROOM),
    ("get", "/v1/portal/drops/{batch_id}"): ("portal_documents.read", PORTAL_DROP_SORT),
    ("post", "/v1/portal/request-items/{item_id}/ignore/undo"): (
        "request_item.ignore",
        PORTAL_DOCUMENTS_V2,
    ),
    ("post", "/v1/portal/binders/{binder_id}/mark-done/undo"): (
        "binder.mark_done",
        PORTAL_DOCUMENTS_V2,
    ),
    ("post", "/v1/portal/binders/{binder_id}/drops"): ("evidence.upload", PORTAL_DROP_SORT),
    ("post", "/v1/engagements/{engagement_id}/fulfilments/{fulfilment_id}/void"): (
        "fulfilment.confirm",
        PORTAL_DROP_SORT,
    ),
}
# Client-visible or external effects (ADR P-36): each takes an Idempotency-Key.
IDEMPOTENT = {
    ("post", "/v1/portal/request-items/{item_id}/ignore/undo"),
    ("post", "/v1/portal/binders/{binder_id}/mark-done/undo"),
    ("post", "/v1/portal/binders/{binder_id}/drops"),
    ("post", "/v1/engagements/{engagement_id}/fulfilments/{fulfilment_id}/void"),
}
CONFLICTS = {
    ("post", "/v1/portal/request-items/{item_id}/ignore/undo"),  # firm_already_acted
    ("post", "/v1/portal/binders/{binder_id}/mark-done/undo"),  # firm_already_acted
    ("post", "/v1/engagements/{engagement_id}/fulfilments/{fulfilment_id}/void"),  # not_voidable
}
STUBS: list[tuple[ModuleType, Flag]] = [
    (portal_pbc, PORTAL_DOCUMENTS_V2),
    (portal_pbc, PORTAL_THIRD_PARTY_ROOM),
    (portal_pbc, PORTAL_DROP_SORT),
    (requests_pbc, PORTAL_DOCUMENTS_V2),
    (requests_pbc, PORTAL_DROP_SORT),
]


def _models(module: ModuleType) -> list[type[BaseModel]]:
    return [
        v
        for v in vars(module).values()
        if isinstance(v, type)
        and issubclass(v, BaseModel)
        and v is not BaseModel
        and v.__module__ == module.__name__
    ]


MODELS = _models(portal_pbc) + _models(requests_pbc) + _models(drops_contract)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_one_action_and_the_stub_answers(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)][0]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


@pytest.mark.parametrize(("method", "path"), sorted(CONFLICTS))
def test_undo_and_void_document_their_conflict(method: str, path: str) -> None:
    assert "409" in cast(Json, PATHS[path][method]["responses"])


def test_the_drop_documents_its_size_and_type_refusals_and_accepts_with_202() -> None:
    responses = cast(Json, PATHS["/v1/portal/binders/{binder_id}/drops"]["post"]["responses"])
    assert {"202", "413", "415"} <= set(responses)


@pytest.mark.parametrize(("method", "path"), sorted(IDEMPOTENT))
def test_every_client_facing_write_takes_an_idempotency_key(method: str, path: str) -> None:
    params = cast(list[Json], PATHS[path][method].get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True


def test_the_drop_carries_its_batch_header() -> None:
    params = cast(list[Json], PATHS["/v1/portal/binders/{binder_id}/drops"]["post"]["parameters"])
    batch = [p for p in params if p["name"] == "X-Drop-Batch" and p["in"] == "header"]
    assert batch and batch[0]["required"] is True


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_the_read_action_is_a_client_action_over_a_covered_scope() -> None:
    rule = RULES["portal_documents.read"]
    granted = {r for r, d in rule.decisions.items() if d != "deny"}
    assert granted == {"client_admin", "client_contributor"}
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"
    assert rule.scope_only


def test_the_void_is_human_only() -> None:
    assert RULES["fulfilment.confirm"].decisions.get("agent") == "deny"


def test_the_undos_reuse_the_client_actions_and_deny_the_agent() -> None:
    for action in ("request_item.ignore", "binder.mark_done"):
        decisions = RULES[action].decisions
        assert decisions.get("agent") == "deny"
        assert {r for r, d in decisions.items() if d != "deny"} == {
            "client_admin",
            "client_contributor",
        }


Stub = Callable[[AuthContext, Flag], Awaitable[object]]


@pytest.mark.parametrize(
    ("module", "flag"), STUBS, ids=[f"{m.__name__.split('.')[-2]}:{f.name}" for m, f in STUBS]
)
async def test_flag_off_is_404_and_flag_on_is_501(
    module: ModuleType, flag: Flag, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = cast(Stub, module._stub)
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, asked: object) -> bool:
        seen.append(asked)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(module, "flag_enabled", off)
    with pytest.raises(NotFound):
        await stub(ctx, flag)
    assert seen == [flag]
    monkeypatch.setattr(module, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await stub(ctx, flag)


async def test_the_drop_is_404_off_and_501_on(monkeypatch: pytest.MonkeyPatch) -> None:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )

    async def off(_tenant: object, asked: object) -> bool:
        assert asked is PORTAL_DROP_SORT
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    module = drops_contract
    stub = cast(Callable[[AuthContext], Awaitable[object]], vars(module)["_stub"])
    monkeypatch.setattr(module, "flag_enabled", off)
    with pytest.raises(NotFound):
        await stub(ctx)
    monkeypatch.setattr(module, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await stub(ctx)


@pytest.mark.parametrize("flag", [PORTAL_DOCUMENTS_V2, PORTAL_DROP_SORT, PORTAL_THIRD_PARTY_ROOM])
def test_the_three_flags_are_boolean_and_default_off(flag: Flag) -> None:
    assert flag.kind == "boolean"
    assert flag.default == "false"


def test_no_route_of_the_family_is_unauthenticated() -> None:
    for method, path in ROUTES:
        assert PATHS[path][method]["x-abacus-action"] not in ("PUBLIC", "PORTAL_PUBLIC")
