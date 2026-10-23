"""C5 v1 stub, the BND-01/BND-02/SHL-14 family (P-06-T01; SPEC-319 AC-1 to AC-4): every route
exists with its one matrix action, answers 404 with `binders.engine` off and 501 with it on until
its task implements it (P-06-T07: the binder lifecycle), and the human-only actions deny the
agent. The consumers' own tests are P-06-T02's."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel._flags import BINDERS_ENGINE
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.evidence import contract as evidence_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import FIRM_SETTING_KEYS, RULES
from abacus.modules.requests import contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
ITEMS = "/v1/engagements/{engagement_id}/request-items/{item_id}"

# (method, path) -> the one matrix action (P-06 §4.3).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/binders"): "binder.read",
    ("post", "/v1/binders"): "binder.create",
    ("get", "/v1/binders/{binder_id}"): "binder.read",
    ("get", "/v1/binders/{binder_id}/requests"): "request_item.read",
    ("get", "/v1/binders/{binder_id}/live"): "request_item.read",
    ("post", "/v1/binders/{binder_id}/publish"): "binder.publish",
    ("post", "/v1/binders/{binder_id}/publish/undo"): "binder.publish",
    ("post", "/v1/binders/{binder_id}/unpublish"): "binder.publish",
    ("post", "/v1/binders/{binder_id}/duplicate"): "binder.create",
    ("put", "/v1/binders/{binder_id}/recipients"): "binder.update",
    ("put", "/v1/binders/{binder_id}/follow-up-override"): "binder.update",
    ("get", "/v1/binders/{binder_id}/client-preview"): "binder.read",
    ("get", "/v1/binders/{binder_id}/activity"): "activity.read",
    ("patch", ITEMS): "request_item.update",
    ("delete", ITEMS): "request_item.update",
    ("post", f"{ITEMS}/send"): "request_item.send",
    ("post", f"{ITEMS}/send/undo"): "request_item.send",
    ("post", f"{ITEMS}/waive"): "request_item.waive",
    ("post", f"{ITEMS}/return-to-client"): "request_item.return",
    ("post", f"{ITEMS}/delegate"): "request_item.delegate",
    ("post", f"{ITEMS}/incorporate"): "request_item.update",
    ("get", f"{ITEMS}/activity"): "activity.read",
    ("post", "/v1/portal/binders/{binder_id}/mark-done"): "binder.mark_done",
    ("post", "/v1/portal/request-items/{item_id}/ignore"): "request_item.ignore",
    ("post", "/v1/portal/request-items/{item_id}/upload-intents"): "evidence.upload",
    (
        "post",
        "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/withdraw",
    ): "evidence.withdraw",
}
# Client-visible effects carry an Idempotency-Key (ADR-139).
IDEMPOTENT = {
    "/v1/binders/{binder_id}/publish",
    f"{ITEMS}/send",
    f"{ITEMS}/return-to-client",
    "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/withdraw",
}
HUMAN_ONLY = {
    "binder.create",
    "binder.update",
    "binder.publish",
    "request_item.send",
    "request_item.return",
    "request_item.delegate",
    "evidence.accept",
    "evidence.reject",
}
CLIENT_ONLY = {"binder.mark_done", "request_item.ignore", "evidence.withdraw"}


# Implemented since the stub (P-06-T07, the binder lifecycle): 404 with the flag off as before,
# and no longer 501 with it on.
IMPLEMENTED: frozenset[tuple[str, str]] = frozenset(
    {
        ("post", "/v1/binders"),
        ("get", "/v1/binders/{binder_id}"),
        ("get", "/v1/binders/{binder_id}/requests"),
        ("post", "/v1/binders/{binder_id}/publish"),
        ("post", "/v1/binders/{binder_id}/publish/undo"),
        ("post", "/v1/binders/{binder_id}/unpublish"),
        ("post", "/v1/binders/{binder_id}/duplicate"),
        ("put", "/v1/binders/{binder_id}/recipients"),
        ("get", "/v1/binders/{binder_id}/client-preview"),
        ("get", "/v1/binders/{binder_id}/activity"),
        ("post", "/v1/portal/binders/{binder_id}/mark-done"),
    }
)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac1_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    responses = cast(Json, op["responses"])
    assert "404" in responses
    if (method, path) in IMPLEMENTED:
        assert "501" not in responses
    else:
        assert "501" in responses


def test_ac1_the_implemented_routes_are_routes_of_the_contract() -> None:
    assert set(ROUTES) >= IMPLEMENTED


@pytest.mark.parametrize("path", sorted(IDEMPOTENT))
def test_ac1_client_visible_effects_take_an_idempotency_key(path: str) -> None:
    params = cast(list[Json], PATHS[path]["post"].get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True


def test_ac2_statuses_are_the_registry_enums() -> None:
    def ref(model: str, field: str) -> object:
        return cast(dict[str, Json], SCHEMAS[model]["properties"])[field].get("$ref")

    assert ref("BinderOut", "status") == "#/components/schemas/BinderStatus"
    assert ref("BinderRowOut", "status") == "#/components/schemas/BinderStatus"
    assert ref("RequestItemV2Out", "status") == "#/components/schemas/RequestStatus"
    assert ref("BinderRequestRowOut", "status") == "#/components/schemas/RequestStatus"


@pytest.mark.parametrize("action", sorted(HUMAN_ONLY | CLIENT_ONLY))
def test_ac3_human_only_and_client_actions_deny_the_agent(action: str) -> None:
    assert RULES[action].decisions.get("agent") == "deny"


@pytest.mark.parametrize("action", sorted(CLIENT_ONLY))
def test_ac3_client_actions_grant_no_firm_role(action: str) -> None:
    granted = {r for r, d in RULES[action].decisions.items() if d != "deny"}
    assert granted == {"client_admin", "client_contributor"}


def test_ac3_the_ignore_needs_a_reason_and_publish_uses_registered_settings() -> None:
    assert RULES["request_item.ignore"].requires_reason
    named = {name for _role, name in RULES["binder.publish"].firm_settings}
    assert named == {"seniors_can_publish", "client_service_can_publish"} <= FIRM_SETTING_KEYS
    assert ("staff", "staff_can_accept_evidence") in RULES["evidence.accept"].firm_settings


Stub = Callable[[AuthContext], Awaitable[object]]


@pytest.mark.parametrize("module", [contract, evidence_contract])
async def test_ac4_flag_off_is_404_and_flag_on_is_501(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = cast(Stub, module._stub)  # the stub gate, tested directly
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(module, "flag_enabled", off)
    with pytest.raises(NotFound):
        await stub(ctx)
    assert seen == [BINDERS_ENGINE]
    monkeypatch.setattr(module, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await stub(ctx)
