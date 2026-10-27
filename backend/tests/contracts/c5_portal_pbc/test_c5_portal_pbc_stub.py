"""C5 section `portal-pbc` stub (R-01-T01; docs/contracts/portal-pbc.md): every route exists with
its one matrix action and answers 404 with its flag off and 501 with it on until its task lands
(`IMPLEMENTED`: the documents reads, R-01-T07, the undos, R-01-T08, the drop, R-01-T09, the
void, TASK-1248, and the room with its suggest, R-01-T13); the read action is a
client action that grants no firm role and denies the agent and system; the void is human only;
every client-facing write takes an `Idempotency-Key`; every model field is classified; the two
remaining flags are boolean and off by default, and the documents reads and the undos are served
to every firm since R-01-T18 retired `portal.documents_v2` (DEC-510). The consumers' own tests
are R-01-T02's, in this directory."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import cast

import pytest
from fastapi import Request
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import (
    FLAGS,
    PORTAL_DROP_SORT,
    PORTAL_THIRD_PARTY_ROOM,
)
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag
from abacus.modules.evidence import drops_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.portal import documents_routes, rooms
from abacus.modules.portal import pbc_contract as portal_pbc
from abacus.modules.requests import pbc_contract as requests_pbc

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])

# (method, path) -> (the one matrix action, the flag that gates it; None: every firm since
# `portal.documents_v2` retired, R-01-T18) (R-01 §4.3; DEC-139 spelling).
ROUTES: dict[tuple[str, str], tuple[str, Flag | None]] = {
    ("get", "/v1/portal/binders"): ("portal_documents.read", None),
    ("get", "/v1/portal/binders/{binder_id}"): ("portal_documents.read", None),
    ("get", "/v1/portal/request-items/{item_id}"): ("portal_documents.read", None),
    ("get", "/v1/portal/room"): ("portal_documents.read", PORTAL_THIRD_PARTY_ROOM),
    ("post", "/v1/portal/room/suggest"): ("portal_documents.read", PORTAL_THIRD_PARTY_ROOM),
    ("get", "/v1/portal/drops/{batch_id}"): ("portal_documents.read", PORTAL_DROP_SORT),
    ("post", "/v1/portal/request-items/{item_id}/ignore/undo"): ("request_item.ignore", None),
    ("post", "/v1/portal/binders/{binder_id}/mark-done/undo"): ("binder.mark_done", None),
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
# Every route of the family is live (R-01-T13 retired the last stubs, the room and its suggest);
# each remaining flag still gates its routes: off, 404 before anything is read.
GATES: list[tuple[ModuleType, str, Flag]] = [
    (rooms, "_delegated", PORTAL_THIRD_PARTY_ROOM),
]
# R-01-T18 (DEC-510): the documents reads and the two undos read no flag at all.
UNGATED: tuple[ModuleType, ...] = (documents_routes, requests_pbc)


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


# Live since their tasks landed: 404 with the flag off as before, and no longer 501 with it on.
IMPLEMENTED: frozenset[tuple[str, str]] = frozenset(
    {
        ("get", "/v1/portal/binders"),  # R-01-T07
        ("get", "/v1/portal/binders/{binder_id}"),  # R-01-T07
        ("get", "/v1/portal/request-items/{item_id}"),  # R-01-T07
        ("post", "/v1/portal/request-items/{item_id}/ignore/undo"),  # R-01-T08
        ("post", "/v1/portal/binders/{binder_id}/mark-done/undo"),  # R-01-T08
        ("post", "/v1/engagements/{engagement_id}/fulfilments/{fulfilment_id}/void"),  # TASK-1248
        ("get", "/v1/portal/room"),  # R-01-T13
        ("post", "/v1/portal/room/suggest"),  # R-01-T13
    }
)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_one_action_and_the_stub_answers(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)][0]
    responses = set(cast(Json, op["responses"]))
    assert "404" in responses
    assert ("501" in responses) == ((method, path) not in IMPLEMENTED)


def test_every_implemented_route_is_one_of_the_family() -> None:
    assert set(ROUTES) >= IMPLEMENTED


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
    # R-01-T13 (DEC-387): the third party reads only what is delegated to them.
    assert granted == {"client_admin", "client_contributor", "third_party"}
    assert rule.decisions["third_party"] == "delegated_only"
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


Gate = Callable[[AuthContext], Awaitable[object]]


@pytest.mark.parametrize(("module", "name", "flag"), GATES, ids=[f.name for _, _, f in GATES])
async def test_flag_off_is_404(
    module: ModuleType, name: str, flag: Flag, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = cast(Gate, getattr(module, name))
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, asked: object) -> bool:
        seen.append(asked)
        return False

    monkeypatch.setattr(module, "flag_enabled", off)
    with pytest.raises(NotFound):
        await gate(ctx)
    assert seen == [flag]


async def test_the_drop_poll_is_404_with_its_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, asked: object) -> bool:
        seen.append(asked)
        return False

    monkeypatch.setattr(portal_pbc, "flag_enabled", off)
    with pytest.raises(NotFound):
        await portal_pbc.get_drop_batch_route(uuid.uuid4(), ctx)
    assert seen == [PORTAL_DROP_SORT]


async def test_the_drop_is_404_off_and_live_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live since R-01-T09 (tests/integration/backfill/test_r01t09_portal_drops.py): off, the
    route answers 404 before reading the body; on, it is served (no longer a 501 stub)."""
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )

    async def off(_tenant: object, asked: object) -> bool:
        assert asked is PORTAL_DROP_SORT
        return False

    module = drops_contract
    assert "_stub" not in vars(module)
    monkeypatch.setattr(module, "flag_enabled", off)
    with pytest.raises(NotFound):
        await module.drop_file_route(
            uuid.uuid4(),
            cast(Request, None),
            ctx,
            filename="a.pdf",
            batch_id=uuid.uuid4(),
            idempotency_key="k",
        )


async def test_the_void_is_404_off_and_live_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live since TASK-1248 (served by evidence; tests/integration/backfill/
    test_r01t09_portal_drops.py): off, the route answers 404 before anything else; requests keeps
    no stub at all."""
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )

    async def off(_tenant: object, asked: object) -> bool:
        assert asked is PORTAL_DROP_SORT
        return False

    assert "_stub" not in vars(requests_pbc)
    assert "_stub" not in vars(drops_contract)
    monkeypatch.setattr(drops_contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await drops_contract.void_fulfilment_route(
            uuid.uuid4(),
            uuid.uuid4(),
            drops_contract.FulfilmentVoidIn(reason="wrong_request"),
            ctx,
            idempotency_key="k",
        )


@pytest.mark.parametrize("flag", [PORTAL_DROP_SORT, PORTAL_THIRD_PARTY_ROOM])
def test_the_two_remaining_flags_are_boolean_and_default_off(flag: Flag) -> None:
    assert flag.kind == "boolean"
    assert flag.default == "false"


def test_r01t18_portal_documents_v2_is_retired() -> None:
    assert "portal.documents_v2" not in FLAGS
    for module in UNGATED:
        assert "flag_enabled" not in vars(module), module.__name__
    ungated = {path for path, (_, flag) in ROUTES.items() if flag is None}
    assert ungated == {
        ("get", "/v1/portal/binders"),
        ("get", "/v1/portal/binders/{binder_id}"),
        ("get", "/v1/portal/request-items/{item_id}"),
        ("post", "/v1/portal/request-items/{item_id}/ignore/undo"),
        ("post", "/v1/portal/binders/{binder_id}/mark-done/undo"),
    }


def test_no_route_of_the_family_is_unauthenticated() -> None:
    for method, path in ROUTES:
        assert PATHS[path][method]["x-abacus-action"] not in ("PUBLIC", "PORTAL_PUBLIC")
