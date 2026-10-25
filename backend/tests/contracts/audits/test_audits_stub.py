"""Audits family stub (A-01-T02; docs/contracts/audits-cockpit.md; SPEC-330 AC-3 to AC-6): every
route exists with its one matrix action and answers 404 with `audits.cockpit` off and 501 with it
on; the record writes take an `Idempotency-Key` and document their conflicts; every model field is
classified; the record actions are human only and grant no client role. The consumers' own tests
are A-01-T03's, in this directory."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import AUDITS_COCKPIT
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.assurance import audits_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
ITEM = "/v1/audits/{work_item_id}"

# (method, path) -> the one matrix action (A-01 §4.3).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/audits"): "engagement.read_metadata",
    # A-01-T09 (DEC-312): the bar and overview are metadata; bands and dock also need
    # `engagement.read`, checked inside.
    ("get", f"{ITEM}/cockpit"): "engagement.read_metadata",
    ("patch", f"{ITEM}/profile"): "engagement.update",
    ("post", f"{ITEM}/phase"): "assurance.record_phase",
    ("post", f"{ITEM}/release-record"): "assurance.record_release",
    ("post", f"{ITEM}/archive-record"): "assurance.record_archive",
    ("get", f"{ITEM}/source-documents"): "request_item.read",
}
RECORDS = {("post", f"{ITEM}/phase"), ("post", f"{ITEM}/release-record")} | {
    ("post", f"{ITEM}/archive-record")
}
CONFLICTS = RECORDS | {("patch", f"{ITEM}/profile")}
CLIENT_ROLES = {"client_admin", "client_contributor", "client_service"}


def _models() -> list[type[BaseModel]]:
    return [
        v
        for v in vars(audits_contract).values()
        if isinstance(v, type)
        and issubclass(v, BaseModel)
        and v is not BaseModel
        and v.__module__ == audits_contract.__name__
    ]


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac3_each_route_declares_its_one_action_and_the_stub_answers(
    method: str, path: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


def test_ac3_the_family_has_exactly_these_routes() -> None:
    family = {(m, p) for p, ops in PATHS.items() if p.startswith("/v1/audits") for m in ops}
    assert family == set(ROUTES)


@pytest.mark.parametrize(("method", "path"), sorted(RECORDS))
def test_ac3_every_record_write_takes_an_idempotency_key_and_creates(
    method: str, path: str
) -> None:
    op = PATHS[path][method]
    params = cast(list[Json], op.get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True
    assert "201" in cast(Json, op["responses"])


@pytest.mark.parametrize(("method", "path"), sorted(CONFLICTS))
def test_ac3_the_writes_document_their_conflicts(method: str, path: str) -> None:
    assert "409" in cast(Json, PATHS[path][method]["responses"])


@pytest.mark.parametrize("model", _models(), ids=lambda m: m.__name__)
def test_ac5_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


async def test_ac4_flag_off_is_404_and_flag_on_is_501(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = cast(Callable[[AuthContext, str], Awaitable[object]], vars(audits_contract)["_stub"])
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

    monkeypatch.setattr(audits_contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await stub(ctx, "engagement.read_metadata")
    assert seen == [AUDITS_COCKPIT]
    monkeypatch.setattr(audits_contract, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await stub(ctx, "engagement.read_metadata")


def test_ac4_the_flag_is_boolean_and_default_off() -> None:
    assert AUDITS_COCKPIT.kind == "boolean"
    assert AUDITS_COCKPIT.default == "false"


@pytest.mark.parametrize(
    ("action", "granted", "mfa"),
    [
        ("assurance.record_phase", {"engagement_partner", "manager"}, False),
        ("assurance.record_release", {"engagement_partner"}, True),
        ("assurance.record_archive", {"engagement_partner", "manager"}, True),
    ],
)
def test_ac6_the_record_actions_are_human_only_and_firm_only(
    action: str, granted: set[str], mfa: bool
) -> None:
    rule = RULES[action]
    assert {r for r, d in rule.decisions.items() if d != "deny"} == granted
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"
    assert not CLIENT_ROLES & granted
    assert rule.independence is True
    assert rule.mfa_recent is mfa


def test_no_route_of_the_family_is_unauthenticated() -> None:
    for method, path in ROUTES:
        assert PATHS[path][method]["x-abacus-action"] not in ("PUBLIC", "PORTAL_PUBLIC")
